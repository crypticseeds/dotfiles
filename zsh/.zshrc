# ~/.zshrc - managed in ~/dotfiles (stow package: zsh)
# Works on macOS and Linux: capability detection over OS detection.

# ----------------------------------------------------------------------------
# PATH + environment
# ----------------------------------------------------------------------------
export PATH="$HOME/.local/bin:$PATH"

# Default editor: Zed, blocking until the file is closed (required by git etc.)
export EDITOR="zed --wait"
export VISUAL="zed --wait"

# Homebrew (Apple Silicon, Intel mac, Linuxbrew) - first match wins
for b in /opt/homebrew /usr/local /home/linuxbrew/.linuxbrew; do
  if [ -x "$b/bin/brew" ]; then
    eval "$("$b/bin/brew" shellenv)"
    break
  fi
done

# uv-managed env (cargo-style env file)
[ -f "$HOME/.local/bin/env" ] && . "$HOME/.local/bin/env"

# ----------------------------------------------------------------------------
# History (previously provided by oh-my-zsh)
# ----------------------------------------------------------------------------
HISTFILE="$HOME/.zsh_history"
HISTSIZE=50000
SAVEHIST=50000
setopt SHARE_HISTORY HIST_IGNORE_ALL_DUPS HIST_IGNORE_SPACE HIST_REDUCE_BLANKS
setopt AUTO_CD INTERACTIVE_COMMENTS
bindkey -e  # emacs keybindings

# ----------------------------------------------------------------------------
# Completions (fpath additions must come before compinit)
# ----------------------------------------------------------------------------
[ -d "$HOME/.docker/completions" ] && fpath=("$HOME/.docker/completions" $fpath)
[ -d "$HOME/.zfunc" ] && fpath=("$HOME/.zfunc" $fpath)  # herdr completion zsh > ~/.zfunc/_herdr
# compinit rescans all of fpath for insecure ownership, which is the single
# slowest thing in this file. Do that at most once a day, else reuse the dump.
# The (N...) qualifier only expands in an array assignment, not inside `[`.
autoload -Uz compinit
_zdump="$HOME/.zcompdump"
_zfresh=("$_zdump"(Nmh-24))          # non-empty only if the dump is under a day old
compinit ${_zfresh:+-C} -d "$_zdump"
unset _zdump _zfresh
zstyle ':completion:*' menu select
zstyle ':completion:*' matcher-list 'm:{a-z}={A-Za-z}'

# ----------------------------------------------------------------------------
# Tool init (each guarded; harmless if a tool is missing)
# ----------------------------------------------------------------------------
command -v zoxide   >/dev/null && eval "$(zoxide init zsh)"
command -v direnv   >/dev/null && eval "$(direnv hook zsh)"
command -v starship >/dev/null && eval "$(starship init zsh)"
command -v fzf      >/dev/null && source <(fzf --zsh)
command -v uv       >/dev/null && eval "$(uv generate-shell-completion zsh)"
command -v uvx      >/dev/null && eval "$(uvx --generate-shell-completion zsh)"

# `kubectl completion zsh` costs ~0.5s to generate, so cache it and refresh
# weekly. Only touches disk on machines that actually have the tool.
# Run `rm -rf ~/.cache/zsh` to force a rebuild after upgrading kubectl.
_zcache() {  # _zcache <name> <command that prints a completion script...>
  local f="$HOME/.cache/zsh/$1.zsh"; shift
  local fresh=("$f"(Nmw-1))  # non-empty only if cached less than a week ago
  (( $#fresh )) || { mkdir -p "$f:h" && "$@" >| "$f" 2>/dev/null; }
  source "$f"
}
command -v kubectl >/dev/null && _zcache kubectl kubectl completion zsh && compdef k=kubectl
command -v kind    >/dev/null && _zcache kind kind completion zsh

# nvm - Node Version Manager (nothing to do with neovim).
# Sourcing nvm.sh costs ~2.6s, so put the default version's bin on PATH now and
# defer loading nvm itself until the first `nvm` call. node/npm/npx work
# immediately; `nvm use` and .nvmrc switching work from that first call onward.
export NVM_DIR="$HOME/.nvm"
if [ -s "$NVM_DIR/nvm.sh" ]; then
  _nvm_default="$(cat "$NVM_DIR/alias/default" 2>/dev/null)"
  _nvm_bin=("$NVM_DIR/versions/node/v${_nvm_default#v}"*/bin(Nn))
  [ -n "${_nvm_bin[-1]}" ] && export PATH="${_nvm_bin[-1]}:$PATH"
  unset _nvm_default _nvm_bin
  nvm() {
    unset -f nvm
    . "$NVM_DIR/nvm.sh"
    [ -s "$NVM_DIR/bash_completion" ] && . "$NVM_DIR/bash_completion"
    nvm "$@"
  }
fi

# bat is `batcat` on Ubuntu
if command -v bat >/dev/null; then
  BAT=bat
elif command -v batcat >/dev/null; then
  BAT=batcat
  alias bat=batcat
fi

# ----------------------------------------------------------------------------
# Aliases - see ~/.config/zsh/aliases.zsh (stow package: zsh)
# Sourced here, after $BAT is set, because the bat/fzf aliases depend on it.
# ----------------------------------------------------------------------------
[ -r "$HOME/.config/zsh/aliases.zsh" ] && source "$HOME/.config/zsh/aliases.zsh"

# ----------------------------------------------------------------------------
# Zsh plugins (brew or distro paths; syntax-highlighting must be sourced LAST)
# ----------------------------------------------------------------------------
for p in \
  "${HOMEBREW_PREFIX:-/nonexistent}/share/zsh-autosuggestions/zsh-autosuggestions.zsh" \
  /usr/share/zsh-autosuggestions/zsh-autosuggestions.zsh; do
  [ -f "$p" ] && source "$p" && break
done
for p in \
  "${HOMEBREW_PREFIX:-/nonexistent}/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh" \
  /usr/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh; do
  [ -f "$p" ] && source "$p" && break
done
