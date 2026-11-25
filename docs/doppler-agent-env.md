# Doppler and agent launch paths

How every harness gets its environment on the Linux agent host. Written 2026-11-15
after the move from `harness/dev` to `harness/dev_maghub`.

## One rule

    agent-env <agent command>

The launcher (`zsh/.local/bin/agent-env`, stowed to `~/.local/bin/agent-env`) sets the
scope for both the aliases and the non-interactive wrappers.

- **`-p harness` is the load-bearing part.** Doppler resolves a bare `doppler run`
  from a per-directory scope, and a repository with its own scope beats the home one:
  `~/REPOS/aws-platform` resolves `agents-pi/aws-platform`, so an unpinned run there
  injects that project's secrets. The project and config flags override directory defaults.
- **Service-token scope can override both flags.** The launcher uses Python 3 to read the
  fetched payload from a private named pipe and checks Doppler's reserved `DOPPLER_PROJECT`
  and `DOPPLER_CONFIG` before injecting it. Missing or mismatched metadata prevents launch.
  Doppler's encrypted fallback can remain on disk and is subject to the same scope check.
- **`-c dev_maghub` is the config every agent gets**: `ANTHROPIC_API_KEY`,
  `ANTHROPIC_BASE_URL`, `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `MCPHUB_DEFAULT_KEY`.
  Only these names are injected from the default payload; other payload variables,
  including dynamic loader settings, are ignored. Existing inherited environment variables are retained.

Measured 2026-11-15 with `~/REPOS/aws-platform` as the working directory:

| form | scope injected | repo secrets |
|---|---|---|
| `doppler run -- ...` | `agents-pi/aws-platform` | `ARGOCD_ADMIN_PASSWORD`, `GRAFANA_ADMIN_PASSWORD`, `DOCKERHUB_PULL_TOKEN`, `GH_TOKEN`, ... present |
| `doppler run -p harness -c dev_maghub -- ...` | `harness/dev_maghub` | all absent |

## Sandboxed launches on the Pi

Run `agent-launch` with a supported harness from your workspace. In a Git checkout, the launcher uses the
worktree root. Outside Git, it uses the current directory. For a fresh agent that needs a special
secret, put the standard gateway values and the extra secret in one dedicated Doppler
config. Select the config and name the extra variable for that launch:

```bash
hc run --bg --cwd "$HOME/REPOS/redress" \
  agent-launch --doppler my-project/dev --secret SERVICE_API_KEY codex
```

The launcher verifies the selected Doppler scope and passes the standard gateway
variables plus requested names from that single config. A missing variable or scope
mismatch stops the launch. Local subprocesses inherit the worker environment. Launch
a separate worker through `hc` with the default config to give it the normal credentials.
Use `--read DIR` or `--allow DIR` before the harness name to grant another directory. For
Claude, `--read` keeps the nono grant read-only and `--allow` also adds the directory to
Claude's working directories, granting sandboxed Bash recursive write access at that layer.
It can include sibling agent configuration files for Bash, while Claude's file-tool permission
rules still apply.

`agent-launch` applies the named harness pack and `pi-agent-host` nono profile to the client. Claude
uses `--permission-mode auto`; OMP, OpenCode and Codex enable automatic approval. Codex also uses
`--no-daemon`. The named harness pack and executable must be available on the worker host.

Auth per launch: `-o` (`--own`) uses the harness's own login: only `MCPHUB_DEFAULT_KEY` and
`--secret` names are passed. `-g` (`--gateway`) adds `ANTHROPIC_API_KEY`, `ANTHROPIC_BASE_URL`,
`OPENAI_API_KEY` and `OPENAI_BASE_URL`. Defaults are in the `auth_default`
table at the top of the script: `claude` uses its own login, the others the gateway. The worker
environment is rebuilt from scratch, so `ANTHROPIC_*` variables from the launching shell
(including `ANTHROPIC_AUTH_TOKEN`) never reach the agent either way. `agent-launch -h` lists the flags.

OpenCode's tools run in the shared background server (`opencode.service`), which runs outside
nono and the launch's `bwrap` (verified 2026-11-25: an `agent-launch opencode` session wrote into
`~/.claude`, which the launch mounts read-only). `-s` (`--standalone`) starts a private server
inside the sandbox instead, so the tools are sandboxed; such sessions are not visible to the
shared service (`opencode api`, the opencode-workers skill). Without `-s` the launcher prints a
one-line reminder.

The nono profiles are split in two (`zsh/.config/nono/profiles/`). `agent-base` is portable
and OS-neutral: it extends `default` (every `deny_*` group nono ships), adds denies for secret
stores the groups miss (`~/.doppler`, `~/.config/magpie`, `~/.config/gh`, `~/.pypirc`, database
history files, Mozilla/Thunderbird/Signal/Telegram/Bitwarden data, `/etc/rancher` and the k3s
server token and TLS), strips `DOPPLER_TOKEN`, `GH_TOKEN`, `GITHUB_TOKEN` and `SSH_AUTH_SOCK`
from the environment, and grants writes to the common caches (`~/.cache/uv`, `~/.cache/pnpm`,
`~/.local/share/pnpm`, `~/.cache/pre-commit`, `~/.coderabbit/reviews`, `~/.coderabbit/logs`,
`~/.cache/agent-usage`). `pi-agent-host` extends it with the host-specific parts below.
Harness auth files (`~/.claude/.credentials.json`, `~/.codex/auth.json`,
`~/.local/share/opencode/auth.json`) are not denied here: each harness pack grants its whole state
directory read-write, and on Linux nono refuses to start when a deny sits inside a grant.
`agent-launch` blanks them instead (see below), except the launched harness's own file.

The shared `pi-agent-host` profile allows connections to the default Herdr Core socket,
so sandboxed agents can use `hc`. Core launches processes with its own permissions;
those processes do not automatically inherit the agent's nono sandbox.
The profile also grants read-only access to `$XDG_STATE_HOME/herdr-core/default/files`
(`~/.local/state/herdr-core/default/files` by default) for copied and pasted files.

The profile also grants access to `/run/docker.sock` for Docker diagnostics and container
operations. Docker socket access gives the client the daemon's full authority, including
access outside nono's filesystem restrictions; nono does not restrict Docker subcommands.
Other harness-specific permissions still apply. Restart an agent session to pick up changes.

On the Pi, Claude Code 2.1.331 under nono 0.82.0 failed to start sandboxed Bash with
`bwrap: setting up uid map: Permission denied` in isolated tests with both the old and new
managed policies. Direct Claude launches from the target workspace passed the Bash write tests.
[See Claude's sandbox troubleshooting](https://code.claude.com/docs/en/sandboxing).

Direct Codex launches through `agent-env` also use `--no-daemon` for local sessions.
An unscoped launch can use `--remote` with the arguments unchanged. A scoped launch rejects
`--remote` because the remote executor would use its own environment.

Use `agent-launch --subagent` for supported delegated Pi workers. It uses the normal `harness/dev_maghub` config by default. GitHub permissions through mcphub are controlled by the server. Workers must leave GitHub writes to the parent or operator. Claude's nested Bash sandbox currently fails under nono; a direct Claude session lacks nono and the read-only Git metadata protection.

```bash
hc run --bg --cwd "$HOME/REPOS/redress" agent-launch --subagent codex
```

Every launch inside a Git checkout, not only `--subagent`, runs under an outer `bwrap` that
mounts these paths read-only for the sandboxed client: the common Git directory's `hooks` and
`config` (so the agent cannot plant hooks or change `core.hooksPath`), the effective hooks directory
when `core.hooksPath` points elsewhere (resolved against the worktree root), any `config.worktree`
(`extensions.worktreeConfig`), and the workspace's agent configuration when it exists: the whole
`.claude` directory (with `.claude/worktrees` re-bound writable, created if missing) plus `.mcp.json`,
`opencode.json`, `.omp` and `.envrc` one by one. The root entries that do not exist yet cannot be
bound, so `agent_guard.py` denies shell commands that write them (`>`, `>>`, `tee`, `cp`, `mv`, `install`,
`ln`, `touch`, `sed -i`); this is accident-level protection, not a barrier.
Every launch, in Git or not, also gets `/dev/null` over every `.env` and `.env.*` regular file or
symlink found in the workspace (excluding `.git` and `node_modules`), except `.env.example` and
`.env.example.bak`. bwrap binds onto the resolved target, so a symlink masks the file it points to,
even outside the workspace; a dangling symlink is skipped. Every launch also gets
`/dev/null` over the other harnesses' stored logins (`~/.claude/.credentials.json`,
`~/.codex/auth.json`, `~/.local/share/opencode/auth.json`); the launched harness keeps its own, so a
script it runs can still read that one. The other harnesses' config directories (`~/.claude`,
`~/.codex`) are also mounted read-only: the opencode pack grants both read-write, which would let
one agent edit another's settings, hooks, or plugin bin directories that Claude puts on `PATH`.
Every launch now needs working `bwrap` user namespaces.
The mask list is built once at
launch, so a `.env` file created after launch is not masked. For `claude`, the launcher also
grants nono read access to the resolved `~/.claude/statusline-command.sh` and
`~/.claude/settings.json` targets, which live outside the workspace.
`AGENT_LAUNCH_DRY_RUN=1 agent-launch ...` prints the final command, one argument per line,
without running it, validating the nono profile, or requiring the harness binary.

Worker checkout files stay writable. When launched in a Git worktree, the launcher mounts
the repository and linked-worktree Git metadata read-only for the sandboxed client. Extra
directories are read-only in worker mode. OpenCode server-side enforcement is unverified.
The parent or operator handles commits, pushes, and merges.
For a special secret, select a separate config with `--doppler PROJECT/CONFIG`
and `--secret NAME`.
On this Pi, a grant over the live dotfiles repo overlaps the protected `.zshrc`
target. Use a separate worktree for sandboxed changes there.

### Deferred: Claude and nono sandbox design

The scoped Linux policy changes in this checkout are not installed. On the Pi, Claude
Code 2.1.331's Bash sandbox fails inside nono 0.82.0 before the command starts. The same
UID-map failure occurred with both the existing and proposed Claude policies, and with
Claude's `enableWeakerNestedSandbox` setting. Do not treat the combined Bash path as
verified until an end-to-end launch succeeds.

The proposed simpler design is to run Claude under nono without Claude's inner Bash
sandbox. A disposable `agent-launch` test with the inner sandbox disabled confirmed
workspace writes, denial of ungranted sibling access, read-only `--read`, and writable
`--allow`, including sibling paths created after launch. A separate local proxy test
allowed a listed hostname, rejected an unlisted one, and blocked direct TCP.

This is not an equivalent replacement yet:

- Linux Landlock cannot enforce a deny inside a recursively granted writable directory
  in this nono version. An existing denied child makes nono refuse startup; a matching
  child created after startup was readable. Keep secrets and other files that must be
  hidden outside the workspace and every directory granted with `--allow`.
- Disabling Claude's Bash sandbox made a synthetic file readable through Bash despite
  a managed Claude `Read` deny. Native tool permission rules are not a substitute for
  filesystem enforcement against arbitrary Bash programs.
- The current nono profile does not reproduce Claude's Bash domain allowlist. A
  session-wide proxy needs the actual model and MCP destinations and must be tested
  with all required traffic before rollout.
- Claude's built-in configuration protections, excluded commands, and trusted-tool
  workflows need separate review. Host daemon sockets and broad credential access
  must not be granted merely to make those workflows run.

An owner-installed AppArmor policy could potentially enforce path restrictions inside
writable directories, but adds a host-maintained security policy and has not been
tested here. The alternative is a narrower workspace layout that gives up arbitrary
root-level writes. Neither option has been selected or installed.

Evidence: [nono Landlock deny-overlap issue](https://github.com/nolabs-ai/nono/issues/2296),
[Linux Landlock documentation](https://docs.kernel.org/userspace-api/landlock.html), and
[Claude sandboxing](https://code.claude.com/docs/en/sandboxing).

## Which launches get the environment

| Launch path | Env injected | How |
|---|---|---|
| `claude`, `cc`, `opencode`, `oc`, `omp`, `codex` typed in a pane | yes | zsh aliases, `zsh/.config/zsh/aliases.zsh` |
| `herdr agent start <name> --kind claude` | yes | types the command into the pane's interactive shell, so the alias fires |
| `hc run <agent>` | yes | `~/.local/bin/hc` wrapper, inserts `agent-env` |
| `rex run <agent>` | yes | `~/.local/bin/rex` wrapper, inserts `agent-env` |
| `hc run --on <machine> <agent>` | yes, if that host has `agent-env` and Doppler auth | `--on` is preserved, so the command runs there |
| systemd, cron, scripts that call the binary directly | no | not covered yet |
| macOS | no, by design | keychain `gh` auth; the darwin alias branch injects nothing |

The wrappers rewrite only `claude`, `codex`, `omp` and `opencode` - agent programs, no
shells. Every other command, option and program passes through untouched, and
`hc`/`rex` subcommands other than `run` are executed unchanged.

Both wrappers live in `~/.local/bin` and are **not tracked by this repo** (same as the
`gh` wrapper and `git-credential-doppler`). `~/.local/bin/hc` was a symlink to
`herdr-core`; `herdr update` may recreate that symlink and silently drop the wrapper. If
`hc run claude` stops seeing `MCPHUB_DEFAULT_KEY`, reinstall the wrapper. `rex` shadows
`/usr/bin/rex` on PATH.

## Where `doppler setup` goes

The scope is stored per path in the global CLI config (`~/.doppler/.doppler.yaml`,
owner-only, never read or edited by an agent). There is no `.doppler.yaml` in `$HOME`,
in `~/REPOS` or in `~/REPOS/aws-platform`, yet each resolves a different project, which
is how the per-path entries show up. Closest ancestor wins.

To make bare `doppler run` default to the maghub config:

    cd ~ && doppler setup -p harness -c dev_maghub

Run it from `$HOME` - the working directory becomes the scope. It updates the `$HOME`
entry only; a repo with its own entry keeps it. CLI v3.77.1 has no `--global` flag on
`setup`; the global `--scope <dir>` flag is the equivalent.

Agents no longer depend on this: `agent-env` pins the project, so a missing or different
`$HOME` scope changes nothing for them. It only affects bare `doppler run` elsewhere.

## The `test` project (inherits `dev_maghub`)

`test` is a separate project whose configs inherit `harness.dev_maghub`:

| project/config | inherits | secrets |
|---|---|---|
| `test/dev`, `test/dev_personal` | `harness.dev_maghub` | the five, plus `NEW_SECRET` |
| `test/prod` | none | nothing |

So `doppler run -p test -c dev -- <cmd>` returns the five inherited keys plus
`NEW_SECRET`, and never needs a second `doppler run` against `harness`: inheritance does
the combining, one project and one config per launch.

Nothing points at it yet. With the pin, an agent started in `~/test` still gets
`harness/dev_maghub`, not `test/dev`. Wiring a directory to a different project would
need an explicit per-directory declaration read by `agent-env` (parsed as fixed
`key=value` lines, never sourced, because the directory is inside an agent's write
boundary). Deliberately not inferred from the directory scope - that is the leak path in
the table above.

Note that `test` re-exposes the same base key values under a second project, so treat it
as equally sensitive as `harness`.

## GitHub through mcphub

GitHub tools now come from the mcphub MCP server, not from a `GH_TOKEN` header.

- Client endpoints: `http://10.10.25.11:3100/mcp/dev` and `/mcp/web`, group-scoped,
  `Authorization: Bearer ${MCPHUB_DEFAULT_KEY}`. Verified: `github-get_me` returns the
  authenticated user.
- **The public hostname does not work.** `https://mcphub.internal.devopsfoundry.com/mcp/*`
  is behind Authelia forward-auth: the 401 is an SSO redirect, and the bearer key never
  reaches mcphub. Either exempt `/mcp` and `/sse` from Authelia in the Traefik router
  (`notes/magpie-agentgateway/mcphub/magic-pi-traefik-mcphub.yml`) or keep using the
  direct port.
- `scripts/agents-sync.py mcp` configures `mcphub-dev` and `mcphub-web` from the manifest's
  `mcp_hub` section in the supported harnesses. The `mcp` section retains the old server
  definitions for reference and continues to supply explicit project opt-ins.

The OpenCode v2 shared server uses its own `MCPHUB_DEFAULT_KEY`. Its launcher honors an
inherited key or fetches only that key from `harness/dev_maghub`. An already-running server
keeps its launch environment until restarted.

## Deliberately left on `harness/dev`

These still read `dev` and keep working after the `$HOME` scope moves, but they are not
on the new funnel and each needs a decision:

- `~/.local/bin/gh` and `~/.local/bin/git-credential-doppler` - fetch `GH_TOKEN` per
  invocation and fall back to `-p harness -c dev`. `dev_maghub` has no `GH_TOKEN`, so
  these must not be repointed as they are. Agents no longer need them for GitHub; the
  CLI still does.
- `~/.local/bin/buzz-*` and `agents/.agents/skills/buzz-external-agents/scripts/buzz-*` -
  `BUZZ_*` keys. Planned: their own config that inherits the maghub secrets.
- `~/.local/bin/opencode-server` and `~/.local/bin/opencode-attach` -
  `OPENCODE_SERVER_PASSWORD`. Same plan as buzz.
- `oca` alias - `doppler run --only-secrets OPENCODE_SERVER_PASSWORD,OPENCODE_SERVER_USERNAME`
  with no `-p`/`-c`. It works today only because the `$HOME` scope is still
  `harness/dev`; the moment that scope moves to `dev_maghub` it fails with "secrets ...
  do not exist". Left as is by request.

## Open items

- **`dev_maghub` is missing the non-secret knobs `dev` had**: `ANTHROPIC_AUTH_TOKEN`,
  `ANTHROPIC_MODEL`, `ANTHROPIC_DEFAULT_{HAIKU,OPUS,SONNET}_MODEL`,
  `CLAUDE_CODE_SUBAGENT_MODEL`, `ENABLE_TOOL_SEARCH`. They do not reach agents any more.
  Add the ones that matter to `dev_maghub` if a launch behaves differently (gateway
  bearer auth, model overrides, tool search).
- **No end-to-end model check yet.** `claude -p` probes on 2026-11-15 were rejected at
  the model layer in both scopes (`claude-opus-5-5`, `claude-sonnet-5-5`, and
  `kimi-k2.5` under `dev`), so the keys authenticated but no completion was verified.
  Confirm with a real interactive launch.
- **Default launch scope is fixed.** Only the five standard names are injected from
  `dev_maghub`; use a scoped `agent-launch --secret NAME` for an additional variable.
