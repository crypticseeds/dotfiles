"""Agent-host guard: a Claude PreToolUse hook for Bash (generate.py --agent-host embeds this file).

The agent host allows every command its deny rules do not match. Glob rules cannot say "only these
subcommands" or look at files, so this hook covers what they cannot, for two concerns only:
  - secrets: tools that run OUTSIDE the sandbox (excludedCommands) can read every secret store, so
    their arguments may not resolve into one, they may not use a flag that sends credentials
    elsewhere, and git may not be pointed at a program (`-c`, `git config`, local config keys);
    `doppler secrets` only with --only-names;
  - destruction: recursive rm, git reset --hard / clean / history rewrites / force push (except
    --force-with-lease to a branch other than main/master), gh deletes and `pr merge --admin`, and the live
    infrastructure tools (terraform, aws, kubectl, helm, docker) limited to read-only subcommands.
It also explains, instead of letting them fail with an auth error, the commands Claude runs inside
the sandbox although their tool is excluded (in a chain or pipeline, or containing < > ` or $().
herdr's arguments are never checked (owner decision); the hook only explains herdr calls that would run
sandboxed, where its socket is blocked. The hook only ever denies; what it passes still goes through the
permission rules.
"""
import json
import os
import re
import shlex
import subprocess
import sys
import time

SECRET_GLOBS = []  # filled in by generate.py: every secret path the policy denies
REPO_ROOTS = []    # filled in by generate.py: where `git-in <dir>` may work (bin/git-in enforces it too)
CREDITS_UNTIL = ""  # filled in by generate.py: last day (YYYY-MM-DD) `coderabbit --use-credits` is allowed
EXCLUDED = []      # filled in by generate.py: the sandbox's excludedCommands

HOME = os.path.expanduser("~")
# excludedCommands that this hook checks (herdr is excluded too, but never checked)
OUTSIDE = {"git", "gh", "pre-commit", "aws", "terraform", "tofu", "kubectl", "helm", "docker", "podman",
           "doppler", "coderabbit"}
# git-in <dir> <git args> (bin/git-in) is the only way to run git in another repo outside the sandbox
OUTSIDE.add("git-in")
# Claude Code never exempts a git command with one of these global options from the sandbox
GIT_REDIRECT = ("-C", "-c", "--git-dir", "--work-tree")
GIT_READ_SUBS = {"status", "log", "diff", "show", "rev-parse", "rev-list", "ls-files", "ls-tree", "blame",
                 "describe", "cat-file", "show-ref", "grep", "shortlog", "diff-tree", "for-each-ref",
                 "name-rev", "merge-base"}
GIT_CONFIG_READ = {"--get", "--get-all", "--get-regexp", "--list", "-l", "--show-origin", "--show-scope"}
GIT_NETWORK = {"push", "pull", "fetch", "clone", "ls-remote"}
# git subcommands that run repo hooks, which fail inside the sandbox (pre-commit fetches, unix sockets)
GIT_HOOKED = {"commit", "merge", "rebase", "cherry-pick", "am", "revert"}
SEPARATORS = {";", ";;", "&", "&&", "|", "||", "|&", "(", ")"}
SHELL_KEYWORDS = {"do", "then", "else", "elif", "{", "!", "time", "if", "while", "until"}
MAIN = {"main", "master"}

# Live infrastructure: read-only subcommands, per tool ("verb" or "verb sub").
READ = {
    "kubectl": {"get", "describe", "logs", "top", "version", "api-resources", "api-versions", "explain",
                "cluster-info", "events", "wait", "port-forward", "completion", "auth can-i",
                "auth whoami", "rollout status", "rollout history", "config current-context",
                "config get-contexts", "config get-clusters", "config view"},
    "helm": {"list", "ls", "status", "history", "template", "lint", "version", "show", "inspect", "search",
             "pull", "fetch", "completion", "repo list", "repo add", "repo update", "dependency list",
             "dependency build", "dependency update", "dep list", "dep build", "dep update",
             "get notes", "get metadata", "plugin list"},
    # docker is root-equivalent here (the user is in the docker group): `docker run -v ~:/h` reads
    # every secret store, so only reads
    "docker": {"ps", "images", "pull", "logs", "version", "info", "stats", "top", "search", "history",
               "port", "events", "image ls", "image list", "image pull", "image history", "container ls",
               "container list", "container logs", "container top", "container port", "container stats",
               "network ls", "network list", "volume ls", "volume list", "system df", "system info",
               "compose ps", "compose ls", "compose logs", "compose images", "compose version"},
    "terraform": {"plan", "init", "validate", "fmt", "version", "-version", "providers", "graph", "get",
                  "state list", "workspace list", "workspace show", "workspace select", "metadata"},
    "doppler": {"run", "projects", "configs", "environments", "secrets", "--version", "-v"},
}
READ["podman"], READ["tofu"] = READ["docker"], READ["terraform"]
# aws: the operation (second positional word) must be a read.
AWS_READ_OPS = re.compile(r"(describe|list|get|head|batch-get|lookup|search|filter-log-events)(-.*)?$")
AWS_READ_EXTRA = {("s3", "ls"), ("logs", "tail"), ("sts", "get-caller-identity"), ("sso", "login"),
                  ("sso", "logout"), ("configure", "list"), ("configure", "list-profiles")}
# gh: deletes, token prints, and things that install or run code (`pr merge --admin` is checked below)
GH_DENY = {"repo delete", "repo archive", "repo rename", "release delete", "secret delete",
           "secret remove", "variable delete", "run delete", "issue delete", "label delete", "workflow run",
           "auth token", "extension", "alias"}

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
                    r"TF_VAR_\w+|NO_COLOR|PAGER|GIT_PAGER|GH_PAGER|GH_REPO)=.*")
# git config keys that make git run a program. git runs outside the sandbox, and a sandboxed script
# can write a sibling repo's .git/config (Linux ignores the wildcard denyWrite), so these are refused
# on the command line (-c, git config) and in the repo's local config. Repo hooks are NOT covered:
# sandboxed code cannot write .git/hooks (Claude's built-in protection), but tracked hook definitions
# (.pre-commit-config.yaml, .husky/) are ordinary files; see the README trade-offs.
GIT_PROGRAM_KEY = re.compile(
    r"core\.(sshcommand|fsmonitor|pager|editor|askpass|gitproxy|hookspath)|sequence\.editor|"
    r"credential\..*|include\.path|includeif\..*|alias\..*|filter\..*|diff\.external|diff\..*\.(textconv|command)|"
    r"merge\..*\.driver|gpg\.(.*\.)?program|uploadpack\..*|remote\..*\.(uploadpack|receivepack|proxy)|"
    r"(http|https)\..*proxy|url\..*\.(push)?insteadof|.*\.helper", re.I)


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
# Directories above each absolute secret path (~/.aws, ~, /): an argument naming one reaches the secret.
SECRET_DIRS = {os.path.dirname(re.split(r"[*?\[]", HOME + g[1:] if g.startswith("~/") else g)[0])
               for g in SECRET_GLOBS if g.startswith(("~/", "/"))}


def reaches_secret(real):
    return any(rx.fullmatch(real) for rx in SECRET_RX) or \
        any(d == real or d.startswith(real.rstrip("/") + "/") for d in SECRET_DIRS)


def check_args(tool, args, cwd):
    """No flag that leaks credentials, no argument (or symlink) that resolves into a secret store."""
    for a in args:
        if re.match(BAD_FLAGS.get(tool, r"(?!)"), a):
            deny("flag %s" % a)
        if a.startswith("-out"):  # terraform plan -out=tfplan overwrites, it does not read
            continue
        for cand in {a, a.split("=", 1)[-1], re.sub(r"^(fileb?://|@)", "", a.split("=", 1)[-1])}:
            if not cand or cand.startswith("-"):
                continue
            p = os.path.join(cwd, os.path.expanduser(cand))
            if os.path.lexists(p) and reaches_secret(os.path.realpath(p)) \
                    and os.path.realpath(p) != os.path.realpath(cwd):
                deny("%s resolves into a secret store" % cand)


def positionals(tool, args):
    out, i, flags = [], 0, VALUE_FLAGS.get(tool, set())
    while i < len(args) and len(out) < 2:
        a = args[i]
        if a.startswith("-") and not out and a in READ.get(tool, ()):
            out.append(a)
        elif a.startswith("-"):
            i += 1 if (a in flags and "=" not in a) else 0
        else:
            out.append(a)
        i += 1
    return out


def git_out(cwd, *a):
    r = subprocess.run(["git", "-C", cwd] + list(a), capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def program_key(key, val=""):
    if key.lower() == "core.fsmonitor" and val.lower() in ("true", "false", ""):
        return False  # the built-in monitor, not a program
    return bool(GIT_PROGRAM_KEY.fullmatch(key))


def check_git(args, cwd, wrapped=False):
    """wrapped: the call comes through git-in, so -c is fine (git-in itself runs outside the sandbox)."""
    i, cfg, redirect = 0, [], False
    while i < len(args) and args[i].startswith("-"):
        a = args[i]
        redirect = redirect or a in GIT_REDIRECT or a.startswith(("--git-dir", "--work-tree"))
        if a in ("-c", "-C") and i + 1 < len(args):
            if a == "-c":
                cfg.append(args[i + 1])
            else:
                cwd = os.path.join(cwd, os.path.expanduser(args[i + 1]))
        if a.startswith("--config-env="):
            cfg.append(a.split("=", 1)[1])
        if a.startswith("--exec-path="):
            deny("git --exec-path runs programs from another directory")
        i += 2 if a in ("-C", "-c", "--git-dir", "--work-tree", "--namespace") else 1
    for c in cfg:
        key, _, val = c.partition("=")
        if program_key(key, val):
            deny("git -c %s runs a program outside the sandbox" % key)
    for line in git_out(cwd, "config", "--local", "--list").splitlines():
        key, _, val = line.partition("=")
        if program_key(key, val):
            deny("this repo's .git/config sets %s, which would run a program outside the sandbox; "
                 "ask the owner to remove it" % key)
    if i >= len(args):
        return
    sub, rest = args[i], args[i + 1:]
    short = [a for a in rest if re.fullmatch(r"-[A-Za-z]+", a)]
    if redirect and not wrapped and sub not in GIT_READ_SUBS:
        deny("`git %s` with -C, -c, --git-dir or --work-tree always runs inside the sandbox (Claude Code never "
             "exempts those forms), without the doppler token, .git/config writes or network hooks: use "
             "`git-in <repo-dir> <git args>` (`.` for the current repo)" % sub)
    if sub == "config" and not set(rest) & GIT_CONFIG_READ:
        for n, a in enumerate(rest):
            if not a.startswith("-") and program_key(a, (rest[n + 1:] or [""])[0]):
                deny("git config %s runs a program outside the sandbox" % a)
    if sub in ("clean", "filter-branch", "filter-repo"):
        deny("git %s deletes work or rewrites history" % sub)
    if sub == "reset" and "--hard" in rest:
        deny("git reset --hard discards work")
    if sub == "worktree" and rest[:1] == ["remove"] and \
            any(a == "--force" or (a in short and "f" in a) for a in rest):
        deny("git worktree remove --force discards uncommitted work (commit or ask the owner first)")
    if sub in ("checkout", "restore") and "." in rest and "--staged" not in rest:
        deny("git %s . discards every uncommitted change (name the files instead)" % sub)
    if sub == "push":
        for a in rest:
            if (a in ("--force", "--delete", "--mirror", "--prune") or a.startswith(("+", ":", "--receive-pack", "--exec"))
                    or (a in short and ("f" in a or "d" in a))):
                deny("git push %s can delete or overwrite remote work (only --force-with-lease to a "
                     "feature branch is allowed)" % a)
        if any(a.startswith("--force-with-lease") for a in rest):
            refs = [a for a in rest if not a.startswith("-")][1:]
            lease = [a.split("=", 1)[1].split(":")[0] for a in rest if a.startswith("--force-with-lease=")]
            dests = [r.split(":")[-1] for r in refs] + lease or [git_out(cwd, "symbolic-ref", "--short", "HEAD")]
            if any(re.sub(r"^refs/heads/", "", d) in MAIN for d in dests):
                deny("force push to main/master")


def check_segment(t, cwd):
    env = []
    while t and re.match(r"[A-Za-z_][A-Za-z0-9_]*=", t[0]):
        env, t = env + [t[0]], t[1:]
    if not t:
        return
    tool, args = os.path.basename(t[0]), t[1:]
    if tool == "rm" or (tool not in OUTSIDE and "rm" in args):
        tail = args[args.index("rm") + 1:] if tool != "rm" else args
        if any(a == "--recursive" or (re.fullmatch(r"-[A-Za-z]+", a) and re.search("[rR]", a)) for a in tail):
            deny("recursive rm: list the paths for the owner to delete")
    if tool == "ansible-playbook" and not set(args) & {"--check", "-C", "--syntax-check", "--list-tasks",
                                                      "--list-hosts", "--list-tags"}:
        deny("ansible-playbook only with --check, --syntax-check or --list-* (the owner applies)")
    if tool not in OUTSIDE:
        return
    bad_env = [e for e in env if not ENV_OK.fullmatch(e)]
    if bad_env:
        deny("%s= prefix on %s: use a flag instead (git -C <dir>, --git-dir)" % (bad_env[0].split("=")[0], tool))
    check_args(tool, args, cwd)
    if tool == "git-in":
        target = os.path.realpath(os.path.join(cwd, os.path.expanduser(args[0]))) if args else ""
        roots = [os.path.realpath(os.path.expanduser(r)) for r in REPO_ROOTS]
        if len(args) < 2 or not os.path.isdir(target) or not any(target.startswith(r + "/") or target == r for r in roots):
            deny("git-in <repo-dir> <git args>: the repo must be under %s" % ", ".join(REPO_ROOTS))
        return check_git(args[1:], target, wrapped=True)
    if tool == "git":
        return check_git(args, cwd)
    if tool == "coderabbit" and any(a.startswith("--use-credits") for a in args) and \
            time.strftime("%Y-%m-%d") > CREDITS_UNTIL:
        deny("coderabbit --use-credits spends paid credits (allowed only until %s)" % (CREDITS_UNTIL or "never"))
    if tool in ("pre-commit", "coderabbit"):  # coderabbit: `-c <file>` uploads it, so check_args above matters
        return
    pos = positionals(tool, args)
    one, two = pos[:1], " ".join(pos[:2])
    if tool == "gh":
        if two in GH_DENY or (one and one[0] in GH_DENY):
            deny("gh %s: deleting and token or code handling stay with the owner" % two)
        if two == "pr merge" and "--admin" in args:
            deny("gh pr merge --admin skips branch protection (a plain `gh pr merge` is allowed)")
        if two == "repo edit" and any(a.startswith("--visibility") for a in args):
            deny("gh repo edit --visibility can publish a private repo")
        method = ""
        for n, a in enumerate(args):
            if a in ("-X", "--method") and n + 1 < len(args):
                method = args[n + 1]
            elif a.startswith("--method="):
                method = a.split("=", 1)[1]
            elif a.startswith("-X"):
                method = a[2:].lstrip("=")
        if one == ["api"] and method.upper() == "DELETE":
            deny("gh api DELETE")
        return
    if tool == "aws":
        if args in (["--version"], ["help"]):
            return
        if len(pos) < 2 or not (AWS_READ_OPS.match(pos[1]) or tuple(pos) in AWS_READ_EXTRA):
            deny("aws %s is not a read-only call (the owner makes changes)" % " ".join(pos))
        return
    if not (two in READ[tool] or (one and one[0] in READ[tool])):
        deny("%s %s is not on the agent host's read-only list (the owner changes live infrastructure)"
             % (tool, two))
    if tool == "doppler" and one == ["secrets"]:
        if "--only-names" not in args or len(pos) > 1:
            deny("doppler secrets prints values: use `doppler secrets --only-names`")
    if tool == "doppler" and one == ["run"]:
        if "--" not in args or not args[args.index("--") + 1:]:
            deny("doppler run only as `doppler run --only-secrets NAME -- <cmd>`")
        inner = args[args.index("--") + 1:]
        name = os.path.basename(inner[0])
        if name in ("env", "printenv", "export", "set", "declare") or \
                (re.fullmatch(r"(ba|z|da|k)?sh|python[0-9.]*|node|perl|ruby", name) and set(inner[1:]) & {"-c", "-e"}):
            deny("doppler run -- %s would print the injected secret" % name)
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


def command_words(words):
    return [w for w in words if w not in SHELL_KEYWORDS and not re.match(r"[A-Za-z_]\w*=", w)]


def excluded(words):
    """The command matches an excludedCommands entry (`x *`: x and anything after it, `x`: exactly x)."""
    for p in EXCLUDED:
        base = p[:-2].split() if p.endswith(" *") else p.split()
        if words[:len(base)] == base and (p.endswith(" *") or len(words) == len(base)):
            return True
    return False


def has_hooks(cwd):
    hooks = git_out(cwd, "rev-parse", "--git-path", "hooks")
    d = os.path.join(cwd, hooks) if hooks else ""
    return bool(d) and os.path.isdir(d) and any(not f.endswith(".sample") for f in os.listdir(d))


def needs_own_command(words, cwd):
    """True for commands that fail inside the sandbox: Claude runs an excluded command outside it only as a
    plain command of its own. herdr has its own check (talks_to_herdr)."""
    words = command_words(words)
    if not words:
        return False
    words = [os.path.basename(words[0])] + words[1:]
    if words[0] == "herdr":
        return False
    if words[0] != "git":
        return excluded(words)
    # sandboxed git works locally, except: no push credentials; ~/.herdr/worktrees and .git/worktrees are
    # read-only (worktree add/remove/move/prune); repo hooks fail
    sub = [w for w in words[1:] if not w.startswith("-")][:2]
    return bool(GIT_NETWORK & set(words)) or (sub[:1] == ["worktree"] and sub[1:] != ["list"]) or \
        (bool(sub) and sub[0] in GIT_HOOKED and has_hooks(cwd))


def talks_to_herdr(words):
    """herdr commands that need its server socket, which the sandbox blocks (help and version do not)."""
    words = command_words(words)
    return bool(words) and os.path.basename(words[0]) == "herdr" and \
        not set(words[1:]) & {"-h", "--help", "-V", "--version", "help"}


def main():
    data = json.load(sys.stdin)
    check_command(data.get("tool_input", {}).get("command", ""), data.get("cwd") or os.getcwd())


def check_command(cmd, cwd):
    raw = cmd
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
        if re.search(r"\b(rm|ansible-playbook|%s)\b" % "|".join(OUTSIDE), cmd):
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
    # Claude runs a command outside the sandbox only when it is a plain command of its own. In a loop,
    # pipeline or chain, or with < > ` $( anywhere in it (even quoted), it runs sandboxed and the
    # excluded tools fail with a confusing auth or permission error. Say so up front, with the fix.
    # herdr: quoted < > && are fine, but a pipe, chain, ` or $( (even in single quotes) puts it in the
    # sandbox (verified 2026-10-24)
    if any(talks_to_herdr(s) for s in segs) and (len(segs) > 1 or re.search(r"`|\$\(", raw)):
        deny("run `herdr ...` as its own Bash command, with no pipe, chain, ` or $( anywhere (even in single "
             "quotes): otherwise it runs inside the sandbox, which blocks the herdr socket "
             "(Operation not permitted). Pass prompt text as one single-quoted argument (newlines are fine, "
             "write ' as '\\'') and read the JSON output directly instead of piping it")
    hit = [s for s in segs if needs_own_command(s, cwd)]
    why = ""
    if hit and len(segs) > 1:
        why = "it is chained with other commands (&&, ||, ;, |, a loop or a subshell)"
    elif hit and re.search(r"[<>`]|\$\(", raw):
        why = "the command contains < > ` or $( (even inside quotes)"
    if why:
        name = " ".join(command_words(hit[0])[:3])
        deny("`%s` would fail here: %s, so Claude runs it inside the sandbox, where it has no credentials, "
             "cannot write outside the project and cannot run git hooks. Do not chain it. Fix: run `%s ...` as "
             "its own Bash call with no pipe, redirect, ` or $(, and run the other commands in separate calls. "
             "Read its output directly instead of piping it (gh --jq, -q), save output to a file in a later "
             "call, put long text in a file (gh --body-file F, git commit -F F), and use "
             "`git-in <repo-dir> <git args>` instead of cd or -C for another repo" % (name, why, name))


if __name__ == "__main__":
    main()
