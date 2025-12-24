
# If you come from bash you might have to change your $PATH.
# export PATH=$HOME/bin:$HOME/.local/bin:/usr/local/bin:$PATH

# Path to your Oh My Zsh installation.
export ZSH="$HOME/.oh-my-zsh"

# Set name of the theme to load --- if set to "random", it will
# load a random theme each time Oh My Zsh is loaded, in which case,
# to know which specific one was loaded, run: echo $RANDOM_THEME
# See https://github.com/ohmyzsh/ohmyzsh/wiki/Themes
ZSH_THEME="robbyrussell"

source $ZSH/oh-my-zsh.sh

# Aliases: Eza
alias ls='eza --icons=always'
alias ll='eza --icons=always -lg'
alias la='eza --icons=always -lag'

# Aliases: Zoxide
alias cd='z'

# Aliases: Tmux
alias tn='tmux new-session -s'
alias ta='tmux attach-session'
alias tl='tmux list-sessions'
alias tat='tmux attach-session -t'
alias td='tmux detach'
alias tk='tmux kill-session -t'
alias tw='tmux new-window -n'
alias tkw='tmux kill-window -t'

# Aliases: Git
alias gs='git status'
alias ga='git add'
alias gc='git commit -m'
alias gco='git checkout'
alias gb='git branch'
alias gu='git pull'
alias gp='git push'
alias gi='git init'
alias gcl='git clone'

# Aliases: General
alias ds='docker stats -a --format "table {{.ID}}\t{{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}"'
alias cls='clear'

. "$HOME/.local/bin/env"
# The following lines have been added by Docker Desktop to enable Docker CLI completions.
fpath=($HOME/.docker/completions $fpath)
autoload -Uz compinit
compinit
# End of Docker CLI completions
export PATH="/usr/local/bin:$PATH"

# Added by Windsurf
export PATH="$HOME/.codeium/windsurf/bin:$PATH"

[[ "$TERM_PROGRAM" == "kiro" ]] && . "$(kiro --locate-shell-integration-path zsh)"
eval "$(uv generate-shell-completion zsh)"
eval "$(uvx --generate-shell-completion zsh)"
# ~/.zshrc

# Initialize zoxide
eval "$(zoxide init zsh)"

# Added by Antigravity
export PATH="$HOME/.antigravity/antigravity/bin:$PATH"

export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"  # This loads nvm
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"  # This loads nvm bash_completion

### MACOS CONFIGURATION STARTS HERE ###

# Aliases: Fzf - MacOS
alias f='fzf --preview="bat --color=always --style=numbers {}"'
alias fnv='nvim $(fzf -m --preview="bat --color=always --style=numbers {}")' 
alias fv='vim $(fzf -m --preview="bat --color=always --style=numbers {}")' 

alias cat='bat' # For use on MacOS

# Load custom zsh plugins - MacOS
source /usr/local/share/zsh-autosuggestions/zsh-autosuggestions.zsh
source /usr/local/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh

# Set up fzf key bindings and fuzzy completion
source <(fzf --zsh) # For use on MacOS

# Initialize Starship prompt - MacOS
eval "$(starship init zsh)"

### UBUNTU CONFIGURATION STARTS HERE ###

# Aliases: Fzf - Linux
# alias f='fzf --preview="batcat --color=always --style=numbers {}"'
# alias fnv='nvim $(fzf -m --preview="batcat --color=always --style=numbers {}")' 
# alias fv='vim $(fzf -m --preview="batcat --color=always --style=numbers {}")'

# alias cat='batcat' # For use on Linux - Ubuntu

# Linux Plugins
# plugins=(zsh-autosuggestions zsh-syntax-highlighting)

# source ~/.fzf.zsh # For use on Linux - Ubuntu
