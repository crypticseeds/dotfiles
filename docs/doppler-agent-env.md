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
OpenCode's shared server may execute outside nono with its own environment and Git access.
The client sandbox's protections for server-side execution are unverified; do not assume scoped
secrets, filesystem grants, or read-only Git metadata apply to the shared server.

The shared `pi-agent-host` profile allows connections to the default Herdr Core socket,
so sandboxed agents can use `hc`. Core launches processes with its own permissions;
those processes do not automatically inherit the agent's nono sandbox.

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
