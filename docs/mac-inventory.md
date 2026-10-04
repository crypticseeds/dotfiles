# Mac inventory

Everything installed on the Intel MacBook as of 2026-09-05 (macOS 15.7.9),
grouped by what it is and how it was installed. Restore order: Homebrew
(`brew bundle --file packages/Brewfile`), App Store, then the manual installs.

Legend for the install column: `brew` = in `packages/Brewfile`, `brew*` =
installable with brew but not yet in the Brewfile, `mas` = Mac App Store,
`manual` = downloaded installer, `npm`/`uv`/`go`/`curl` = language or vendor
installer. Restore hint in the last column.

## Terminal and shell

| Software | Install | Restore |
|---|---|---|
| WezTerm (primary terminal) | brew | `cask wezterm` |
| Ghostty | manual (brew* `ghostty`) | |
| cmux | manual (brew* `cmux`) | |
| iTerm2 | manual (brew* `iterm2`) | |
| Warp | manual (brew* `warp`) | |
| zsh + zsh-autosuggestions, zsh-syntax-highlighting | brew | |
| starship (prompt) | brew | |
| tmux | brew | plugins via tpm, `prefix + I` |
| herdr (agent workspace manager) | curl -> `~/.local/bin` | `packages/harnesses.sh` |
| direnv, zoxide, fzf, eza, bat, jq, glow, superfile | brew | |
| btop, htop, glances | brew (htop, glances not in Brewfile) | |
| just (task runner) | brew* | |
| hermit | brew* | |
| minicom, picocom (serial consoles), tftp-now | brew* | Raspberry Pi work |
| stow, gnupg, bash-completion@2 | brew | |

## Editors and IDEs

| Software | Install | Restore |
|---|---|---|
| Neovim 0.12 + config | brew + `make nvim` | LSP servers via Mason on first launch |
| Zed | manual (brew* `zed`) | config in `zed/` |
| Visual Studio Code | manual (brew* `visual-studio-code`) | 0 extensions |
| Sublime Text | manual (brew* `sublime-text`) | |
| GoLand, PyCharm, JetBrains Toolbox | manual (brew* `goland`, `pycharm`, `jetbrains-toolbox`) | Toolbox restores the IDEs |
| JetBrains Air (AI agent, `Air.app`) | manual | |
| Xcode + Command Line Tools | mas | `xcode-select --install` for CLT only |
| Texifier (LaTeX) | manual (brew* `texifier`) | |

## AI coding agents

| Software | Install | Restore |
|---|---|---|
| opencode | brew (`anomalyco/tap/opencode`) | config in `opencode/` |
| Claude Code (`claude`) + Claude desktop app | curl -> `~/.local/bin`; app manual (brew* `claude`) | `packages/harnesses.sh` |
| Codex CLI (`@openai/codex`) + Codex desktop app | npm; app manual (brew* `codex`) | |
| Gemini CLI (`@google/gemini-cli`) | npm | |
| cursor-agent | curl -> `~/.local/bin` | `packages/harnesses.sh` |
| Antigravity (Google IDE) | manual (brew* `antigravity`) | |
| Amazon Q, Kiro CLI | brew | `cask amazon-q`, `cask kiro-cli` |
| CodeRabbit CLI | brew | `cask coderabbit` |
| Langflow Desktop | manual (brew* `langflow`) | |
| Buzz (Block, `buzz` CLI + app) | manual (brew* `buzz`) | CLI in `~/.local/bin` |
| Handy (local speech to text) | manual (brew* `handy`) | |

## Languages and runtimes

| Software | Install | Restore |
|---|---|---|
| Go 1.27 | brew | `~/go/bin`: gopls, air, govulncheck (`go` lines in Brewfile) |
| Node 24 | brew `node@24` + nvm (default 24) | npm globals: `@usebruno/cli`, corepack; pnpm, bun via brew |
| Python 3.13/3.14 | brew `python@3.13` | uv + ruff via `scripts/shell.sh`; `uv tool list`: ruff |
| Rust 1.98 | brew `rust` (not in Brewfile) | `~/.cargo`, `~/.rustup` present |
| Lua + lua-language-server | brew (lua-language-server not in Brewfile) | |
| tree-sitter-cli | brew | nvim parsers |
| cmake, automake, libtool | brew* | build tools, pulled in by something |

## Containers, Kubernetes, cloud

| Software | Install | Restore |
|---|---|---|
| Docker Desktop | manual (brew* `docker-desktop`) | |
| docker CLI, colima | brew | colima as alternative runtime |
| kubectl (`kubernetes-cli`), kind, helm, k6 | brew | notes in `docs/kubernetes/` |
| terraform | manual, `/usr/local/bin` | |
| aws CLI | manual, `/usr/local/bin` | |
| Tailscale | manual (brew* `tailscale-app`) | |
| doppler (secrets) | brew (`dopplerhq/doppler`) | |
| Redis Insight | manual (brew* `redis-insight`) | |
| DB Pro (database client) | manual (brew* `db-pro`) | |
| Bruno (API client) + `@usebruno/cli` | manual (brew* `bruno`) + npm | |
| Webex, AnyDesk (remote) | manual (brew* `webex`, `anydesk`) | |

## Git and version control

| Software | Install | Restore |
|---|---|---|
| git (Xcode CLT), git-delta, lazygit, gh | brew | |
| Graphite `gt` CLI + Graphite desktop app | brew (`withgraphite/tap/graphite`, not in Brewfile) + manual app | |
| Linear | manual (brew* `linear-linear`) | |

## Window management and menu bar

| Software | Install | Restore |
|---|---|---|
| AeroSpace (tiling WM) | brew (`nikitabobko/tap`) | config in `aerospace/` |
| Hammerspoon | brew | config in `hammerspoon/` |
| sketchybar + borders (`felixkratz/formulae`) + sketchybar-app-font | brew | `brew services start`; config in `sketchybar/` |
| Moom | manual (brew* `moom`) | |
| Ice (menu bar) | brew | `cask jordanbaird-ice` |
| Bartender 6 | manual (brew* `bartender`) | overlaps with Ice |
| iStat Menus | manual (brew* `istat-menus`) | launch agents present |
| BetterDisplay | manual (brew* `betterdisplay`, tap `waydabber/betterdisplay`) | |
| KeyClu (shortcut cheatsheet) | brew | `cask keyclu` (not in Brewfile) |
| kommand | mas | |
| Raycast | manual (brew* `raycast`) | |
| Vorssaint (menu bar toolkit) | not installed yet | brew* `vorssaint` |
| Caffeinated | mas | |
| darker | mas | |
| Noir (Safari dark mode) | mas | |

## Productivity and notes

| Software | Install | Restore |
|---|---|---|
| Obsidian | manual (brew* `obsidian`) | |
| Notion | manual (brew* `notion`) | |
| Paste (clipboard manager) | mas | |
| Be Focused Pro | mas | |
| Path Finder | manual (brew* `path-finder`) | |
| SSH Config Editor | manual | |
| Pages, Numbers | mas | |
| Microsoft Word, Excel, Teams | manual (brew* `microsoft-word`, `microsoft-excel`, `microsoft-teams`) | |
| Adobe Acrobat DC | manual (brew* `adobe-acrobat-reader` is Reader only) | |
| PDF Reader Pro | manual (brew* `pdf-reader-pro`) | |
| Developer (Apple WWDC app) | mas | |
| TestFlight | mas | |
| SF Symbols | brew | `cask sf-symbols` |

## Browsers and communication

| Software | Install | Restore |
|---|---|---|
| Safari + Ghostery, Proton Pass for Safari, Noir | mas (extensions) | |
| Brave Browser | manual (brew* `brave-browser`) | |
| Google Chrome | manual (brew* `google-chrome`) | |
| Firefox Developer Edition | manual (brew* `firefox@developer-edition`) | |
| FreeTube | manual (brew* `freetube`) | |
| Slack, Discord, WhatsApp, zoom.us | manual (brew* `slack`, `discord`, `whatsapp`, `zoom`); WhatsApp via mas | |
| Zoho Mail desktop | `~/Applications` | |

## Privacy, security, sync

| Software | Install | Restore |
|---|---|---|
| Proton Mail, Proton Drive, ProtonVPN, Proton Pass (Safari) | manual (brew* `proton-mail`, `proton-drive`, `protonvpn`) | |
| Little Snitch | manual (brew* `little-snitch`) | |
| MEGAsync | manual (brew* `megasync`) | launch agent present |
| Ledger Live | manual (brew* `ledger-live`) | |
| CleanMyMac 5 | manual (brew* `cleanmymac`) | |

## Virtualisation and hardware

| Software | Install | Restore |
|---|---|---|
| VMware Fusion | manual | Ubuntu / Fedora VMs |
| Raspberry Pi Imager | manual (brew* `raspberry-pi-imager`) | |
| MacX Video Converter Pro | manual | |

## Fonts

| Font | Install |
|---|---|
| JetBrains Mono + JetBrains Mono Nerd Font (terminal font) | brew casks |
| Hack Nerd Font, Meslo LG Nerd Font (all variants) | manual, `~/Library/Fonts` |
| sketchybar-app-font | brew cask |

## Homebrew taps

`anomalyco/tap` (opencode), `dopplerhq/doppler`, `felixkratz/formulae`
(sketchybar, borders), `nikitabobko/tap` (aerospace), `opgginc/tap`,
`steipete/tap`, `thezoraiz/ascii-image-converter`, `waydabber/betterdisplay`,
`withgraphite/tap` (gt).

## Gaps between this Mac and the Brewfile

Installed but missing from `packages/Brewfile`, so a fresh `brew bundle` would
not bring them back: `automake`, `cmake`, `glances`, `gopls` (brew copy; the
`go` line covers it), `hermit`, `htop`, `just`, `libtool`,
`lua-language-server`, `minicom`, `picocom`, `rust`, `superfile`, `tftp-now`,
`withgraphite/tap/graphite`, `thezoraiz/ascii-image-converter/ascii-image-converter`,
cask `keyclu`.

Every app marked `brew*` above could be moved into the Brewfile as a `cask`
line so the whole machine restores from one command; today they are manual
downloads. Not brew-installable: VMware Fusion, MacX Video Converter Pro,
SSH Config Editor, Graphite desktop app, the App Store items (use `mas` to
script those: `brew install mas`, then `mas install <id>`).
