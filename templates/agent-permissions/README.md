# agent-permissions

Permission files for Claude Code, opencode and omp that enforce two things:

1. **Secret hygiene** (from the `secret-hygiene` skill): agents cannot read or print
   credentials, state files or key material, and cannot run commands that dump them.
2. **A write boundary**: agents write inside the project directory and `/tmp`, and
   nowhere else unless you approve it. Skill directories are readable.

Tuned for AWS, Terraform/OpenTofu, Ansible, Kubernetes (k3s, EKS) and Doppler.
`generate.py` is the single source. The files under `standard/` and `strict/` are output:
edit the lists at the top of `generate.py`, never the output files.

## Pick a profile

| Profile | Use when | Difference |
|---|---|---|
| `standard/` (**default**) | Everyday agentic work, any project | Read-only AWS, kubectl and `terraform plan` calls run without a prompt, so the agent is not waiting on you for routine commands |
| `strict/` | Only when you want to approve every call that touches live infrastructure | Those calls prompt; offline checks (`fmt`, `validate`, `helm lint`, `gitleaks --redact`) still run freely |

The guardrails against reading secrets are identical in both. The profiles differ only in
how many harmless read-only calls you are asked to approve.

Both deny: credential and state reads, secret-printing commands, `terraform destroy`,
force pushes, namespace deletes, `rm -rf`, `sudo`, and the AWS commands that mint or
read secrets.

## Install

| Agent | Project install | Global install |
|---|---|---|
| Claude Code | copy `<profile>/claude-settings.<macos\|linux>.json` to `<project>/.claude/settings.json` | merge into `~/.claude/settings.json` |
| opencode | copy `<profile>/opencode.json` to `<project>/opencode.json` | merge `permission` into `~/.config/opencode/opencode.jsonc` |
| omp | copy `<profile>/omp-config.yml` to `<project>/.omp/config.yml` | `~/.omp/agent/config.yml` |

Claude, opencode and omp all merge user-level and project-level settings, so you can
install `standard` globally and add a small project file only for what differs.
When merging into an existing file, merge the arrays; do not replace them.

**One command for a whole project** (Claude + opencode + omp for this host; it never overwrites a
file that already exists, and `--force` is needed to replace one):

    python3 generate.py --install <project> [--os linux] [--profile strict] [--no-sandbox]

Or generate just the Claude file:

    python3 generate.py --claude-out <project>/.claude/settings.json [--os linux] [--profile strict] \
        --extra-claude-deny mcp__someserver        # optional project-specific denies

## The write boundary, per agent

| Agent | Write/Edit tools | Shell commands |
|---|---|---|
| Claude Code | Prompts outside the project (built-in default); `/tmp` allowed by rule | **OS sandbox**: writes only inside the project and `/tmp`. Permission rules cannot see `cp x ~/y`, the sandbox can |
| opencode | `external_directory`: ask outside the project, allow `/tmp` and skills | same rule covers paths in shell commands |
| omp | **Not enforceable.** No setting found | **Not enforceable** |

Claude sandbox details (`sandbox` block in the Claude file):
- `autoAllowBashIfSandboxed: false`, so the prompts in this policy stay in force.
- Anything the sandbox blocks (a legitimate write elsewhere) can be retried outside
  the sandbox, which prompts you. That is the "unless explicitly allowed" path.
- Network: `allowedDomains` lists GitHub, Terraform registry, AWS, Doppler, Go/npm/PyPI,
  Docker registries. Anything else prompts the first time.
- **Runs outside the sandbox** (`SANDBOX_EXCLUDED`): `docker`, `podman`, `terraform`, `tofu`, `aws`
  and `doppler`. They still go through every permission rule above, which is where the secret
  guardrails live. Reasons: docker/podman need a socket; terraform, aws and doppler need
  credentials the sandbox hides on purpose (the SSO cache, and on macOS doppler's Keychain
  token), so inside the sandbox every `terraform plan` would fail and force an approval prompt.
  Cost: these commands lose the OS-level write boundary.
- Skills are readable everywhere; in opencode they are also made read-only.
  `LOCAL_SKILL_DIRS` in `generate.py` holds this machine's stow paths; edit it per machine.
- Tools that cache outside the project (helm repos, tflint plugins, npm/uv/go caches)
  may fail inside the sandbox. Add that cache directory to `filesystem.allowWrite`
  rather than turning the sandbox off.
- Claude folds every `Read(...)` deny rule into the sandbox's read-deny, and nothing is re-opened
  (`SANDBOX_ALLOW_READ` is empty, `--check` enforces it): any sandboxed script could read a
  re-opened store. A tool that needs a credential store runs outside the sandbox instead.
- **`~/.aws/sso` stays unreadable to sandboxed commands on purpose.** Admin and agent SSO sessions
  cache in the same directory, so a sandboxed process able to read it could read the admin
  token. That is why `aws` and `terraform` run outside the sandbox (above): only they read it.
- **Doppler keeps its token in the macOS Keychain, which the sandbox blocks** (verified:
  `doppler me` fails inside, succeeds outside), hence `doppler *` is excluded too. On Linux the
  token is a file in `~/.doppler` that reaches every Doppler project; it stays blocked as well.
- The admin-profile deny covers command lines only. It cannot see a `profile = "..."` line the
  agent writes into Terraform code. Keep the admin login off any machine agents run on.
- A nested `claude -p` cannot log in inside the sandbox (credential store blocked). Run
  nested tests from a normal terminal.

## Agent host (`--agent-host`): a machine used only by agents

For a box where agents work unattended (the Pi). Pass it with `--claude-out` or `--install`; the
`standard/` and `strict/` bundles are unchanged by it.

- `git push` and `gh pr create/edit/comment/diff` run without a prompt; `gh pr merge` and
  `gh repo delete` are denied (the human reviews and merges); force push stays denied.
- `terraform apply` (and `tofu apply`, plain or Doppler-wrapped, with or without `-auto-approve`)
  is denied rather than asked: nobody is there to answer the prompt. `plan` and `init` stay allowed.
- `kubectl` and `helm` run outside the sandbox, like `terraform` and `aws`: they need `~/.kube` and
  the AWS SSO cache for EKS tokens. Their secret reads stay denied by rule (`kubectl get secret`,
  `helm get values`), so the agent's EKS RBAC should not grant secret reads either.
- `doppler projects`, `doppler configs` and `doppler environments` are allowed (names, no values),
  so an agent can see what is set up. Their `tokens`, `logs`, `--print-config`, mutating forms and
  `--api-host`-style flags are denied. `doppler configure` (it can print the token), `doppler
  secrets`, `--plain` and `doppler run -- printenv` stay denied.
- `git push *` and `gh *` also run outside the sandbox (`AGENT_HOST_EXCLUDED`): the git credential
  helper and the `~/.local/bin/gh` wrapper fetch `GH_TOKEN` from doppler per call, and `~/.doppler`
  stays unreadable to sandboxed code. The permission rules above still apply to both.
- `~/REPOS` is writable (`AGENT_HOST_WRITE`), so agents can work across repos.
- **Linux ignores wildcard `denyWrite`** (verified live 2026-10-04), so on the Pi the next item is
  enforced for the Edit tool only; sandboxed scripts can write sibling repos' config.
- Sibling repos' agent config stays write-denied (`AGENT_HOST_DENY_WRITE`): `.claude` settings,
  hooks, skills, agents, commands, workflows, `.mcp.json`, `opencode.json`, `.omp`, `.envrc`,
  `.git/hooks`, `.git/config`. Claude protects these only in the project it runs in; writable, they
  would let an agent loosen another repo's next session or plant a hook that runs unsandboxed.
  `.claude/worktrees` stays writable.
- `~/.local/bin`, shell rc files and `~/dotfiles` stay outside the write boundary: anything there
  runs outside the sandbox.
- Required alongside, outside this file: branch protection on `main` (PR required, no force push,
  no deletion), because a glob cannot stop a plain `git push` made while on main, and a
  fine-grained, repo-scoped `GH_TOKEN` with no admin rights.
- On the Pi, `~/REPOS/aws-platform/.claude/settings.local.json` must only ever be regenerated with
  `bash regen-agent-host.sh`. It runs `git pull --rebase --autostash` on the dotfiles, then `--check`
  (and stops if either fails), then writes the file
  with `--os linux --agent-host --mcpjson-server aws --mcpjson-server eks`. A hand-run
  `generate.py --claude-out` without those flags silently drops the host rules and
  `enabledMcpjsonServers`. An optional argument writes elsewhere, for a dry run.

## SSO login: `--no-browser` only

A plain `aws sso login` opens the default browser, which may be signed in as the admin account.
So only `aws sso login ... --no-browser` is allowed (it prints a URL and a code that you open in a
private window). Three layers, because rules cannot express "deny unless the flag is present":
- Exact-match denies for the regular forms (`aws sso login`, `... --sso-session seeds-agent`,
  `... --profile agent-readonly`). They never match a `--no-browser` command. All three agents.
- Allow `aws sso login *--no-browser*`. The admin denies still beat it, so `--no-browser` cannot
  be used with `seeds-admin` or `platform-admin`.
- **Claude only:** a `PreToolUse` hook catches any other regular form and tells the agent to
  re-run with `--no-browser` and hand you the URL and code. opencode and omp just get the denial.
  The hook needs `python3`. If it ever fails, the exact denies still apply and other forms prompt.

Not verified: how the Bash tool shows the URL while the command waits for you to authorise. If
you cannot see it, ask the agent to run the login in the background and read its output.

## Admin AWS profile

Commands naming a profile or sso-session containing `admin`, `Admin` or `ADMIN` are denied:
`--profile`, `--sso-session`, `AWS_PROFILE=`, also inside `doppler run -- ...`
(`ADMIN_AWS_PROFILES` in `generate.py`; add your exact names once they exist). This is name
matching, not isolation. The real separation is separate SSO sessions and permission sets.
Reading `~/.aws/sso/**` and `~/.aws/cli/cache/**` is denied for the file tools and shell commands.

## Linux (Fedora in VMware Fusion)

Only the Claude file differs per OS (secret paths, temp dirs); command rules are shared and the
opencode and omp files cover both OSes. The Linux file adds: Firefox/Chrome/Chromium/Brave
profiles (native, snap, flatpak), keyrings and KWallet, password stores, Thunderbird/Signal/
Telegram, `/etc/shadow`, `/etc/sudoers*`, SSH host keys, saved WiFi/VPN passwords
(`/etc/NetworkManager/system-connections`), WireGuard, kubeadm paths, `/proc/*/environ`,
`/proc/*/cmdline`, and `/mnt/hgfs` (VMware shared folders = the Mac's files).

Fedora-specific rule coverage:
- `podman` gets every `docker` rule; `k3s kubectl` gets every `kubectl` rule (otherwise they bypass them).
- `su`, `doas`, `pkexec`, `run0`, `visudo`, `setenforce` are denied like `sudo`.
- Credential stores: `keyctl read`, `systemd-creds decrypt`, `secret-tool`, Secret Service over D-Bus
  (`gdbus`/`busctl`), `nmcli --show-secrets`, `wg showconf`, `podman secret inspect --showsecret`.
- `journalctl`, `firewall-cmd`, `semanage`, `setsebool`, `restorecon` prompt.

Setup in the VM, in this order (run `bash linux-preflight.sh` to check every item):
1. `sudo dnf install bubblewrap socat`. Claude's sandbox needs them. The Linux file sets
   `sandbox.failIfUnavailable: true`, so a missing dependency stops Claude with an error
   instead of silently running commands unsandboxed (the default).
2. Fusion VM settings: turn off Shared Folders and copy/paste and drag-and-drop (Isolation).
3. SSH in without agent forwarding (`ssh -a`, or `ForwardAgent no`).
4. Run agents as a normal user with no sudo. Keep SELinux enforcing.
5. Only the `AgentReadOnly` SSO session lives in the VM; keep admin credentials on the Mac.

**If the sandbox will not start on Fedora** (the preflight tells you why), do not stay stuck:
re-run the install with `--no-sandbox --force`. The permission rules, secret denies and the SSO login
hook all stay; only the OS-level write boundary for shell commands goes (Write/Edit tools still
prompt outside the project). Fix the sandbox later and re-run without the flag.

Verified vs not: the command and path rules for Linux are tested offline (`--check`, 1200+
cases). **Not tested on Linux itself**: that the bubblewrap sandbox starts with this config, and
Claude's own handling of the Linux paths. Do
the first live run in the VM with the check list in the preflight script and a few canary reads.

## Known gaps (do not rely on these files for more than they do)

- **omp** has no per-path rules and no write boundary: it only gets command rules, and its
  default (`yolo`) prompts for nothing, so the file sets `approvalMode: write`. For a hard
  boundary run omp as a separate user, in a VM, or on the Pi.
- Command matching is not a sandbox. `python -c`, scripts and any program that opens a file
  itself bypass it (interpreters are set to prompt, not blocked). `doppler run` must stay
  allowed, so a child process can always see injected secrets.
- `.env.example`: readable and editable with the file tools in all three (verified live in
  Claude; also `.env.Example`). Claude's matcher has no negated character classes and is
  case-insensitive, so the carve-out is spelled as ranges that leave out both cases of each
  letter of `example`. Shell commands that mention it (`cat .env.example`) are still blocked
  because shell patterns cannot carve out.
- Claude applies settings changes one step late: after editing the settings file, the next
  tool call can still run under the old rules.
- `ssh -i key.pem` and `rm -rf .terraform` are blocked; run them yourself.
- Claude does not look inside `doppler run -- <cmd>`, so every AWS/Terraform/Ansible/kubectl/
  helm rule has a `doppler run * -- <cmd>` twin.

## Is this a standard you can template from?

There is no cross-agent standard for permissions (`AGENTS.md` standardises instructions, not
permissions), so each agent needs its own file. This bundle is the closest thing: one policy,
one generator, three formats, two named profiles, and a test (`--check`) that reads the written
files back. As a template it is sound; what it does not do yet:

- **Per-project differences** (extra allowed domains, a project-specific deny): use
  `--extra-claude-deny` or a small project-level settings file layered over a global install.
  There is no per-project config file for the generator itself.
- **Per-machine paths**: `LOCAL_SKILL_DIRS` is machine-specific.
- **No `init` command** that drops all three files into a project in one step; copy per the table.

## Regenerate and test

    python3 generate.py              # git pull --rebase, then writes standard/ and strict/
    python3 generate.py --check      # reads the files back, tests commands and paths
