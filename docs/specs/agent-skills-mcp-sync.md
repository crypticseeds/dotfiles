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
3. `make doctor` reports drift in both directions, so an ad-hoc install is
   noticed instead of silently lost.

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
    "marketplaces": { "claude-code-warp": "warpdotdev/claude-code-warp", "antonbabenko": "antonbabenko/agent-plugins" },
    "enabled": ["coderabbit@claude-plugins-official", "superpowers@claude-plugins-official", "..."]
  },
  "mcp": {
    "playwright": { "command": "npx", "args": ["-y", "@playwright/mcp@<version>"] },
    "linear":     { "url": "https://mcp.linear.app/mcp", "auth": "oauth", "except": ["claude"] },
    "firecrawl":  { "url": "https://mcp.firecrawl.dev/v2/mcp-oauth", "auth": "oauth", "except": ["claude"] },
    "aws-mcp":    { "command": "uvx", "args": ["mcp-proxy-for-aws-cli==1.7.0", "https://aws-mcp.us-east-1.api.aws/mcp", "--skip-auth"] }
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
- Secrets as `${VAR}` references to Doppler names, and a `headers` entry,
  are not implemented (future). Any entry containing `${` is rejected today.
  Harnesses already launch under `doppler run`; the generator never resolves
  values.
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

One function per harness renders the manifest's neutral entries into that
harness's format and merges only the keys it owns:

- Claude: `claude mcp add-json --scope user <name> '<json>'` per entry;
  `claude mcp remove --scope user` for names previously written by the sync
  (tracked in `~/.cache/dotfiles-skills/state.json`) that left the manifest.
- Hermes: remote MCPs only, via `hermes config set --force`; stdio entries are
  skipped. Never rewrite `config.yaml` (it holds the Buzz allowlist and other
  host state).
- omp, Cursor, Codex: merge into the `mcpServers` / `[mcp_servers]` table,
  preserving unmanaged entries.
- opencode: generated into the untracked `~/.config/opencode/opencode.json`
  (opencode merges it with the tracked `opencode.jsonc`). The `mcp` block is
  removed from `opencode.jsonc`, so no generated content enters git history.

Entries the sync did not write are left alone and reported by doctor.

### 5. Claude plugins

`settings.json` stays the record of `enabledPlugins` and
`extraKnownMarketplaces`; the manifest's `plugins` block is the input the sync
uses to run `claude plugin marketplace add` / `claude plugin install` for
anything missing. (If Claude Code turns out to auto-install enabled plugins
from known marketplaces on first launch, this step reduces to a check.)

### 6. Doctor drift report

`make doctor` gains a section that lists:
- skills in `~/.agents/skills` that are neither committed nor in the manifest;
- manifest skills missing on disk or at a different SHA;
- link targets occupied by real directories;
- per-harness MCP servers not in the manifest, and manifest MCPs missing;
- enabled Claude plugins not installed, and installed plugins not enabled.

Report only; it never deletes. It is produced by the read-only
`agents-sync.py check` subcommand (not part of `all`), which prints one
`WARN  drift: ...` line per finding or `OK    drift: none`, and always exits 0.

### 7. Entry point

`make agents-sync` runs fetch, link, MCP and plugin steps in order. `make
install` / `make restow` call it after stowing (the existing load-bearing order
stays: `agents` stows first).

## One-time migration

See `docs/plans/agent-skills-mcp-sync-migration.md`.

## Decisions (resolved 2026-10-08)

1. **opencode MCP block**: generated into the untracked `opencode.json`;
   `opencode.jsonc` keeps no `mcp` block. Cleaner git history.
2. **aws-mcp**: one form everywhere, with `--skip-auth` (as the aws-core
   plugin ships it). Not host-restricted. If credentialed access is ever
   needed, the owner commits a separate MCP file for it by hand.
3. **Firecrawl/TinyFish/Linear/Sentry in Claude**: the claude.ai connectors
   cover these for Claude, and the owner logs in once per service anyway, so
   these entries carry `"except": ["claude"]` to avoid duplicate tools in
   Claude. Other harnesses get them as local MCPs.
4. **Cursor skills**: Cursor loads `~/.agents/skills` natively (cursor.com
   docs, Agent Skills), so no `~/.cursor/skills` links.

## Acceptance criteria

| # | Criterion | Check |
|---|---|---|
| 1 | Fresh `$HOME` reproduces skills | In a clean container with the repo cloned, `make install` then `ls ~/.agents/skills` equals committed + manifest skills (minus host-restricted) |
| 2 | Every installed harness sees them | Links resolve in `~/.claude/skills`, `~/.codex/skills`, `~/.hermes/skills`; omp/opencode list them (`omp` skill listing, opencode skill tool) |
| 3 | MCPs consistent | `claude mcp list`, omp `mcp.json`, `hermes config` and opencode config each contain exactly the manifest MCPs applicable to them, plus untouched unmanaged ones |
| 4 | Idempotent | Second `make agents-sync` makes no changes (no file mtimes change, no CLI add/remove calls) |
| 5 | Never clobbers | A real directory at a link target and an unmanaged MCP entry both survive a sync and appear in the doctor report |
| 6 | Drift detected | Installing a skill with `npx skills add` and adding an MCP by hand both show up in `make doctor` |
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
