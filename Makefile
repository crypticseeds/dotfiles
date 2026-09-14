# Dotfiles deployment. `make install` auto-detects the OS and stows everything.
# `make setup` (= shell + nvim) installs dependencies too: use it on a fresh
# machine where you want a working shell and editor, not the whole toolbox.
#
# ORDER IS LOAD-BEARING: `agents` must stow before the tool packages and
# `skills` - the per-tool shim layer resolves through ~/.agents.
#
# TOOLS are stowed with --no-folding so runtime state (sessions, auth, caches,
# node_modules, logs) stays in the real ~/.claude, ~/.codex, ~/.config/herdr
# etc. and never enters the repo. `agents` deliberately folds so new skills
# installed into ~/.agents/skills land directly in the repo.

COMMON    := zsh nvim starship wezterm
TOOLS     := claude codex cursor opencode pi herdr
MACONLY   := hammerspoon aerospace sketchybar
LINUXONLY := hyprland niri
MINIMAL   := zsh starship

UNAME := $(shell uname -s)
STOW  := stow -v -t $(HOME)

# Printed after a restow. Make cannot reload the calling shell itself: every
# recipe line runs in its own subshell, so `exec zsh` here would replace that
# subshell, not your terminal. Remind instead, and let you pick the moment.
reload-hint = printf '\nRestow complete. Run "exec zsh" to load the changes in this shell.\n'

.PHONY: install mac linux minimal restow restow-mac restow-linux delete tmux-on tmux-off skills doctor setup shell nvim

install:
ifeq ($(UNAME),Darwin)
	$(MAKE) mac
else
	$(MAKE) linux
endif

mac:
	$(STOW) agents
	$(STOW) $(COMMON) $(MACONLY)
	$(STOW) --no-folding $(TOOLS)
	$(MAKE) skills
	$(MAKE) doctor

linux:
	$(STOW) agents
	$(STOW) $(COMMON) $(LINUXONLY)
	$(STOW) --no-folding $(TOOLS)
	$(MAKE) skills
	$(MAKE) doctor

# Headless servers (the DNS Pi and friends): shell + prompt, nothing else.
# Deliberately skips agents, TOOLS and doctor - doctor only validates AI harness
# links, which these hosts are not meant to have. -R so it is safe to re-run.
minimal:
	$(STOW) -R $(MINIMAL)

restow:
ifeq ($(UNAME),Darwin)
	$(MAKE) restow-mac
else
	$(MAKE) restow-linux
endif

restow-mac:
	$(STOW) -R agents $(COMMON) $(MACONLY)
	$(STOW) -R --no-folding $(TOOLS)
	$(MAKE) skills
	@$(reload-hint)

restow-linux:
	$(STOW) -R agents $(COMMON) $(LINUXONLY)
	$(STOW) -R --no-folding $(TOOLS)
	$(MAKE) skills
	@$(reload-hint)

delete:
	$(STOW) -D agents $(COMMON) $(MACONLY) $(LINUXONLY) $(TOOLS) tmux

# tmux is opt-in, not default (herdr is the daily multiplexer). The config,
# keybindings and plugins stay in the repo; these targets flip deployment.
# The binary is not auto-installed: brew install tmux / sudo dnf install tmux.
tmux-on:
	$(STOW) tmux
	@[ -d tmux/.config/tmux/plugins/tpm ] || git clone --depth 1 https://github.com/tmux-plugins/tpm tmux/.config/tmux/plugins/tpm
	@command -v tmux >/dev/null || printf 'NOTE: tmux binary not installed (brew install tmux / sudo dnf install tmux)\n'
	@printf 'tmux config deployed. prefix + I inside tmux installs any missing plugins.\n'

tmux-off:
	$(STOW) -D tmux

# Per-skill links for harnesses that do not read ~/.agents/skills natively.
# pi and opencode read it natively and need nothing here. Absolute links are
# intentional (regenerated per machine, never committed). The find pass prunes
# links whose skill was deleted from the repo.
skills:
	@for t in $(HOME)/.claude/skills $(HOME)/.codex/skills; do \
		mkdir -p $$t; \
		find $$t -maxdepth 1 -type l ! -exec test -e {} \; -delete; \
		for s in $(HOME)/.agents/skills/*/; do \
			ln -sfn "$${s%/}" "$$t/$$(basename $$s)"; \
		done; \
	done

doctor:
	@sh scripts/doctor.sh

# Working environment on any machine: shell + Neovim with every dependency
# they need to function. `make setup` is the one-command version.
setup: shell nvim

# Shell: zsh, starship, plugins and the tools behind the aliases (eza, zoxide,
# fzf, bat, direnv), then stow zsh + starship. A pre-existing plain
# ~/.zshrc is kept as ~/.zshrc.pre-dotfiles so stow does not fail on it.
shell:
	sh scripts/shell.sh
	@if [ -f $(HOME)/.zshrc ] && [ ! -L $(HOME)/.zshrc ]; then mv $(HOME)/.zshrc $(HOME)/.zshrc.pre-dotfiles; echo "moved ~/.zshrc to ~/.zshrc.pre-dotfiles"; fi
	$(STOW) -R zsh starship
	@printf '\nShell ready. Run "exec zsh" to load it.\n'

# Neovim, end to end: OS dependencies (nvim 0.12+, tree-sitter-cli, ripgrep,
# go, node, lazygit), stow the config, download plugins. LSP servers and
# parsers install themselves on the first interactive launch (Mason).
# PATH: the script may have just installed nvim into ~/.local/bin.
nvim: export PATH := $(HOME)/.local/bin:$(PATH)
nvim:
	sh scripts/nvim.sh
	$(STOW) -R nvim
	nvim --headless "+Lazy! sync" +qa
	@printf '\nNeovim ready. First launch installs LSP servers and parsers (about a minute); :checkhealth to verify.\n'
