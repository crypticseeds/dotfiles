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
- **Tmux Plugins Manager**: A plugin manager for Tmux.
- **Nerd Fonts**: Icon‑patched font collection used for terminal glyphs.
- Preferred font: JetBrainsMono Nerd Font

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
   git clone https://github.com/crypticseeds/dotfiles.git
   cd dotfiles
   ```
2. Use **GNU Stow** to symlink the configurations. For example:
   ```bash
   stow .
   ```
2. Use **GNU Stow** to symlink the configurations. From your home directory:
   ```bash
   cd ~/dotfiles
   stow --target="$HOME" .config
   ```
For **Starship**, stow only its configuration from the `.config` directory:
   ```bash
   cd ~/dotfiles/.config
   stow --target="$HOME/.config" starship
   ```

For hammerspoon
```bash
stow --target=$HOME hammerspoon 
```
## Harness

Use Claude Code with Moonshot AI Kimi models.

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

### Environment variables

Export these variables (or manage them with Doppler):

export ANTHROPIC_BASE_URL=https://api.moonshot.ai/anthropic
export ANTHROPIC_AUTH_TOKEN=${YOUR_MOONSHOT_API_KEY}
export ANTHROPIC_MODEL=kimi-k2.5
export ANTHROPIC_DEFAULT_OPUS_MODEL=kimi-k2-thinking
export ANTHROPIC_DEFAULT_SONNET_MODEL=kimi-k2.5
export ANTHROPIC_DEFAULT_HAIKU_MODEL=kimi-k2.5
export CLAUDE_CODE_SUBAGENT_MODEL=kimi-k2.5
export ENABLE_TOOL_SEARCH=true
