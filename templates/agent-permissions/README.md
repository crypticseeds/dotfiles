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

It protects exactly two things, and otherwise gets out of the way:

1. **Secrets never leak.** The secret stores are unreadable to sandboxed commands (OS read-deny, from
   the `Read(...)` rules): `~/.doppler`, `~/.aws/credentials|sso|cli/cache`, `~/.ssh/id_*`, `~/.gnupg`,
   `~/.kube`, `~/.config/gh/hosts.yml`, `~/.git-credentials`, `~/.netrc`, keyrings and password
   managers, browser profiles, shell history, `.env`/`*.pem`/`*.key`. Commands that print secret
   values are denied (`doppler secrets` without `--only-names`, `kubectl get secret`, `helm get values`,
   the AWS secret reads, `env`/`printenv`, `terraform output`/`state pull`). Name-only listing works:
   `doppler secrets --only-names`, `gh secret list`.
2. **Destructive commands are blocked.** Recursive `rm`, `git reset --hard`, `git clean`,
   `filter-branch`/`filter-repo`, discarding the whole tree (`git checkout .`), force push (`--force`,
   `-f`, `+refspec`, `--delete`, `:branch`, `--mirror`) and `--force-with-lease` to `main`/`master`,
   `gh pr merge`, `gh repo delete|archive|rename`, `gh release delete`, `gh api -X DELETE`,
   `terraform apply|destroy|import`, mutating `aws` calls, `kubectl`/`helm` changes, `docker` beyond
   reads, `ansible-playbook` without `--check`.

Everything else runs without a prompt: `git` in the session's repo, and in any repo under `~/REPOS` through
`git-in <dir> <git args>` (branch creation with tracking, `commit` with hooks, `update-ref -d`, push),
`--force-with-lease` to a
feature branch, `gh pr create|edit|close|reopen|comment|ready`, `gh run rerun|cancel|watch`,
`gh issue create|comment|close`, `gh api` GET/PATCH/POST, `gh secret set`, `pre-commit install|run`,
every `herdr` command, `terraform plan`, read-only `aws`/`kubectl`/`helm`.

**How (Claude):**
- Default allow (`Bash(*)`), no ask rules, `WebFetch(domain:*)`: nobody is there to answer a prompt.
  `generate.py` refuses to run while an `ASK_BASH` entry is undecided for the agent host.
- Sandbox on (bubblewrap), `allowUnsandboxedCommands: false`, `allowManagedPermissionRulesOnly: true`.
- `excludedCommands` (run outside the sandbox): `git *`, `gh *`, `git-in *`, `pre-commit *`, `herdr *`,
  `kubectl *`, `helm *`, plus the standard `terraform *`, `tofu *`, `aws *`, `doppler *`, `docker *`, `podman *`.
- Guard hook (`agent_host_guard.py`, embedded inline in the settings file) for what globs cannot
  express: spellings (`rm -Rf`, `git -C x reset --hard`, `gh -R o/r pr merge`), the branch a
  lease-push targets, arguments of unsandboxed tools that resolve into a secret store (also through a
  symlink), git config keys that run a program, live infra limited to read-only subcommands. It never
  checks `herdr` (owner decision).
- **`git -C <dir>`, `git -c k=v`, `--git-dir` and `--work-tree` can never run outside the sandbox.** Claude
  Code's matcher refuses to exempt a git command with one of those global options (hard-coded, found in the
  2.1.291 binary; no pattern, `git -C *` included, can match), so they run sandboxed: no doppler token, no
  `.git/config` write, no network hooks. The read-only subcommands still work (`git -C d status|log|diff`);
  anything else is denied by the guard with the fix: `git-in <repo-dir> <git args>` (`.` = current repo).
  `bin/git-in` (installed root-owned in `/usr/local/bin`) is not `git`, so it is excluded, does the `cd`
  itself, and refuses repos outside `~/REPOS`; the guard checks its git arguments like a plain `git` call.
  Neither `cd <dir> && git ...` (chains are never exempt) nor `GIT_DIR=` prefixes work either.
- It also explains, instead of letting it fail with "could not fetch GH_TOKEN", a credentialed command
  that Claude would run inside the sandbox anyway: inside `&&`/`|`/a loop, or containing `<`, `>`, a
  backtick or `$(` (even quoted). Fix: run it alone, `git-in <dir> ...`, `gh -R owner/repo`, `--jq`,
  `--body-file F`, `git commit -F F`.
- `~/REPOS` and `~/.cache/pre-commit` are writable. Sibling repos' agent config stays write-denied
  for the Edit tool (`AGENT_HOST_DENY_WRITE`); Linux ignores the wildcard sandbox `denyWrite`.

**opencode and omp** (`agent-host/opencode.json`, `agent-host/omp-config.yml`) have no sandbox and no
hook: the same deny rules, the ordinary dev commands above as allows, everything else still prompts.
Gaps without the guard: they cannot see the current branch (`git push --force-with-lease` with no
refspec while on main), combined short flags (`git push -uf`), lowercase `gh api --method=delete`,
symlinks, or a repo's `.git/config`.

**Trade-offs (one line each; the owner decides):**
- `git *` and `git-in *` outside the sandbox: commit hooks and push credentials work, but repo hooks run unsandboxed;
  `.git/hooks` stays unwritable to sandboxed code (Claude's built-in protection), tracked hook
  definitions (`.pre-commit-config.yaml` local hooks, `.husky/`) do not.
- `.git/config` writable by git (branch tracking works) instead of `branch.autoSetupMerge=false`;
  `hooksPath`/`alias`/`sshCommand`/`credential.helper`-style keys are refused by the guard on the command
  line (`-c`, `git config`) and when present in the repo's local config (sibling repos' `.git/config` is
  writable to sandboxed code on Linux).
- `pre-commit *` outside the sandbox: hook installs and GitHub fetches work; hook code runs unsandboxed.
- `herdr *` outside the sandbox, unchecked: visible panes work, but `herdr pane run` starts any command
  unsandboxed, so herdr is a full sandbox escape for a determined agent.
- Not `allowAllUnixSockets` for herdr: on Linux it is all-or-nothing (`allowUnixSockets` is macOS only)
  and would also open the docker socket (root-equivalent), the dbus session bus and the gpg/ssh agents.
- `doppler run --only-secrets X -- <cmd>` runs `<cmd>` outside the sandbox (any program); the guard
  only refuses env printers and inline `-c`/`-e` code there.
- Plain push to `main` is not blocked by a rule (only force/lease to main): GitHub branch protection
  on `main` (PR required, no force push, no deletion) is the real control. Keep it on.
- docker stays read-only: the `ai` user is in the `docker` group, so `docker run -v ~:/h` would read
  every secret store.
- Threat model is accident, not a determined process: anything that runs outside the sandbox (above)
  can read the stores if an agent deliberately writes code to do it.

**What no rule can stop:** a script the agent writes can still delete files inside the write
boundary (`~/REPOS`, `/tmp`). Unpushed work is the exposure; GitHub branch protection covers pushed work.

**Install on the Pi** only with `bash regen-agent-host.sh`, run by you (it uses sudo). It runs
`git pull --rebase --autostash` on the dotfiles, then `--check` (and stops if either fails), then:
- Claude: `/etc/claude-code/managed-settings.json` (root-owned managed settings, every project),
  generated with `--os linux --agent-host --mcpjson-server aws --mcpjson-server eks`. A hand-run
  `generate.py --claude-out` without those flags silently drops the host rules.
- opencode: `/etc/opencode/opencode.json` (root-owned managed config, highest priority).
- omp: `~/.omp/agent/config.yml`, merged: `bash`, `secrets` and `tools.approvalMode` are replaced,
  your other settings kept. omp has no managed config, so this file stays user-writable.

An optional directory argument writes the three files there instead, without sudo, for a dry run.
Then restart the agent sessions. Live test from a new Claude session on the Pi (inside herdr):
`herdr pane list`, `herdr pane split`, `herdr pane run <id> 'echo ok'`, `herdr pane close <id>`,
`git-in ~/REPOS/<other> push --dry-run origin <branch>`, `doppler secrets --only-names`, and two
denials: `cat ~/.doppler/.doppler.yaml`, `git push --force origin <branch>`.

## Starting agents with token access (every session, pane and worktree)

Start every agent as `doppler run --only-secrets GH_TOKEN -- <agent command>`. Then `GH_TOKEN` is in its
environment, `git` (through the doppler credential helper) and `gh` authenticate from it, and nothing has
to fetch the token from `~/.doppler`, which the sandbox hides. On Linux the zsh aliases do this for
`claude`, `opencode`, `oc` (`opencode --auto`) and `omp` (`--approval-mode=yolo`); see
`zsh/.config/zsh/aliases.zsh`.

**Agents starting other agents** (new herdr panes, worktrees, delegated sessions): spell out the full
command, because aliases exist only in interactive zsh and a pane's environment is not the parent agent's:

    herdr pane run <pane-id> 'cd ~/REPOS/<repo> && doppler run -p harness -c dev --only-secrets GH_TOKEN -- claude --agent implementer'
    herdr pane run <pane-id> 'cd ~/REPOS/<repo> && doppler run -p harness -c dev --only-secrets GH_TOKEN -- opencode --auto'
    herdr pane run <pane-id> 'cd ~/REPOS/<repo> && doppler run -p harness -c dev --only-secrets GH_TOKEN -- omp --approval-mode=yolo'

- `-p harness -c dev` is the project and config the git credential helper falls back to. Use it for a
  new worktree or a repo with no `doppler setup`: without `-p`/`-c`, doppler picks the project from the
  directory's setup and fails to start the agent where there is none.
- A worktree is a new directory under `~/REPOS`, so it is inside the write boundary: `git worktree add
  ../<repo>-<branch> -b <branch>`, then start the agent in it as above.
- Nothing else is needed per session: Claude reads `/etc/claude-code/managed-settings.json`, opencode
  `/etc/opencode/opencode.json` and omp `~/.omp/agent/config.yml` in every directory, so a pane in any repo
  or worktree, and every subagent, gets the same policy.

**What the token exposes.** Everything that runs in the session can read `GH_TOKEN`: sandboxed commands,
scripts the agent writes, subagents. `env`/`printenv` are denied by rule, but that is accident protection,
not a barrier. The token must be fine-grained, repo-scoped and without admin rights, so the exposure is
what the agent can already do (push branches, open and edit PRs). Rotate it on any leak. The guard's
checks on chains, pipes and `<` `>` backticks in git/gh commands are unchanged.

## Which rules file each agent reads

The shared rules live in `agents/.agents/AGENTS.md` (secret detail in the `secret-hygiene` skill);
every path below resolves to it (verified 2026-10-06 on the Pi):

| Agent | Reads | Resolves to |
|---|---|---|
| Claude Code | `~/.claude/CLAUDE.md` | symlink to `agents/.agents/AGENTS.md` |
| omp | `~/.claude/CLAUDE.md`, `~/.agents/AGENTS.md`, `~/.omp/agent/RULES.md` (absent), project `AGENTS.md`/`CLAUDE.md` | both user files are the same file |
| opencode | `~/.config/opencode/AGENTS.md` | symlink to `agents/.agents/AGENTS.md` |
| Codex | `~/.codex/AGENTS.md` | symlink to `agents/.agents/AGENTS.md` |

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
The `/proc` paths are blocked by a `PreToolUse` hook (file tools) and command denies, not by
Read/Edit rules: Claude folds those into the sandbox read-deny and bubblewrap then fails to start
(`Can't mkdir parents for /proc/<pid>/mem`, verified on the Pi 2026-10-05).

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

Verified vs not: the command and path rules for Linux are tested offline (`--check`, ~780
checks). On the Pi (Raspberry Pi OS, Claude Code 2.1.289) the bubblewrap sandbox starts with the
agent-host config and enforces the write boundary (verified live 2026-10-05). **Not tested on
Fedora**: do the first live run in the VM with the check list in the preflight script and a few
canary reads.

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
