#!/usr/bin/env sh
# AI harness installers. Every block is guarded by command -v, so this is
# idempotent and safe to rerun. On macOS, opencode and codex come from the
# Brewfile; these guards simply skip them.
set -u

# Installers put the harness CLIs here; make the `have` checks see them.
export PATH="$HOME/.local/bin:$HOME/.opencode/bin:$PATH"

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

# omp (oh-my-pi) - https://github.com/can1357/oh-my-pi
have omp || curl -fsSL https://omp.sh/install | sh

# herdr (terminal multiplexer / agent runtime) - https://herdr.dev
# On macOS the Brewfile installs it; this guard covers Linux and skips if present.
have herdr || curl -fsSL https://herdr.dev/install.sh | sh

exit 0
