# Neovim quick reference

The keys you need in the first week. Leader is `Space`. Press `Space` and wait
half a second to see what can follow, or `Space fk` to search every keymap.

Saving (`:w`) formats the file and fixes imports (Go: goimports + gofumpt,
Python: ruff). LSP servers install themselves on first launch via `:Mason`.

## Files and moving around

| Do | Keys |
|---|---|
| open a file by name | `Space ff`, type a few letters, `Enter` |
| find text in the project | `Space fg` |
| file tree, opens on the current file | `Space e` - `Enter` opens, `q` closes it |
| tree <-> file | `Ctrl-h` / `Ctrl-l` |
| switch between the last two files | `Ctrl-^` |
| open buffers / recent files | `Space fb` / `Space fr` |
| save / close this file / quit | `:w` / `Space bd` / `:qa` |
| split vertically / close split | `Space sv` / `Space sx` |

## Reading code

| Do | Keys |
|---|---|
| docs for the thing under cursor | `K` |
| go to definition / come back | `gd` / `Ctrl-o` |
| all references | `grr` |
| implementations of an interface | `gri` |
| outline of the file | `gO` |
| next / previous error | `]d` / `[d` - `Space cd` shows the full message |
| all problems in the project | `Space fd` |
| rename symbol everywhere | `grn` |
| code action: add import, fill struct, fix | `gra` |
| toggle inlay hints | `Space uh` |

## Editing

| Do | Keys |
|---|---|
| change inside quotes / parens / word | `ci"` `ci(` `ciw` - `d` instead of `c` deletes, `v` selects |
| change a function argument | `cia` |
| jump out of the brackets you are typing in | `Tab` (insert mode), `Shift-Tab` back in |
| accept completion | `Enter` or `Tab` while the menu is open, `Ctrl-e` dismisses |
| split a one-line struct or call onto lines, or join back | `Space m` (`Space M` nested too) |
| move selected lines | `V` to select, then `J` / `K` |
| indent / dedent selection | `>` / `<` |
| undo / redo / history tree | `u` / `Ctrl-r` / `Space u` |
| repeat last change | `.` |
| format now / toggle format on save | `Space cf` / `Space uf` |

## Search and git

| Do | Keys |
|---|---|
| search in file, next / previous match | `/word Enter`, `n` / `N` - shows `[2/7]` |
| search the word under cursor | `*` |
| replace the word under cursor in the file | `Space rw` |
| clear highlights | `Esc` |
| next / previous changed hunk | `]h` / `[h` |
| preview hunk / blame line / stage hunk | `Space hp` / `Space hb` / `Space hs` |
| lazygit | `Space lg` |

## Markdown

| Do | Keys |
|---|---|
| toggle rendered view | `Space um` |

## Maintenance

| Do | Command |
|---|---|
| update plugins | `:Lazy update` |
| LSP servers and formatters | `:Mason` |
| health check | `:checkhealth` |
| fresh machine | `make setup` in `~/dotfiles` |
