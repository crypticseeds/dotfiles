# ~/.config/zsh/aliases.zsh - managed in ~/dotfiles (stow package: zsh)
# Sourced from ~/.zshrc. Kept separate so .zshrc stays environment + init only.
#
# Note: the bat/fzf aliases below depend on $BAT, which .zshrc sets just
# before sourcing this file (bat is `batcat` on Ubuntu).

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

# Kubectl (completion is set up in the tool init section above)
alias k='kubectl'
alias kg='kubectl get'
alias kgp='kubectl get pods'
alias kgs='kubectl get svc'
alias kgd='kubectl get deploy'
alias kgn='kubectl get nodes'
alias kga='kubectl get all'
alias kd='kubectl describe'
alias kl='kubectl logs'
alias klf='kubectl logs -f'
alias kex='kubectl exec -it'
alias kaf='kubectl apply -f'
alias kdf='kubectl delete -f'
alias kpf='kubectl port-forward'
alias kev='kubectl get events --sort-by=.lastTimestamp'
# Context and namespace (plain kubectl - no kubectx/kubens dependency)
alias kctx='kubectl config use-context'
alias kctxl='kubectl config get-contexts'
alias kns='kubectl config set-context --current --namespace'

# Kind - local clusters (never alias `kind` itself; it shadows the binary)
alias kindc='kind create cluster'
alias kindd='kind delete cluster'
alias kindl='kind get clusters'
alias kindi='kind load docker-image'

# Harnesses
alias oc='opencode'
# alias claude='doppler run -- claude'

# General
alias ds='docker stats -a --format "table {{.ID}}\t{{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}"'
alias cls='clear'
