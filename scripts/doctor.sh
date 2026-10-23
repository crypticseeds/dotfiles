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

# 2. ~/.agents must route into the repo. Stow links the directory itself when
#    ~/.agents did not pre-exist, or its contents when it did; both are valid,
#    so check the canonical file rather than the directory.
got=$(readlink -f "$HOME/.agents/AGENTS.md" 2>/dev/null || true)
if [ "$got" = "$want" ]; then echo "OK    ~/.agents"; else echo "FAIL  ~/.agents/AGENTS.md -> ${got:-missing}"; fail=1; fi

# 3. No dangling links in the skill farms
for d in "$HOME/.agents/skills" "$HOME/.claude/skills" "$HOME/.codex/skills" \
         "$HOME/.hermes/skills"; do
  [ -d "$d" ] || continue
  bad=$(find -L "$d" -maxdepth 1 -type l 2>/dev/null)
  if [ "$d" = "$HOME/.hermes/skills" ]; then
    # hermes owns its dir: only links into ~/.agents/skills are ours (as prune does)
    ours=""
    for l in $bad; do
      case "$(readlink "$l")" in
        */.agents/skills/*) ours="$ours$l
" ;;
      esac
    done
    ours=${ours%?}
    if [ -n "$ours" ]; then echo "WARN  dangling links in $d:"; echo "$ours"; fi
  elif [ -n "$bad" ]; then echo "FAIL  dangling links in $d:"; echo "$bad"; fail=1; fi
done

# 4. opencode config + agents must parse. v1: `agent list` fails on a bad config. v2 has no
#    `agent list`, and `debug agents` exits 0 even when a config or agent file is rejected (it just
#    drops it), so check that every agent in the repo is actually loaded. v2 answers from its
#    background service: it prints [] while the service is still starting, and it reads config at
#    start, so edits show up after `opencode service restart`.
if command -v opencode >/dev/null 2>&1; then
  case "$(opencode --version 2>/dev/null)" in
    *v2.*|2.*)
      tries=0
      while loaded=$(opencode debug agents 2>/dev/null); [ "$loaded" = "[]" ] && [ "$tries" -lt 15 ]; do
        tries=$((tries + 1)); sleep 1
      done
      missing=""
      for f in "$repo"/opencode/.config/opencode/agent/*.md; do
        id=$(basename "$f" .md)
        printf '%s' "$loaded" | grep -q "\"id\": *\"$id\"" || missing="$missing $id"
      done
      if [ -z "$missing" ]; then echo "OK    opencode agents parse"
      else echo "FAIL  opencode agents not loaded:$missing (opencode's log names the rejected file; restart the service after fixing)"; fail=1; fi ;;
    *)
      if opencode agent list >/dev/null 2>&1; then echo "OK    opencode agents parse"; else echo "FAIL  opencode agents do not parse"; fail=1; fi ;;
  esac
fi

# 5. No credential files inside the repo
creds=$(find "$repo" \( -name auth.json -o -name '*.credentials.json' -o -name '.env' \) -not -path '*/node_modules/*' 2>/dev/null)
if [ -n "$creds" ]; then echo "FAIL  credential files inside repo:"; echo "$creds"; fail=1; fi

# 6. Drift: skills, MCP servers and plugins vs the manifest (report only, never fails)
echo "-- Drift"
python3 -B "$repo/scripts/agents-sync.py" check || true

[ "$fail" = 0 ] && echo "doctor: all checks passed"
exit "$fail"
