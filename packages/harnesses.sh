#!/usr/bin/env sh
# AI harness installers. Every block is guarded by command -v, so this is
# idempotent and safe to rerun. On macOS, opencode and codex come from the
# Brewfile; these guards simply skip them.
set -u

have() { command -v "$1" >/dev/null 2>&1; }

# opencode - https://opencode.ai
have opencode || curl -fsSL https://opencode.ai/install | bash

# Claude Code - https://claude.ai/code
have claude || curl -fsSL https://claude.ai/install.sh | bash

# Codex CLI (needs node/npm; Brewfile installs node@24 + npm section on macOS)
if ! have codex && have npm; then npm install -g @openai/codex; fi

# Cursor CLI
have cursor-agent || curl -fsS https://cursor.com/install | bash

# pi coding agent
if ! have pi && have npm; then npm install -g --ignore-scripts @earendil-works/pi-coding-agent; fi

# herdr - no public one-line installer; install manually if missing
have herdr || echo "NOTE: herdr not installed - install it manually (https://github.com/ogulcancelik/herdr)"

# herdr agent integrations (hook scripts + wiring; versioned and updated by herdr)
if have herdr; then
  for t in claude codex cursor opencode; do
    herdr integration install "$t" >/dev/null 2>&1 || true
  done
fi

exit 0
