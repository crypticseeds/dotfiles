# Spec: reproducible agent skills, plugins and MCP servers

Status: built on branch feat/agent-skills-mcp-sync (2026-10-08).

## Problem

A fresh VM or dev box gets only the skills that are committed to
`agents/.agents/skills/`. Everything installed some other way (skills.sh,
the AWS installer, hand copies, MCPs added through a harness CLI) lives only on
the machine where it was installed, with no record of where it came from.
Each harness also keeps its own hand-written MCP list, partly outside the repo.

Inventory on the Pi at the time of writing:

| What | State |
|---|---|
| `~/.agents/skills` | 35 skills; 9 tracked in git, 24 AWS + herdr gitignored, buzz-external-agents hidden by `.git/info/exclude` |
| AWS skills | three real copies (`~/.agents`, `~/.claude/skills`, `~/.pi/agent/skills`) plus the aws-core Claude plugin loading a different version of the same 24 |
| `orchestrate` | in the repo but not linked into claude/codex (`make skills` not re-run) |
| Claude plugins | 8 enabled in tracked `settings.json`; superpowers installed twice (two marketplaces) |
| MCPs | Claude: aws-mcp (user scope, unmanaged, failing - no AWS creds). opencode: playwright, chrome-devtools, linear, firecrawl, tinyfish (managed) + aws-mcp, chrome-devtools (unmanaged). omp: linear (unmanaged). Hermes: firecrawl (OAuth). codex, cursor: none |
| Hermes | ~40 own skills in `~/.hermes/skills` (bundled + curator-managed), 3 Buzz skills copied from `tonbistudio/buzz-skills`, 4 links into `~/.agents/skills` |

Account-level things (claude.ai connectors, Cowork/claude.ai plugin skills)
follow the account to every machine and are out of scope.

## Goals

1. `make install` on a new machine yields the same skills, Claude plugins and
   MCP servers on every installed harness, with no manual steps beyond auth.
2. One manifest in the repo is the source of truth; the repo stores sources and
   pins, not third-party skill content.
3. `make doctor` reports drift (unmanaged skills, manifest items missing or
   different), so an ad-hoc install is noticed instead of silently lost.

## Non-goals

- Installing the harnesses themselves (stays in `packages/harnesses.sh`).
- Managing secrets or OAuth logins. The manifest names Doppler variables only;
  OAuth MCPs still need a one-time login per machine.
- Hermes' bundled skills, `.archive` and curator state.
- Buzz Desktop's `buzz-cli` skill (written into `~/.buzz` by Buzz Desktop
  itself, `desktop/src-tauri/src/managed_agents/nest.rs`).
- claude.ai account connectors and claude.ai-provided plugin skills.

## Harnesses and how each gets skills

| Harness | Skills from `~/.agents/skills` | MCP config written to |
|---|---|---|
| Claude Code | per-skill links in `~/.claude/skills` (existing `make skills`) | `claude mcp add-json --scope user` |
| Codex | per-skill links in `~/.codex/skills` (existing) | `[mcp_servers.*]` in `~/.codex/config.toml` |
| Hermes | per-skill links in `~/.hermes/skills` (new, user decision) | remote MCPs via `hermes config set --force mcp_servers.<name>...`; stdio skipped |
| opencode | native | untracked `~/.config/opencode/opencode.json` |
| omp | native (verified: loads `.agents/skills` from user home) | `~/.omp/agent/mcp.json` |
| pi | native | n/a until pi supports MCP; skip |
| Cursor | native (docs: loads `~/.agents/skills`, plus `~/.claude/skills` and `~/.codex/skills` for compatibility) | `~/.cursor/mcp.json` |

A harness that is not installed on the machine is skipped, not an error.
Codex and Cursor presence is detected by `~/.codex` / `~/.cursor`, which stow
creates, so their MCP files are written even without the CLI installed.

## Design

### 1. Manifest: `agents/.agents/manifest.json`

JSON so it parses with stock `python3` on macOS (3.9, no `tomllib`) and Linux
without new dependencies.

```json
{
  "skills": [
    { "name": "find-skills", "repo": "vercel-labs/skills", "path": "skills/find-skills", "ref": "<commit sha>" },
    { "name": "herdr",       "repo": "herdrdev/herdr",     "path": "<path>",             "ref": "<commit sha>" },
    { "group": "aws",        "repo": "aws/agent-toolkit-for-aws", "path": "plugins/aws-core/skills", "ref": "<commit sha>", "all": true },
    { "group": "buzz",       "repo": "tonbistudio/buzz-skills", "path": ".", "ref": "<commit sha>", "only": ["hermes-in-buzz", "buzz-media-attachments", "buzz-self-hosting"], "harnesses": ["hermes"] },
    { "name": "buzz-external-agents", "local": true, "hosts": ["<pi hostname>"] }
  ],
  "plugins": {
    "marketplaces": { "<name>": "<owner>/<repo>" },
    "enabled": ["<plugin>@<marketplace>"]
  },
  "mcp": {
    "playwright": { "command": "npx", "args": ["-y", "@playwright/mcp@<version>"] },
    "linear":     { "url": "https://mcp.linear.app/mcp", "auth": "oauth", "except": ["claude"] },
    "firecrawl":  { "url": "https://mcp.firecrawl.dev/v2/mcp-oauth", "auth": "oauth", "except": ["claude"] },
    "aws":        { "project": true, "command": "uvx", "args": ["mcp-proxy-for-aws-cli==1.7.0", "https://aws-mcp.eu-west-2.api.aws/mcp", "--profile", "agent-readonly", "..."] },
    "github":     { "url": "https://api.githubcopilot.com/mcp/", "except": ["hermes"],
                    "headers": { "Authorization": "Bearer ${GH_TOKEN}", "X-MCP-Toolsets": "context,repos,issues,pull_requests,actions" } }
  }
}
```

Rules:
- Every remote skill is pinned to a full commit SHA. Updating is an explicit
  `make agents-update` that bumps refs and shows the diff for review. (Not
  implemented, future: refs are bumped by hand today.)
- `local: true` marks a skill whose files live only on the listed hosts; the
  sync never fetches it and doctor does not flag it there.
- `harnesses` / `except` restrict an entry; default is all installed harnesses.
- A remote entry may carry `headers`. Inside header values only, `${VAR}` names
  an environment variable (a Doppler name); `${` anywhere else is rejected.
  Each harness gets its own reference syntax and the sync never resolves or
  writes a value: Claude and omp `${VAR}`, Cursor `${env:VAR}`, opencode
  `{env:VAR}`, Codex `bearer_token_env_var` (for `Authorization: Bearer
  ${VAR}`) or `env_http_headers` (for a whole `${VAR}` value). Codex cannot
  express a reference mixed into other text, and Hermes cannot be compared
  (`hermes config get` prints resolved values), so such entries must list them
  in `except` or are rejected. The variable must be in the harness's
  environment: launch it under `doppler run`.
- A remote skill entry may carry `rewrite`: literal string replacements
  applied to every UTF-8 file of each fetched skill (e.g. superpowers'
  `docs/superpowers/` -> `docs/`, so plans and specs land in `docs/plans/` and
  `docs/specs/`). The marker records it, so changing it reinstalls the skill and
  doctor reports a stale copy.
- Skills a single project needs (e.g. `terraform-skill` in `aws-platform`) are
  not in the manifest: they live in that project's `.agents/skills/<name>` with
  a `.claude/skills/<name>` link, like its `.mcp.json` servers.
- `harnesses` restricts per-skill LINKS only. Skills in `~/.agents/skills` are
  still visible to harnesses that read it natively (pi, opencode, omp, cursor).
- Repo-owned skills (`delegate-visibly`, `orchestrate`, ...) are not listed:
  everything committed under `agents/.agents/skills/` is managed by definition.

### 2. Fetcher: `scripts/agents-sync.py`

Own small fetcher instead of `npx skills`: the skills.sh lock stores a folder
hash, not a commit, has no restore command we can rely on, and `npx` is not on
minimal boxes. The fetcher does a shallow sparse `git` fetch of the pinned SHA
into a cache (`~/.cache/dotfiles-skills/`), copies each skill into
`~/.agents/skills/<name>`, and writes a `.managed-by-manifest` marker with the
source and SHA. It is idempotent: an unchanged SHA is a no-op.

Fetched skills stay gitignored. `.gitignore` gets one rule driven by the marker
convention (or a generated ignore list) instead of today's hand-maintained
per-skill lines.

### 3. Linking: extend `make skills`

- Add `~/.hermes/skills` to the link targets. Cursor, omp, opencode and pi
  read `~/.agents/skills` natively and get no links.
- Fix an existing hazard: `ln -sfn src dest` where `dest` is a real directory
  creates `dest/<name>` inside it. Today `~/.claude/skills` holds 24 real AWS
  directories, so a plain `make skills` would plant a link inside each. The
  target must skip (and doctor must report) a real directory occupying a
  link's place. The one-time migration removes those copies.
- Pruning stays limited to dangling symlinks, so Hermes' bundled skills and any
  other real directories are never touched.

### 4. MCP generation

Every manifest MCP name that applies to a present harness is managed there:
created if missing, updated to the manifest definition if different, left alone
if equal. Names that are not in the manifest are never touched, and nothing is
ever removed automatically: dropping an entry from the manifest leaves the
existing copies in place (delete them by hand). There is no state file. An
invalid manifest entry is skipped with an ERROR line and the rest still sync.

One function per harness renders the neutral entry into that harness's format:

- Claude: reads `mcpServers` from the global config Claude itself uses
  (`~/.claude.json`, or a legacy `~/.claude/.config.json` when that exists,
  reported with a WARN because it hides `~/.claude.json`); a missing entry is
  created with `claude mcp add-json --scope user <name> '<json>'`, a different
  one is replaced with `claude mcp remove --scope user <name>` then the add.
- Hermes: remote MCPs only (stdio is skipped). Each key is compared with the
  read-only `hermes config get mcp_servers.<name>.<key>`, and only keys that
  differ are written with `hermes config set --force`. Never rewrite
  `config.yaml` (it holds the Buzz allowlist and other host state).
- omp, Cursor: merge the entry into the `mcpServers` object of their JSON file.
- opencode (v2): entries go under `mcp.servers` of the untracked
  `~/.config/opencode/opencode.json` (opencode merges it with the tracked
  `opencode.jsonc`, which has no `mcp` block, so no generated content enters
  git history). A v1 entry with the same name directly under `mcp` is moved
  there ("migrated"). Header-credential remotes get `oauth: false`. If the
  installed opencode is v1, which cannot read `mcp.servers`, opencode is
  skipped with a WARN.
  v2 resolves `{env:VAR}` and runs MCP servers and tools in one shared
  background server, so that server needs `GH_TOKEN` and the tool PATH, not
  the client. On Linux `make opencode-service` runs it as a systemd user unit
  (`opencode.service` -> `opencode-shared-server`: `doppler run ... opencode
  serve --service`). The wrapper first stops any server a client started
  without the token, and `Restart=always` takes the server back after a
  client's `opencode service restart`. Verified with v2.0.27: one server,
  `github` connected from a client without `GH_TOKEN`, after a boot race, a
  client restart and a crash.
- Codex: the block between the `# >>> agents-sync managed MCP` and
  `# <<< agents-sync managed MCP` markers in `~/.codex/config.toml` is
  regenerated from the manifest; tables already in the block for other names are
  kept as they are. A manifest name that already has a `[mcp_servers.<name>]`
  table outside the block is reported (WARN) and left out of the block, to avoid
  a duplicate TOML table. Corrupted markers (not exactly one start before one
  end) are an ERROR and the file is not written.

JSON files are written atomically and only when something changed; an
unparseable file is an ERROR and stays untouched.

### 4b. Project MCPs

Servers only some repos need (aws, eks) are manifest entries with
`"project": true`. They are never installed globally. A repo opts in with
`.agents/project.json`:

```json
{ "mcp": ["aws", "eks"] }
```

`agents-sync.py project` (part of `all`, so `make agents-sync`) finds opted-in
repos one level below `~/REPOS` (or only the ones given with `--project DIR`)
and writes each harness's project file:

| File in the repo | Read by |
|---|---|
| `.mcp.json` | Claude, omp |
| `.cursor/mcp.json` | Cursor |
| `opencode.json` (`mcp` key, merged) | opencode |
| `.codex/config.toml` (managed block) | Codex, trusted projects only |

A file is written only when a harness that reads it is present. In an opted-in
repo the project entries are managed exactly: a listed name is added or
updated, an unlisted one is removed. Other servers in these files are never
touched. Listing a name that is not a project entry is an ERROR for that repo.
Hermes has no project config. Claude only connects approved `.mcp.json`
servers: `regen-agent-host.sh` approves every project entry by name. `make
doctor` reports project drift with the global drift.

### 5. Claude plugins

`settings.json` stays the record of `enabledPlugins` and
`extraKnownMarketplaces`; the manifest's `plugins` block is the input the sync
uses to run `claude plugin marketplace add` / `claude plugin install` for
anything missing. (If Claude Code turns out to auto-install enabled plugins
from known marketplaces on first launch, this step reduces to a check.)

### 6. Doctor drift report

`make doctor` gains a section that lists:
- (a) skills in `~/.agents/skills` that are not committed, not in the manifest
  and carry no manifest marker;
- (b) manifest skills missing on this host, or whose marker repo/path/ref
  differs from the manifest;
- (c) manifest MCPs missing or different in a present harness (what
  `mcp --dry-run` would change);
- (d) manifest-enabled Claude plugins that are not installed;
- (e) stale skills: carry the sync's marker but no manifest entry claims them
  any more (entry removed, or dropped from an `only` list). Never deleted:
  `check` and `fetch` both list them with the exact `rm -r ... && make skills`
  command, so the user decides.

Report only; it never writes or runs a mutating CLI. It is produced by the
read-only `agents-sync.py check` subcommand (not part of `all`), which prints
one `WARN  drift: ...` line per finding or `OK    drift: none`, and always exits
0. A finder that fails prints `WARN  drift: <finder> failed: ...` and the others
still run.

### 7. Entry point

`make agents-sync` runs fetch, link, MCP and plugin steps in order. `make
install` / `make restow` call it after stowing (the existing load-bearing order
stays: `agents` stows first).

## One-time migration

See `docs/plans/agent-skills-mcp-sync-migration.md`.

## Decisions (resolved 2026-10-08)

1. **opencode MCP block**: generated into the untracked `opencode.json`;
   `opencode.jsonc` keeps no `mcp` block. Cleaner git history.
2. **AWS**: no global AWS MCP. The authenticated AWS MCP Server (`aws`, a
   project entry) already serves the docs, skills and region tools as well
   as API access, so a separate unauthenticated docs-only `aws-mcp` (removed
   2026-10-11) only duplicated it and exposed API tools that always failed.
3. **Remote MCPs in Claude**: Linear, Sentry, Firecrawl and TinyFish go to
   every harness, Claude included (no claude.ai connectors for them, and no
   Claude plugins are used: skills and MCPs come from the manifest only).
   `except` / `harnesses` stay available to keep an entry out of Claude or any
   other harness later.
4. **Cursor skills**: Cursor loads `~/.agents/skills` natively (cursor.com
   docs, Agent Skills), so no `~/.cursor/skills` links.
5. **MCP ownership**: the manifest names are the managed set. A same-name entry
   a user added by hand is updated to the manifest definition; other names are
   never touched; nothing is ever removed automatically. This replaced the
   earlier state-file ownership record, which cost more code than it saved.
6. **Drift scope**: only the five findings above. Link slots occupied by real
   directories are reported by the link step itself (WARN), and extra MCPs or
   plugins are not drift because the sync never removes them.

## Acceptance criteria

| # | Criterion | Check |
|---|---|---|
| 1 | Fresh `$HOME` reproduces skills | In a clean container with the repo cloned, `make install` then `ls ~/.agents/skills` equals committed + manifest skills (minus host-restricted) |
| 2 | Every installed harness sees them | Links resolve in `~/.claude/skills`, `~/.codex/skills`, `~/.hermes/skills`; omp/opencode list them (`omp` skill listing, opencode skill tool) |
| 3 | MCPs consistent | `claude mcp list`, omp `mcp.json`, `hermes config` and opencode config each contain the manifest MCPs applicable to them (equal to the manifest definition), plus untouched other entries |
| 4 | Idempotent | Second `make agents-sync` makes no changes (no file mtimes change, no CLI add/remove calls) |
| 5 | Never clobbers | A real directory at a link target survives a sync with a WARN; an MCP whose name is not in the manifest is untouched; nothing is removed when an entry leaves the manifest |
| 6 | Drift detected | A skill installed with `npx skills add` and a manifest MCP deleted by hand both show up in `make doctor` |
| 7 | No secrets | `git grep` over the manifest and generated files finds only `${VAR}` references; no values written to disk by the sync |
| 8 | Hermes host state intact | `config.yaml` diff after sync touches only `mcp_servers` keys |

## Delegation outline

| Task | Tier |
|---|---|
| Manifest schema + fetcher + `make agents-sync` skeleton | Sonnet |
| Linking changes in `make skills` incl. real-dir guard | Sonnet |
| Per-harness MCP renderers | Sonnet |
| Doctor drift report | Sonnet |
| Migration commands list + manifest population with SHAs | Haiku (from facts in this spec) |
| Verification in a clean container, final review | Opus |
