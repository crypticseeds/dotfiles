# Shared nono sandbox for every agent

Written 2026-11-25. Goal: one nono profile set that every harness (Claude, opencode, omp, codex)
runs under, with the same behaviour on every machine and OS. nono owns everything it can enforce
at the OS level. A standalone guard script owns what nono cannot see (command meaning). The
generator (`templates/agent-permissions/generate.py`) stops being the source of the nono and guard
policy: both become hand-edited config files that are easy to adapt per agent, host and OS.

## Decisions (owner, 2026-11-25)

- Q1: run every agent under nono. Use nono for what it can enforce; put the rest in the guard.
- Q2 (docker): keep the docker socket granted, and run the guard's docker checks in every harness.
  This fits the existing threat model (accident, not a determined process). A daemon-level authz
  plugin is a possible later step, not part of this plan.
- Guard: port it to opencode and omp, so all harnesses run the same script.
- Network: no egress allowlist yet. Files first.
- `~/.config/agentgateway/secrets` is out of scope (the service is being removed). Every other
  secret store must be covered.
- The Claude status line must work under `agent-launch` (grant reads to it).

## Who enforces what

| Concern | Owner | Notes |
|---|---|---|
| Secret files unreadable by any process | nono deny groups + custom denies | portable base profile |
| Writes only in the workspace, caches, granted dirs | nono | |
| Secret env vars | `agent-env` + nono `deny_vars` | already in place |
| Unix sockets (herdr-core, docker) | nono host overlay | per host |
| Protected files inside the writable workspace (`.git/hooks`, `.git/config`, `.claude/`, existing `.env*`) | outer bwrap in `agent-launch` | Landlock cannot deny inside a grant (nono #2296) |
| Command meaning (force push, `rm -Rf`, `docker run -v ~`, `git -c core.sshCommand`, `hc run` args) | guard script, all harnesses | nono has no child-process command enforcement |
| Network egress allowlist | nono proxy, later | deferred |

Known residual gap: a `.env` created inside the workspace after launch is readable by scripts.
The guard covers accidental shell reads of it.

## Layout (target)

    zsh/.config/nono/profiles/
      agent-base.json        portable: every nono deny group, custom secret denies, deny_vars,
                             common cache writes. No host paths, no sockets.
      pi-agent-host.json     extends agent-base: herdr-core socket and files, docker socket,
                             Pi-specific grants. One small file per host/OS.
    templates/agent-guard/   (phase 2)
      agent_guard.py         standalone guard, stdin JSON -> decision; reads policy.json
      policy.json            editable lists (secret globs, repo roots, docker rules, ...)
      adapters/              Claude hook entry, opencode plugin, omp extension

## Phase 1 status (2026-11-25)

Implemented, uncommitted, static checks pass. T1 profiles validated and live canaries passed under
all four packs (secret reads denied, workspace and `~/.cache/uv` writes allowed, token env vars
scrubbed). Harness auth files could not be nono denies (pack grants overlap), so `agent-launch`
blanks the other harnesses' auth files with bwrap on every launch, and mounts the other harnesses'
config dirs (`~/.claude`, `~/.codex`) read-only, since the opencode pack grants them read-write
(nono warned that Claude's plugin bin dir on `PATH` was sandbox-writable). `~/.cache/agent-usage`
write verified live. Pending owner checks: outer
bwrap live on the Pi, status line under `agent-launch claude`, opencode still starts with
`~/.claude` read-only.

## Phase 1 (delegated)

### T1 - Portable nono profiles with full secret coverage (Sonnet)

Scope: `zsh/.config/nono/profiles/` (new `agent-base.json`, rewrite `pi-agent-host.json` to extend
it), the README/docs section that describes them. Nothing else.

- `agent-base.json` extends `default` and enables every `deny_*` group nono 0.82 ships
  (`nono profile groups`), plus custom denies for stores the groups miss. Verified missing from
  `deny_credentials`: `~/.doppler`, `~/.config/magpie`, `~/.config/gh` (hosts.yml),
  `~/.claude/.credentials.json`, `~/.codex/auth.json`, `~/.local/share/opencode/auth.json`. Also check
  and cover if missing: `~/.password-store`, `~/.local/share/keyrings`, `~/.mozilla`, browser profiles,
  `~/.thunderbird`, `~/.config/Signal`, `~/.local/share/TelegramDesktop`, `~/.psql_history`,
  `~/.mysql_history`, `~/.python_history`, `~/.pypirc`, `~/.config/op`, `~/.config/Bitwarden`,
  `/etc/rancher`, k3s server token/tls. Not `~/.config/agentgateway/secrets`.
- `deny_vars`: `DOPPLER_TOKEN`, `GH_TOKEN`, `GITHUB_TOKEN`, `SSH_AUTH_SOCK` (move from the host file).
- Writable caches agents need: `~/.cache/uv`, `~/.cache/pnpm`, `~/.local/share/pnpm`,
  `~/.cache/pre-commit`, `~/.coderabbit/reviews`, `~/.coderabbit/logs`, `~/.cache/agent-usage`
  (status line snapshot).
- `pi-agent-host.json`: `extends: agent-base`; keeps workdir readwrite, `af_unix_mediation`,
  herdr-core socket and files read, `/run/docker.sock`, `capability_elevation: false`.

Acceptance:
- `nono profile validate` passes for both files; `nono profile show pi-agent-host` lists every
  path above under deny (except the caches, which are allow).
- A comment-free JSON diff reviewed by the orchestrator: no path from the old file was dropped.
- Live canaries (run by the owner outside Claude's sandbox, commands listed in the report):
  `cat ~/.doppler/.doppler.yaml` and `cat ~/.config/gh/hosts.yml` fail under
  `nono run --profile nolabs-ai/opencode --extends pi-agent-host`; a workspace write and a
  `~/.cache/uv` write succeed.

### T2 - agent-launch: status line, protected in-repo files (Sonnet)

Scope: `zsh/.local/bin/agent-launch` and its docs section in `docs/doppler-agent-env.md`.

- Claude: grant `--read-file` on the resolved `~/.claude/statusline-command.sh` target and on
  `~/.claude/settings.json`'s target (they live in `~/dotfiles/claude/.claude/`).
- Every launch in a Git checkout (not only `--subagent`): outer bwrap mounts `.git/hooks` and
  `.git/config` (of the common dir) read-only, the workspace's agent config read-only if present
  (`.claude/settings*.json`, `.claude/{hooks,skills,agents,commands,workflows}`, `.mcp.json`,
  `opencode.json`, `.omp`, `.envrc`; not all of `.claude/`, which holds `.claude/worktrees`), and
  binds `/dev/null` over every `.env` / `.env.*` that exists at launch, except `.env.example` and
  `.env.example.bak`. Worker mode keeps its existing read-only git metadata.
- No behaviour change outside a Git checkout.

Acceptance:
- `bash -n` and `shellcheck` clean.
- A dry-run mode or printed argv test showing the bwrap arguments for: a plain repo, a linked
  worktree, a repo with `.env` and `.env.example`, a non-git directory.
- Live check (owner): status line shows under `agent-launch claude`; inside the session
  `echo x >> .git/hooks/pre-commit` and `cat .env` fail, `cat .env.example` works, normal edits work.

## Phase 2 (after phase 1 is merged)

### T3 - Standalone guard (Sonnet, orchestrator reviews; security-sensitive)

- Move `templates/agent-permissions/agent_host_guard.py` to `templates/agent-guard/agent_guard.py`.
  It reads `policy.json` (root-owned install path, e.g. `/etc/agent-guard/policy.json`) instead of
  `generate.py` string substitution. Input: a neutral `{command, cwd, harness}` JSON; adapters
  translate each harness's hook payload.
- Under nono, git, gh, docker and friends run inside the sandbox, so the guard's
  "chained command runs sandboxed" explanations apply only to Claude's own sandbox; make them
  conditional on a policy flag.
- Add `hc run` argument checks (Core starts processes outside nono).
- Keep `generate.py --check` green: the Claude managed settings call the installed script.

Acceptance: every existing guard check in `generate.py --check` passes against the standalone
script; a new `agent_guard.py --selftest` runs the same samples without `generate.py`.

### T4 - opencode plugin and omp extension (Sonnet, after T3)

- opencode: plugin in `opencode/.config/opencode/plugins/` using `tool.execute.before` on the bash
  tool, calling the installed guard and throwing on deny with the reason.
- omp: extension using its tool-call hook (verify the API on the installed omp version first).
- Acceptance: a denied command (`git push --force origin x`, `docker run -v ~:/h alpine`) is refused
  in a live opencode and omp session with the guard's reason; `git status` runs.

## Phase 3 (needs owner decisions and sudo)

### T5 - Claude on nono only

- Managed settings for nono launches set `sandbox.enabled: false`; the guard hook stays. Since
  managed settings are global, this means every Claude launch on the Pi goes through
  `agent-launch` (alias `claude` to it). Direct launches would lose their sandbox.
- Push path: inside nono, `~/.doppler` is unreadable, so `git push` and `gh` cannot fetch
  `GH_TOKEN`. Options: push through `hc run` (guard-checked, runs outside nono), or nono's
  credential proxy for github.com. Owner decides before T5 starts.
- Acceptance: canary reads denied, workspace writes work, push path works, `generate.py --check`
  updated for the new managed settings.

## Out of scope

Network allowlist, docker daemon authz plugin, macOS host overlay (the base profile is written to
allow one later), Codex-specific hooks.
