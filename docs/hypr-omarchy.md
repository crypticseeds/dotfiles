# hypr-omarchy: Omarchy-style Hyprland session (Fedora)

A second Hyprland session for comparing with the regular one. Nothing in
`~/.config/hypr` changes; this session lives in `~/.config/hypr-omarchy`.

It runs [Omarchy](https://github.com/omacom/omarchy)'s Hyprland defaults (branch
`quattro`, pinned commit) and the Omarchy shell (Quickshell): top bar,
notifications, launcher and menus, OSD, clipboard, polkit prompts, idle timer and
the dock. Preinstalled app/webapp bindings, dictation, the agent console, reminders,
weather and media controls are off: this is a dev session.

## Set up

```sh
make hypr-omarchy   # checks tools (quickshell >= 0.3.1), prints any `dnf install` needed
```

`make hypr-omarchy`:

- stows `~/.config/hypr-omarchy` and `~/.local/bin/hypr-omarchy`;
- checks out Omarchy at the pinned commit into `~/.local/share/omarchy`;
- seeds `~/.config/omarchy/shell.json` (bar, dock pins: WezTerm, Strata, Nautilus, Firefox, Zed);
- installs the `gruvbox-hard-seeds` theme (Omarchy's gruvbox on the darker backgrounds
  of the Zed and Neovim gruvbox themes) and applies it to Hyprland and the shell only;
  `THEME=kanagawa make hypr-omarchy` picks an Omarchy theme instead (first setup only);
- installs JetBrainsMono Nerd Font into `~/.local/share/fonts`;
- installs the [Strata](https://github.com/lgse/strata) file manager into
  `~/.local/bin/strata` (checksum-verified release, plus a launcher entry; it
  updates itself from Settings -> Updates) and lists any missing GTK4 libraries;
- runs `Hyprland --verify-config`.

Rerunning it never overwrites a file you changed. `make hypr-omarchy-off` unstows it.

Start it from a TTY: `hypr-omarchy` (the regular session stays `start-hyprland`).
It runs under uwsm because Omarchy launches every app with `uwsm-app`.

## Keys you'll use

| Keys | Does |
|---|---|
| Super + Return | Terminal (WezTerm, in the focused terminal's directory) |
| Super + W / Super + Q | Close window |
| Super + C / V / X / A | Copy / paste / cut / select all (terminal-aware) |
| Super + T | Float / tile window |
| Super + F, Super + Alt + F | Fullscreen, full width |
| Super + L, Super + Alt + L | Cycle this workspace: tiling -> scrolling -> floating + dock |
| Super + M | Minimize to the dock (floating workspaces) |
| Super + Alt + Space | App grid |
| Super + Space | Omarchy menu |
| Super + K | Every binding, searchable |
| Super + arrows, Super + Shift + arrows | Focus, swap |
| Super + 1-0, Super + Shift + 1-0 | Workspace, move window to workspace |
| Super + S | Scratchpad |
| Super + G | Group windows |
| Super + Ctrl + L | Lock |
| Super + Escape | Lock / suspend / log out / shut down |
| Print | Screenshot a region (clipboard + ~/Pictures/Screenshots) |
| Super + Shift + F (+ Alt: in the focused terminal's directory) | Strata, or Nautilus if Strata isn't installed |
| Super + Ctrl + V | Clipboard history |

Change keys in `~/.config/hypr-omarchy/bindings.lua` (`o.bind`, `o.rebind`,
`hl.unbind`); a floating default for new workspaces:
`omarchy-hyprland-workspace-layout-default floating`.

## Omarchy parts replaced with standard tools

| Omarchy | Here | Why |
|---|---|---|
| Shell lock screen | hyprlock (`~/.config/hypr-omarchy/hyprlock.conf`) | Omarchy's lock PAM file includes Arch's `system-local-login`; on Fedora that risks a lock you can't unlock |
| `omasnap` screenshots | grim + slurp + wl-copy | omasnap is Omarchy-only |
| `omarchy-theme-set` at setup | only its template step, for Hyprland and the shell | the full command also rethemes terminals, editors, the browser, herdr and Claude |
| Titlebar plugin on floating windows | none: floating works without titlebars; Super + M and the dock still minimize/restore | the plugin must be rebuilt against every Hyprland update |
| First-run provisioning, post-boot hooks | not run | Arch/Omarchy-install specific |

The lock and screenshot replacements are scripts in `~/.config/hypr-omarchy/bin`,
which comes before Omarchy's `bin` on this session's PATH.

In Strata, turn on **Settings -> Appearance -> Follow Omarchy** to use this session's
theme. Strata stays out of the regular session: the default folder handler is not
changed.

## Known gaps

- Choosing another theme from the Omarchy menu runs the full `omarchy-theme-set`,
  which also rethemes other apps.
- The dock's "uninstall" and the system-update widget call pacman: they fail
  harmlessly (the update widget is not in the bar).
- `Super + K` reads key names for Lua-only bindings from `~/.config/hypr/hyprland.lua`
  (the regular session's file), so a few entries may show without a key.
- Tested on the Pi up to config load: the Lua chain against a stub of Hyprland's API,
  the setup script with stubs for the Fedora binaries (including a real Strata
  download and checksum check), the screenshot script. First real run is on Fedora.
