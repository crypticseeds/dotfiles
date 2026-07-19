# Dotfiles repo instructions

This repo deploys configs to $HOME with GNU Stow. Each top-level directory is
a stow package whose contents mirror $HOME (see README.md for the layout).

## Rules

- Global AI instructions live in `agents/.agents/AGENTS.md` (deployed as
  `~/.agents/AGENTS.md` and read by every harness through symlinks). Edit that
  file for behavior changes; this file is only about working on the repo.
- Many files here are symlink targets for live tools. Editing a file in the
  repo changes the running system immediately - no deploy step needed for
  content changes.
- After ADDING or REMOVING files in a package, run `make restow`. After
  adding/removing a skill in `agents/.agents/skills/`, run `make skills`.
- Verify with `make doctor` after structural changes.
- Tool packages (claude, codex, cursor, opencode, pi, herdr) are stowed with
  `--no-folding` on purpose: never add runtime state (sessions, auth, caches,
  logs, node_modules, sqlite) to this repo, and never commit credentials.
  `.env` files and auth.json are expected to stay in $HOME only.
- opencode agents (`opencode/.config/opencode/agent/*.md`) use opencode
  frontmatter (mode/permission). Claude/Cursor subagents
  (`agents/.agents/subagents/`) use name/description/tools frontmatter. Do not
  copy files between the two formats mechanically - permission semantics
  differ.
- Package lists: `packages/Brewfile` (macOS), `packages/apt.txt` (Ubuntu),
  `packages/dnf.txt` (Fedora), `packages/harnesses.sh` (AI CLIs, guarded).
  Adding an app = one line in the right list.
- opencode config changes (opencode.jsonc, agent/, plugins/) require an
  opencode restart to take effect.
