# Dotfiles deployment. `make install` auto-detects the OS.
#
# ORDER IS LOAD-BEARING: `agents` must stow before the tool packages and
# `skills` - the per-tool shim layer resolves through ~/.agents.
#
# TOOLS are stowed with --no-folding so runtime state (sessions, auth, caches,
# node_modules, logs) stays in the real ~/.claude, ~/.codex, ~/.config/herdr
# etc. and never enters the repo. `agents` deliberately folds so new skills
# installed into ~/.agents/skills land directly in the repo.

COMMON  := zsh nvim tmux starship
TOOLS   := claude codex cursor opencode pi herdr
MACONLY := wezterm hammerspoon aerospace sketchybar

UNAME := $(shell uname -s)
STOW  := stow -v -t $(HOME)

.PHONY: install mac linux restow restow-mac restow-linux delete skills doctor

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
	$(STOW) $(COMMON)
	$(STOW) --no-folding $(TOOLS)
	$(MAKE) skills
	$(MAKE) doctor

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

restow-linux:
	$(STOW) -R agents $(COMMON)
	$(STOW) -R --no-folding $(TOOLS)
	$(MAKE) skills

delete:
	$(STOW) -D agents $(COMMON) $(MACONLY) $(TOOLS)

# Per-skill links for harnesses that do not read ~/.agents/skills natively.
# pi and opencode read it natively and need nothing here. Absolute links are
# intentional (regenerated per machine, never committed). The find pass prunes
# links whose skill was deleted from the repo.
skills:
	@for t in $(HOME)/.claude/skills $(HOME)/.codex/skills; do \
		mkdir -p $$t; \
		find -L $$t -maxdepth 1 -type l -delete; \
		for s in $(HOME)/.agents/skills/*/; do \
			ln -sfn "$${s%/}" "$$t/$$(basename $$s)"; \
		done; \
	done

doctor:
	@sh scripts/doctor.sh
