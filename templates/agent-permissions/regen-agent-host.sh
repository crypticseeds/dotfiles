#!/usr/bin/env bash
# Regenerate the Pi's (agent host) Claude settings for aws-platform. Always use this script there:
# a plain generate.py run drops --agent-host and the enabled .mcp.json servers.
#   bash regen-agent-host.sh [OUTPUT]   (default: ~/REPOS/aws-platform/.claude/settings.local.json)
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
out="${1:-$HOME/REPOS/aws-platform/.claude/settings.local.json}"
# Mac and the Pi share the dotfiles repo: rebase onto upstream first, so the rules come from the
# latest commit. The generate.py calls below then skip their own pull.
if ! git -C "$here" pull --rebase --autostash; then
  echo "regen-agent-host: git pull --rebase failed in $here, nothing written" >&2
  exit 1
fi
export AGENT_PERMS_PULLED=1
if ! python3 "$here/generate.py" --check; then
  echo "regen-agent-host: generate.py --check failed, nothing written" >&2
  exit 1
fi
python3 "$here/generate.py" --claude-out "$out" --os linux --agent-host \
  --mcpjson-server aws --mcpjson-server eks
