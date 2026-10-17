# niri desktop (Fedora VM)

niri (scrollable tiling) with the [Noctalia 5](https://github.com/noctalia-dev/noctalia)
shell, set up for the Fedora VM on VMware Fusion. Ghostty is the terminal, Zed the
editor, Firefox the browser, Strata the file manager.

| Piece | Provided by | Config |
|---|---|---|
| Compositor, window rules, keys | niri | `niri/.config/niri/config.kdl` |
| Bar, launcher, notifications, lock screen, OSD, polkit agent, screenshots, wallpaper, session menu | Noctalia (`noctalia` package) | `noctalia/.config/noctalia/config.toml` |
| Palette (Gruvbox Hard, matches Zed and Neovim) | Noctalia custom palette | `noctalia/.config/noctalia/palettes/Gruvbox Hard.json` |
| Terminal | Ghostty (`scottames/ghostty` COPR) | `ghostty/.config/ghostty/config`, default via `ghostty/.config/xdg-terminals.list` |
| Alt+Tab switcher | niri's built-in recent-windows switcher | none needed |

## Setup

```sh
make niri
```

`scripts/niri.sh` enables the ghostty COPR, installs `packages/niri.txt`, then the
per-user apps the binds launch: Zed (zed.dev installer), Strata (checksum-verified
release archive into `~/.local/bin`; its own installer only runs unattended on Arch) and
Herdr UI (herdrui.dev installer, needs herdr from `packages/harnesses.sh`). It sets the
Papirus-Dark icon theme and creates `~/Pictures/Wallpapers`. `make niri` then
stows niri, ghostty and noctalia (`--no-folding`) and runs `niri validate`. Rerunning
only installs what is missing. `bootstrap.sh` runs the same script on Fedora.

Log out, click the gear on the GDM password screen, pick **Niri**, log in. GNOME stays
installed as a fallback session.

niri gets its PATH from the systemd user manager (`/usr/local/bin:/usr/bin`), not from
zsh. `niri/.config/environment.d/10-local-bin.conf` adds `~/.local/bin` so binds for
per-user installs (Zed, Strata) work. It is read at login.

### Generated files (not in the repo)

Noctalia renders the active palette into files next to the stowed configs, which is why
these packages are stowed `--no-folding`:

- `~/.config/niri/noctalia.kdl` (border, tab, switcher colors; `config.kdl` includes it last)
- `~/.config/ghostty/themes/noctalia` (`theme = noctalia` in the Ghostty config)
- `~/.config/gtk-3.0/noctalia.css`, `~/.config/gtk-4.0/noctalia.css` (+ an `@import` in each
  `gtk.css`, and GTK3 switched to `adw-gtk3-dark`). These also apply in the GNOME session.

Noctalia's templates only touch `config.kdl` / the Ghostty config if the include /
`theme = noctalia` line is missing: keep those lines.

Changes made in Noctalia's Settings window go to `~/.local/state/noctalia/settings.toml`,
which overrides `config.toml`. Copy anything worth keeping into `config.toml`.

## VMware Fusion specifics

- **Cursor**: `debug { disable-cursor-plane }` in `config.kdl`. vmwgfx's hardware cursor
  plane leaves the pointer invisible or offset; niri draws it in software instead.
  Remove that line on real hardware.
- **Resolution**: `output "Virtual-1" { mode "1920x1080"; scale 1 }`. The virtual GPU also
  advertises 4096x2160; without the pin niri may pick it. Resizing the Fusion window does
  not change the mode. Check names and modes with `niri msg outputs`.
- **Super key**: Super is the Mac's Cmd key. macOS keeps its global shortcuts (Cmd+Tab,
  Cmd+Space, ...) unless Fusion > Settings > Keyboard & Mouse > Mac Host Shortcuts >
  **Enable Mac OS Host Keyboard Shortcuts** is unticked. That switch is all-or-nothing and
  applies in Single Window and Full Screen view; the same pane picks which Cmd key
  (either, left, right) maps to Super.
- **Blur is off** (niri layer rule + `compositor_blur = false`): the virtual GPU renders
  every pass. Noctalia runs on the hardware renderer (`SVGA3D`, OpenGL ES 3.1).

## Workspaces

`1 term`, `2 code`, `3 web` always exist; `Mod+4`.. are created on demand.

- Zed opens on **code** and Firefox on **web**, filling the workspace. Ghostty opens
  wherever you are.
- **Side by side**: open the second app on the same workspace (e.g. `Mod+2` then
  `Mod+Return` for a terminal next to Zed), then `Mod+F` on the full-width window: both
  are half width. `Mod+R` cycles 1/3, 1/2, 2/3, full on the focused column.
- Move a window elsewhere with `Mod+Ctrl+<n>` (e.g. Firefox next to the terminal:
  `Mod+Ctrl+1`).
- New windows open at half width, starting from the left edge.
- The Herdr GUI (`Mod+A`) opens maximized, filling its workspace; `Mod+F` toggles it.
- **Floating**: Strata and Nautilus always float, centered. `Mod+V` floats or tiles any
  window, `Mod+Shift+V` jumps focus between the floating and tiled layers.
- `Mod+O` shows the overview of all workspaces.

## Keys

`Mod` is Super (Cmd). `Mod+Shift+/` shows the list on screen.

| Keys | Action |
|---|---|
| `Mod+Return` / `Mod+T` | Ghostty |
| `Mod+B` / `Mod+Z` / `Mod+E` / `Mod+A` | Firefox / Zed / Strata / Herdr GUI (on demand, never autostarted) |
| `Mod+Space` / `Mod+D` | App launcher (`/calc`, `/emo`, `/wall`, `/win` prefixes) |
| `Mod+S` | Control center (audio, network, notifications, calendar) |
| `Mod+Shift+Comma` | Noctalia settings (palette, bar, wallpaper) |
| `Mod+Shift+N` | Do not disturb |
| `Super+Alt+L` | Lock screen |
| `Mod+Shift+E` | Session menu (log out, reboot, power off); `Ctrl+Alt+Delete` quits niri |
| `Alt+Tab` | Recent windows switcher |
| `Mod+Shift+S` | Screenshot region, annotate, then `Ctrl+C` copy / `Ctrl+S` save |
| `Mod+Ctrl+S` / `Mod+Alt+S` | Screenshot screen / window (clipboard + `~/Pictures/Screenshots`) |
| `Mod+Q` | Close window |
| `Mod+H/J/K/L`, arrows | Focus left/down/up/right; add `Ctrl` to move |
| `Mod+1..9` / `Mod+Ctrl+1..9` | Go to / move column to workspace |
| `Mod+Tab` | Previous workspace |
| `Mod+F` / `Mod+Shift+F` / `Mod+M` | Maximize column / fullscreen / maximize to edges |
| `Mod+R`, `Mod+Minus`, `Mod+Equal` | Column width presets, -10%, +10% |
| `Mod+[` / `Mod+]` | Stack window into / out of the neighboring column |
| `Mod+W` | Tabbed column |
| `Mod+Escape` | Release shortcuts an app is holding |

## Palette

Gruvbox Hard is the default. Kanagawa and Catppuccin are Noctalia built-ins. Switch in
Settings -> Theme, or:

```sh
noctalia msg color-scheme-set builtin Kanagawa
noctalia msg color-scheme-set builtin Catppuccin
noctalia msg color-scheme-set custom "Gruvbox Hard"
```

niri borders, Ghostty, Noctalia and GTK apps recolor live. The switch is stored in
`settings.toml`; to change the default for every machine, edit `[theme]` in `config.toml`.

## Wallpaper

Put images in `~/Pictures/Wallpapers`, then pick one with the launcher (`/wall`) or in
Settings -> Wallpaper. With none set, the desktop is the palette's surface color.

## Troubleshooting

- niri config errors: `niri validate`; live log: `journalctl --user -b -u niri`.
- A bind does nothing but the command works in a terminal: the binary is outside the
  session PATH. Check with `systemctl --user show-environment | grep PATH`.
- Noctalia: `noctalia config validate`, log at `~/.cache/noctalia/noctalia.log`,
  restart with `pkill -x noctalia; noctalia --daemon`.
- Do not install mako, dunst or swaync: they compete with Noctalia for notifications.
