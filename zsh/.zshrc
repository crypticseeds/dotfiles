# ~/.zshrc - managed in ~/dotfiles (stow package: zsh)
# Works on macOS and Linux: capability detection over OS detection.

# ----------------------------------------------------------------------------
# PATH + environment
# ----------------------------------------------------------------------------
export PATH="$HOME/.local/bin:$PATH"

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
autoload -Uz compinit && compinit
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

# nvm
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"

# bat is `batcat` on Ubuntu
if command -v bat >/dev/null; then
  BAT=bat
elif command -v batcat >/dev/null; then
  BAT=batcat
  alias bat=batcat
fi

# ----------------------------------------------------------------------------
# Aliases
# ----------------------------------------------------------------------------
# Eza
alias ls='eza --icons=always'
alias ll='eza --icons=always -lg'
alias la='eza --icons=always -lag'

# Zoxide
alias cd='z'

# NeoVim
alias nv='nvim'

# bat / fzf previews
if [ -n "${BAT:-}" ]; then
  alias cat="$BAT"
  alias f="fzf --preview=\"$BAT --color=always --style=numbers {}\""
  alias fnv="nvim \$(fzf -m --preview=\"$BAT --color=always --style=numbers {}\")"
  alias fv="vim \$(fzf -m --preview=\"$BAT --color=always --style=numbers {}\")"
fi

# Tmux
alias tn='tmux new-session -s'
alias ta='tmux attach-session'
alias tl='tmux list-sessions'
alias tat='tmux attach-session -t'
alias td='tmux detach'
alias tk='tmux kill-session -t'
alias tw='tmux new-window -n'
alias tkw='tmux kill-window -t'

# Git (note: gs = git switch, gst = git status)
alias gst='git status'
alias gs='git switch'
alias ga='git add'
alias gc='git commit -m'
alias gac='git add . && git commit -m'
alias gco='git checkout'
alias gb='git branch'
alias gu='git pull'
alias gp='git push'
alias gi='git init'
alias gcl='git clone'

# Graphite - stacked PR workflow
alias gtb='gt branch create'
alias gts='gt stack'
alias gtsy='gt sync'
alias gtsb='gt submit'
alias gtst='gt status'
alias gtd='gt doctor'
alias gtu='gt branch up'
alias gtdn='gt branch down'

# Pnpm
alias pf='pnpm format'
alias pl='pnpm lint'
alias plf='pnpm lint:fix'
alias ptc='pnpm type-check'

# Ruff
alias rc='ruff check .'
alias rcf='ruff check --fix .'
alias rf='ruff format .'

# Doppler
alias dc='doppler run -- docker-compose'
alias dcu='doppler run -- docker-compose up'
alias dcd='doppler run -- docker-compose down'
alias drd='doppler run -- npm run dev'

# Coderabbit
alias cr='coderabbit'
alias crp='coderabbit --prompt-only'

# Herdr
alias hr='herdr'
alias hrs='herdr status'
alias hru='herdr update'
alias hrwl='herdr workspace list'
alias hrwc='herdr workspace create'
alias hrtl='herdr tab list'
alias hrns='herdr --session'
alias hrsl='herdr session list'
alias hrsa='herdr session attach'
alias hrss='herdr session stop'
alias hrsd='herdr session delete'

# Harnesses
alias oc='opencode'
# alias claude='doppler run -- claude'

# General
alias ds='docker stats -a --format "table {{.ID}}\t{{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}"'
alias cls='clear'

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
