#!/usr/bin/env sh
# Health check: instruction links, skill farms, agent parse, no credentials in repo.
# Run via `make doctor` or directly any time drift is suspected.
set -u
repo=$(cd "$(dirname "$0")/.." && pwd)
fail=0

# 1. Every harness's global instructions must resolve to the canonical file
want="$repo/agents/.agents/AGENTS.md"
for f in "$HOME/.claude/CLAUDE.md" "$HOME/.codex/AGENTS.md" \
         "$HOME/.cursor/AGENTS.md" "$HOME/.config/opencode/AGENTS.md" \
         "$HOME/.pi/agent/AGENTS.md"; do
  got=$(readlink -f "$f" 2>/dev/null || true)
  if [ "$got" = "$want" ]; then echo "OK    $f"; else echo "FAIL  $f -> ${got:-missing}"; fail=1; fi
done

# 2. ~/.agents must route into the repo
got=$(readlink -f "$HOME/.agents" 2>/dev/null || true)
if [ "$got" = "$repo/agents/.agents" ]; then echo "OK    ~/.agents"; else echo "FAIL  ~/.agents -> ${got:-missing}"; fail=1; fi

# 3. No dangling links in the skill farms
for d in "$HOME/.agents/skills" "$HOME/.claude/skills" "$HOME/.codex/skills"; do
  [ -d "$d" ] || continue
  bad=$(find -L "$d" -maxdepth 1 -type l 2>/dev/null)
  if [ -n "$bad" ]; then echo "FAIL  dangling links in $d:"; echo "$bad"; fail=1; fi
done

# 4. opencode config + agents must parse
if command -v opencode >/dev/null 2>&1; then
  if opencode agent list >/dev/null 2>&1; then echo "OK    opencode agents parse"; else echo "FAIL  opencode agents do not parse"; fail=1; fi
fi

# 5. No credential files inside the repo
creds=$(find "$repo" \( -name auth.json -o -name '*.credentials.json' -o -name '.env' \) -not -path '*/node_modules/*' 2>/dev/null)
if [ -n "$creds" ]; then echo "FAIL  credential files inside repo:"; echo "$creds"; fail=1; fi

[ "$fail" = 0 ] && echo "doctor: all checks passed"
exit "$fail"
