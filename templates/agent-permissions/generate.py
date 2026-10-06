#!/usr/bin/env python3
"""Generate secret-hygiene + write-boundary permission files for Claude Code, opencode and omp.

One policy, three output formats, two profiles, two operating systems:

  standard  generic AWS / Terraform / Ansible / Kubernetes work, any project.
            Read-only cloud and cluster calls are allowed.
  strict    nothing that touches live AWS or a live cluster is allowed without a
            prompt (the human runs those). Offline checks still run freely.

  macos / linux  only the Claude file differs (OS-specific secret paths, temp dirs,
            sandbox prerequisites). The command rules are OS-independent.

Both profiles also enforce a write boundary: agents may write inside the project
directory, in /tmp, and nowhere else unless you explicitly approve. Skill
directories are readable (and, in opencode, read-only).

Usage:
    python3 generate.py                          write standard/ and strict/ bundles
    python3 generate.py --claude-out PATH        also write one Claude settings file
                         [--profile standard|strict (default: standard)] [--os macos|linux (default: this host)]
                         [--extra-claude-deny RULE ...] [--no-sandbox]
    python3 generate.py --install PROJECT_DIR    drop the right files for this host into a project:
                         [--profile ...] [--os ...] [--no-sandbox] [--force]
                         .claude/settings.json, opencode.json, .omp/config.yml
                         (existing files are left alone unless --force)
    python3 generate.py --check                  verify the written files behave as intended

--no-sandbox is the fallback if the Linux sandbox will not start: the permission rules stay,
the OS-level write boundary for shell commands goes (Write/Edit tools still prompt outside
the project).

Pattern conventions used in the lists below:
    "terraform plan"   prefix: matches `terraform plan` and `terraform plan <anything>`
    "=env"             exact: matches only `env`
    "aws * delete-*"   already contains `*`, used as written

Decision order differs per agent, and the output files are arranged to match:
    Claude    deny beats ask beats allow (order irrelevant)
    opencode  last matching rule wins   -> allow, then ask, then deny
    omp       first matching rule wins  -> deny, then ask, then allow
Anything unmatched falls through to a prompt in all three.

How the write boundary is enforced, per agent:
    Claude    Write/Edit tools: default is to prompt outside the project; /tmp is allowed.
              Shell commands: the OS sandbox (permission rules cannot see `cp x ~/y`).
    opencode  `external_directory` (native): ask outside the project, allow /tmp and skills.
    omp       no equivalent setting found; see the header of omp-config.yml.
"""
import argparse
import contextlib
import io
import json
import os
import pathlib
import platform
import re
import shlex
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
PROFILES = ("standard", "strict")
OSES = ("macos", "linux")
HOST_OS = {"Darwin": "macos", "Linux": "linux"}.get(platform.system(), "linux")

# --------------------------------------------------------------------------
# File paths that must never be read or edited
# --------------------------------------------------------------------------

SECRET_PATHS_HOME = [  # both OSes
    "~/.ssh/id_*", "~/.ssh/*.pem", "~/.gnupg/**",
    "~/.aws/credentials", "~/.aws/sso/**", "~/.aws/cli/cache/**",
    "~/.config/gcloud/**", "~/.azure/**", "~/.kube/**",
    "~/.docker/config.json", "~/.npmrc", "~/.pypirc", "~/.netrc",
    "~/.git-credentials", "~/.config/gh/hosts.yml", "~/.doppler/**",
    "~/.claude/.credentials.json", "~/.codex/auth.json",
    "~/.local/share/opencode/auth.json",
    "~/.zsh_history", "~/.bash_history",
]
SECRET_PATHS_HOME_MACOS = [
    "~/Library/Keychains/**", "~/Library/Messages/**", "~/Library/Mail/**",
    "~/Library/Passes/**", "~/Library/Cookies/**", "~/Library/Safari/**",
    "~/Library/Application Support/Google/Chrome/**",
    "~/Library/Application Support/BraveSoftware/**",
    "~/Library/Application Support/Firefox/**",
]
SECRET_PATHS_HOME_LINUX = [
    # keyrings and password managers
    "~/.local/share/keyrings/**", "~/.local/share/kwalletd/**", "~/.password-store/**",
    "~/.config/op/**", "~/.config/Bitwarden/**", "~/.pki/**", "~/.config/goa-1.0/**",
    # browsers (native, snap and flatpak) and mail / chat clients
    "~/.mozilla/**", "~/.config/google-chrome/**", "~/.config/chromium/**",
    "~/.config/BraveSoftware/**", "~/.config/microsoft-edge/**", "~/.var/app/**",
    "~/snap/*/common/.mozilla/**", "~/.thunderbird/**", "~/.config/Signal/**",
    "~/.local/share/TelegramDesktop/**",
    # shell and database histories
    "~/.local/share/fish/fish_history", "~/.python_history", "~/.psql_history",
    "~/.mysql_history",
]

# System paths, written as absolute paths (Claude spells these with a leading //).
SECRET_PATHS_ABS = [  # both OSes
    "/etc/rancher/**",                       # k3s.yaml (cluster-admin kubeconfig), config.yaml, registries.yaml
    "/var/lib/rancher/k3s/server/token",
    "/var/lib/rancher/k3s/server/node-token",
    "/var/lib/rancher/k3s/server/tls/**",
]
SECRET_PATHS_ABS_LINUX = [
    "/etc/shadow", "/etc/gshadow", "/etc/sudoers", "/etc/sudoers.d/**",
    "/etc/ssh/ssh_host_*", "/etc/pki/tls/private/**", "/etc/ssl/private/**",
    "/etc/NetworkManager/system-connections/**",    # saved WiFi / VPN passwords
    "/etc/wireguard/**", "/etc/kubernetes/admin.conf", "/etc/kubernetes/pki/**",
    "/var/lib/kubelet/**",
    "/mnt/hgfs/**",                          # VMware Fusion shared folders = the Mac's files
]
# Other processes' environment and memory. NOT a Claude Read/Edit deny: Claude folds those into the
# sandbox read-deny, and bubblewrap then fails to start (`Can't mkdir parents for /proc/<pid>/mem`,
# verified live on the Pi 2026-10-05) because the sandbox mounts its own /proc. Inside the sandbox
# only its own processes are visible anyway. Claude's file tools get PROC_READ_HOOK instead; shell
# commands that name these paths are denied by PATH_MENTIONS. opencode denies them as paths.
PROC_SECRET_PATHS = ["/proc/*/environ", "/proc/*/cmdline", "/proc/*/mem"]

SECRET_PATHS_ANY = [
    "**/.env", "**/.env.*",
    "**/*.pem", "**/*.key", "**/*.p12", "**/*.pfx", "**/*.jks",
    "**/*.keystore", "**/*.ppk", "**/*.kdbx", "**/id_rsa", "**/id_ed25519",
    "**/.netrc", "**/.doppler.yaml",
    # Terraform: state and plan files hold plaintext secrets
    "**/*.tfstate", "**/*.tfstate.*", "**/.terraform/**", "**/*.tfplan", "**/tfplan",
    # Ansible vault material
    "**/.vault_pass*", "**/*vault-pass*", "**/*.vault", "**/vault.yml", "**/vault.yaml",
    # Kubernetes
    "**/kubeconfig*", "**/*.kubeconfig",
]

# Claude cannot carve `.env.example` out of a `.env.*` deny (deny beats allow), so for
# Claude `**/.env.*` is replaced by patterns matching every `.env.<x>` EXCEPT exactly
# `.env.example`: "the name differs from `example` at character N" for each N, plus
# the proper prefixes of `example` and anything longer than it (`.env.example.bak`).
# opencode needs no such trick (last match wins), so it keeps the plain pattern.
#
# Claude's matcher has NO negated character class: `[!e]` and `[^e]` both behave as the plain
# set {!, e} or {^, e} (verified live: they matched `.env.example` and missed `.env.local`).
# So "any character except c" is spelled positively, as a set of ranges with c left out.
# Matching is also case-insensitive, so both cases of c are left out (so `.env.Example` passes).
ENV_PATTERN = "**/.env.*"
_NAME_CHARS = sorted(set("." + "0123456789" + "ABCDEFGHIJKLMNOPQRSTUVWXYZ" + "_" + "abcdefghijklmnopqrstuvwxyz"))


def _all_but(c):
    chars, out, i = [x for x in _NAME_CHARS if x.lower() != c.lower()], "", 0
    while i < len(chars):
        j = i
        while j + 1 < len(chars) and ord(chars[j + 1]) == ord(chars[j]) + 1:
            j += 1
        out += chars[i] if j - i < 2 else "%s-%s" % (chars[i], chars[j])  # ranges only for runs of 3+
        i = j + 1
    return out + "-"  # a trailing `-` is a literal hyphen


_WORD = "example"
ENV_EXCEPT_EXAMPLE = (
    ["**/.env.%s[%s]*" % (_WORD[:i], _all_but(c)) for i, c in enumerate(_WORD)]
    + ["**/.env.example?*"]                                  # longer: .env.example.bak
    + ["**/.env.%s" % _WORD[:i] for i in range(1, len(_WORD))]  # shorter prefixes: .env.e ... .env.exampl
)

# Any shell command that merely mentions one of these is blocked, so
# cat / grep / less / cp / base64 ... cannot be used to read them.
# (These are plain `*` globs, so `.env.example` is blocked here too: use the Read tool.)
PATH_MENTIONS = [
    "*.env", "*.env *", "*.env.*", "*.tfstate*", "*.tfplan*",
    "*.pem", "*.pem *", "*.key", "*.key *", "*.p12*", "*.pfx*", "*.jks*",
    "*.keystore*", "*.ppk*", "*id_rsa*", "*id_ed25519*",
    "*.aws/credentials*", "*.aws/sso*", "*.aws/cli/cache*", "*.ssh/id_*",
    "*.gnupg*", "*.kube/*", "* kubeconfig*", "*/kubeconfig*", "*.kubeconfig*", "*.netrc*",
    "*.git-credentials*", "*.config/gh/*", "*.config/gcloud*", "*.azure/*",
    "*.docker/config.json*", "*.npmrc*", "*.pypirc*", "*.doppler*", "*.vault_pass*",
    "*vault-pass*", "*Library/Keychains*", "*Library/Messages*", "*Library/Mail*",
    "*Library/Passes*", "*Library/Cookies*", "*Library/Safari*",
    "*chat.db*", "*Login Data*", "*key4.db*", "*logins.json*",
    "*zsh_history*", "*bash_history*", "*fish_history*", "*.psql_history*",
    "*.python_history*", "*.mysql_history*",
    "*.claude/.credentials*", "*.codex/auth.json*", "*opencode/auth.json*",
    "*/etc/rancher*", "*k3s.yaml*", "*k3s/server/tls*", "*k3s/server/*token*",
    # Linux
    "*.local/share/keyrings*", "*kwalletd*", "*.password-store*", "*.mozilla/*",
    "*.config/google-chrome*", "*.config/chromium*", "*.config/BraveSoftware*",
    "*.config/microsoft-edge*", "*.thunderbird*", "*.config/Signal*", "*TelegramDesktop*",
    "*.var/app/*", "*.pki/*", "*/etc/shadow*", "*/etc/gshadow*", "*/etc/sudoers*",
    "*/etc/ssh/ssh_host*", "*system-connections*", "*/etc/pki/tls/private*",
    "*/etc/ssl/private*", "*/etc/wireguard*", "*/etc/kubernetes/admin.conf*",
    "*/etc/kubernetes/pki*", "*/proc/*/environ*", "*/proc/*/cmdline*", "*/mnt/hgfs*",
]

# --------------------------------------------------------------------------
# Write boundary
# --------------------------------------------------------------------------

# Writable outside the project directory without asking. macOS also spells /tmp as /private/tmp.
TMP_DIRS_BY_OS = {"macos": ["/tmp", "/private/tmp"], "linux": ["/tmp"]}

# Skill / agent directories an agent needs to read to work. Read-only on purpose.
SKILL_DIRS = [
    "~/.claude/skills/**", "~/.claude/plugins/**", "~/.claude/agents/**",
    "~/.agents/**", "~/.codex/skills/**", "~/.omp/agent/skills/**",
    "~/.config/opencode/skill/**", "~/.config/opencode/skills/**",
    "~/.config/opencode/agent/**", "~/.config/opencode/agents/**",
    "~/.config/opencode/plugins/**",
]
# This machine's GNU Stow layout: ~/.agents and ~/.claude/agents are symlinks into dotfiles,
# and symlink targets are checked too. Edit for your own layout.
LOCAL_SKILL_DIRS = ["~/dotfiles/agents/.agents/**", "~/dotfiles/claude/.claude/agents/**"]

# Claude sandbox (macOS Seatbelt / Linux bubblewrap): shell commands can write only inside the
# project directory plus the temp dirs. Claude folds every Read(...) deny rule above into the
# sandbox's read-deny, so the secret stores are unreadable to shell commands too (a `python -c`
# that opens a secret file is blocked by the OS, not just by command matching).
#
# Nothing is re-opened: any sandboxed script could read what is listed here, so a tool that needs a
# credential store runs OUTSIDE the sandbox instead (see SANDBOX_EXCLUDED). That covers the AWS SSO
# cache (admin and agent sessions share ~/.aws/sso/cache) and doppler's token (macOS Keychain, or
# the ~/.doppler file on Linux, which reaches every Doppler project). `--check` keeps this list empty.
SANDBOX_ALLOW_READ = []
# Hosts sandboxed commands may reach without a prompt. Anything else prompts the first time.
ALLOWED_DOMAINS = [
    "github.com", "*.github.com", "*.githubusercontent.com", "ghcr.io",
    "registry.terraform.io", "releases.hashicorp.com", "checkpoint-api.hashicorp.com",
    "*.amazonaws.com", "*.awsapps.com", "api.doppler.com",
    "proxy.golang.org", "sum.golang.org", "registry.npmjs.org",
    "pypi.org", "files.pythonhosted.org",
    "registry-1.docker.io", "auth.docker.io", "index.docker.io",
    "production.cloudflare.docker.com", "quay.io", "registry.fedoraproject.org",
]
# Run outside the sandbox. They still go through the permission rules above, which is where the
# secret guardrails live. Two reasons:
#  - docker/podman need a socket / user namespaces the sandbox blocks.
#  - terraform, aws and doppler need credentials the sandbox hides on purpose: the SSO token
#    cache (~/.aws/sso) and, on macOS, doppler's Keychain token. Inside the sandbox every
#    `terraform plan` would fail and force an approval prompt, which defeats an agentic workflow.
# The cost: these commands lose the OS-level write boundary (the rules still apply). Note the
# admin-profile deny covers command lines only, not a `profile =` line in Terraform code.
# Read-only gh: the ~/.local/bin/gh wrapper fetches GH_TOKEN from doppler, so these run outside the
# sandbox too. Only these subcommands: gh writes (pr create, push...) stay sandboxed and fail.
GH_READ = [
    "gh pr view", "gh pr list", "gh pr status", "gh pr checks", "gh issue view",
    "gh issue list", "gh run view", "gh run list", "gh repo view", "gh repo list",
]
# The pre-edit sync every agent runs (AGENTS.md): exact form only, no other `git pull`. Outside the
# sandbox for the same reason as gh: the credentials (doppler helper, SSH keys) are hidden in it.
GIT_SYNC = "git pull --rebase --autostash"
SANDBOX_EXCLUDED = ["docker *", "podman *", "terraform *", "tofu *", "aws *", "doppler *"] + \
    [p for c in GH_READ for p in (c, c + " *")] + [GIT_SYNC]

# --------------------------------------------------------------------------
# Shell commands: deny
# --------------------------------------------------------------------------

DENY_BASH = [
    # --- environment and credential dumps ---
    "=env", "printenv", "=export -p", "ps e*", "history", "=set",
    "declare -p", "declare -x", "typeset -x", "cat /proc/*/environ*",
    "gh auth token", "gh auth status *-t*", "gh auth status *--show-token*",
    "doppler secrets", "doppler configure", "doppler *--plain*",
    "doppler run *-- env", "doppler run *-- env *", "doppler run *-- printenv*",
    "doppler run *-- export*",
    "docker inspect", "docker exec * env*", "systemctl show", "systemctl cat",
    "security", "secret-tool", "op", "bw", "lpass", "pass show", "keepassxc-cli",
    "pbpaste", "xclip -o", "xsel -o", "wl-paste", "defaults read", "log show",
    # --- Linux credential stores and secrets ---
    "keyctl read", "keyctl print", "keyctl pipe", "systemd-creds decrypt", "systemd-creds cat",
    "gdbus *secrets*", "busctl *secrets*", "dbus-send *secrets*",
    "nmcli *--show-secrets*", "nmcli *-s *", "wg showconf", "wg show *private*",
    "podman secret inspect *--showsecret*",
    # --- AWS: credential minting and secret reads ---
    "aws configure get", "aws configure export-credentials",
    "aws sts get-session-token", "aws sts assume-role*", "aws sts get-federation-token",
    "aws sso get-role-credentials",
    "aws secretsmanager *get-secret-value*", "aws ssm get-parameter*",
    "aws kms decrypt", "aws kms generate-data-key*", "aws ec2 get-password-data",
    "aws ec2 create-key-pair", "aws iam create-access-key", "aws iam create-login-profile",
    "aws iam update-login-profile", "aws iam create-service-specific-credential",
    "aws iam reset-service-specific-credential",
    "aws ecr get-login-password", "aws ecr get-authorization-token", "aws eks get-token",
    "aws codeartifact get-authorization-token", "aws rds generate-db-auth-token",
    # --- AWS: blast radius ---
    "aws s3 rb", "aws s3 rm *--recursive*", "aws organizations", "aws iam delete-*",
    "aws kms schedule-key-deletion", "aws kms disable-key", "aws ec2 terminate-instances",
    "aws rds delete-db-*", "aws cloudformation delete-stack", "aws dynamodb delete-table",
    "aws s3api delete-bucket*", "aws eks delete-cluster",
    # --- Terraform / OpenTofu ---
    "terraform destroy", "terraform apply *-destroy*", "terraform force-unlock",
    "terraform state rm", "terraform state push", "terraform state pull",
    "terraform state show", "terraform console", "terraform workspace delete",
    "terraform show *-json*", "terraform output *-json*", "terraform output *-raw*",
    # --- Ansible ---
    "ansible-vault view", "ansible-vault decrypt", "ansible-vault edit",
    "ansible-vault rekey", "ansible-vault encrypt_string", "ansible* *-vvv*",
    # --- Kubernetes / Helm / k3s ---
    # kubectl accepts mixed-case resource names (Secret, SECRETS), so cover the common spellings
    "kubectl get *secret*", "kubectl describe *secret*",
    "kubectl get *Secret*", "kubectl describe *Secret*",
    "kubectl get *SECRET*", "kubectl describe *SECRET*",
    "kubectl config view *--raw*",
    "kubectl delete namespace*", "kubectl delete ns*", "kubectl delete *--all*",
    "kubectl delete *-A*", "helm get values", "helm get all", "helm get manifest",
    "k3s token",
    # --- destruction ---
    "rm -rf", "rm -fr", "rm -r", "rm -R", "shred", "truncate", "mkfs", "fdisk", "parted",
    "dd if=*of=/dev/*", "find *-delete*", "find *-exec rm*",
    "chown -R", "chmod 777", "chmod -R 777",
    "docker system prune", "docker volume rm", "docker rm -f",
    "docker compose down *-v*", "docker-compose down *-v*", "crontab -r",
    # --- git data loss ---
    # force push; written so --force-with-lease does not match (the agent host allows it off main)
    "git reset --hard", "git clean", "git branch -D", "git push --force", "git push * --force",
    "git push * --force *", "git push -f", "git push * -f", "git push * -f *",
    "git push *--force-with-lease*main*", "git push *--force-with-lease*master*",
    "git filter-branch", "git filter-repo",
    # --- privilege / availability ---
    "sudo", "su", "doas", "pkexec", "run0", "visudo", "setenforce",
    "pkill", "killall", "systemctl stop", "systemctl disable", "systemctl mask",
    "ufw disable", "iptables", "nft", "tailscale down", "tailscale logout",
    "apt purge", "apt-get purge",
    # --- piping a download into a shell (agents split pipes, so match the shell side) ---
    "=sh", "=bash", "=zsh",
]

# The AWS profiles / permission sets the agent must never use (the human's admin role).
# Matched as a substring of the profile name, case-sensitively, so list each spelling.
# Add your exact profile and sso-session names here once they exist.
#   platform-admin  = the human's admin profile (Mac only)
#   agent-readonly  = the agent's profile; its name must NOT contain any token below
#   seeds-admin     = the human's admin sso-session; seeds-agent = the agent's (must stay clear of the tokens)
ADMIN_AWS_PROFILES = ["platform-admin", "seeds-admin", "admin", "Admin", "ADMIN"]
DENY_BASH += (
    ["aws *--profile*%s*" % n for n in ADMIN_AWS_PROFILES]
    + ["aws *--sso-session*%s*" % n for n in ADMIN_AWS_PROFILES]
    + ["*AWS_PROFILE=*%s*" % n for n in ADMIN_AWS_PROFILES]
    # botocore (AWS CLI) also honours the legacy AWS_DEFAULT_PROFILE variable
    + ["*AWS_DEFAULT_PROFILE=*%s*" % n for n in ADMIN_AWS_PROFILES]
)

# SSO login. A plain `aws sso login` opens the default browser, which may be signed in as the
# admin account. The agent must use --no-browser (it prints a URL and a code; the human opens
# them in a private window). Rules cannot say "deny unless --no-browser" (deny beats allow, and
# globs have no negation), so:
#  1. exact-match denies for the regular forms: they never match a --no-browser command, so
#  2. the --no-browser forms can be allowed; the admin denies above still beat that allow;
#  3. Claude only: a hook catches every other regular form and tells the agent what to do,
#     which a deny rule cannot do. Other agents just get the denial.
AGENT_AWS_PROFILE, AGENT_AWS_SESSION = "agent-readonly", "seeds-agent"
DENY_BASH += [
    "=aws sso login",
    "=aws sso login --sso-session %s" % AGENT_AWS_SESSION,
    "=aws sso login --sso-session=%s" % AGENT_AWS_SESSION,
    "=aws sso login --profile %s" % AGENT_AWS_PROFILE,
    "=aws sso login --profile=%s" % AGENT_AWS_PROFILE,
]
ALLOW_SSO_LOGIN = ["aws sso login *--no-browser*"]

SSO_LOGIN_MESSAGE = (
    "Plain `aws sso login` is blocked here: it opens the default browser, which may be signed in "
    "to the admin account. Re-run it with --no-browser, for example "
    "`aws sso login --sso-session %s --no-browser`, then give the user the URL and code it prints "
    "so they can open it in a private browser window." % AGENT_AWS_SESSION)
_HOOK_CODE = (
    "import json, re, sys\n"
    "c = json.load(sys.stdin).get('tool_input', {}).get('command', '')\n"
    # The `if` filter in the hook entry is only an optimisation: for commands Claude cannot parse
    # (loops, compound lines) it runs the hook anyway. So the script must decide for itself, or it
    # would block unrelated commands.
    "if re.search(r'\\baws\\b.*\\bsso\\s+login\\b', c) and '--no-browser' not in c:\n"
    "    print(json.dumps({'hookSpecificOutput': {'hookEventName': 'PreToolUse',\n"
    "        'permissionDecision': 'deny', 'permissionDecisionReason': %s}}))\n" % json.dumps(SSO_LOGIN_MESSAGE))
# No AI attribution in commits or PRs (global AGENTS.md rule). `attribution` below stops Claude Code
# adding it; this hook rejects it if an agent writes it anyway. The message may come inline, from a
# heredoc, or from a file (-F / --file / --body-file / --input), so files named that way are read too.
_ATTRIBUTION_HOOK_CODE = (
    "import json, os, re, sys\n"
    "d = json.load(sys.stdin)\n"
    "c, cwd = d.get('tool_input', {}).get('command', ''), d.get('cwd') or '.'\n"
    "if re.search(r'\\bgit\\b.*\\b(commit|tag|notes)\\b|\\bgh\\b.*\\b((pr|issue|release)\\s+(create|edit|comment)|api)\\b', c, re.S):\n"
    "    text = c\n"
    "    for m in re.finditer(r'(?:-F|--file|--body-file|--input)[= ]+(\\S+)', c):\n"
    "        try:\n"
    "            text += open(os.path.join(cwd, os.path.expanduser(m.group(1).strip(chr(34) + chr(39)))), errors='replace').read(200000)\n"
    "        except OSError:\n"
    "            pass\n"
    "    if re.search(r'Generated with \\[?Claude Code|Co-Authored-By:\\s*Claude|noreply@anthropic\\.com', text, re.I):\n"
    "        print(json.dumps({'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'deny',\n"
    "            'permissionDecisionReason': 'No AI attribution in commits or PRs: remove the Generated with / Co-Authored-By line and retry.'}}))\n")
ATTRIBUTION_HOOK = {
    "matcher": "Bash",
    "hooks": [{"type": "command", "command": "python3 -c " + shlex.quote(_ATTRIBUTION_HOOK_CODE), "timeout": 10}],
}

SSO_LOGIN_HOOK = {
    "matcher": "Bash",
    "hooks": [{
        "type": "command",
        "if": "Bash(*aws sso login*)",   # only spawn for login commands
        "command": "python3 -c " + shlex.quote(_HOOK_CODE),
        "timeout": 10,
    }],
}

# Linux only: Claude's file tools may not read PROC_SECRET_PATHS (see there for why this is a hook).
_PROC_HOOK_CODE = (
    "import json, os, re, sys\n"
    "t = json.load(sys.stdin).get('tool_input', {})\n"
    "for p in (t.get('file_path'), t.get('path')):\n"
    "    if p and re.fullmatch(r'/proc/[^/]+/(environ|cmdline|mem)', os.path.normpath(p)):\n"
    "        print(json.dumps({'hookSpecificOutput': {'hookEventName': 'PreToolUse',\n"
    "            'permissionDecision': 'deny', 'permissionDecisionReason': 'process environment and memory are secret'}}))\n"
    "        break\n")
PROC_READ_HOOK = {
    "matcher": "Read|Edit|Write|Grep|Glob",
    "hooks": [{"type": "command", "command": "python3 -c " + shlex.quote(_PROC_HOOK_CODE), "timeout": 10}],
}

# --------------------------------------------------------------------------
# Shell commands: always prompt (matters where a broader allow would otherwise win)
# --------------------------------------------------------------------------

ASK_BASH = [
    # --- Terraform / OpenTofu ---
    "terraform apply", "terraform import", "terraform taint", "terraform untaint",
    "terraform state mv", "terraform init *-migrate-state*", "terraform init *-reconfigure*",
    "terraform show", "terraform output", "terraform login", "terraform refresh",
    # --- AWS ---
    "aws * delete-*", "aws * terminate-*", "aws * put-*", "aws * create-*",
    "aws * update-*", "aws * modify-*", "aws iam attach-*", "aws iam detach-*",
    "aws iam add-*", "aws s3 rm", "aws s3 mv", "aws s3 cp", "aws s3 presign",
    "aws s3 sync *--delete*", "aws cloudformation deploy",
    "aws ssm start-session", "aws ssm send-command", "aws ecs execute-command",
    "aws lambda invoke", "aws configure", "aws configure list", "aws configure sso*",
    # AWS read calls that return secrets (env vars, user data); override the read allows
    "aws lambda list-functions", "aws lambda get-function*", "aws ecs describe-task-definition",
    "aws ecs describe-tasks", "aws batch describe-job-definitions",
    "aws apprunner describe-service", "aws elasticbeanstalk describe-configuration-settings",
    "aws ec2 describe-instance-attribute", "aws ec2 describe-launch-template-versions",
    "aws codebuild batch-get-projects",
    # --- Ansible ---
    "ansible", "ansible-inventory", "ansible-galaxy install",
    "ansible-galaxy collection install",
    # --- Kubernetes / Helm / k3s ---
    "kubectl delete", "kubectl apply", "kubectl create", "kubectl patch",
    "kubectl replace", "kubectl scale", "kubectl edit", "kubectl exec", "kubectl cp",
    "kubectl rollout", "kubectl port-forward", "helm install", "helm upgrade",
    "helm uninstall", "helm rollback", "k3s secrets-encrypt", "k3s etcd-snapshot",
    # --- containers, git, doppler ---
    "docker login", "docker compose config", "docker-compose config",
    "git push", "git restore", "git checkout -- *", "git stash drop", "git stash clear",
    "git rebase", "gh auth status", "gh repo create", "gh repo delete",
    "doppler login", "doppler setup",
    # --- Linux host administration ---
    "journalctl", "firewall-cmd", "semanage", "setsebool", "restorecon",
    # --- shells and interpreters hide what they run ---
    "bash -*c *", "sh -*c *", "zsh -*c *", "python -c", "python3 -c", "node -e",
    "ruby -e", "perl -e", "eval", "osascript",
]

# --------------------------------------------------------------------------
# Shell commands: allow
# --------------------------------------------------------------------------

# Safe anywhere: purely offline checks and read-only local inspection.
ALLOW_OFFLINE = [
    "git status", "git diff", "git log", "git show", "git blame", "git ls-files",
    "git rev-parse", "=git branch", "=git branch --show-current",
    "terraform fmt", "terraform validate", "terraform version", "=terraform -version",
    "terraform init *-backend=false*", "terraform providers", "terraform graph",
    "tflint", "tfsec", "checkov", "terraform-docs", "trivy config",
    "helm lint", "helm template", "helm version", "helm repo list", "helm search",
    "kubeconform", "yamllint", "ansible-lint", "ansible-doc", "ansible --version",
    "ansible-playbook *--check*", "ansible-playbook *--syntax-check*",
    "ansible-playbook *--list-tasks*", "ansible-playbook *--list-hosts*",
    # gitleaks prints the secrets it finds unless told to redact them
    "gitleaks detect *--redact*", "gitleaks git *--redact*", "gitleaks dir *--redact*",
    "gitleaks protect *--redact*",
    "=aws --version", "=doppler --version", "docker ps", "docker images", "docker version",
] + GH_READ + ["=" + GIT_SYNC]

# Read-only calls that reach live AWS or a live cluster. Standard profile only.
ALLOW_LIVE = [
    "terraform plan", "terraform init", "terraform state list", "terraform workspace list",
    "terraform workspace show",
    # `aws *x` so global flags before the service (--profile, --region) still match
    "aws *sts get-caller-identity*", "aws * describe-*", "aws * list-*", "aws *s3 ls*",
    "aws configure list-profiles",
    "kubectl get", "kubectl describe", "kubectl logs", "kubectl top", "kubectl version",
    "kubectl api-resources", "kubectl explain", "kubectl cluster-info",
    "kubectl config current-context", "kubectl config get-contexts",
    "helm list", "helm status", "helm history",
]

# --------------------------------------------------------------------------
# Agent host (--agent-host): a machine used only for agent work (the Pi)
# --------------------------------------------------------------------------

# Agents there work unattended: they push branches and open PRs, the human reviews and merges. The
# policy protects exactly two things: secrets never leak, destructive commands never run. Everything
# else (git in any repo, gh PR housekeeping, commit hooks, herdr) should just work.
# The real guard on `main` is GitHub branch protection (PR required, no force push).
#
# Run outside the sandbox (prefix match, only as a plain command of its own):
#  - git: the credential helper fetches GH_TOKEN from doppler (~/.doppler is hidden from the sandbox),
#    git writes .git/config (branch tracking) and runs commit hooks
#    (pre-commit fetching from GitHub, terraform providers needing unix sockets) that fail in bwrap.
#  - git-in <dir> <git args> (bin/git-in, installed root-owned in /usr/local/bin by regen-agent-host.sh):
#    git in another repo. Claude Code NEVER exempts a git command with a global -C, -c, --git-dir or
#    --work-tree option from the sandbox (hard-coded in its matcher; no pattern, `git -C *` included, can
#    match), so `git -C <dir> push` always runs sandboxed. The wrapper is not `git` and does the cd itself.
#  - gh: the ~/.local/bin/gh wrapper fetches GH_TOKEN from doppler too.
#  - pre-commit: `pre-commit install` writes .git/hooks, which the sandbox protects.
#  - herdr: its socket (~/.config/herdr/sessions/<session>/herdr.sock) is blocked by the sandbox's
#    seccomp filter, and Linux has no per-path socket allowance (allowUnixSockets is macOS only).
#  - kubectl and helm read ~/.kube and get EKS tokens through the AWS SSO cache, both hidden.
# The guard hook (agent_host_guard.py) checks the destructive and secret-reading forms of all of
# these except herdr; the deny rules still apply.
AGENT_HOST_EXCLUDED = ["git *", "gh *", "git-in *", "pre-commit *", "herdr *", "kubectl *", "helm *"]
AGENT_HOST_WRITE = ["~/REPOS", "~/.cache/pre-commit"]
# NOTE: the Linux sandbox ignores these wildcard denyWrite entries (verified live 2026-10-04); only
# the Edit-tool deny rules generated from them are enforced. Kept for macOS and future support.
# Claude protects the config of the project it runs in, not of sibling repos. Writable, these
# would let an agent loosen the next session in another repo or plant a git hook.
# `.claude` itself stays writable: worktrees live in `.claude/worktrees`.
AGENT_HOST_DENY_WRITE = ["~/REPOS/*/%s" % p for p in (
    ".claude/settings.json", ".claude/settings.local.json", ".claude/hooks", ".claude/skills",
    ".claude/agents", ".claude/commands", ".claude/workflows", ".claude/scheduled_tasks.json",
    ".mcp.json", "opencode.json", ".omp", ".envrc", ".git/hooks", ".git/config",
)]
# Ordinary dev work. Claude allows every command anyway (`Bash(*)`); opencode and omp, which prompt for
# anything unlisted, get these as allows.
AGENT_HOST_ALLOW_BASH = [
    "git push", "git-in", "git -C", "git fetch", "git pull", "git commit", "git add", "git checkout",
    "git switch", "git branch", "git merge", "git rebase", "git stash", "git update-ref", "git tag",
    "git restore",
    "gh pr create", "gh pr edit", "gh pr close", "gh pr reopen", "gh pr comment", "gh pr ready",
    "gh pr diff", "gh pr checkout", "gh run rerun", "gh run cancel", "gh run watch", "gh issue create",
    "gh issue comment", "gh issue close", "gh issue edit", "gh api", "gh secret list", "gh secret set",
    "gh repo clone", "gh repo create",
    "pre-commit", "herdr",
    # Doppler: list projects, configs and environments (names, never values)
    "doppler projects", "doppler configs", "doppler environments",
]
# Name-only listing. A glob cannot say "doppler secrets, but only with --only-names", so for Claude the
# guard decides (the `doppler secrets` deny rules are dropped); opencode and omp get these exact
# forms placed so they beat the deny (opencode: after it, omp: before it).
AGENT_HOST_NAME_ONLY = ["=doppler secrets --only-names", "doppler secrets --only-names -p *",
                        "doppler secrets --only-names --project *"]
AGENT_HOST_DENY_BASH = [
    # --- GitHub: merging and deleting stay with the human; tokens and code-running extensions ---
    "gh pr merge", "gh repo delete", "gh repo archive", "gh repo rename", "gh repo edit *--visibility*",
    "gh release delete", "gh api *-X DELETE*", "gh api *-XDELETE*", "gh api *--method DELETE*",
    "gh api *--method=DELETE*", "gh secret delete", "gh secret remove", "gh variable delete",
    "gh run delete", "gh issue delete", "gh label delete", "gh workflow run", "gh extension", "gh alias",
    "gh auth", "gh ssh-key", "gh gpg-key",
    # --- remote branches: delete, mirror or force by refspec ---
    "git push *--delete*", "git push * -d *", "git push * :*", "git push * +*", "git push *--mirror*",
    "git push *--prune*",
    # --- discarding every uncommitted change (single files are fine) ---
    "=git checkout .", "=git checkout -- .", "=git restore .", "=git restore --worktree .",
    "terraform apply",  # nobody is there to approve it, so deny instead of a prompt that stalls
    # The Doppler list commands above must not reach their token-minting, mutating, log or
    # config-printing forms, nor a flag that sends the token to another host.
    "doppler *tokens*", "doppler *--print-config*", "doppler *--api-host*", "doppler *--dashboard-host*",
    "doppler *--no-verify-tls*", "doppler *dns-resolver*",
] + ["doppler %s *%s*" % (sub, verb) for sub in ("projects", "configs", "environments")
     for verb in ("create", "delete", "update", "rename", "clone", "lock", "unlock", "logs")] + [
    # --- live infrastructure: read only, the owner makes changes ---
    "terraform import", "terraform taint", "terraform untaint", "terraform state mv",
    "terraform init *-migrate-state*", "terraform refresh", "terraform login",
    "terraform show", "terraform output",  # print state values
    "aws * delete-*", "aws * terminate-*", "aws * put-*", "aws * create-*", "aws * update-*",
    "aws * modify-*", "aws iam attach-*", "aws iam detach-*", "aws iam add-*", "aws s3 rm",
    "aws s3 mv", "aws s3 cp", "aws s3 presign", "aws s3 sync", "aws cloudformation deploy",
    "aws ssm start-session", "aws ssm send-command", "aws ecs execute-command", "aws lambda invoke",
    "=aws configure", "aws configure set", "aws configure import", "aws configure sso*",
    # AWS reads that return secrets (env vars, user data)
    "aws lambda list-functions", "aws lambda get-function*", "aws ecs describe-task-definition",
    "aws ecs describe-tasks", "aws batch describe-job-definitions", "aws apprunner describe-service",
    "aws elasticbeanstalk describe-configuration-settings", "aws ec2 describe-instance-attribute",
    "aws ec2 describe-launch-template-versions", "aws codebuild batch-get-projects",
    "ansible", "ansible-inventory",  # ansible-playbook: the guard allows only --check / list modes
    "kubectl delete", "kubectl apply", "kubectl create", "kubectl patch", "kubectl replace",
    "kubectl scale", "kubectl edit", "kubectl exec", "kubectl cp", "kubectl rollout restart",
    "kubectl rollout undo", "kubectl rollout pause", "kubectl rollout resume", "kubectl label",
    "kubectl annotate", "kubectl set", "kubectl taint", "kubectl cordon", "kubectl uncordon",
    "kubectl drain", "kubectl autoscale", "kubectl expose", "kubectl run", "kubectl debug",
    "kubectl attach", "kubectl certificate",
    # kubectl and helm run outside the sandbox: a kubeconfig the agent writes could carry an
    # `exec:` credential plugin that runs any program unsandboxed
    "kubectl *--kubeconfig*", "helm *--kubeconfig*", "*KUBECONFIG=*",
    "helm install", "helm upgrade", "helm uninstall", "helm rollback", "helm test",
    "k3s secrets-encrypt", "k3s etcd-snapshot",
    # --- docker is root-equivalent (docker group) and runs outside the sandbox: a container can mount ~ ---
    "docker run", "docker create", "docker exec", "docker cp", "docker build", "docker buildx",
    "docker compose config", "docker-compose", "docker service",  # docker compose: guard allows reads
    "docker login",
    # --- credentials, logs, host administration ---
    "doppler login", "doppler setup", "journalctl",
    "firewall-cmd", "semanage", "setsebool", "restorecon",
]
# Claude only (opencode and omp have no sandbox or guard hook, so they keep prompting): every Bash
# command not denied runs. Nobody is there to answer a prompt. The deny rules still win, the
# sandbox read-deny still hides the secret stores, and the guard hook covers what globs cannot.
AGENT_HOST_CLAUDE_ALLOW = ["Bash(*)"]
# `WebFetch(domain:*)` also opens every host to sandboxed commands (the sandbox honours bare `*`
# in WebFetch domain rules, Claude Code 2.1.186+). Secret files stay unreadable inside it.
AGENT_HOST_ALLOW_TOOLS = ["WebFetch(domain:*)", "WebSearch"]
# Every ASK_BASH entry must be decided for the agent host (denied above, also by a deny prefix such
# as `gh auth` for `gh auth status`, or allowed here): an unattended agent cannot answer a prompt.
# bash_rules() exits if one is missing.
AGENT_HOST_ALLOW_FROM_ASK = [
    "terraform init *-reconfigure*", "aws configure list", "ansible-galaxy install",
    "ansible-galaxy collection install", "kubectl rollout", "kubectl port-forward",
    "git push", "git rebase", "git restore", "git checkout -- *", "git stash drop", "git stash clear",
    "gh repo create",
    # interpreters run inside the sandbox, which hides the secret stores at the OS level
    "bash -*c *", "sh -*c *", "zsh -*c *", "python -c", "python3 -c", "node -e", "ruby -e",
    "perl -e", "eval", "osascript",
]

WRAP_TOOLS = ("terraform", "tofu", "aws", "ansible", "kubectl", "k3s", "helm", "packer", "sops", "vault")

# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def expand(cmd):
    """One list entry -> the glob patterns it stands for."""
    if cmd.startswith("="):
        return [cmd[1:]]
    if "*" in cmd:
        return [cmd]
    return [cmd, cmd + " *"]


def wrap(cmds, allow):
    """Doppler-wrapped twins, so `doppler run -- <cmd>` is judged like `<cmd>`.

    Allow rules insist on --only-secrets (least privilege); deny/ask rules do not.
    """
    pre = "doppler run *--only-secrets* -- " if allow else "doppler run * -- "
    out = []
    for c in cmds:
        bare = c.lstrip("=")
        if bare.split()[0].startswith(WRAP_TOOLS):
            out.append(("=" if c.startswith("=") else "") + pre + bare)
    return out


def uniq(items):
    return list(dict.fromkeys(items))


def _twin(cmds, matches, rename):
    """Add a renamed copy of every rule whose command starts with one of `matches`."""
    twins = []
    for c in cmds:
        bare = c.lstrip("=")
        if any(bare == m or bare.startswith(m + " ") or bare.startswith(m + "*") for m in matches):
            twins.append(("=" if c.startswith("=") else "") + rename(bare))
    return list(cmds) + twins


def with_tofu(cmds):
    """Every `terraform ...` rule gets an OpenTofu twin."""
    return _twin(cmds, ("terraform",), lambda b: b.replace("terraform", "tofu", 1))


def with_podman(cmds):
    """Every `docker ...` rule gets a podman twin (Fedora ships podman, not docker)."""
    cmds = _twin(cmds, ("docker-compose",), lambda b: b.replace("docker-compose", "podman-compose", 1))
    return _twin(cmds, ("docker",), lambda b: b.replace("docker", "podman", 1))


def with_k3s(cmds):
    """Every `kubectl ...` rule gets a `k3s kubectl ...` twin (the bundled kubectl)."""
    return _twin(cmds, ("kubectl",), lambda b: "k3s " + b)


def twins(cmds):
    return with_k3s(with_podman(with_tofu(cmds)))


def expand_all(cmds):
    return uniq(p for c in cmds for p in expand(c))


def with_git_c(cmds):
    """Every expanded `git ...` pattern gets `git -C * ...` and `git-in * ...` twins (opencode and omp)."""
    both = _twin(cmds, ("git",), lambda b: "git -C * " + b[len("git "):])
    return _twin(both, ("git",), lambda b: "git-in * " + b[len("git "):])


def bash_rules(profile, agent_host=False, guarded=False):
    """guarded: Claude, with its sandbox and guard hook. opencode and omp have neither, so on the agent
    host they get the name-only doppler listing as an extra `override` tier that beats the deny rules."""
    deny_src, ask_src, allow = twins(DENY_BASH), twins(ASK_BASH), twins(ALLOW_OFFLINE) + ALLOW_SSO_LOGIN
    override = []
    if agent_host:
        bare = [d.lstrip("=") for d in AGENT_HOST_DENY_BASH]
        undecided = [a for a in ASK_BASH if a not in AGENT_HOST_ALLOW_FROM_ASK
                     and not any(a == d or a.startswith(d + " ") for d in bare)]
        if undecided:
            sys.exit("agent host: decide allow or deny for ASK_BASH entries %s" % undecided)
        ask_src = []  # Claude: allowed by `Bash(*)` unless denied; opencode/omp: unmatched still prompts
        deny_src = deny_src + twins(AGENT_HOST_DENY_BASH)
        allow += AGENT_HOST_ALLOW_BASH
        if guarded:  # the guard allows `doppler secrets --only-names` and denies every other form
            deny_src = [d for d in deny_src if d != "doppler secrets"]
        else:
            override = AGENT_HOST_NAME_ONLY
    deny = deny_src + wrap(deny_src, allow=False)
    ask = ask_src + wrap(ask_src, allow=False)
    if profile == "standard":
        live = twins(ALLOW_LIVE)
        allow += live + wrap(live, allow=True)
    rules = {
        "deny": (with_git_c(expand_all(deny)) if agent_host else expand_all(deny)) + PATH_MENTIONS,
        "ask": expand_all(ask),
        "allow": expand_all(allow),
        "override": expand_all(override),
    }
    clash = set(rules["allow"]) & set(rules["deny"]) | set(rules["ask"]) & set(rules["deny"])
    clash |= set(rules["allow"]) & set(rules["ask"])
    if clash:
        sys.exit("same pattern in two tiers: %s" % sorted(clash))
    return rules


def abs_claude(p):
    """Absolute path -> Claude rule spelling (leading //)."""
    return "/" + p


def home_paths(os_name):
    return SECRET_PATHS_HOME + (SECRET_PATHS_HOME_MACOS if os_name == "macos" else SECRET_PATHS_HOME_LINUX)


def abs_paths(os_name):
    return SECRET_PATHS_ABS + (SECRET_PATHS_ABS_LINUX if os_name == "linux" else [])


# --------------------------------------------------------------------------
# Writers
# --------------------------------------------------------------------------


def claude_secret_paths(os_name):
    any_paths = []
    for p in SECRET_PATHS_ANY:
        any_paths += ENV_EXCEPT_EXAMPLE if p == ENV_PATTERN else [p]
    return home_paths(os_name) + [abs_claude(p) for p in abs_paths(os_name)] + any_paths


def agent_host_guard_hook(os_name, repo_roots=("~/REPOS",)):
    """agent_host_guard.py with this policy's secret paths, embedded inline so the
    root-owned managed settings file is self-contained (no script an agent could edit)."""
    src = (HERE / "agent_host_guard.py").read_text()
    globs = home_paths(os_name) + abs_paths(os_name) + PROC_SECRET_PATHS + SECRET_PATHS_ANY
    src = src.replace("SECRET_GLOBS = []", "SECRET_GLOBS = %r" % globs, 1)
    src = src.replace("REPO_ROOTS = []", "REPO_ROOTS = %r" % list(repo_roots), 1)
    return {"matcher": "Bash", "hooks": [{"type": "command", "command": "python3 -c " + shlex.quote(src),
                                          "timeout": 30}]}


def excluded_commands(agent_host):
    if not agent_host:
        return SANDBOX_EXCLUDED
    # `git *` and `gh *` replace the narrower git/gh entries
    return [e for e in SANDBOX_EXCLUDED if not e.startswith(("git ", "gh "))] + AGENT_HOST_EXCLUDED


def claude_settings(profile, os_name, extra_deny=(), sandbox=True, agent_host=False, mcpjson_servers=()):
    r = bash_rules(profile, agent_host, guarded=True)
    paths = claude_secret_paths(os_name)
    tmp = TMP_DIRS_BY_OS[os_name]
    write = tmp + (AGENT_HOST_WRITE if agent_host else [])
    deny_write = AGENT_HOST_DENY_WRITE if agent_host else []
    deny = ["Read(%s)" % p for p in paths] + ["Edit(%s)" % p for p in paths]
    deny += ["Edit(%s)" % p for p in deny_write] + ["Edit(%s/**)" % p for p in deny_write]
    deny += ["Bash(%s)" % p for p in r["deny"]] + list(extra_deny)
    allow = ["Bash(%s)" % p for p in r["allow"]]
    allow += ["Read(%s)" % p for p in SKILL_DIRS + LOCAL_SKILL_DIRS]
    for d in write:
        d = abs_claude(d) if d.startswith("/") else d
        allow += ["Read(%s/**)" % d, "Edit(%s/**)" % d]
    settings = {
        "$schema": "https://json.schemastore.org/claude-code-settings.json",
        "permissions": {
            "allow": uniq(allow),
            "ask": ["Bash(%s)" % p for p in r["ask"]],
            "deny": uniq(deny),
        },
        "hooks": {"PreToolUse": [SSO_LOGIN_HOOK, ATTRIBUTION_HOOK] + ([PROC_READ_HOOK] if os_name == "linux" else [])},
        # no "Generated with" / Co-Authored-By lines: Claude Code adds none and is not reminded to
        "attribution": {"commit": "", "pr": ""},
        "sandbox": {
            "enabled": True,
            # Linux needs bubblewrap + socat. Without this, a missing dependency means a warning
            # and commands running UNSANDBOXED, which silently removes the write boundary.
            "failIfUnavailable": True,
            # keep the prompts above in force instead of auto-approving sandboxed commands
            "autoAllowBashIfSandboxed": False,
            "filesystem": {"allowWrite": write, "denyWrite": deny_write, "allowRead": SANDBOX_ALLOW_READ},
            "network": {"allowedDomains": ALLOWED_DOMAINS},
            "excludedCommands": excluded_commands(agent_host),
        },
    }
    if agent_host:
        # Unattended and default-allow: web access never prompts, and the sandbox (not the
        # command rules) is what keeps secret files unreadable, so nothing may leave it except
        # excludedCommands. An allowed unsandboxed retry would run with no OS read-deny at all.
        settings["permissions"]["allow"] += AGENT_HOST_CLAUDE_ALLOW + AGENT_HOST_ALLOW_TOOLS
        settings["hooks"]["PreToolUse"].append(agent_host_guard_hook(os_name))
        settings["sandbox"]["allowUnsandboxedCommands"] = False
        # Meant for /etc/claude-code/managed-settings.json: repo settings cannot add prompts that
        # stall an unattended run, nor loosen these rules. (Has no effect in a project file.)
        settings["allowManagedPermissionRulesOnly"] = True
        if not sandbox:
            sys.exit("--agent-host needs the sandbox: its default-allow relies on the OS read-deny")
    if not sandbox:
        del settings["sandbox"]
    if mcpjson_servers:
        settings["enabledMcpjsonServers"] = list(mcpjson_servers)
    return settings


def oc_path(p):
    """Claude/gitignore style path glob -> opencode's plain `*` glob."""
    if p.startswith("**/"):
        p = "*" + p[3:]
    return p.replace("**", "*")


def opencode_config(profile, agent_host=False):
    r = bash_rules(profile, agent_host)
    bash = {"*": "ask"}
    for tier in ("allow", "ask", "deny", "override"):  # last match wins
        for p in r[tier]:
            bash[p] = "allow" if tier == "override" else tier
    # opencode is OS-independent: deny both OSes' paths (globs for absent paths are harmless)
    secret = uniq(oc_path(p) for p in (
        SECRET_PATHS_HOME + SECRET_PATHS_HOME_MACOS + SECRET_PATHS_HOME_LINUX
        + SECRET_PATHS_ABS + SECRET_PATHS_ABS_LINUX + PROC_SECRET_PATHS + SECRET_PATHS_ANY))
    skills = [oc_path(p) for p in SKILL_DIRS + LOCAL_SKILL_DIRS]
    tmp = uniq(d + "/*" for dirs in TMP_DIRS_BY_OS.values() for d in dirs)
    carve = oc_path("**/.env.example")  # last match wins, so a plain allow after the deny works

    read = {"*": "allow"}
    read.update({p: "deny" for p in secret})
    read[carve] = "allow"
    edit = {"*": "allow"}
    edit.update({p: "deny" for p in secret})
    edit[carve] = "allow"
    edit.update({p: "deny" for p in skills})  # skills are read-only
    # Outside the project: ask, except /tmp and skills; secrets stay denied (listed last).
    external = {"*": "ask"}
    external.update({p: "allow" for p in tmp + skills})
    if agent_host:
        external.update({p + "/*": "allow" for p in AGENT_HOST_WRITE})
        protected = [p for d in AGENT_HOST_DENY_WRITE for p in (d, d + "/*")]
        edit.update({p: "deny" for p in protected})
        external.update({p: "deny" for p in protected})
    external.update({p: "deny" for p in secret if p.startswith(("~/", "/"))})
    return {
        "$schema": "https://opencode.ai/config.json",
        "permission": {
            "bash": bash, "read": read, "edit": edit, "external_directory": external,
        },
    }


def omp_config(profile, agent_host=False):
    r = bash_rules(profile, agent_host)
    lines = [
        "# omp (oh-my-pi) approval policy generated from the secret-hygiene policy.",
        "# Install: ~/.omp/agent/config.yml (global) or <project>/.omp/config.yml (project)",
        "#",
        "# What this covers: shell commands (bash.patterns, first match wins, so deny",
        "# comes first). Unmatched commands prompt because approvalMode is `write`.",
        "# omp's default approvalMode is `yolo`, which prompts for nothing.",
        "#",
        "# What it does NOT cover:",
        "#  - Per-path rules. omp has no read/edit deny, so .env, *.tfstate or",
        "#    ~/.aws/credentials can still be opened with omp's own read tool.",
        "#  - A write boundary. I found no setting that confines edits to the project",
        "#    directory, and in `write` mode file edits are auto-approved. For a hard",
        "#    boundary run omp as a separate user / in a VM, or use approvalMode:",
        "#    always-ask (prompts on every edit and command).",
        "# Subagents run headless in yolo mode; the deny patterns below still bind them.",
        "tools:",
        "  approvalMode: write",
        "",
        "secrets:",
        "  enabled: true",
        "",
        "bash:",
        "  patterns:",
    ]
    for tier, name in (("override", "allow"), ("deny", "deny"), ("ask", "prompt"), ("allow", "allow")):
        if r[tier]:
            lines.append("    # --- %s ---" % (name if tier != "override" else "allow (before the denies)"))
        for p in r[tier]:
            lines.append('    - match: "%s"' % p)
            lines.append("      approval: %s" % name)
    return "\n".join(lines) + "\n"


def pull_upstream():
    """Rebase onto upstream before rewriting the tracked bundles (Mac and the Pi share this repo).

    If the pull moved HEAD, generate.py itself may have changed, so re-run the fresh copy rather
    than write bundles from the stale code already loaded. AGENT_PERMS_PULLED skips a second pull.
    """
    if os.environ.get("AGENT_PERMS_PULLED"):
        return
    head = lambda: subprocess.run(["git", "-C", str(HERE), "rev-parse", "HEAD"],
                                  capture_output=True, text=True).stdout
    before = head()
    if subprocess.run(["git", "-C", str(HERE), "pull", "--rebase", "--autostash"]).returncode:
        sys.exit("generate.py: git pull --rebase failed; resolve it, then re-run")
    os.environ["AGENT_PERMS_PULLED"] = "1"
    if head() != before:
        os.execv(sys.executable, [sys.executable, __file__] + sys.argv[1:])


def write(path, text):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    print("wrote", path)


def dump(obj):
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def claude_file(profile, os_name):
    return HERE / profile / ("claude-settings.%s.json" % os_name)


def install(project, profile, os_name, sandbox=True, force=False, extra_deny=(), agent_host=False):
    """Drop the files for this host into a project. Existing files are left alone unless force."""
    project = pathlib.Path(project)
    files = {
        project / ".claude" / "settings.json":
            dump(claude_settings(profile, os_name, extra_deny, sandbox, agent_host)),
        project / "opencode.json": dump(opencode_config(profile, agent_host)),
        project / ".omp" / "config.yml": omp_config(profile, agent_host),
    }
    for path, text in files.items():
        if path.exists() and not force:
            print("kept   %s (exists: merge by hand, or rerun with --force)" % path)
        else:
            write(path, text)


# --------------------------------------------------------------------------
# Check: read the written files back and test sample commands and paths
# --------------------------------------------------------------------------


def glob_match(pattern, text):
    return re.fullmatch(".*".join(re.escape(x) for x in pattern.split("*")), text, re.S) is not None


def gi_match(pattern, path):
    """Approximate gitignore-style matching, as used by Claude Read/Edit rules."""
    if pattern.startswith("~/"):
        pattern = "/h/" + pattern[2:]
    elif pattern.startswith("//"):
        pattern = pattern[1:]
    out, i = "", 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out, i = out + "(?:.*/)?", i + 3
        elif pattern.startswith("**", i):
            out, i = out + ".*", i + 2
        elif pattern[i] == "*":
            out, i = out + "[^/]*", i + 1
        elif pattern[i] == "?":
            out, i = out + "[^/]", i + 1
        elif pattern[i] == "[":
            j = pattern.index("]", i)
            body = pattern[i + 1:j]
            # Claude has no negated classes: a leading `^` or `!` is just another member
            body = re.sub(r"^\^", r"\\^", body.replace("\\", "\\\\"))
            out, i = out + "[" + body + "]", j + 1
        else:
            out, i = out + re.escape(pattern[i]), i + 1
    return re.fullmatch(out, path, re.I) is not None  # Claude's matching is case-insensitive


def decide_claude(cmd, deny, ask, allow):
    for tier, pats in (("deny", deny), ("ask", ask), ("allow", allow)):
        if any(glob_match(p, cmd) for p in pats):
            return tier
    return "ask"


def decide_ordered(cmd, rules, last_wins):
    seq = rules if last_wins else list(rules)
    hit = "ask"
    for pat, tier in seq:
        if glob_match(pat, cmd):
            hit = tier
            if not last_wins:
                break
    return hit


# The checks prove the two things this policy is for, plus that the output files are current:
#   1. secrets: stores unreadable, secret-printing commands denied
#   2. destruction: destructive commands denied
#   3. normal dev work runs (agent host)

# Denied in every profile and agent.
SECRET_PRINTING = [
    "env", "printenv HOME", "doppler secrets", "doppler secrets get X --plain", "doppler secrets download",
    "doppler configure get token", "doppler run --only-secrets X -- printenv", "kubectl get secret x -o yaml",
    "kubectl get Secret -A", "helm get values x", "aws secretsmanager get-secret-value --secret-id x",
    "terraform output -json", "terraform state pull", "gh auth token", "cat ~/.aws/credentials", "cat .env",
    "cat ~/.doppler/.doppler.yaml", "pbpaste", "aws --profile platform-admin s3 ls",
]
DESTRUCTIVE = [
    "rm -rf build", "git reset --hard HEAD~1", "git clean -fdx", "git push --force origin main",
    "git push origin main -f", "git push --force-with-lease origin main", "git filter-branch",
    "terraform destroy", "kubectl delete ns foo", "docker system prune -a", "docker volume rm v",
    "aws s3 rb s3://b", "sudo ls",
]
# (command, standard, strict): the profiles differ only in live read-only calls
PROFILE_SAMPLES = [
    ("terraform plan", "allow", "ask"), ("kubectl get pods -A", "allow", "ask"),
    ("terraform fmt -check", "allow", "allow"), ("git status", "allow", "allow"),
    ("terraform apply", "ask", "ask"), ("git push origin feat/x", "ask", "ask"),
    ("git push --force-with-lease origin feat/x", "ask", "ask"),
    ("aws sso login --sso-session seeds-agent --no-browser", "allow", "allow"),
    ("aws sso login", "deny", "deny"),
]

# Agent host, with the guard. fixture: the repo the command runs in (see check()).
# (command, fixture, gap): denied in Claude. opencode and omp have no guard, so they must not allow it
# either, except where gap is True (needs the guard: file contents, symlinks, current branch, spellings).
AGENT_HOST_SECRET = [
    ("doppler secrets -p x -c y", "clean", False), ("doppler secrets get X", "clean", False),
    ("doppler secrets --only-names get X", "clean", False),
    ("gh gist create values.yaml", "link", False), ("git diff --no-index values.yaml /dev/null", "link", True),
    ("git -c core.sshCommand='cat x' push origin feat/x", "clean", False),
    ("git config core.sshCommand 'sh x'", "clean", False), ("git config --global alias.x '!sh'", "clean", False),
    ("git push origin feat/x", "sshcmd", True), ("git status", "sshcmd", True),
    ("GIT_SSH_COMMAND=x git push origin feat/x", "clean", False),
    ("doppler run --only-secrets X -- python3 -c 'import os'", "clean", False),
    ("doppler run --only-secrets X -- bash -c 'echo $X'", "clean", False),
    ("aws s3 ls --endpoint-url https://x", "clean", True), ("kubectl get pods --kubeconfig ./k", "clean", False),
    ("docker run -v /home/ai:/h alpine ls", "clean", False),
]
AGENT_HOST_DESTRUCTIVE = [
    ("rm -Rf build", "clean", False), ("rm --recursive build", "clean", False),
    ("find . -name x | xargs rm -rf", "clean", False), ("git -C . reset --hard", "clean", False), ("git-in . reset --hard", "clean", False),
    ("git checkout .", "clean", False), ("git push origin :feat/x", "clean", False),
    ("git push origin --delete feat/x", "clean", False), ("git push origin +main", "clean", False),
    ("git push --mirror origin", "clean", False), ("git push -uf origin main", "clean", True),
    ("git push --force-with-lease", "onmain", True), ("git -C . push --force origin feat/x", "clean", False),
    ("git-in . push --force origin feat/x", "clean", False), ("git-in . push origin +main", "clean", False),
    ("git-in . push --force-with-lease origin main", "clean", False), ("git-in /etc status", "clean", True),
    ("git-in", "clean", True), ("git-in . push --mirror origin", "clean", False),
    ("git-in . -c core.sshCommand=x push origin feat/x", "clean", True),
    ("gh pr merge 3", "clean", False), ("gh -R o/r pr merge 3", "clean", False),
    ("gh repo delete x", "clean", False), ("gh repo archive x", "clean", False),
    ("gh release delete v1", "clean", False), ("gh api -X DELETE repos/x/y", "clean", False),
    ("gh api --method=delete repos/x/y", "clean", True), ("gh secret delete X", "clean", False),
    ("terraform apply", "clean", False), ("terraform apply -auto-approve", "clean", False),
    ("tofu destroy", "clean", False), ("doppler run --only-secrets X -- terraform apply", "clean", False),
    ("aws ec2 terminate-instances --instance-ids i", "clean", False), ("aws s3 cp s3://b/k .", "clean", False),
    ("aws ec2 stop-instances --instance-ids i", "clean", False), ("kubectl delete pod x", "clean", False),
    ("kubectl apply -f x.yaml", "clean", False), ("helm uninstall x", "clean", False),
    ("ansible-playbook site.yml", "clean", False), ("bash <<'EOF'\nrm -rf build\nEOF", "clean", False),
]
AGENT_HOST_NORMAL = [  # (command, fixture, opencode/omp decision): allowed in Claude
    ("git push -u origin feat/x", "clean", "allow"), ("git-in . push origin feat/x", "clean", "allow"),
    ("git-in . push --force-with-lease origin feat/x", "clean", "allow"),
    ("git-in . commit -m 'feat: x'", "clean", "allow"), ("git-in . branch feat/y origin/main", "clean", "allow"),
    ("git-in . -c user.name=x commit -m x", "clean", "allow"), ("git -C . status", "clean", "allow"),
    ("git -C . log --oneline -3", "clean", "allow"), ("git config --get credential.helper", "clean", "ask"),
    ("git push --force-with-lease origin feat/x", "clean", "allow"),
    ("git push --force-with-lease", "clean", "allow"), ("git commit -m 'feat: x'", "clean", "allow"),
    ("git branch feat/y origin/main", "clean", "allow"), ("git checkout -b feat/y", "clean", "allow"),
    ("git update-ref -d refs/tmp/x", "clean", "allow"), ("git pull --rebase --autostash", "clean", "allow"),
    ("git rebase origin/main", "clean", "allow"), ("git checkout -- a.txt", "clean", "allow"),
    ("git restore --staged a.txt", "clean", "allow"), ("git branch -d feat/x", "clean", "allow"),
    ("gh pr create --fill", "clean", "allow"), ("gh pr edit 3 --title x", "clean", "allow"),
    ("gh pr close 3", "clean", "allow"), ("gh pr reopen 3", "clean", "allow"),
    ("gh pr comment 3 --body x", "clean", "allow"), ("gh pr ready 3", "clean", "allow"),
    ("gh run rerun 123", "clean", "allow"), ("gh run cancel 123", "clean", "allow"),
    ("gh run watch 123", "clean", "allow"), ("gh issue create --title x --body y", "clean", "allow"),
    ("gh issue comment 1 --body x", "clean", "allow"), ("gh issue close 1", "clean", "allow"),
    ("gh api repos/x/y/pulls/3", "clean", "allow"),
    ("gh api -X PATCH repos/x/y/pulls/3 -f state=closed", "clean", "allow"),
    ("gh secret list", "clean", "allow"), ("gh secret set X --body y", "clean", "allow"),
    ("doppler secrets --only-names", "clean", "allow"), ("doppler secrets --only-names -p x -c y", "clean", "allow"),
    ("doppler projects", "clean", "allow"), ("pre-commit install", "clean", "allow"),
    ("pre-commit run --all-files", "clean", "allow"),
    ("herdr pane list", "clean", "allow"), ("herdr pane split", "clean", "allow"),
    ("herdr pane run 2 'make test && make lint > out.log'", "clean", "allow"),
    ("herdr pane close 2", "clean", "allow"),
    ("terraform plan -out=tfplan", "clean", "allow"), ("kubectl get pods -A", "clean", "allow"),
    ("npm test", "clean", "ask"), ("ls -la", "clean", "ask"), ("python3 -c 'print(1)'", "clean", "ask"),
    ("rm build.log", "clean", "ask"), ("git add -A && git commit -m 'rm -r mention'", "clean", "allow"),
    ("cat > f.py <<'EOF'\nx = 'git reset --hard'\nEOF", "clean", "ask"),
]
# Claude runs these sandboxed although their tool is excluded; the guard explains instead of an auth error
AGENT_HOST_EXPLAINED = [
    "git -C ../other push origin feat/x", "git -C . commit -m x", "git -c user.name=x commit -m x",
    "git --git-dir=x/.git push origin feat/x", "git-in . push origin feat/x && echo done",
    "cd x && git push", "gh pr list --json title | jq .", "gh pr create --title x --body 'a <b> c'",
    "gh pr create --title x --body 'uses `make`'", "terraform plan 2>&1",
]

# (path, decision) for Claude Read/Edit deny rules: "deny" or "ok" (not matched by any deny).
CLAUDE_PATH_SAMPLES = [
    ("/p/.env", "deny"), ("/p/.env.local", "deny"), ("/p/.env.example", "ok"), ("/p/key.pem", "deny"),
    ("/p/x.key", "deny"), ("/p/terraform.tfstate", "deny"), ("/p/main.tf", "ok"),
    ("/h/.doppler/.doppler.yaml", "deny"), ("/h/.aws/credentials", "deny"),
    ("/h/.aws/sso/cache/0a1b2c.json", "deny"), ("/h/.aws/cli/cache/x.json", "deny"), ("/h/.aws/config", "ok"),
    ("/h/.ssh/id_ed25519", "deny"), ("/h/.gnupg/private-keys-v1.d/x", "deny"), ("/h/.kube/config", "deny"),
    ("/h/.config/gh/hosts.yml", "deny"), ("/h/.git-credentials", "deny"), ("/h/.netrc", "deny"),
    ("/h/.zsh_history", "deny"), ("/etc/rancher/k3s/k3s.yaml", "deny"),
    ("/h/.claude/skills/x/SKILL.md", "ok"), ("/tmp/x", "ok"),
]
MACOS_PATH_SAMPLES = [
    ("/h/Library/Keychains/login.keychain-db", "deny"),
    ("/h/Library/Application Support/Google/Chrome/Default/Cookies", "deny"),
]
LINUX_PATH_SAMPLES = [
    ("/h/.local/share/keyrings/login.keyring", "deny"), ("/h/.mozilla/firefox/x/logins.json", "deny"),
    ("/h/.password-store/aws.gpg", "deny"), ("/etc/shadow", "deny"), ("/etc/os-release", "ok"),
]
OC_READ_SAMPLES = [
    ("/p/.env", "deny"), ("/p/.env.example", "allow"), ("/p/main.tf", "allow"), ("/h/.ssh/id_rsa", "deny"),
    ("/h/.doppler/.doppler.yaml", "deny"), ("/p/terraform.tfstate", "deny"), ("/proc/1234/environ", "deny"),
]


def load_claude(path):
    perms = json.loads(pathlib.Path(path).read_text())["permissions"]
    tiers = {}
    for tier in ("deny", "ask", "allow"):
        tiers[tier] = [re.fullmatch(r"Bash\((.*)\)", e, re.S).group(1)
                       for e in perms.get(tier, []) if e.startswith("Bash(")]
    return tiers


def load_opencode(path):
    return json.loads(pathlib.Path(path).read_text())["permission"]


def load_omp(path):
    pairs = re.findall(r'- match: "(.*)"\n\s+approval: (\w+)', pathlib.Path(path).read_text())
    return [(m, "ask" if a == "prompt" else a) for m, a in pairs]


def oc_decide(table, path, default):
    got = default
    for pat, tier in table.items():
        if glob_match(pat.replace("~", "/h", 1) if pat.startswith("~") else pat, path):
            got = tier
    return got


def check():
    import shutil
    import tempfile
    failures = total = 0

    def expect(label, want, got):
        nonlocal failures, total
        total += 1
        if want != got:
            failures += 1
            print("FAIL %s want %s got %s" % (label, want, got))

    def hook_denies(entry, payload):
        out = subprocess.run(["sh", "-c", entry["hooks"][0]["command"]], input=json.dumps(payload),
                             capture_output=True, text=True)
        if out.returncode or out.stderr:
            expect("[hook runs cleanly] %s" % str(payload)[:60], "", out.stderr)
        return '"permissionDecision": "deny"' in out.stdout

    # --- generation: every output file is current, parses, and keeps the sandbox safety switches ---
    host = claude_settings("standard", "linux", agent_host=True)
    expected = {claude_file(pr, o): dump(claude_settings(pr, o)) for pr in PROFILES for o in OSES}
    for pr in PROFILES:
        expected[HERE / pr / "opencode.json"] = dump(opencode_config(pr))
        expected[HERE / pr / "omp-config.yml"] = omp_config(pr)
    expected[HERE / "agent-host" / "opencode.json"] = dump(opencode_config("standard", agent_host=True))
    expected[HERE / "agent-host" / "omp-config.yml"] = omp_config("standard", agent_host=True)
    for path, text in expected.items():
        expect("[generated] %s is current (run generate.py)" % path.relative_to(HERE), text, path.read_text())
    for name, st in [("%s/%s" % (pr, o), json.loads(claude_file(pr, o).read_text())) for pr in PROFILES for o in OSES] \
            + [("agent-host", host)]:
        sb = st["sandbox"]
        expect("[%s] sandbox on, fails closed, keeps prompts" % name, (True, True, False),
               (sb["enabled"], sb["failIfUnavailable"], sb["autoAllowBashIfSandboxed"]))
        expect("[%s] no secret store re-opened to the sandbox" % name, [], sb["filesystem"]["allowRead"])
        expect("[%s] attribution off" % name, {"commit": "", "pr": ""}, st.get("attribution"))
        expect("[%s] attribution hook" % name, True, ATTRIBUTION_HOOK in st["hooks"]["PreToolUse"])
    expect("[agent-host] nothing prompts", [], host["permissions"]["ask"])
    expect("[agent-host] default allow", True, "Bash(*)" in host["permissions"]["allow"])
    expect("[agent-host] no unsandboxed retry", False, host["sandbox"]["allowUnsandboxedCommands"])
    expect("[agent-host] repo settings cannot add rules", True, host["allowManagedPermissionRulesOnly"])
    excluded = host["sandbox"]["excludedCommands"]
    for tool in ("git *", "gh *", "git-in *", "herdr *", "pre-commit *", "terraform *", "aws *", "doppler *", "kubectl *"):
        expect("[agent-host] %s runs outside the sandbox" % tool, True, tool in excluded)
    expect("[agent-host] no mid-pattern exclusions (they never match)", [], [e for e in excluded if "*" in e[:-1]])
    expect("[agent-host] ~/REPOS writable", True, "~/REPOS" in host["sandbox"]["filesystem"]["allowWrite"])
    expect("[agent-host] the guard is installed", True,
           "Agent-host guard" in host["hooks"]["PreToolUse"][-1]["hooks"][0]["command"])
    try:
        claude_settings("standard", "linux", sandbox=False, agent_host=True)
        refused = False
    except SystemExit:
        refused = True
    expect("[agent-host] refuses --no-sandbox", True, refused)
    with tempfile.TemporaryDirectory() as tmp:
        with contextlib.redirect_stdout(io.StringIO()):
            install(tmp, "standard", "linux")
            pathlib.Path(tmp, ".claude/settings.json").write_text("{}")
            install(tmp, "standard", "linux")
        expect("[install] writes all three, keeps existing files", ["{}", True, True],
               [pathlib.Path(tmp, ".claude/settings.json").read_text(), pathlib.Path(tmp, "opencode.json").exists(),
                pathlib.Path(tmp, ".omp/config.yml").exists()])

    # --- 1. secret stores unreadable (Claude folds Read denies into the sandbox read-deny) ---
    for os_name, extra in (("macos", MACOS_PATH_SAMPLES), ("linux", LINUX_PATH_SAMPLES)):
        for name, st in (("standard", json.loads(claude_file("standard", os_name).read_text())),
                         ("agent-host", claude_settings("standard", os_name, agent_host=True))):
            deny = [re.fullmatch(r"Read\((.*)\)", e).group(1) for e in st["permissions"]["deny"] if e.startswith("Read(")]
            for path, want in CLAUDE_PATH_SAMPLES + extra:
                expect("[%s %s Read] %s" % (name, os_name, path), want,
                       "deny" if any(gi_match(p, path) for p in deny) else "ok")
    oc = load_opencode(HERE / "agent-host/opencode.json")
    for path, want in OC_READ_SAMPLES:
        expect("[opencode read] " + path, want, oc_decide(oc["read"], path, "allow"))
    lin = [e for e in json.loads(claude_file("standard", "linux").read_text())["permissions"]["deny"] if e.startswith("Read(")]
    expect("[linux] no /proc Read rule (it breaks bubblewrap); the hook covers it", False, any("/proc/" in e for e in lin))
    for tool_input, blocked in (({"file_path": "/proc/1/environ"}, True), ({"file_path": "/proc/cpuinfo"}, False)):
        expect("[proc hook] %s" % tool_input, blocked, hook_denies(PROC_READ_HOOK, {"tool_input": tool_input}))

    # --- 2 and 3: commands, standard and strict (interactive: unlisted commands prompt) ---
    for idx, profile in enumerate(PROFILES):
        tiers = load_claude(claude_file(profile, "linux"))
        oc_rules = list(load_opencode(HERE / profile / "opencode.json")["bash"].items())
        omp_rules = load_omp(HERE / profile / "omp-config.yml")
        samples = [(c, "deny", "deny") for c in SECRET_PRINTING + DESTRUCTIVE] + PROFILE_SAMPLES
        for cmd, *want in samples:
            for agent, got in (("claude", decide_claude(cmd, tiers["deny"], tiers["ask"], tiers["allow"])),
                               ("opencode", decide_ordered(cmd, oc_rules, True)),
                               ("omp", decide_ordered(cmd, omp_rules, False))):
                expect("[%s/%s] %s" % (profile, agent, cmd), want[idx], got)

    # --- 2 and 3: commands, agent host (Claude: rules + guard hook, run on real git repos) ---
    tiers = {t: [re.fullmatch(r"Bash\((.*)\)", e, re.S).group(1) for e in host["permissions"][t] if e.startswith("Bash(")]
             for t in ("deny", "ask", "allow")}
    # the installed guard allows git-in only under ~/REPOS; the tests build one whose repo root is a temp dir
    expect("[agent-host] guard embeds ~/REPOS as the git-in root", True, "REPO_ROOTS = ['~/REPOS']" in
           shlex.split(host["hooks"]["PreToolUse"][-1]["hooks"][0]["command"])[2])
    root = pathlib.Path(tempfile.mkdtemp(prefix="guard-root-"))
    made = [root]
    guard = agent_host_guard_hook("linux", [str(root)])

    def repo(name, branch="feat/x", cfg=(), link=None):
        d = pathlib.Path(tempfile.mkdtemp(prefix="guard-%s-" % name, dir=root))
        subprocess.run(["git", "init", "-q", "-b", branch, str(d)], check=True)
        for k, v in cfg:
            subprocess.run(["git", "-C", str(d), "config", k, v], check=True)
        if link:
            (d / "values.yaml").symlink_to(os.path.expanduser(link))
        return str(d)
    fixtures = {"clean": repo("clean"), "onmain": repo("onmain", branch="main"),
                "sshcmd": repo("sshcmd", cfg=[("core.sshCommand", "sh -c x")]),
                "link": repo("link", link="~/.doppler/.doppler.yaml")}

    def claude_host(cmd, where):
        if hook_denies(guard, {"tool_input": {"command": cmd}, "cwd": fixtures[where]}):
            return "deny"
        return decide_claude(cmd, tiers["deny"], tiers["ask"], tiers["allow"])
    oc_rules = list(load_opencode(HERE / "agent-host/opencode.json")["bash"].items())
    omp_rules = load_omp(HERE / "agent-host/omp-config.yml")
    expect("[agent-host opencode] unlisted commands prompt", "ask", dict(oc_rules)["*"])
    for cmd in SECRET_PRINTING + DESTRUCTIVE:
        expect("[agent-host claude] %s" % cmd, "deny", claude_host(cmd, "clean"))
    for cmd, where, gap in AGENT_HOST_SECRET + AGENT_HOST_DESTRUCTIVE:
        expect("[agent-host claude] %s (%s)" % (cmd, where), "deny", claude_host(cmd, where))
        if not gap:
            for agent, rules, last in (("opencode", oc_rules, True), ("omp", omp_rules, False)):
                expect("[agent-host %s] %s is not allowed" % (agent, cmd), True,
                       decide_ordered(cmd, rules, last) != "allow")
    for cmd in SECRET_PRINTING + DESTRUCTIVE:
        for agent, rules, last in (("opencode", oc_rules, True), ("omp", omp_rules, False)):
            expect("[agent-host %s] %s is not allowed" % (agent, cmd), True, decide_ordered(cmd, rules, last) != "allow")
    for cmd, where, oc_want in AGENT_HOST_NORMAL:
        expect("[agent-host claude] %s" % cmd, "allow", claude_host(cmd, where))
        expect("[agent-host opencode] %s" % cmd, oc_want, decide_ordered(cmd, oc_rules, True))
        expect("[agent-host omp] %s" % cmd, oc_want, decide_ordered(cmd, omp_rules, False))
    for cmd in AGENT_HOST_EXPLAINED:
        expect("[agent-host guard explains] %s" % cmd, True,
               hook_denies(guard, {"tool_input": {"command": cmd}, "cwd": fixtures["clean"]}))
    for d in made:
        shutil.rmtree(d)

    # --- hooks that every Claude file carries ---
    sso = json.loads(claude_file("standard", "linux").read_text())["hooks"]["PreToolUse"][0]
    for cmd, blocked in (("aws sso login --sso-session seeds-agent", True),
                         ("aws sso login --sso-session seeds-agent --no-browser", False), ("ls -la", False)):
        expect("[sso hook] %s" % cmd, blocked, hook_denies(sso, {"tool_input": {"command": cmd}}))
    gen = "Generated with " + "[Claude Code](https://claude.com/claude-code)"
    for cmd, blocked in (("git commit -m 'feat: x' -m '" + gen + "'", True),
                         ("gh pr create --title x --body 'Co-Authored-By: " + "Claude <noreply@anthropic.com>'", True),
                         ("git commit -m 'feat: add login'", False), ("git log --grep=Claude", False)):
        expect("[attribution hook] %s" % cmd[:50], blocked, hook_denies(ATTRIBUTION_HOOK, {"tool_input": {"command": cmd}}))

    print("%d checks, %d failures" % (total, failures))
    return 1 if failures else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--claude-out", help="also write one Claude settings file to this path")
    ap.add_argument("--profile", choices=PROFILES, default="standard",
                    help="profile for --claude-out (default: standard)")
    ap.add_argument("--os", choices=OSES, default=HOST_OS, dest="os_name",
                    help="OS for --claude-out (default: this host, %s)" % HOST_OS)
    ap.add_argument("--extra-claude-deny", action="append", default=[], metavar="RULE",
                    help="extra raw Claude deny rule for --claude-out, e.g. mcp__someserver")
    ap.add_argument("--install", metavar="PROJECT_DIR",
                    help="write .claude/settings.json, opencode.json and .omp/config.yml into a project")
    ap.add_argument("--no-sandbox", action="store_true",
                    help="omit the Claude sandbox block (fallback if the sandbox will not start)")
    ap.add_argument("--force", action="store_true", help="with --install: overwrite existing files")
    ap.add_argument("--agent-host", action="store_true",
                    help="with --claude-out/--install: machine used only by agents (push + PRs, ~/REPOS writable)")
    ap.add_argument("--mcpjson-server", action="append", default=[], metavar="NAME",
                    help="with --claude-out: enable this project .mcp.json server (enabledMcpjsonServers)")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    if args.check:
        return check()
    if args.install:
        install(args.install, args.profile, args.os_name, not args.no_sandbox, args.force,
                args.extra_claude_deny, args.agent_host)
        return 0
    pull_upstream()
    for profile in PROFILES:
        for os_name in OSES:
            write(claude_file(profile, os_name), dump(claude_settings(profile, os_name)))
        write(HERE / profile / "opencode.json", dump(opencode_config(profile)))
        write(HERE / profile / "omp-config.yml", omp_config(profile))
    # the agent host's opencode and omp files (its Claude file is written by regen-agent-host.sh)
    write(HERE / "agent-host" / "opencode.json", dump(opencode_config("standard", agent_host=True)))
    write(HERE / "agent-host" / "omp-config.yml", omp_config("standard", agent_host=True))
    if args.claude_out:
        write(args.claude_out,
              dump(claude_settings(args.profile, args.os_name, args.extra_claude_deny,
                                   not args.no_sandbox, args.agent_host, args.mcpjson_server)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
