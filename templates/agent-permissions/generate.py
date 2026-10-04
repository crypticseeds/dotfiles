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
import json
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
    "/proc/*/environ", "/proc/*/cmdline", "/proc/*/mem",
    "/mnt/hgfs/**",                          # VMware Fusion shared folders = the Mac's files
]

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
# That also hides the stores some tools legitimately need, so re-open exactly those. Deliberately
# NOT listed: ~/.aws. The SSO token cache lives in ~/.aws/sso/cache, and the admin and agent SSO
# sessions both cache there, so a sandboxed process able to read it could read the admin token.
# Sandboxed commands therefore cannot use AWS credentials, and on macOS doppler's Keychain token
# is blocked too: those tools run OUTSIDE the sandbox instead (see SANDBOX_EXCLUDED).
# `~/.doppler` is re-allowed for Linux, where the token is a plain file.
SANDBOX_ALLOW_READ = [
    "~/.doppler", "~/.kube", "~/.docker", "~/.config/gh", "~/.ssh",
    "~/.netrc", "~/.git-credentials", "~/.npmrc",
]
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
SANDBOX_EXCLUDED = ["docker *", "podman *", "terraform *", "tofu *", "aws *", "doppler *"]

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
    "kubectl get *secret*", "kubectl describe *secret*", "kubectl config view *--raw*",
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
    "git reset --hard", "git clean -f", "git branch -D", "git push --force*",
    "git push -f*", "git push *--force*", "git push *-f", "git filter-branch",
    "git filter-repo",
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
SSO_LOGIN_HOOK = {
    "matcher": "Bash",
    "hooks": [{
        "type": "command",
        "if": "Bash(*aws sso login*)",   # only spawn for login commands
        "command": "python3 -c " + shlex.quote(_HOOK_CODE),
        "timeout": 10,
    }],
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
    "gh pr view", "gh pr list", "gh pr status", "gh pr checks", "gh issue view",
    "gh issue list", "gh run view", "gh run list", "gh repo view",
]

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


def bash_rules(profile):
    deny_src, ask_src = twins(DENY_BASH), twins(ASK_BASH)
    deny = deny_src + wrap(deny_src, allow=False)
    ask = ask_src + wrap(ask_src, allow=False)
    allow = twins(ALLOW_OFFLINE) + ALLOW_SSO_LOGIN
    if profile == "standard":
        live = twins(ALLOW_LIVE)
        allow += live + wrap(live, allow=True)
    rules = {
        "deny": expand_all(deny) + PATH_MENTIONS,
        "ask": expand_all(ask),
        "allow": expand_all(allow),
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


def claude_settings(profile, os_name, extra_deny=(), sandbox=True):
    r = bash_rules(profile)
    paths = claude_secret_paths(os_name)
    tmp = TMP_DIRS_BY_OS[os_name]
    deny = ["Read(%s)" % p for p in paths] + ["Edit(%s)" % p for p in paths]
    deny += ["Bash(%s)" % p for p in r["deny"]] + list(extra_deny)
    allow = ["Bash(%s)" % p for p in r["allow"]]
    allow += ["Read(%s)" % p for p in SKILL_DIRS + LOCAL_SKILL_DIRS]
    for d in tmp:
        allow += ["Read(%s/**)" % abs_claude(d), "Edit(%s/**)" % abs_claude(d)]
    settings = {
        "$schema": "https://json.schemastore.org/claude-code-settings.json",
        "permissions": {
            "allow": uniq(allow),
            "ask": ["Bash(%s)" % p for p in r["ask"]],
            "deny": uniq(deny),
        },
        "hooks": {"PreToolUse": [SSO_LOGIN_HOOK]},
        "sandbox": {
            "enabled": True,
            # Linux needs bubblewrap + socat. Without this, a missing dependency means a warning
            # and commands running UNSANDBOXED, which silently removes the write boundary.
            "failIfUnavailable": True,
            # keep the prompts above in force instead of auto-approving sandboxed commands
            "autoAllowBashIfSandboxed": False,
            "filesystem": {"allowWrite": tmp, "allowRead": SANDBOX_ALLOW_READ},
            "network": {"allowedDomains": ALLOWED_DOMAINS},
            "excludedCommands": SANDBOX_EXCLUDED,
        },
    }
    if not sandbox:
        del settings["sandbox"]
    return settings


def oc_path(p):
    """Claude/gitignore style path glob -> opencode's plain `*` glob."""
    if p.startswith("**/"):
        p = "*" + p[3:]
    return p.replace("**", "*")


def opencode_config(profile):
    r = bash_rules(profile)
    bash = {"*": "ask"}
    for tier in ("allow", "ask", "deny"):  # last match wins
        for p in r[tier]:
            bash[p] = tier
    # opencode is OS-independent: deny both OSes' paths (globs for absent paths are harmless)
    secret = uniq(oc_path(p) for p in (
        SECRET_PATHS_HOME + SECRET_PATHS_HOME_MACOS + SECRET_PATHS_HOME_LINUX
        + SECRET_PATHS_ABS + SECRET_PATHS_ABS_LINUX + SECRET_PATHS_ANY))
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
    external.update({p: "deny" for p in secret if p.startswith(("~/", "/"))})
    return {
        "$schema": "https://opencode.ai/config.json",
        "permission": {
            "bash": bash, "read": read, "edit": edit, "external_directory": external,
        },
    }


def omp_config(profile):
    r = bash_rules(profile)
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
    for tier, name in (("deny", "deny"), ("ask", "prompt"), ("allow", "allow")):
        lines.append("    # --- %s ---" % name)
        for p in r[tier]:
            lines.append('    - match: "%s"' % p)
            lines.append("      approval: %s" % name)
    return "\n".join(lines) + "\n"


def write(path, text):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    print("wrote", path)


def dump(obj):
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def claude_file(profile, os_name):
    return HERE / profile / ("claude-settings.%s.json" % os_name)


def install(project, profile, os_name, sandbox=True, force=False, extra_deny=()):
    """Drop the files for this host into a project. Existing files are left alone unless force."""
    project = pathlib.Path(project)
    files = {
        project / ".claude" / "settings.json":
            dump(claude_settings(profile, os_name, extra_deny, sandbox)),
        project / "opencode.json": dump(opencode_config(profile)),
        project / ".omp" / "config.yml": omp_config(profile),
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


# (command, standard decision, strict decision)
SAMPLES = [
    ("env", "deny", "deny"), ("printenv HOME", "deny", "deny"), ("set", "deny", "deny"),
    ("history", "deny", "deny"), ("security find-generic-password -s x", "deny", "deny"),
    ("pbpaste", "deny", "deny"), ("sudo ls", "deny", "deny"), ("rm -rf build", "deny", "deny"),
    ("bash", "deny", "deny"), ("bash -c 'echo hi'", "ask", "ask"),
    ("cat .env", "deny", "deny"), ("cat .env.example", "deny", "deny"),
    ("cat ~/.aws/credentials", "deny", "deny"), ("grep -r x terraform.tfstate", "deny", "deny"),
    ("cat /etc/rancher/k3s/k3s.yaml", "deny", "deny"),
    ("ls -la", "ask", "ask"),
    ("doppler secrets get X --plain", "deny", "deny"), ("doppler secrets", "deny", "deny"),
    ("doppler configure get token", "deny", "deny"),
    ("doppler run --only-secrets X -- env", "deny", "deny"),
    ("doppler run --only-secrets X -- terraform plan", "allow", "ask"),
    ("doppler run -p a -c b -- terraform plan", "ask", "ask"),
    ("doppler run --only-secrets X -- terraform apply", "ask", "ask"),
    ("doppler run --only-secrets X -- terraform destroy", "deny", "deny"),
    ("doppler run --only-secrets X -- kubectl get secrets -A", "deny", "deny"),
    ("terraform fmt -check", "allow", "allow"), ("terraform validate", "allow", "allow"),
    ("terraform init -backend=false", "allow", "allow"), ("terraform init", "allow", "ask"),
    ("terraform init -migrate-state", "ask", "ask"),
    ("terraform plan", "allow", "ask"), ("terraform plan -out=tfplan", "allow", "ask"),
    ("terraform apply", "ask", "ask"), ("terraform destroy", "deny", "deny"),
    ("terraform apply -destroy", "deny", "deny"), ("terraform output", "ask", "ask"),
    ("terraform output -json", "deny", "deny"), ("terraform state pull", "deny", "deny"),
    ("terraform state list", "allow", "ask"), ("terraform show", "ask", "ask"),
    ("tofu plan", "allow", "ask"), ("tofu destroy", "deny", "deny"),
    ("aws sts get-caller-identity", "allow", "ask"), ("aws ec2 describe-instances", "allow", "ask"),
    ("aws lambda list-functions", "ask", "ask"), ("aws iam list-users", "allow", "ask"),
    ("aws secretsmanager get-secret-value --secret-id x", "deny", "deny"),
    ("aws ssm get-parameter --name x --with-decryption", "deny", "deny"),
    ("aws ssm get-parameters-by-path --path /", "deny", "deny"),
    ("aws sts assume-role --role-arn r --role-session-name s", "deny", "deny"),
    ("aws s3 rb s3://b", "deny", "deny"), ("aws s3 rm s3://b/k", "ask", "ask"),
    ("aws iam delete-user --user-name x", "deny", "deny"),
    ("aws ec2 delete-volume --volume-id v", "ask", "ask"),
    ("aws eks update-kubeconfig --name c", "ask", "ask"),
    ("aws configure list", "ask", "ask"), ("aws configure get aws_secret_access_key", "deny", "deny"),
    ("kubectl get pods -A", "allow", "ask"), ("kubectl get secrets -A", "deny", "deny"),
    ("kubectl describe secret x", "deny", "deny"), ("kubectl delete ns foo", "deny", "deny"),
    ("kubectl delete pod x", "ask", "ask"), ("kubectl apply -f x.yaml", "ask", "ask"),
    ("kubectl config view --raw", "deny", "deny"), ("kubectl exec -it p -- sh", "ask", "ask"),
    ("helm lint .", "allow", "allow"), ("helm template x .", "allow", "allow"),
    ("helm list -A", "allow", "ask"), ("helm get values x", "deny", "deny"),
    ("helm upgrade --install x .", "ask", "ask"),
    ("git status", "allow", "allow"), ("git diff --staged", "allow", "allow"),
    ("git push origin main", "ask", "ask"), ("git push --force origin main", "deny", "deny"),
    ("git push origin main -f", "deny", "deny"), ("git reset --hard HEAD~1", "deny", "deny"),
    ("gitleaks detect --redact", "allow", "allow"), ("gitleaks detect", "ask", "ask"),
    ("ansible-playbook site.yml --check", "allow", "allow"), ("ansible-playbook site.yml", "ask", "ask"),
    ("ansible-playbook site.yml --check -vvv", "deny", "deny"),
    ("ansible-vault view group_vars/all/vault.yml", "deny", "deny"),
    ("ansible-lint", "allow", "allow"),
    # the human's admin profile is off limits; the agent's read-only profile is not
    ("aws --profile admin s3 ls", "deny", "deny"),
    ("aws s3 ls --profile=PlatformAdmin", "deny", "deny"),
    ("aws sso login --profile platform-admin", "deny", "deny"),
    ("aws sso login --sso-session admin-session", "deny", "deny"),
    ("AWS_PROFILE=admin terraform plan", "deny", "deny"),
    ("doppler run --only-secrets X -- aws --profile admin sts get-caller-identity", "deny", "deny"),
    ("aws sso login --sso-session seeds-admin", "deny", "deny"),
    ("aws sso login --sso-session=seeds-admin", "deny", "deny"),
    # SSO login: only the --no-browser forms are allowed; the regular forms are denied
    ("aws sso login", "deny", "deny"),
    ("aws sso login --sso-session seeds-agent", "deny", "deny"),
    ("aws sso login --sso-session=seeds-agent", "deny", "deny"),
    ("aws sso login --profile agent-readonly", "deny", "deny"),
    ("aws sso login --sso-session seeds-agent --no-browser", "allow", "allow"),
    ("aws sso login --no-browser --sso-session seeds-agent", "allow", "allow"),
    ("aws sso login --profile agent-readonly --no-browser", "allow", "allow"),
    ("aws sso login --sso-session seeds-admin --no-browser", "deny", "deny"),
    ("aws sso login --profile platform-admin --no-browser", "deny", "deny"),
    ("aws sso login --no-browser --sso-session=seeds-admin", "deny", "deny"),
    ("aws sso login --sso-session seeds-agent --use-device-code", "ask", "ask"),
    ("aws sso logout --sso-session seeds-admin", "deny", "deny"),
    ("aws --profile platform-admin sts get-caller-identity", "deny", "deny"),
    ("aws sts get-caller-identity --profile platform-admin", "deny", "deny"),
    ("AWS_PROFILE=platform-admin terraform plan", "deny", "deny"),
    ("aws --profile agent-readonly sts get-caller-identity", "allow", "ask"),
    ("aws --profile agent-readonly s3 ls", "allow", "ask"),
    ("aws --profile agent-readonly --region eu-west-2 ec2 describe-instances", "allow", "ask"),
    # Linux / Fedora: privilege escalation alternatives to sudo
    ("su -", "deny", "deny"), ("doas ls", "deny", "deny"), ("pkexec bash", "deny", "deny"),
    ("run0 ls", "deny", "deny"), ("setenforce 0", "deny", "deny"), ("visudo", "deny", "deny"),
    # Linux / Fedora: podman is docker, k3s bundles kubectl; neither may bypass the rules
    ("podman inspect c", "deny", "deny"), ("podman exec c env", "deny", "deny"),
    ("podman system prune -a", "deny", "deny"), ("podman rm -f c", "deny", "deny"),
    ("podman ps", "allow", "allow"), ("podman login quay.io", "ask", "ask"),
    ("podman secret inspect x --showsecret", "deny", "deny"),
    ("k3s kubectl get secrets -A", "deny", "deny"), ("k3s kubectl get pods -A", "allow", "ask"),
    ("k3s kubectl delete ns foo", "deny", "deny"), ("k3s kubectl apply -f x.yaml", "ask", "ask"),
    ("k3s token create", "deny", "deny"), ("k3s etcd-snapshot save", "ask", "ask"),
    ("doppler run --only-secrets X -- k3s kubectl get secrets", "deny", "deny"),
    # Linux / Fedora: credential stores and secrets
    ("nmcli connection show --show-secrets home", "deny", "deny"),
    ("nmcli -s connection show home", "deny", "deny"),
    ("wg showconf wg0", "deny", "deny"), ("keyctl read 12345", "deny", "deny"),
    ("systemd-creds decrypt x.cred", "deny", "deny"),
    ("gdbus call --session --dest org.freedesktop.secrets --object-path / --method x.y", "deny", "deny"),
    ("secret-tool lookup service x", "deny", "deny"),
    ("cat /proc/1/environ", "deny", "deny"), ("cat /etc/shadow", "deny", "deny"),
    ("cat /etc/NetworkManager/system-connections/home.nmconnection", "deny", "deny"),
    ("ls ~/.mozilla/firefox", "deny", "deny"), ("ls /mnt/hgfs", "deny", "deny"),
    ("journalctl -u sshd", "ask", "ask"), ("firewall-cmd --reload", "ask", "ask"),
]

# (path, decision) for Claude Read/Edit deny rules: "deny" or "ok" (not matched by any deny).
CLAUDE_PATH_SAMPLES = [
    ("/p/.env", "deny"), ("/p/.env.local", "deny"), ("/p/.env.production", "deny"),
    ("/p/.env.extra", "deny"), ("/p/.env.exampl", "deny"), ("/p/.env.e", "deny"),
    ("/p/.env.example.bak", "deny"), ("/p/.env.examples", "deny"), ("/p/.env.Example", "ok"),
    ("/p/.ENV.LOCAL", "deny"),
    ("/p/.env.example", "ok"), ("/p/app/.env.example", "ok"),
    ("/p/terraform.tfstate", "deny"), ("/p/.terraform/terraform.tfstate", "deny"),
    ("/p/main.tf", "ok"), ("/p/terraform.tfvars", "ok"), ("/p/key.pem", "deny"),
    ("/h/.ssh/id_rsa", "deny"), ("/h/.aws/credentials", "deny"),
    ("/h/.aws/sso/cache/0a1b2c.json", "deny"), ("/h/.aws/cli/cache/x.json", "deny"),
    ("/h/.aws/config", "ok"),
    ("/etc/rancher/k3s/k3s.yaml", "deny"), ("/etc/rancher/k3s/config.yaml", "deny"),
    ("/var/lib/rancher/k3s/server/node-token", "deny"),
    ("/h/.claude/skills/x/SKILL.md", "ok"), ("/tmp/x", "ok"),
]
MACOS_PATH_SAMPLES = [
    ("/h/Library/Keychains/login.keychain-db", "deny"), ("/h/Library/Messages/chat.db", "deny"),
    ("/h/Library/Application Support/Google/Chrome/Default/Cookies", "deny"),
    ("/private/tmp/x", "ok"),
]
LINUX_PATH_SAMPLES = [
    ("/h/.local/share/keyrings/login.keyring", "deny"),
    ("/h/.mozilla/firefox/abc.default/logins.json", "deny"),
    ("/h/.config/google-chrome/Default/Login Data", "deny"),
    ("/h/.config/chromium/Default/Cookies", "deny"), ("/h/.thunderbird/x/prefs.js", "deny"),
    ("/h/.password-store/work/aws.gpg", "deny"), ("/h/.var/app/org.mozilla.firefox/x", "deny"),
    ("/h/.python_history", "deny"),
    ("/etc/shadow", "deny"), ("/etc/sudoers.d/90-x", "deny"), ("/etc/ssh/ssh_host_ed25519_key", "deny"),
    ("/etc/NetworkManager/system-connections/home.nmconnection", "deny"),
    ("/etc/pki/tls/private/server.key", "deny"), ("/etc/wireguard/wg0.conf", "deny"),
    ("/etc/kubernetes/admin.conf", "deny"), ("/proc/1234/environ", "deny"),
    ("/mnt/hgfs/Documents/notes.txt", "deny"),
    ("/etc/os-release", "ok"), ("/etc/hosts", "ok"), ("/etc/ssh/ssh_config", "ok"),
    ("/proc/cpuinfo", "ok"), ("/h/.config/nvim/init.lua", "ok"),
]

# (path, decision) for opencode, last matching rule wins, default "ask" outside the project.
OC_EXTERNAL_SAMPLES = [
    ("/tmp/x", "allow"), ("/private/tmp/y", "allow"), ("/h/.claude/skills/a/SKILL.md", "allow"),
    ("/h/.agents/skills/a/SKILL.md", "allow"), ("/h/Documents/notes.md", "ask"),
    ("/h/.ssh/id_rsa", "deny"), ("/etc/rancher/k3s/k3s.yaml", "deny"), ("/h/.aws/credentials", "deny"),
    ("/etc/shadow", "deny"), ("/h/.mozilla/firefox/x/logins.json", "deny"),
]
OC_EDIT_SAMPLES = [
    ("/p/.env", "deny"), ("/p/.env.example", "allow"), ("/p/main.tf", "allow"),
    ("/h/.claude/skills/a/SKILL.md", "deny"), ("/tmp/x", "allow"),
]
OC_READ_SAMPLES = [
    ("/p/.env", "deny"), ("/p/.env.example", "allow"), ("/p/main.tf", "allow"),
    ("/h/.ssh/id_rsa", "deny"), ("/p/terraform.tfstate", "deny"),
    ("/p/.terraform/terraform.tfstate", "deny"), ("/p/secrets.pem", "deny"),
    ("/etc/rancher/k3s/k3s.yaml", "deny"), ("/etc/shadow", "deny"), ("/proc/1234/environ", "deny"),
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
    failures = total = 0

    def expect(label, want, got):
        nonlocal failures, total
        total += 1
        if want != got:
            failures += 1
            print("FAIL %s want %s got %s" % (label, want, got))

    for idx, profile in enumerate(PROFILES):
        oc = list(load_opencode(HERE / profile / "opencode.json")["bash"].items())
        omp = load_omp(HERE / profile / "omp-config.yml")
        for os_name in OSES:  # the command rules must behave the same in every Claude variant
            tiers = load_claude(claude_file(profile, os_name))
            for cmd, *want in SAMPLES:
                expect("[%s/claude-%s] %s" % (profile, os_name, cmd), want[idx],
                       decide_claude(cmd, tiers["deny"], tiers["ask"], tiers["allow"]))
        for cmd, *want in SAMPLES:
            expect("[%s/opencode] %s" % (profile, cmd), want[idx], decide_ordered(cmd, oc, True))
            expect("[%s/omp] %s" % (profile, cmd), want[idx], decide_ordered(cmd, omp, False))

    # Claude Read and Edit path rules (approximate gitignore matching), per OS
    for os_name, extra in (("macos", MACOS_PATH_SAMPLES), ("linux", LINUX_PATH_SAMPLES)):
        settings = json.loads(claude_file("standard", os_name).read_text())
        perms = settings["permissions"]
        for tool in ("Read", "Edit"):
            deny = [re.fullmatch(tool + r"\((.*)\)", e).group(1) for e in perms["deny"] if e.startswith(tool + "(")]
            for path, want in CLAUDE_PATH_SAMPLES + extra:
                got = "deny" if any(gi_match(p, path) for p in deny) else "ok"
                expect("[claude-%s %s] %s" % (os_name, tool, path), want, got)
        sb = settings["sandbox"]
        expect("[%s] sandbox enabled" % os_name, True, sb["enabled"])
        expect("[%s] sandbox fails closed" % os_name, True, sb["failIfUnavailable"])
        expect("[%s] sandbox keeps prompts" % os_name, False, sb["autoAllowBashIfSandboxed"])
        expect("[%s] write boundary is tmp only" % os_name, sorted(TMP_DIRS_BY_OS[os_name]),
               sorted(sb["filesystem"]["allowWrite"]))
        expect("[%s] ~/.aws not re-opened to the sandbox" % os_name, False,
               any(p.startswith("~/.aws") for p in sb["filesystem"]["allowRead"]))
        for tool in ("terraform *", "aws *", "doppler *"):
            expect("[%s] %s runs outside the sandbox" % (os_name, tool), True, tool in sb["excludedCommands"])
        # the SSO login hook: run the real script on sample commands
        hook = settings["hooks"]["PreToolUse"][0]["hooks"][0]
        for cmd, blocked in (
                ("aws sso login", True), ("aws sso login --sso-session seeds-agent", True),
                ("aws sso login --profile agent-readonly --use-device-code", True),
                ("doppler run -- aws sso login --sso-session seeds-agent", True),
                ("aws sso login --sso-session seeds-agent --no-browser", False),
                ("aws sso login --no-browser", False),
                # unrelated commands must never be touched, including ones Claude cannot parse
                ("ls -la", False), ("terraform plan", False), ("aws sts get-caller-identity", False),
                ("for k in a b; do printf '%s' \"$k\"; jq -r . x.json; done", False),
                ("git commit -m 'document aws login handling'", False)):
            out = subprocess.run(["sh", "-c", hook["command"]], input=json.dumps({"tool_input": {"command": cmd}}),
                                 capture_output=True, text=True).stdout
            expect("[%s hook] %s" % (os_name, cmd), blocked, '"permissionDecision": "deny"' in out)
            if blocked:
                expect("[%s hook] tells the agent to use --no-browser" % os_name, True, "--no-browser" in out)
    # OS-specific paths must not leak into the other OS's file (absent paths can break sandbox setup)
    def path_rules(os_name):  # Read/Edit rules only; the shell-command patterns are shared by design
        deny = json.loads(claude_file("standard", os_name).read_text())["permissions"]["deny"]
        return [e for e in deny if e.startswith(("Read(", "Edit("))]
    mac, lin = path_rules("macos"), path_rules("linux")
    expect("macOS file has no Linux-only paths", False, any("keyrings" in e or "/proc/" in e for e in mac))
    expect("Linux file has no macOS-only paths", False, any("Library/" in e for e in lin))

    # opencode path rules
    oc = load_opencode(HERE / "standard/opencode.json")
    for path, want in OC_READ_SAMPLES:
        expect("[opencode read] " + path, want, oc_decide(oc["read"], path, "allow"))
    for path, want in OC_EDIT_SAMPLES:
        expect("[opencode edit] " + path, want, oc_decide(oc["edit"], path, "allow"))
    for path, want in OC_EXTERNAL_SAMPLES:
        expect("[opencode external] " + path, want, oc_decide(oc["external_directory"], path, "ask"))

    # --install: writes the right files, never clobbers, --no-sandbox drops only the sandbox block
    import contextlib
    import io
    import tempfile
    def quiet_install(*a, **k):  # silence install()'s progress lines only, never a failure message
        with contextlib.redirect_stdout(io.StringIO()):
            install(*a, **k)

    with tempfile.TemporaryDirectory() as tmp:
        for os_name in OSES:
            proj = pathlib.Path(tmp) / os_name
            quiet_install(proj, "standard", os_name)
            expect("[install %s] claude file" % os_name, claude_file("standard", os_name).read_text(),
                   (proj / ".claude/settings.json").read_text())
            expect("[install %s] opencode file" % os_name, True, (proj / "opencode.json").exists())
            expect("[install %s] omp file" % os_name, True, (proj / ".omp/config.yml").exists())
            (proj / ".claude/settings.json").write_text("{}")
            quiet_install(proj, "standard", os_name)  # second run must not overwrite
            expect("[install %s] existing file kept" % os_name, "{}", (proj / ".claude/settings.json").read_text())
            quiet_install(proj, "standard", os_name, force=True)
            expect("[install %s] --force overwrites" % os_name, True,
                   "permissions" in json.loads((proj / ".claude/settings.json").read_text()))
        nosb = claude_settings("standard", "linux", sandbox=False)
        expect("--no-sandbox drops the sandbox block", False, "sandbox" in nosb)
        expect("--no-sandbox keeps the permission rules", True, len(nosb["permissions"]["deny"]) > 100)
        expect("--no-sandbox keeps the SSO login hook", True, "hooks" in nosb)

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
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    if args.check:
        return check()
    if args.install:
        install(args.install, args.profile, args.os_name, not args.no_sandbox, args.force,
                args.extra_claude_deny)
        return 0
    for profile in PROFILES:
        for os_name in OSES:
            write(claude_file(profile, os_name), dump(claude_settings(profile, os_name)))
        write(HERE / profile / "opencode.json", dump(opencode_config(profile)))
        write(HERE / profile / "omp-config.yml", omp_config(profile))
    if args.claude_out:
        write(args.claude_out,
              dump(claude_settings(args.profile, args.os_name, args.extra_claude_deny,
                                   not args.no_sandbox)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
