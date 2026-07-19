# Dotfiles

Personal configuration for macOS and Linux, deployed with GNU Stow. One
source of truth for shell, editor, terminal, and AI harness config (Claude
Code, Codex, Cursor, opencode, pi).

## Fresh machine

```sh
# macOS
xcode-select --install
git clone git@github.com:crypticseeds/dotfiles.git ~/dotfiles
cd ~/dotfiles && sh scripts/bootstrap.sh

# Ubuntu / Debian / Fedora
sudo apt install -y git   # or: sudo dnf install -y git
git clone git@github.com:crypticseeds/dotfiles.git ~/dotfiles
cd ~/dotfiles && sh scripts/bootstrap.sh
```

`bootstrap.sh` detects the OS, installs packages (`packages/Brewfile` on
macOS, `packages/apt.txt` / `packages/dnf.txt` on Linux), installs any missing
AI harnesses (`packages/harnesses.sh`), backs up conflicting distro defaults,
runs `make install`, and clones TPM (tmux plugins themselves are gitignored -
press `prefix + I` inside tmux once to install them).

If stow hits a conflict it aborts safely without changing anything: move the
conflicting file out of the way and rerun `make install`.

Already provisioned? Just run:

```sh
make install    # auto-detects OS, stows everything, runs health check
```

## Make targets

| Target | What it does |
|---|---|
| `make install` | Stow everything for this OS + `skills` + `doctor` |
| `make restow` | Re-stow after adding/removing files in packages |
| `make delete` | Remove all managed symlinks (safe; only touches links) |
| `make skills` | Regenerate per-skill links for claude/codex |
| `make doctor` | Health check: links, skills, agents, credential scan |

## Layout

Each top-level directory is a stow package mirroring `$HOME`:

| Package | Deploys to | Notes |
|---|---|---|
| `agents/` | `~/.agents` | AI source of truth: AGENTS.md, skills, subagents |
| `claude/` `codex/` `cursor/` `opencode/` `pi/` | `~/.claude` etc. | Harness configs; stowed `--no-folding` so runtime state stays out of the repo |
| `zsh/` `nvim/` `tmux/` `starship/` `herdr/` | `~/.zshrc`, `~/.config/...` | Cross-platform |
| `wezterm/` `hammerspoon/` `aerospace/` `sketchybar/` | | macOS only |
| `packages/` `scripts/` | not stowed | Provisioning lists + bootstrap/doctor |
| `cursor-themes/` `zed/` | not stowed | Reference copies |

## AI harness config (one source of truth)

`agents/.agents/AGENTS.md` is the single global instruction file. Every
harness reads it through symlinks committed to this repo:

```
~/.claude/CLAUDE.md ─┐
~/.codex/AGENTS.md ──┤
~/.cursor/AGENTS.md ─┼──> agents/.agents/AGENTS.md
~/.config/opencode/AGENTS.md ─┤
~/.pi/agent/AGENTS.md ────────┘
```

- **Skills** live in `agents/.agents/skills/` (Agent Skills standard). pi and
  opencode read `~/.agents/skills` natively; `make skills` links them into
  claude/codex. Installing a new skill (e.g. `npx skills add ...`) writes
  through `~/.agents` straight into the repo - commit it.
- **Subagents**: `agents/.agents/subagents/` is shared by Claude Code and
  Cursor (same format). opencode agents live in
  `opencode/.config/opencode/agent/` (different frontmatter schema).
- **Per-project instructions** belong in each project's own `AGENTS.md`, not
  here - every harness picks those up natively.

## Adding things

- **An app config**: create `<pkg>/.config/<app>/...`, add `<pkg>` to the
  right group in the `Makefile` (`COMMON`, `TOOLS`, or `MACONLY`), run
  `make restow`.
- **A macOS app**: add a line to `packages/Brewfile`.
- **A Linux package**: add a line to `packages/apt.txt` / `packages/dnf.txt`.
- **A file to an existing package**: just add it, then `make restow`.

## Harness: Claude Code with Moonshot Kimi

After installing the Claude Code CLI, mark onboarding as complete:

```bash
node --eval "
   const homeDir = os.homedir();
   const filePath = path.join(homeDir, '.claude.json');
   if (fs.existsSync(filePath)) {
      const content = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
      fs.writeFileSync(filePath,JSON.stringify({ ...content, hasCompletedOnboarding: true }, 2), 'utf-8');
   } else {
      fs.writeFileSync(filePath,JSON.stringify({ hasCompletedOnboarding: true }), null, 'utf-8');
   }"
```
