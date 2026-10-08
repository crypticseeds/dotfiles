# Plan: agent skills, plugins and MCP sync

Implements `docs/specs/agent-skills-mcp-sync.md`. Branch: `feat/agent-skills-mcp-sync`, checked out in the worktree `.worktrees/agent-skills-mcp-sync`
(from `main`), so the live `~/dotfiles` checkout never changes branch; each task runs in its own worktree on `agent/<slug>` and is merged
locally after verification.

## Ground rules for every task

- **Never touch the real `$HOME`.** All runs and tests use a throwaway home:
  `HOME=$(mktemp -d)` (plus the Docker check in T5). The owner applies to real
  machines after merge.
- No new dependencies: stock `python3` (stdlib only, must run on 3.9) and POSIX
  `sh`/`make`. Harness CLIs (`claude`, `hermes`, `omp`, ...) are called only if
  installed; absent harness = skip with a one-line note, exit 0.
- No secret values anywhere: only `${VAR}` references to Doppler names.
- Deletions of real-machine files are listed for the owner, never run.

## Tasks (sequential: T1 -> T2 -> T3 -> T4 -> T5)

### T1 - Manifest + fetcher + `make agents-sync`  (Sonnet)
Real engineering with a clear spec; no design choices left open.

**Scope:** `agents/.agents/manifest.json` (skills + plugins sections),
`scripts/agents-sync.py` (fetch step + CLI skeleton with subcommands
`fetch|link|mcp|plugins|all` and `--dry-run`), `Makefile` (`agents-sync`
target, called from `install`/`restow` after `skills`), `.gitignore`.
**Not:** `make skills`, MCP, doctor.

**Acceptance criteria:**
1. Manifest lists find-skills, shadcn, code-review (vercel-labs/skills,
   shadcn/ui, coderabbitai/skills), herdr, the AWS group
   (`aws/agent-toolkit-for-aws`, `plugins/aws-core/skills`, all 24) and buzz
   group (`tonbistudio/buzz-skills`, 3 skills, `harnesses: ["hermes"]`), each
   pinned to a full 40-char SHA resolved with `git ls-remote`; plus
   `buzz-external-agents` as `local: true` with `hosts` = this Pi's hostname.
   Check: `python3 -c` script asserting every non-local entry has a 40-hex `ref`.
2. `HOME=$(mktemp -d) python3 scripts/agents-sync.py fetch` populates
   `$HOME/.agents/skills` with all 29 non-local manifest skills, each containing
   `SKILL.md` and a `.managed-by-manifest` marker (source + SHA).
3. Second run is a no-op: no files modified (compare `find -newer` on a stamp
   file) and output says unchanged.
4. Fetch never overwrites a skill dir that lacks the marker (pre-create one,
   run, assert content untouched and a warning printed).
5. `.gitignore` per-skill AWS/herdr/cmux lines replaced by one rule that keeps
   fetched skills out of git while repo-owned skills stay tracked:
   `git check-ignore` true for a fetched skill path, false for
   `agents/.agents/skills/orchestrate/SKILL.md`.
6. Runs under Python 3.9 syntax (`python3 -m py_compile` plus no 3.10+
   constructs such as `match` or `X | Y` types).

### T2 - Linking: Hermes target + real-dir guard  (Sonnet)
Small but behavior-changing shell logic; not mechanical.

**Scope:** `Makefile` `skills` target only (or move its logic into
`agents-sync.py link` and have `make skills` call it - worker's choice, must
keep `make skills` working).
**Acceptance criteria:**
1. In a temp HOME with `~/.agents/skills/{a,b}` and `~/.claude/skills/b` as a
   **real directory**: `make skills` links `a` into claude, codex and hermes,
   leaves `~/.claude/skills/b` untouched (no `b/b` link inside it), prints a
   warning naming it, exits 0.
2. Links created in `~/.hermes/skills` only if `~/.hermes` exists.
3. Pruning removes dangling symlinks only; a real dir and a non-skill file in
   `~/.hermes/skills` survive.
4. Running twice produces no change.
5. Skills with `harnesses: [...]` in the manifest are linked only into those
   harnesses (the buzz group goes to hermes only).

### T3 - MCP generation  (Sonnet)
Six output formats with merge semantics; needs care, not design.

**Scope:** `manifest.json` `mcp` section, `agents-sync.py mcp`,
`opencode/.config/opencode/opencode.jsonc` (remove `mcp` block only).
**Manifest MCPs:** playwright, chrome-devtools, linear, firecrawl, tinyfish
(from current opencode.jsonc; linear/firecrawl/tinyfish `except: ["claude"]`),
aws-mcp (`uvx mcp-proxy-for-aws-cli==1.7.0 https://aws-mcp.us-east-1.api.aws/mcp --skip-auth`).
**Acceptance criteria:**
1. Temp HOME with fake config files for each harness containing one
   unmanaged MCP each: after `mcp`, each file contains exactly the applicable
   manifest MCPs plus the untouched unmanaged entry. Files: `~/.omp/agent/mcp.json`,
   `~/.cursor/mcp.json`, `~/.codex/config.toml` (`[mcp_servers.*]`, written
   without a TOML library: managed tables delimited by marker comments),
   `~/.config/opencode/opencode.json`.
2. Claude and Hermes go through their CLIs (`claude mcp add-json --scope user`,
   `hermes config set`); with `--dry-run` the exact commands are printed and
   nothing runs. Hermes never writes `config.yaml` directly.
3. Names the sync previously wrote and later dropped from the manifest are
   removed (state in `~/.cache/dotfiles-skills/state.json`); unmanaged names
   never are.
4. Idempotent: second run changes no file (mtime check) and issues no CLI
   add/remove (dry-run output empty of mutations).
5. Claude receives no linear/firecrawl/tinyfish entry.
6. `opencode.jsonc` still parses (strip comments, `json.loads`) and has no
   `mcp` key; `git diff` touches only that block.
7. `git grep -nE '(sk|pk|ghp|xox)[-_][A-Za-z0-9]{10,}'` over changed files: no hits.

### T4 - Plugins step + doctor drift report  (Sonnet)
**Scope:** `manifest.json` `plugins`, `agents-sync.py plugins`,
`scripts/doctor.sh` (new drift section, may call `agents-sync.py --check`).
**Acceptance criteria:**
1. `plugins --dry-run` prints `claude plugin marketplace add` / `claude plugin
   install` only for marketplaces/plugins missing from a fake
   `~/.claude/plugins/installed_plugins.json`; aws-core is not in `enabled`.
2. Doctor drift section, in a temp HOME, reports each of: an unmanaged skill
   dir in `~/.agents/skills`; a manifest skill missing; a marker SHA differing
   from the manifest; a real dir at a link target; an unmanaged MCP entry in
   omp's `mcp.json`; a manifest MCP missing. Each fixture produces its line.
3. A host-restricted `local` skill is not reported on its host, and is not
   reported as missing elsewhere.
4. Drift is reported as `WARN` (doctor's exit code unaffected by drift alone);
   existing doctor checks still pass on this machine.

### T5 - Clean-room verification + review + migration list  (Opus, orchestrator)
1. Docker (`debian:bookworm` + git/python3/make/stow): clone the branch, run
   `make install`-equivalent with stubbed harness dirs; spec criteria 1, 4, 5,
   6, 7 verified.
2. `code-reviewer` (sonnet) over the full branch diff against spec + plan.
3. Write the owner's migration command list (spec "One-time migration"):
   removing real-dir AWS copies, `claude plugin disable aws-core`, uninstalling
   duplicate superpowers, removing now-managed unmanaged MCPs, replacing the
   copied Buzz skills in `~/.hermes/skills`. Commands only, not run.

## Out of scope (report, don't fix)
Installing harnesses, OAuth logins, Hermes bundled skills, `~/.buzz`, the
zoxide warning in shell startup, `templates/agent-permissions/__pycache__/`.
