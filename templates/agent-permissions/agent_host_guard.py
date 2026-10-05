"""Agent-host guard: a Claude PreToolUse hook for Bash (generate.py --agent-host embeds this file).

The agent-host policy allows every command its deny rules do not match. Glob rules cannot say "only
these subcommands" or look at files, so this hook covers what they cannot:
  - tools that run OUTSIDE the sandbox (excludedCommands) may only run listed read-only subcommands,
    with no VAR= prefix, no flag that sends credentials elsewhere or runs a program, no argument or
    planted symlink that resolves into a secret store, and (git, gh) no repo config or hook that
    would run code unsandboxed; Terraform code may not run programs or talk to custom endpoints;
  - destructive spellings the globs miss (rm -Rf, git -C x reset --hard, git clean, push --delete);
  - ansible-playbook only in check or list modes (it runs sandboxed, so it cannot read secrets).
It only ever denies; whatever it passes still goes through the permission rules.
"""
import json
import os
import re
import shlex
import subprocess
import sys

SECRET_GLOBS = []  # filled in by generate.py: every secret path the policy denies
WRITABLE = []      # filled in by generate.py: where sandboxed code can write (plant symlinks)

HOME = os.path.expanduser("~")
EXCLUDED = {"aws", "terraform", "tofu", "kubectl", "helm", "docker", "podman", "gh", "doppler"}
SEPARATORS = {";", ";;", "&", "&&", "|", "||", "|&", "(", ")"}
SHELL_KEYWORDS = {"do", "then", "else", "elif", "{", "!", "time", "if", "while", "until"}
GIT_SYNC_WORDS = {"pull", "--rebase", "--autostash"}

# Read-only subcommands, per tool: "verb" or "verb sub" (first one or two positional words).
READ = {
    "kubectl": {"get", "describe", "logs", "top", "version", "api-resources", "api-versions", "explain",
                "cluster-info", "events", "wait", "port-forward", "completion", "auth can-i",
                "auth whoami", "rollout status", "rollout history", "config current-context",
                "config get-contexts", "config get-clusters", "config view"},
    "helm": {"list", "ls", "status", "history", "template", "lint", "version", "show", "inspect", "search",
             "pull", "fetch", "completion", "repo list", "repo add", "repo update", "dependency list",
             "dependency build", "dependency update", "dep list", "dep build", "dep update",
             "get notes", "get metadata", "plugin list"},
    "docker": {"ps", "images", "pull", "logs", "version", "info", "stats", "top", "search", "history",
               "port", "events", "image ls", "image list", "image pull", "image history", "container ls",
               "container list", "container logs", "container top", "container port", "container stats",
               "network ls", "network list", "volume ls", "volume list", "system df", "system info",
               "compose ps", "compose ls", "compose logs", "compose images", "compose version"},
    "gh": {"pr view", "pr list", "pr status", "pr checks", "pr diff", "pr create", "pr edit", "pr comment",
           "pr ready", "issue view", "issue list", "issue status", "issue create",
           "issue comment", "run view", "run list", "run watch", "repo view", "repo list", "repo clone",
           "workflow list", "workflow view", "release list", "release view", "label list", "search",
           "api", "status", "--version", "version"},
    "terraform": {"plan", "init", "validate", "fmt", "version", "-version", "providers", "graph", "get",
                  "state list", "workspace list", "workspace show", "workspace select", "metadata"},
    "doppler": {"run", "projects", "configs", "environments", "--version", "-v"},
}
READ["podman"], READ["tofu"] = READ["docker"], READ["terraform"]
# aws: the operation (second positional word) must be a read.
AWS_READ_OPS = re.compile(r"(describe|list|get|head|batch-get|lookup|search|filter-log-events)(-.*)?$")
AWS_READ_EXTRA = {("s3", "ls"), ("logs", "tail"), ("sts", "get-caller-identity"), ("sso", "login"),
                  ("sso", "logout"), ("configure", "list"), ("configure", "list-profiles")}

# Global flags that take a value (so the value is not mistaken for the subcommand).
VALUE_FLAGS = {
    "aws": {"--profile", "--region", "--output", "--query", "--color", "--cli-read-timeout",
            "--cli-connect-timeout", "--cli-binary-format"},
    "kubectl": {"-n", "--namespace", "--context", "--cluster", "--user", "--request-timeout", "-v",
                "--v", "-l", "--selector", "-o", "--output", "--as", "--as-group"},
    "helm": {"-n", "--namespace", "--kube-context", "--registry-config", "--repository-cache",
             "--repository-config", "--burst-limit", "--qps"},
    "docker": {"--context", "-c", "--log-level", "-l", "-f", "--file", "-p", "--project-name",
               "--profile", "--env-file", "--project-directory"},
    "gh": {"-R", "--repo"},
    "terraform": set(),
    "doppler": {"-p", "--project", "-c", "--config", "--scope"},
}
VALUE_FLAGS["podman"], VALUE_FLAGS["tofu"] = VALUE_FLAGS["docker"], VALUE_FLAGS["terraform"]

# Flags that send credentials to another host, turn off TLS checks, or run a program unsandboxed.
_K8S = r"--(server|insecure-skip-tls-verify|kubeconfig|certificate-authority|enable-alpha-plugins|enable-exec|enable-helm)(=|$)"
BAD_FLAGS = {
    "aws": r"--(endpoint-url|ca-bundle|no-verify-ssl)(=|$)",
    "kubectl": _K8S + r"|-s$",
    "helm": _K8S + r"|--(post-renderer|kube-apiserver|kube-insecure-skip-tls-verify|kube-ca-file)",
    "docker": r"--config(=|$)|-H$|--host(=|$)",
    "terraform": r"-+plugin-dir(=|$)",
    "doppler": r"--(command|mount|token|config-dir|fallback)",
    "gh": r"--hostname(=|$)",
}
BAD_FLAGS["podman"], BAD_FLAGS["tofu"] = BAD_FLAGS["docker"], BAD_FLAGS["terraform"]
# VAR= prefixes allowed before a tool that runs outside the sandbox (others could point it at a
# config file or plugin the agent wrote). Admin profiles stay denied by the permission rules.
ENV_OK = re.compile(r"(AWS_PROFILE|AWS_REGION|AWS_DEFAULT_REGION|AWS_PAGER|TF_IN_AUTOMATION|TF_INPUT|"
                    r"TF_VAR_\w+|NO_COLOR|PAGER)=.*")
# Local git config a push or pull may run under. Anything else (hooksPath, sshCommand, credential
# helpers, filters, include.path, fsmonitor...) can run a program outside the sandbox.
GIT_CONFIG_OK = re.compile(
    r"core\.(repositoryformatversion|filemode|bare|logallrefupdates|ignorecase|precomposeunicode|"
    r"symlinks|sparsecheckout|sparsecheckoutcone|untrackedcache|autocrlf|eol)|remote\.[^=]+\.(url|pushurl|fetch|tagopt|prune|gh-resolved)|branch\.[^=]+\.[\w-]+|user\.(name|email)|extensions\.[a-z]+|pull\.rebase|"
    r"push\.autosetupremote|submodule\.[^=]+\.(url|active)|lfs\.repositoryformatversion", re.I)
GIT_REMOTE_OK = re.compile(r"(https://|ssh://|git@)")
GIT_PUSH_HOOKS = ("pre-push", "reference-transaction", "post-checkout", "post-merge", "post-rewrite",
                  "pre-rebase", "pre-auto-gc", "post-index-change", "push-to-checkout")
# Terraform code that runs a program or sends credentials to a custom endpoint during `plan`.
# (Provider `exec {}` blocks are checked separately: `command = "aws"` is the standard EKS login.)
TF_BAD = re.compile(r'data\s+"external"|hashicorp/external|\bendpoints\s*\{|'
                    r'custom_ca_bundle|\binsecure\s*=\s*true')
TF_REGISTRIES = ("registry.terraform.io", "registry.opentofu.org")
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "providers"}


def deny(why):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse", "permissionDecision": "deny",
        "permissionDecisionReason": "agent host: %s (blocked by the agent-host guard)" % why}}))
    sys.exit(0)


def _regex(glob):
    glob = HOME + glob[1:] if glob.startswith("~/") else glob
    out, i = "", 0
    while i < len(glob):
        if glob.startswith("**/", i):
            out, i = out + "(?:.*/)?", i + 3
        elif glob.startswith("**", i):
            out, i = out + ".*", i + 2
        elif glob[i] == "*":
            out, i = out + "[^/]*", i + 1
        else:
            out, i = out + re.escape(glob[i]), i + 1
    return re.compile(out, re.I)


SECRET_RX = [_regex(g) for g in SECRET_GLOBS]
# Directories above each absolute secret path (~/.aws, ~, /): a symlink to one reaches the secret.
SECRET_DIRS = {os.path.dirname(re.split(r"[*?\[]", HOME + g[1:] if g.startswith("~/") else g)[0])
               for g in SECRET_GLOBS if g.startswith(("~/", "/"))}
WRITABLE_DIRS = [os.path.realpath(os.path.expanduser(w)) for w in WRITABLE]


def is_secret(real):
    return any(rx.fullmatch(real) for rx in SECRET_RX)


def reaches_secret(real):
    return is_secret(real) or any(d == real or d.startswith(real.rstrip("/") + "/") for d in SECRET_DIRS)


def scan_root(path):
    """The top directory under a writable root that contains path, or None outside them."""
    real = os.path.realpath(path)
    for w in WRITABLE_DIRS:
        if real == w:
            return w
        if real.startswith(w + "/"):
            return os.path.join(w, real[len(w) + 1:].split("/")[0])
    return None


def braced(text, opener):
    """Bodies of the `{...}` blocks that start where `opener` (ending in `{`) matches."""
    for m in re.finditer(opener, text):
        depth, i = 1, m.end()
        while i < len(text) and depth:
            depth += {"{": 1, "}": -1}.get(text[i], 0)
            i += 1
        yield text[m.end():i]


def scan(root, terraform):
    """Deny planted symlinks into secret stores and, for Terraform, code that runs programs."""
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in dirs + files:
            p = os.path.join(dirpath, name)
            if os.path.islink(p) and reaches_secret(os.path.realpath(p)):
                deny("%s is a symlink into a secret store" % p)
            if terraform and name.endswith((".tf", ".tf.json")) and os.path.isfile(p):
                try:
                    text = open(p, errors="replace").read()
                except OSError:
                    continue
                if TF_BAD.search(text):
                    deny("%s runs a program or uses a custom endpoint during plan" % p)
                for block in braced(text, r"\bexec\s*\{"):
                    if not re.search(r'\bcommand\s*=\s*"aws"', block):
                        deny("%s: provider exec block runs something other than aws" % p)
                for block in braced(text, r"\brequired_providers\s*\{"):
                    for src in re.findall(r'source\s*=\s*"([^"]+)"', block):
                        parts = src.split("/")
                        if len(parts) == 3 and parts[0].lower() not in TF_REGISTRIES:
                            deny("provider %s is not from the public registry" % src)


def check_args(tool, args, cwd):
    for a in args:
        if re.match(BAD_FLAGS.get(tool, r"(?!)"), a):
            deny("flag %s" % a)
        if a.startswith("-out"):  # terraform plan -out=tfplan overwrites, it does not read
            continue
        for cand in {a, a.split("=", 1)[-1], re.sub(r"^(fileb?://|@)", "", a.split("=", 1)[-1])}:
            if not cand or cand.startswith("-"):
                continue
            p = os.path.join(cwd, os.path.expanduser(cand))
            if os.path.lexists(p):
                if reaches_secret(os.path.realpath(p)) and os.path.realpath(p) != os.path.realpath(cwd):
                    deny("%s resolves into a secret store" % cand)


def positionals(tool, args):
    out, i, flags = [], 0, VALUE_FLAGS.get(tool, set())
    while i < len(args) and len(out) < 2:
        a = args[i]
        if a.startswith("-") and not out and tool in ("gh", "terraform", "tofu", "doppler") and a in READ.get(tool, ()):
            out.append(a)
        elif a.startswith("-"):
            i += 1 if (a in flags and "=" not in a) else 0
        else:
            out.append(a)
        i += 1
    return out


NOHOOKS = "core.hookspath=/dev/null"  # `git -c core.hooksPath=/dev/null push|pull`: no hooks run


def git_repo_checks(cwd, nohooks):
    def git(*a):
        r = subprocess.run(["git", "-C", cwd] + list(a), capture_output=True, text=True)
        return r.stdout if r.returncode == 0 else None
    if git("rev-parse", "--git-dir") is None:
        return
    how = "run `git -c core.hooksPath=/dev/null push ...` (or `... pull --rebase --autostash`) instead"
    for line in (git("config", "--local", "--list") or "").splitlines():
        key, _, val = line.partition("=")
        if key.lower() == "core.hookspath":
            if not nohooks:
                deny("this repo sets core.hooksPath and hooks would run outside the sandbox; " + how)
        elif not GIT_CONFIG_OK.fullmatch(key):
            deny("local git config %s could run a program; remove it or push yourself" % key)
        if re.fullmatch(r"remote\..+\.(push)?url", key, re.I) and not GIT_REMOTE_OK.match(val):
            deny("remote %s is not https/ssh" % val)
    if nohooks:
        return
    hooks = os.path.join(cwd, (git("rev-parse", "--git-path", "hooks") or ".git/hooks").strip())
    for h in GIT_PUSH_HOOKS:
        if os.path.exists(os.path.join(hooks, h)):
            deny("git hook %s would run outside the sandbox; %s" % (h, how))


def check_git(args, cwd):
    i, cfg = 0, []
    while i < len(args) and args[i].startswith("-"):
        if args[i] == "-c" and i + 1 < len(args):
            cfg.append(args[i + 1].lower())
        i += 2 if args[i] in ("-C", "-c", "--git-dir", "--work-tree", "--namespace") else 1
    if i >= len(args):
        return
    sub, rest, glob = args[i], args[i + 1:], args[:i]
    # `git -C * push *` runs outside the sandbox, and that glob also matches anything with " push "
    # after `-C`. Only `[-C <dir>] [-c core.hooksPath=/dev/null] push` may use it.
    if glob[:1] == ["-C"]:
        if sub != "push" and "push" in " ".join(args).split():
            deny("`git -C <dir> ...` containing the word push runs outside the sandbox; only "
                 "`git -C <dir> [-c core.hooksPath=/dev/null] push ...` may (reword, e.g. the message)")
        if sub == "push" and not (glob[2:] == [] or (len(glob) == 4 and glob[2] == "-c" and cfg == [NOHOOKS])):
            deny("only `git -C <dir> [-c core.hooksPath=/dev/null] push ...`")
        cwd = os.path.join(cwd, os.path.expanduser(glob[1]))
    short = [a for a in rest if re.fullmatch(r"-[A-Za-z]+", a)]
    if sub == "clean" or sub in ("filter-branch", "filter-repo"):
        deny("git %s deletes work" % sub)
    if sub == "reset" and set(rest) & {"--hard", "--merge", "--keep"}:
        deny("git reset %s discards work" % " ".join(set(rest) & {"--hard", "--merge", "--keep"}))
    if sub == "checkout" and (set(rest) & {".", "--", "--force"} or any("f" in s for s in short)):
        deny("git checkout that discards changes")
    if sub == "restore" and ("--staged" not in rest or set(rest) & {"--worktree", "-W"}):
        deny("git restore discards changes (only --staged is allowed)")
    if sub == "branch" and ("-D" in rest or (set(rest) & {"-d", "--delete"} and set(rest) & {"-f", "--force"})):
        deny("git branch force delete")
    if sub == "stash" and rest[:1] in (["drop"], ["clear"]):
        deny("git stash %s" % rest[0])
    if (sub == "reflog" and rest[:1] in (["expire"], ["delete"])) or (sub == "update-ref" and "-d" in rest):
        deny("git %s deletes history" % sub)
    if sub == "push":
        for a in rest:
            if (a in ("--delete", "-d", "--mirror", "--prune") or a.startswith(("--force", "+", ":", "--receive-pack", "--exec"))
                    or (re.fullmatch(r"-[A-Za-z]+", a) and ("f" in a or "d" in a))):
                deny("git push %s can delete or overwrite remote work" % a)
        dest = [a for a in rest if not a.startswith("-")][:1]
        if dest and (dest[0].startswith(("/", ".", "~", "file:")) or os.path.exists(os.path.join(cwd, dest[0]))):
            deny("git push to a local path runs that repo's hooks outside the sandbox")
    # the forms that run outside the sandbox: plain, `-C <dir>`, either with only the hooks-off override
    local = glob[2:] if glob[:1] == ["-C"] else glob
    if sub in ("push", "pull") and (local == [] or local == ["-c", local[1]] and cfg == [NOHOOKS]):
        git_repo_checks(cwd, nohooks=local != [])


def check_segment(t, cwd):
    env = []
    while t and re.match(r"[A-Za-z_][A-Za-z0-9_]*=", t[0]):
        env, t = env + [t[0]], t[1:]
    if not t:
        return
    tool, args = os.path.basename(t[0]), t[1:]
    if tool == "rm" or (tool not in ("git",) and "rm" in args):
        tail = args[args.index("rm") + 1:] if tool != "rm" else args
        if any(a == "--recursive" or (re.fullmatch(r"-[A-Za-z]+", a) and re.search("[rR]", a)) for a in tail):
            deny("recursive rm")
    if tool == "git":
        check_git(args, cwd)
    if tool == "ansible-playbook" and not set(args) & {"--check", "-C", "--syntax-check", "--list-tasks",
                                                      "--list-hosts", "--list-tags"}:
        deny("ansible-playbook only with --check, --syntax-check or --list-*")
    if tool not in EXCLUDED:
        return
    bad_env = [e for e in env if not ENV_OK.fullmatch(e)]
    if bad_env:
        deny("%s prefix on %s: it runs outside the sandbox" % (bad_env[0].split("=")[0], tool))
    check_args(tool, args, cwd)
    pos = positionals(tool, args)
    if tool == "aws":
        if args in (["--version"], ["help"]):
            return
        if len(pos) < 2 or not (AWS_READ_OPS.match(pos[1]) or tuple(pos) in AWS_READ_EXTRA):
            deny("aws %s is not a read-only call" % " ".join(pos))
        return
    one, two = pos[:1], " ".join(pos[:2])
    if not (two in READ[tool] or (one and one[0] in READ[tool])):
        deny("%s %s is not on the agent host's read-only list" % (tool, two))
    roots = {r for r in (scan_root(cwd),) if r}
    for a in args:  # directories named in args (-chdir=x, chart dirs, -f dir)
        p = os.path.join(cwd, os.path.expanduser(a.split("=", 1)[-1]))
        if os.path.isdir(p) and scan_root(p):
            roots.add(scan_root(p))
    for r in roots:
        scan(r, tool in ("terraform", "tofu"))
    if tool == "doppler" and one == ["run"]:
        if "--" not in args or not args[args.index("--") + 1:]:
            deny("doppler run only as `doppler run ... -- <terraform|tofu|aws|kubectl|helm> ...`")
        inner = args[args.index("--") + 1:]
        if os.path.basename(inner[0]) not in EXCLUDED - {"doppler", "gh", "docker", "podman"}:
            deny("doppler run -- %s: only terraform, tofu, aws, kubectl or helm" % inner[0])
        check_segment(inner, cwd)


HEREDOC = re.compile(r"(?<!<)<<(?!<)-?\s*(['\"]?)([A-Za-z_]\w*)\1")
SHELL_LINE = re.compile(r"\s*(?:[A-Za-z_]\w*=\S*\s+)*(?:\S*/)?(?:ba|z|da|k)?sh\b")


def split_heredocs(cmd):
    """Drop heredoc bodies (data), except bodies fed to a shell, which are returned to be checked."""
    lines, out, shell_bodies, i = cmd.replace("\\\n", " ").split("\n"), [], [], 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        i += 1
        for _, tag in HEREDOC.findall(line):
            body = []
            while i < len(lines) and lines[i].strip() != tag:
                body.append(lines[i])
                i += 1
            i += 1
            if SHELL_LINE.match(line):
                shell_bodies.append("\n".join(body))
    return " ; ".join(out), shell_bodies


def main():
    data = json.load(sys.stdin)
    check_command(data.get("tool_input", {}).get("command", ""), data.get("cwd") or os.getcwd())


def check_command(cmd, cwd):
    cmd, shell_bodies = split_heredocs(cmd)
    for body in shell_bodies:
        check_command(body, cwd)
    try:
        lex = shlex.shlex(cmd, posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        tokens = list(lex)
    except ValueError:
        tokens = None
    if tokens is None:  # unparseable: fail closed if it names anything this guard watches
        if re.search(r"\b(rm|git|ansible-playbook|%s)\b" % "|".join(EXCLUDED), cmd):
            deny("could not parse the command")
        return
    segs, seg = [], []
    for tok in tokens + [";"]:
        if tok in SEPARATORS or tok == "\n":
            if seg:
                segs.append([s for s in seg if s not in ("<", ">", ">>", "<<", "2>", "&>")])
            seg = []
        else:
            seg.append(tok)
    for s in segs:
        check_segment(s, cwd)
    # Credentialed tools leave the sandbox only as a command of their own. Inside a loop, pipeline or
    # chain they run sandboxed, cannot read their credentials, and fail with a confusing auth error.
    if len(segs) > 1:
        for s in segs:
            while s and s[0] in SHELL_KEYWORDS:
                s = s[1:]
            words = [w for w in s if not re.match(r"[A-Za-z_]\w*=", w)]
            if words and (os.path.basename(words[0]) in EXCLUDED or
                          (words[0] == "git" and ("push" in words or GIT_SYNC_WORDS <= set(words)))):
                deny("run `%s` as its own Bash command: in a loop, pipeline or && chain it runs inside the "
                     "sandbox without credentials (use `git -C <dir> push`, `gh -R owner/repo`, `--jq`)"
                     % " ".join(words[:3]))


if __name__ == "__main__":
    main()
