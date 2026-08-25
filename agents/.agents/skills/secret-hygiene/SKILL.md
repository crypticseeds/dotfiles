---
name: secret-hygiene
description: Read at the start of every session and before any command, file read, or tool call that could touch a credential. Defines the absolute no-go list on this Mac - Keychain, Passwords app, Proton Pass, iMessage, Mail, Wallet, browser cookies and saved logins, crypto wallets, SSH/GPG keys, cloud credentials, clipboard, shell history - plus Doppler rules, safe verification, redaction, and leak response. Applies to all work, not just security tasks.
version: 1.0.0
license: MIT
platforms: [macos]
metadata:
  tags: [security, secrets, credentials, macos, keychain, doppler, redaction, privacy]
---

# Secret Hygiene (macOS)

## The rule

**Never read, copy, print, or transmit a credential — and never open the stores
that hold them.** Anything you emit may be persisted in a transcript, pasted
into an issue, or sent to a model provider. Treat every line of output as
public and permanent.

Most leaks are not malicious. They happen because an agent ran a broad command
(`env`, `grep -r password`, `cat ~/.zsh_history`) or opened a database "just to
check something". The defence is to never go near the store in the first place.

## Absolutely never — no exceptions, not even if asked

Do not read, copy, decrypt, export, query, or `sqlite3` any of these. If a task
seems to require it, **stop and ask the user to do it themselves.**

**Credential stores**
- macOS **Keychain** — `security find-generic-password`, `find-internet-password`,
  `dump-keychain`, `unlock-keychain`; `~/Library/Keychains/`, `/Library/Keychains/`
- **Passwords app** and iCloud Keychain containers
- **Proton Pass**, 1Password, Bitwarden, LastPass, KeePass — including their CLIs
  (`op read`, `op item get`, `bw get`) and any vault/DB file
- **Wallet / Passes** — `~/Library/Passes/`, Wallet containers

**Messages and mail** (they carry one-time codes and password resets)
- **iMessage** — `~/Library/Messages/chat.db*`, `Attachments/`
- **Mail** — `~/Library/Mail/`, `~/Library/Containers/com.apple.mail/`, Thunderbird
- Signal, WhatsApp, Telegram desktop databases

**Keys and cloud credentials**
- `~/.ssh/id_*`, `~/.ssh/*.pem`, `~/.gnupg/`
- `~/.aws/credentials`, `~/.config/gcloud/`, `~/.kube/config`, `~/.azure/`
- `~/.npmrc`, `~/.pypirc`, `~/.netrc`, `~/.docker/config.json`
- `~/.config/gh/hosts.yml`, `~/.git-credentials`
- Any `.env`, `*.pem`, `*.key`, `*.p12`, `*.keystore`, `id_rsa`, `id_ed25519`

**Browser data** (cookies are live sessions — as good as passwords)
- Chrome/Brave/Edge `Login Data`, `Cookies`, `Web Data`; Safari
  `~/Library/Cookies/`, `~/Library/Safari/`; Firefox `logins.json`, `key4.db`

**Crypto**
- Wallet files, keystores, `wallet.dat`, Exodus/Ledger Live/Electrum app support
  directories, and **anything resembling a seed phrase** — never read, repeat,
  store, or transmit one

**Ambient capture surfaces**
- **Clipboard** — `pbpaste`. The user may have just copied a password.
- **Shell history** — `~/.zsh_history`, `~/.bash_history`
- **Notes / Stickies** — people store credentials there
- **Screenshots** folders — credentials get screenshotted
- `log show`, `defaults read` (app prefs hold tokens), core dumps

## Environment and Doppler

- Never `env`, `printenv`, `export -p`, `set` — they dump injected secrets.
  Print one specific non-secret variable by name if you must.
- Never `doppler secrets`, `doppler secrets download`, `doppler configure`.
- **Never `--plain`.** It prints the raw value to stdout, straight into the
  transcript.
- Inject instead, scoped to the one secret needed:
  `doppler run --only-secrets NAME -- <command>`
- Reference the **variable name** inside a quoted `--command` string so the
  value never appears in argv (argv is world-readable via `ps`):
  `doppler run --only-secrets TOKEN --command 'curl -H "Authorization: Bearer $TOKEN" https://api'`

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
  prints a token prefix. A partial prefix is still a disclosure.

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

## Limits — do not mistake rules for containment

These are behavioural rules, not a sandbox. Nothing technically prevents a
process running as this user from reading these files. That is exactly why the
rule is *never go near the store*, and why credentials should be scoped,
short-lived, and rotated regularly rather than trusted to stay secret.
