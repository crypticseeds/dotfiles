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
  There is no allow-list, so anything added to that config reaches every agent: keep
  it to keys every agent may hold, and nothing personal.

Measured 2026-11-15 with `~/REPOS/aws-platform` as the working directory:

| form | scope injected | repo secrets |
|---|---|---|
| `doppler run -- ...` | `agents-pi/aws-platform` | `ARGOCD_ADMIN_PASSWORD`, `GRAFANA_ADMIN_PASSWORD`, `DOCKERHUB_PULL_TOKEN`, `GH_TOKEN`, ... present |
| `doppler run -p harness -c dev_maghub -- ...` | `harness/dev_maghub` | all absent |

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
- Wired for **omp only** (`~/.omp/agent/mcp.json`, `mcphub-dev` and `mcphub-web`). That
  file is generated by `scripts/agents-sync.py`, but these two entries are unmanaged
  additions: the sync only creates or updates manifest names, so they survive.
  `make doctor` still reports drift for the per-server entries the manifest lists for
  omp (`chrome-devtools`, `firecrawl`, `github`, `linear`, `playwright`, `sentry`,
  `tinyfish`); that drift is expected until the manifest itself moves to the hub form.

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
- `opencode/.local/bin/opencode-shared-server` - pins `-c dev` because the `github` MCP
  header needs `GH_TOKEN` in the server process. Move it once the opencode harness reads
  GitHub through mcphub, or add `GH_TOKEN` back if the header has to stay.

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
- **No allow-list on launches.** One `dev_maghub` serves every agent, so a key added
  there for one purpose reaches all of them. That is the accepted trade for a single
  clean command; the per-directory alternative was dropped.
- mcphub is wired for omp only; roll out once it has been used in anger.
