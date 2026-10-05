#!/usr/bin/env bash
# Regenerate and install the Pi's (agent host) permission policy for Claude, opencode and omp.
# Always use this script there: a plain generate.py run drops --agent-host and the enabled .mcp.json
# servers. Run it yourself: it needs sudo, agents cannot.
#   bash regen-agent-host.sh [DIR]   default: install
#     Claude   -> /etc/claude-code/managed-settings.json   (root-owned, every project)
#     opencode -> /etc/opencode/opencode.json              (root-owned managed config, every project)
#     omp      -> ~/.omp/agent/config.yml                  (merged: your other omp settings are kept)
#     git-push-to -> /usr/local/bin (root-owned): how agents push a repo other than their own
#   with DIR: write the three files into DIR instead, without sudo, for a dry run
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
dir="${1:-}"
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
tmp="$(mktemp -d)"
trap 'rm -f "$tmp"/*; rmdir "$tmp"' EXIT
python3 "$here/generate.py" --claude-out "$tmp/claude.json" --os linux --agent-host \
  --mcpjson-server aws --mcpjson-server eks
omp_target="${dir:-$HOME/.omp/agent}/config.yml"
# omp has no managed config: merge the policy keys into the user's file, keeping everything else
python3 - "$here/agent-host/omp-config.yml" "$HOME/.omp/agent/config.yml" "$tmp/omp.yml" <<'PY'
import os, sys, yaml
policy_path, user_path, out_path = sys.argv[1:]
policy = yaml.safe_load(open(policy_path))
user = yaml.safe_load(open(user_path)) if os.path.exists(user_path) else {}
user = user or {}
for key in ("secrets", "bash"):
    user[key] = policy[key]
user.setdefault("tools", {})["approvalMode"] = policy["tools"]["approvalMode"]
header = "".join(l for l in open(policy_path) if l.startswith("#"))
open(out_path, "w").write(header + yaml.safe_dump(user, sort_keys=False))
PY
if [ -n "$dir" ]; then
  mkdir -p "$dir"
  cp "$tmp/claude.json" "$dir/managed-settings.json"
  cp "$here/agent-host/opencode.json" "$dir/opencode.json"
  cp "$tmp/omp.yml" "$omp_target"
  echo "regen-agent-host: wrote $dir/{managed-settings.json,opencode.json,config.yml}"
else
  sudo install -D -m 0644 -o root -g root "$tmp/claude.json" /etc/claude-code/managed-settings.json
  sudo install -D -m 0644 -o root -g root "$here/agent-host/opencode.json" /etc/opencode/opencode.json
  sudo install -D -m 0755 -o root -g root "$here/bin/git-push-to" /usr/local/bin/git-push-to
  install -D -m 0600 "$tmp/omp.yml" "$omp_target"
  echo "regen-agent-host: installed Claude, opencode and omp policies (restart their sessions)"
fi
