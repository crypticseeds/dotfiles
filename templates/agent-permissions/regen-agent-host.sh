#!/usr/bin/env bash
# Regenerate the Pi's (agent host) Claude settings for aws-platform. Always use this script there:
# a plain generate.py run drops --agent-host and the enabled .mcp.json servers.
#   bash regen-agent-host.sh [OUTPUT]   (default: ~/REPOS/aws-platform/.claude/settings.local.json)
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
out="${1:-$HOME/REPOS/aws-platform/.claude/settings.local.json}"
if ! python3 "$here/generate.py" --check; then
  echo "regen-agent-host: generate.py --check failed, nothing written" >&2
  exit 1
fi
python3 "$here/generate.py" --claude-out "$out" --os linux --agent-host \
  --mcpjson-server aws --mcpjson-server eks
