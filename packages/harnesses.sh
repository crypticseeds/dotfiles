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
# npm_config_prefix: distro npm defaults its global prefix to /usr/local
# (root-owned); install into ~/.local instead - its bin is on PATH via the
# stowed zshrc.
if ! have codex && have npm; then npm_config_prefix="$HOME/.local" npm install -g @openai/codex; fi

# Cursor CLI
have cursor-agent || curl -fsS https://cursor.com/install | bash

# pi coding agent
if ! have pi && have npm; then npm_config_prefix="$HOME/.local" npm install -g --ignore-scripts @earendil-works/pi-coding-agent; fi

# herdr (terminal multiplexer / agent runtime) - https://herdr.dev
# On macOS the Brewfile installs it; this guard covers Linux and skips if present.
have herdr || curl -fsSL https://herdr.dev/install.sh | sh

# herdr agent integrations (hook scripts + wiring; versioned and updated by herdr)
if have herdr; then
  for t in claude codex cursor opencode; do
    herdr integration install "$t" >/dev/null 2>&1 || true
  done
fi

exit 0
