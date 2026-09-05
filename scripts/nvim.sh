#!/usr/bin/env sh
# Installs Neovim 0.12+ and everything nvim/.config/nvim needs, per OS.
# macOS: Homebrew. Linux (Ubuntu/Debian/Fedora): distro packages for the basics,
# official release binaries into ~/.local for anything the distro ships too old
# (neovim, go, tree-sitter-cli, lazygit). No sudo beyond the package manager.
# Idempotent: re-running only installs what is missing or outdated.
# LSP servers and formatters are NOT installed here: Mason does that inside
# nvim on first launch (see lua/plugins/lsp.lua, lua/plugins/formatting.lua).
set -eu

NVIM_MIN=0.12
GO_MIN=1.24
BIN="$HOME/.local/bin"
mkdir -p "$BIN"
PATH="$BIN:$PATH" # binaries installed below must be visible to the checks below

say() { printf '\033[1m==> %s\033[0m\n' "$*"; }
have() { command -v "$1" >/dev/null 2>&1; }
# version_ge 0.12.4 0.12 -> true
version_ge() { [ "$(printf '%s\n%s\n' "$2" "$1" | sort -V | head -1)" = "$2" ]; }
arch() {
  case "$(uname -m)" in
    x86_64|amd64) echo x86_64 ;;
    aarch64|arm64) echo arm64 ;;
    *) echo "unsupported arch: $(uname -m)" >&2; exit 1 ;;
  esac
}
latest_tag() { # latest_tag owner/repo -> v1.2.3
  curl -fsSL "https://api.github.com/repos/$1/releases/latest" | sed -n 's/.*"tag_name": *"\([^"]*\)".*/\1/p'
}

# --- Neovim ---------------------------------------------------------------
install_nvim_release() {
  case "$(arch)" in x86_64) a=x86_64 ;; arm64) a=arm64 ;; esac
  say "neovim: installing latest release to ~/.local/nvim"
  tmp="$(mktemp -d)"
  curl -fsSL "https://github.com/neovim/neovim/releases/latest/download/nvim-linux-$a.tar.gz" | tar -xz -C "$tmp"
  rm -rf "$HOME/.local/nvim"
  mv "$tmp"/nvim-linux-* "$HOME/.local/nvim"
  ln -sfn "$HOME/.local/nvim/bin/nvim" "$BIN/nvim"
  rm -rf "$tmp"
}
nvim_ok() {
  have nvim && version_ge "$(nvim --version | sed -n '1s/^NVIM v\([0-9.]*\).*/\1/p')" "$NVIM_MIN"
}

# --- Go (Mason builds gopls with it; distro Go is often too old) -----------
install_go_release() {
  case "$(arch)" in x86_64) a=amd64 ;; arm64) a=arm64 ;; esac
  ver="$(curl -fsSL 'https://go.dev/VERSION?m=text' | head -1)"
  say "go: installing $ver to ~/.local/go"
  rm -rf "$HOME/.local/go"
  curl -fsSL "https://go.dev/dl/$ver.linux-$a.tar.gz" | tar -xz -C "$HOME/.local"
  ln -sfn "$HOME/.local/go/bin/go" "$BIN/go"
  ln -sfn "$HOME/.local/go/bin/gofmt" "$BIN/gofmt"
}
go_ok() {
  have go && version_ge "$(go version | sed -n 's/^go version go\([0-9.]*\).*/\1/p')" "$GO_MIN"
}

# --- tree-sitter CLI (compiles treesitter parsers) --------------------------
install_tree_sitter_release() {
  case "$(arch)" in x86_64) a=x64 ;; arm64) a=arm64 ;; esac
  say "tree-sitter: installing latest release to ~/.local/bin"
  curl -fsSL "https://github.com/tree-sitter/tree-sitter/releases/latest/download/tree-sitter-linux-$a.gz" | gunzip > "$BIN/tree-sitter"
  chmod +x "$BIN/tree-sitter"
}

# --- lazygit ---------------------------------------------------------------
install_lazygit_release() {
  tag="$(latest_tag jesseduffield/lazygit)"
  say "lazygit: installing $tag to ~/.local/bin"
  tmp="$(mktemp -d)"
  curl -fsSL "https://github.com/jesseduffield/lazygit/releases/download/$tag/lazygit_${tag#v}_linux_$(arch).tar.gz" | tar -xz -C "$tmp" lazygit
  mv "$tmp/lazygit" "$BIN/lazygit"
  rm -rf "$tmp"
}

# ---------------------------------------------------------------------------
case "$(uname -s)" in
  Darwin)
    have brew || { echo "Homebrew required: https://brew.sh" >&2; exit 1; }
    say "brew: neovim tree-sitter-cli ripgrep go node@24 lazygit + Nerd Font"
    brew install neovim tree-sitter-cli ripgrep go node@24 lazygit
    brew install --cask font-jetbrains-mono-nerd-font
    ;;
  Linux)
    . /etc/os-release
    case "$ID" in
      ubuntu|debian)
        say "apt: build tools, stow, ripgrep, node"
        sudo apt-get update -qq
        sudo apt-get install -y git curl tar gzip unzip build-essential stow ripgrep nodejs npm
        ;;
      fedora)
        say "dnf: build tools, stow, ripgrep, node, lazygit"
        sudo dnf install -y git curl tar gzip unzip gcc make stow ripgrep nodejs npm lazygit
        ;;
      *) echo "unsupported distro: $ID (add it to scripts/nvim.sh)" >&2; exit 1 ;;
    esac
    nvim_ok || install_nvim_release
    go_ok || install_go_release
    have tree-sitter || install_tree_sitter_release
    have lazygit || install_lazygit_release
    case ":$PATH:" in *":$BIN:"*) ;; *) echo "NOTE: add $BIN to PATH (the stowed zshrc does this)" ;; esac
    ;;
  *) echo "unsupported OS: $(uname -s)" >&2; exit 1 ;;
esac

say "versions"
for t in nvim tree-sitter rg go node lazygit; do
  if ! have "$t"; then printf '  %-12s MISSING\n' "$t"
  elif [ "$t" = go ]; then printf '  %-12s %s\n' go "$(go version)"
  else printf '  %-12s %s\n' "$t" "$("$t" --version 2>/dev/null | head -1)"
  fi
done
nvim_ok || { echo "neovim >= $NVIM_MIN required" >&2; exit 1; }
