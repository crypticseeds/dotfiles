# Dotfiles

My personal configuration files for macOS, managed with GNU Stow.

## Prerequisites

To get this setup running properly, you will need to install the following tools. You can find the installation instructions on their respective official websites.

### Shell & Terminal
- **WezTerm**: A GPU-accelerated cross-platform terminal emulator.
- **Zsh**: The default shell for macOS.
- **Oh My Zsh**: A framework for managing your Zsh configuration.
- **Starship**: A fast, customizable, and intelligent prompt for any shell.
- **Tmux**: A terminal multiplexer for managing multiple terminal sessions.

### Core CLI Utilities
- **GNU Stow**: A symlink farm manager (used to manage these dotfiles).
- **Zoxide**: A smarter `cd` command.
- **Eza**: A modern replacement for `ls` with icons and colors.
- **Bat**: A `cat` clone with syntax highlighting and Git integration.
- **Fzf**: A general-purpose command-line fuzzy finder.
- **Zsh Autosuggestions**: Fish-like fast-forward autosuggestions for Zsh.
- **Zsh Syntax Highlighting**: Fish-shell like syntax highlighting for Zsh.

### Window Management (macOS)
- **AeroSpace**: An i3-like tiling window manager for macOS.
- **Sketchybar**: A highly customizable macOS status bar.

### Development Tools
- **Neovim**: A hyperextensible Vim-based text editor.
- **UV**: An extremely fast Python package manager and resolver.
- **Docker**: A platform for developing, shipping, and running applications in containers.
- **Git**: Distributed version control system.

## Setup

1. Clone this repository:
   ```bash
   git clone https://github.com/femiakinlotan/dotfiles.git ~/dotfiles
   ```
2. Navigate to the directory:
   ```bash
   cd ~/dotfiles
   ```
3. Use **GNU Stow** to symlink the configurations. For example:
   ```bash
   stow .
   ```
