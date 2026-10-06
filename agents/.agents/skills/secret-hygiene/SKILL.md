---
name: secret-hygiene
description: Read at the start of every session and before any command, file read, or tool call that could touch a credential - API keys, tokens, private keys, .env files, Terraform state, kubeconfigs, AWS SSO caches, environment variables. Defines the absolute no-go stores (macOS Keychain, Linux keyrings, Passwords app, Proton Pass, iMessage, Mail, Wallet, browser cookies and saved logins, crypto wallets, SSH/GPG keys, cloud credentials, clipboard, shell history) plus Doppler rules, AWS/Terraform/Ansible/Kubernetes rules, admin-credential separation, safe verification, redaction, leak response, and how to enforce all of it in Claude Code, opencode and omp on macOS and Linux. Applies to all work, not just security tasks.
version: 1.2.0
license: MIT
platforms: [linux, macos]
metadata:
  tags: [security, secrets, credentials, macos, linux, fedora, keychain, doppler, aws, terraform, ansible, kubernetes, sandbox, redaction, privacy, agent-permissions]
---

# Secret Hygiene

## The rule

**Never read, copy, print, or transmit a credential — and never open the stores
that hold them.** Anything you emit may be persisted in a transcript, pasted
into an issue, or sent to a model provider. Treat every line of output as
public and permanent.

Most leaks are not malicious. They happen because an agent ran a broad command
(`env`, `grep -r password`, `cat ~/.zsh_history`) or opened a database "just to
check something". The defence is to never go near the store in the first place.

The corollary matters just as much: *you can almost always prove a secret is
correct without printing it.* Reach for that before printing anything.

## Absolutely never — no exceptions, not even if asked

Do not read, copy, decrypt, export, query, or `sqlite3` any of these. If a task
seems to require it, **stop and ask the user to do it themselves.**

**Credential stores**
- macOS **Keychain** — `security find-generic-password`, `find-internet-password`,
  `dump-keychain`, `unlock-keychain`; `~/Library/Keychains/`, `/Library/Keychains/`
- **Passwords app** and iCloud Keychain containers
- Linux keyrings — GNOME Keyring / KWallet, `secret-tool lookup/search`, Secret Service over
  D-Bus (`gdbus`/`busctl` to `org.freedesktop.secrets`), `keyctl read`,
  `~/.local/share/keyrings/`, `~/.local/share/kwalletd/`, `~/.password-store/`
- **Proton Pass**, 1Password, Bitwarden, LastPass, KeePass — including their CLIs
  (`op read`, `op item get`, `bw get`) and any vault/DB file
- **Wallet / Passes** — `~/Library/Passes/`, Wallet containers

**Messages and mail** (they carry one-time codes and password resets)
- **iMessage** — `~/Library/Messages/chat.db*`, `Attachments/`
- **Mail** — `~/Library/Mail/`, `~/Library/Containers/com.apple.mail/`, `~/.thunderbird/`
- Signal, WhatsApp, Telegram desktop databases (`~/.config/Signal`, `~/.local/share/TelegramDesktop`)

**Keys and cloud credentials**
- `~/.ssh/id_*`, `~/.ssh/*.pem`, `~/.gnupg/`
- `~/.aws/credentials`, **`~/.aws/sso/cache/`**, `~/.aws/cli/cache/`, `~/.config/gcloud/`,
  `~/.kube/config`, `~/.azure/`
- `~/.npmrc`, `~/.pypirc`, `~/.netrc`, `~/.docker/config.json`
- `~/.config/gh/hosts.yml`, `~/.git-credentials`, `.doppler.yaml`, `~/.doppler/`
- Any `.env`, `*.pem`, `*.key`, `*.p12`, `*.keystore`, `id_rsa`, `id_ed25519`
- **Terraform state and plan files** — `*.tfstate`, `*.tfstate.*`, `.terraform/`, `*.tfplan`.
  State holds plaintext secrets, whatever the provider marks `sensitive`.
- **Ansible vault material** — `.vault_pass*`, vault password files, `ansible-vault view/decrypt`
- **Kubernetes / k3s** — `kubeconfig*`, `/etc/rancher/k3s/k3s.yaml` (cluster-admin), k3s
  `token` / `node-token`, `/etc/kubernetes/admin.conf`
- Linux system secrets — `/etc/shadow`, `/etc/sudoers*`, SSH host keys, saved WiFi/VPN
  passwords (`/etc/NetworkManager/system-connections/`), `/etc/wireguard/`
- **Hypervisor shares** — VMware Fusion `/mnt/hgfs` is the host's files; treat as no-go

**Browser data** (cookies are live sessions — as good as passwords)
- Chrome/Brave/Edge `Login Data`, `Cookies`, `Web Data`; Safari
  `~/Library/Cookies/`, `~/Library/Safari/`; Firefox `logins.json`, `key4.db`
- Linux: `~/.mozilla/`, `~/.config/google-chrome/`, `~/.config/chromium/`,
  `~/.config/BraveSoftware/`, and snap/flatpak copies (`~/.var/app/`)

**Crypto**
- Wallet files, keystores, `wallet.dat`, Exodus/Ledger Live/Electrum app support
  directories, and **anything resembling a seed phrase** — never read, repeat,
  store, or transmit one

**Ambient capture surfaces**
- **Clipboard** — `pbpaste` (macOS), `xclip -o` / `wl-paste` (Linux). The user
  may have just copied a password.
- **Shell and database history** — `~/.zsh_history`, `~/.bash_history`, fish history,
  `~/.psql_history`, `~/.python_history`
- **Notes / Stickies** — people store credentials there
- **Screenshots** folders — credentials get screenshotted
- `log show`, `defaults read` (app prefs hold tokens), `journalctl` (logs carry secrets),
  core dumps, `/proc/<pid>/environ`, `/proc/<pid>/cmdline`

## Never run these

| Never | Why | Do this instead |
|---|---|---|
| `doppler secrets get X --plain` | prints the raw value to stdout | `doppler run --only-secrets X -- <cmd>` |
| `doppler secrets` / `doppler secrets download` | dumps values | `doppler run --only-secrets`; to see what exists, `doppler secrets --only-names` (names only) |
| `doppler configure` | prints the Doppler auth token itself | nothing — there is no safe variant |
| `env`, `printenv`, `export -p`, `set` | dumps the whole environment incl. injected secrets | print one non-secret var by name |
| `cat .env`, `cat *.pem`, `cat ~/.ssh/id_*` | direct disclosure | check existence/permissions with `test -e`, `stat` |
| `cat /proc/<pid>/environ` | reads another process's injected secrets | — |
| `docker inspect <c>`, `docker exec <c> env` (and the same with `podman`) | container env includes passwords | `inspect --format` on a specific non-secret field |
| `systemctl show`, `systemctl cat` | unit files carry `Environment=` lines | `systemctl is-active`, `systemctl status --no-pager` |
| `history`, `ps e` | recall/expose secrets from other contexts | `ps -o pid,args` |
| `gh auth token` | prints the PAT | `gh auth status` (still partially masks — see below) |
| secrets in argv (`--token abc`, `curl -H "Authorization: Bearer abc"`) | world-readable in `ps` | pass via env or stdin |
| `su`, `doas`, `pkexec`, `run0`, `sudo` | privilege escalation | ask the user to run the step |
| `nmcli ... --show-secrets`, `wg showconf`, `keyctl read`, `systemd-creds decrypt` | prints stored secrets | — |

## Infrastructure tools (AWS, Terraform, Ansible, Kubernetes)

| Never | Why | Do this instead |
|---|---|---|
| `terraform show -json`, `terraform output -json/-raw`, `terraform state pull/show`, `terraform console` | print state, including secrets | `terraform plan`, `terraform validate`; ask the user for a specific non-secret output |
| reading a saved plan file (`-out=tfplan`) | contains secrets | read the plan from `terraform plan` output only |
| `aws secretsmanager get-secret-value`, `aws ssm get-parameter*`, `aws kms decrypt` | return secrets | name the resource and let the user fetch it |
| `aws sts assume-role`, `get-session-token`, `configure export-credentials`, `eks get-token`, `ecr get-login-password` | mint credentials | use the already-logged-in profile |
| `aws lambda list-functions`, `ecs describe-task-definition`, `ec2 describe-instance-attribute` (userData) | ordinary-looking reads that return env vars and user data | prompt the user first |
| `kubectl get secret`, `kubectl config view --raw`, `helm get values` | print secrets | `kubectl get` on non-secret kinds |
| `k3s kubectl ...`, `podman ...` | same tools under another name; they bypass rules written for `kubectl`/`docker` | apply every rule to both names |
| `ansible-vault view/decrypt`, `ansible ... -vvv` | print vault contents / module args | `ansible-playbook --check` |
| `gitleaks detect` without `--redact` | prints the secrets it finds | `gitleaks detect --redact` |
| `doppler run -- <anything>` treated as one safe command | a rule on `terraform apply` does not see `doppler run -- terraform apply` | write every infra rule with a `doppler run * -- ` twin |

## AWS access: keep admin credentials out of the agent's reach

- Use separate SSO sessions and permission sets for the human's admin role and the agent's
  read-only role. A shared session means the agent can mint admin credentials.
- **Both sessions cache tokens in the same directory, `~/.aws/sso/cache`.** Anything that can
  read that directory can read the admin token. Deny it to the file tools and to shell commands.
- Deny the admin profile and session *names* on command lines (`--profile`, `--sso-session`,
  `AWS_PROFILE=`, also inside `doppler run --`). This is name matching, not isolation: it cannot
  see a `profile = "..."` line the agent writes into Terraform code. The durable control is that
  the admin login does not exist on the machine agents run on.
- **Agent logins use `aws sso login --no-browser` only.** A plain login opens the default
  browser, which may be signed in as admin. `--no-browser` prints a URL and a code; the human
  opens them in a private window. Deny the plain forms, allow only `--no-browser`, and (Claude)
  use a hook to tell the agent to re-run with the flag, since rules cannot carry a message.
- Never put an AWS account ID in a public repo or paste one into a public file.
- Identity checks: `aws sts get-caller-identity --query Arn` is a safe read, but it prints the
  account ID. Do not paste it.

## Safe patterns

**Inject, never fetch.** Let the secret exist only in a child process
environment, scoped to the single secret needed:

```bash
doppler run -p <project> -c <config> --only-secrets API_KEY -- <command>
```

`--only-secrets` matters: without it the whole project is loaded, so an
unrelated command inherits every credential you own.

**Reference the variable name, never the value.** Inside a `--command` string,
write the name and let the injected shell expand it. The value then never
appears in argv (argv is world-readable via `ps`):

```bash
doppler run --only-secrets TOKEN --command 'curl -H "Authorization: Bearer $TOKEN" https://api'
```

**Feed via stdin when a tool insists on a literal:**

```bash
doppler run --only-secrets TOKEN --command 'printf "%s" "$TOKEN" | some-tool --stdin'
```

**Prefer tools that read the environment natively.** Many CLIs (`gh`, `aws`,
`kubectl`) pick up a token from env with no login step, so there is nothing to
persist to disk. A stored credential file is a resting secret every process
running as your user can read; an injected env var is not.

## Silent leak paths — these are the ones that actually bite

- **`curl -v` / `-i` prints request headers**, including `Authorization`. Use
  plain `curl`, or strip headers before showing output.
- **`set -x` in a shell script echoes every command**, secrets included.
- **Error messages and stack traces** often embed the connection string or token
  that failed. Redact before pasting.
- **Writing a secret into a file you create** — a test fixture, a scratch script,
  a log, a committed `.env`. It then lives on disk and in git forever.
- **Sending file contents to an external service** — a "summarise this log" call
  can exfiltrate a token. Check what you are uploading.
- **Committing before reading the diff.** Always inspect `git diff --staged`.
- **Tool output you did not author** can contain partial secrets. `gh auth status`
  prints a token prefix. A partial prefix is still a disclosure. So does
  `aws configure list` (it shows the last characters of keys).
- **Synced folders.** A project inside Dropbox/MEGA/iCloud uploads whatever lands in it,
  including a local `terraform.tfstate`. Keep state remote and code outside synced folders.
- **Read-only calls that return secrets.** `describe`/`list` look harmless; some return
  environment variables, user data or connection strings (see the infrastructure table).
- **Shared folders, clipboard and agent forwarding into a VM** hand the host to the guest:
  VMware shared folders, copy/paste, and `ssh -A` (the guest can sign with the host's keys).

## Never echo a secret — not even to test it

**A secret variable must never appear inside `echo`, `printf`, a here-string, a
log line, or any shell expansion that can fall through to its value.** There is
no "just checking" exception. This is the rule broken most often, because the
check feels harmless at the moment you write it.

Only these two constructs may touch a secret variable:

```bash
[ -n "$VAR" ] && echo "present"      # presence — prints a literal, never $VAR
echo "${#VAR}"                       # length — prints a number, never $VAR
```

Everything else is banned outright, including things that look like presence
checks:

| Banned | What it actually does |
|---|---|
| `echo "$VAR"`, `printf "%s" "$VAR"` | prints the secret |
| `echo "${VAR:-missing}"` | **prints the secret** when set — `:-` substitutes only when UNSET |
| `echo "${VAR:=x}"`, `echo "${VAR:?msg}"` | same fall-through to the value |
| `echo "${VAR:+yes}${VAR:-no}"` | the second half prints the secret |
| `echo "${VAR:0:4}"` | a prefix is still a disclosure |
| `set -x` around any secret use | echoes the expanded command |
| `curl -v` with an auth header | prints `Authorization` |

`${VAR:+x}` and `${VAR:-x}` differ by one character and behave in opposite ways.
`:+` substitutes when the variable **is** set; `:-` substitutes when it is
**not**, so it emits the real value in the common case. Do not try to recall
which is which under time pressure — use `[ -n "$VAR" ]` and stop.

**This rule exists because it was violated in practice**, by an agent that had
this skill loaded, writing a presence check as `${VAR:-NO}`. Having the rule
available is demonstrably not enough. Do not construct expansions around
secrets at all — there is no version of this you are clever enough to get right
while thinking about something else.

If you need to prove something beyond presence and length, use the table below:
derive a public value, or let a command consume the secret and report its own
result.

## Verify without disclosing

You can almost always prove the property without printing the value:

| Question | Safe check |
|---|---|
| Is it set? | `[ -n "$VAR" ] && echo yes` — never `echo "${VAR:-no}"` |
| Is it the right key? | derive the **public** half — pubkey, fingerprint, `gh api user --jq .login` |
| Right shape? | `echo "${#VAR}"`, or a regex printing only pass/fail |
| Does it authenticate? | make a read-only API call, print the **result** |
| Is Doppler logged in? | `doppler me >/dev/null 2>&1; echo $?` — exit code only |
| Does it have write access? | `git push --dry-run` — authenticates, writes nothing |
| Does the file exist / is it exposed? | `test -e`, `stat` — never `cat` |

## Redact before showing

When piping output that might contain a credential:

```bash
<cmd> 2>&1 | sed -E 's/(gh[pousr]_|github_pat_|sk-|xox[baprs]-|AKIA|ey[A-Za-z0-9_-]{10,})[A-Za-z0-9._-]*/[REDACTED]/g'
```

If an unknown blob appears in output you are about to show, redact it and say
what you redacted.

## If something leaks

Do not reason about whether anyone saw it. **Rotate.**

1. Rotate at the source (provider console, or the user rotates the password).
2. Update the store — stdin prompt, never argv, never `--plain`.
3. Remove any on-disk copy the leak created.
4. State plainly what leaked, where it went, and that it was rotated.

Deleting a message, file, or commit does **not** undo exposure. If it reached a
transcript sent to a model provider, or a git remote, assume it is disclosed.

## When a task seems to need a secret

Ask the user to supply it through the proper channel, or to run that one step
themselves. "I need to read your Keychain to continue" is never the right answer
— say what you need and let them inject it.

## Make new agents inherit this

The rules above are advisory; agents also need **enforcement**, in every place that matters:

- **Command denies** — stop the leaking commands being run at all.
- **File-read and file-edit denies** — command rules do nothing about a file-reading tool.
  Without these, an agent simply opens `.env` directly and the command rules are theatre.
- **A write boundary** — see the next section.

**Use the generator, not hand-written rules:** `~/dotfiles/templates/agent-permissions/`
(`generate.py`, README alongside). One policy, written for Claude Code, opencode and omp, on
macOS and Linux, in two profiles:

- `standard` (default) — read-only AWS/kubectl/`terraform plan` calls run without a prompt, so
  agents are not waiting on the human for routine work. Secret guardrails are the same in both.
- `strict` — those calls prompt. Only if the human wants to approve every live call.

```bash
python3 ~/dotfiles/templates/agent-permissions/generate.py --claude-out .claude/settings.json [--os linux]
python3 ~/dotfiles/templates/agent-permissions/generate.py --check     # reads the files back, tests them
```

Edit the lists at the top of `generate.py`, never the output files. On a new Linux host run
`linux-preflight.sh` from the same directory first.

`scripts/apply-agent-permissions.py` (this skill) is the older, opencode-only patcher for
persona/subagent files. It still works for patching existing opencode agent configs, but it
does not cover Claude, omp, Linux, AWS/Terraform, the `doppler run` wrapper, or the write
boundary. Prefer the generator.

**Also patch the template.** Whatever file scaffolds new agents is the only one that decides
what *future* agents get, and it is the easiest to forget.

**Agents match rules differently. Get the order wrong and a deny silently does nothing:**

| Agent | Rule resolution | Notes |
|---|---|---|
| Claude Code | deny beats ask beats allow | cannot carve an allow out of a deny; matcher is case-insensitive and has **no negated character classes** (`[!x]`/`[^x]` are plain sets), so exceptions are spelled as ranges; settings reload **one step late** |
| opencode | last matching rule wins | put allow, then ask, then deny; has native `external_directory` |
| omp (oh-my-pi) | first matching rule wins | **defaults to `yolo` (no prompts)**: set `tools.approvalMode: write`; no per-path rules |

Always test deny rules by actually trying the command or read once. Several rules in this
project looked correct and were not until a live test showed the matcher behaving differently.
Do not trust an offline model of a matcher you have not verified.

## Write boundary and sandbox

Agents may write inside the project and in a temp directory, nowhere else unless the human
approves. Permission rules only cover the agent's file tools; a shell command like `cp x ~/y`
needs an OS sandbox.

- **Claude Code:** enable the sandbox (`sandbox.enabled`). It confines shell writes and, because
  Claude folds every `Read(...)` deny rule into the sandbox's read-deny, it also stops a script
  from opening a secret file that command matching would miss. Set `autoAllowBashIfSandboxed:
  false` or sandboxed commands skip the prompts, and **`failIfUnavailable: true`** or a missing
  dependency (bubblewrap/socat on Linux) silently runs everything unsandboxed.
- **Sandbox costs, so plan for them.** The sandbox hides credentials on purpose, so tools that
  need them fail inside it and force a prompt every time: `aws` and `terraform` (SSO cache),
  `doppler` (macOS Keychain token), `docker`/`podman` (sockets). Run exactly those outside the
  sandbox (`excludedCommands`); they still obey every permission rule. Do not re-open
  `~/.aws/sso` to the sandbox to fix it. A workflow that prompts for every routine command
  defeats the point of agents.
- **opencode:** `external_directory` (ask outside the project, allow temp and skills) and make
  skill directories read-only with `edit` denies.
- **omp:** no setting found for either. Run it as a separate user or in a VM.
- A nested `claude -p` cannot authenticate inside the sandbox (credential store blocked): run
  nested tests from a normal terminal.

## Linux and VMs

Agents are safest on a machine that does not hold the human's personal stores or admin login.
For a Linux VM (e.g. Fedora on VMware Fusion): turn off shared folders and copy/paste/drag-drop,
SSH in without agent forwarding, run agents as a normal user with no sudo, keep SELinux
enforcing, install `bubblewrap` and `socat`, and keep admin credentials on the host only.
`linux-preflight.sh` in the generator directory checks these. The Linux rule set is tested
offline; the bubblewrap sandbox itself has not been confirmed on a real Linux host yet, so run
the preflight and a few canary reads (`.env`, `/etc/shadow`) on first use.

## Known limits — state these rather than implying safety

- **Command filtering is not a sandbox.** Patterns match the command string, so
  `sh -c "..."`, a script, or any language runtime bypasses them. Interpreters should prompt
  rather than run silently. Claude's OS sandbox is the real control for shell file access,
  within the costs above; the other agents have no equivalent.
- **Injection tools must stay allowed.** `doppler run` cannot be denied — it is
  how credentials reach the process. So an agent can always place a secret in a
  child environment and print it from there.
- **Same-user processes see everything.** Agents sharing a Unix user can read
  each other's files and `/proc` entries. File permissions do not isolate them.
- **Admin-profile denies are name matching.** They stop the command line, not Terraform code
  or an environment the agent can edit. Separation of credentials is the real control.
- **Tools run outside the sandbox lose its write boundary** (terraform, aws, doppler, docker).
  Their secret protection comes from the permission rules alone. On the agent host this also
  covers `git` (so repo hooks run unsandboxed), `gh`, `pre-commit` and `herdr` (`herdr pane run`
  starts any command unsandboxed); see the agent-permissions README trade-offs.
- Therefore the durable controls are **scope and rotation**, not filtering:
  least-privilege tokens, narrow resource selection, short expiry, and routine
  rotation. Treat deny rules as protection against accident, which is the
  common case, not against a determined process.
