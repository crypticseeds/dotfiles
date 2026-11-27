#!/usr/bin/env bash

input=$(cat)

cwd=$(echo "$input" | jq -r '.workspace.current_dir // .cwd // empty')
model=$(echo "$input" | jq -r '.model.display_name // empty')
# Custom (--name, /rename) or auto-generated session title; absent for default names
session_name=$(echo "$input" | jq -r '.session_name // empty')
# Reasoning effort; absent when the model does not support it
effort=$(echo "$input" | jq -r '.effort.level // empty')
case "$effort" in
  low) effort="Low" ;; medium) effort="Medium" ;; high) effort="High" ;;
  xhigh) effort="xHigh" ;; max) effort="Max" ;;
esac
used=$(echo "$input" | jq -r '.context_window.used_percentage // empty')
cost=$(echo "$input" | jq -r '.cost.total_cost_usd // empty')
duration_ms=$(echo "$input" | jq -r '.cost.total_duration_ms // empty')
five_pct=$(echo "$input" | jq -r '.rate_limits.five_hour.used_percentage // empty')
five_reset=$(echo "$input" | jq -r '.rate_limits.five_hour.resets_at // empty')
week_pct=$(echo "$input" | jq -r '.rate_limits.seven_day.used_percentage // empty')
week_reset=$(echo "$input" | jq -r '.rate_limits.seven_day.resets_at // empty')

# Snapshot the usage for herdr-app's status bar (mods/usage), one file per herdr-core terminal
# so the bar shows the focused agent's. Written via a temp file so a reader never sees half a file.
if [ -n "$used$five_pct" ] && [ -n "${HC_TERMINAL_ID:-}" ]; then
  snap="$HOME/.cache/agent-usage"
  file="$snap/claude-$HC_TERMINAL_ID.json"
  mkdir -p "$snap"
  echo "$input" | jq -c '{ctx: .context_window.used_percentage,
    five: .rate_limits.five_hour.used_percentage, five_reset: .rate_limits.five_hour.resets_at,
    week: .rate_limits.seven_day.used_percentage, week_reset: .rate_limits.seven_day.resets_at,
    at: now}' > "$file.tmp" && mv "$file.tmp" "$file"
fi

# OS and branch symbols (Nerd Font, same glyphs as starship). Written as UTF-8
# byte escapes because editors and tools strip private-use characters.
case "$(uname -s)" in
  Darwin) os_icon=$'\xef\x8c\x82' ;;
  Linux)
    if grep -qi '^ID=debian' /etc/os-release 2>/dev/null; then os_icon=$'\xef\x8c\x86'; else os_icon=$'\xef\x8c\x9a'; fi ;;
  *) os_icon="" ;;
esac
branch_icon=$'\xef\x90\x98'

# Epoch seconds -> local time; BSD date (macOS) and GNU date (Linux) differ
fmt_epoch() {
  date -r "$1" "+$2" 2>/dev/null || date -d "@$1" "+$2" 2>/dev/null
}

# Current folder name only (~ at home)
if [ "$cwd" = "$HOME" ]; then short_cwd="~"; else short_cwd="${cwd##*/}"; fi

# Git branch, staged and modified file counts (skip optional locks to avoid contention)
git_branch=""; git_staged=0; git_modified=0
if git -C "$cwd" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git_branch=$(GIT_OPTIONAL_LOCKS=0 git -C "$cwd" symbolic-ref --short HEAD 2>/dev/null)
  git_staged=$(GIT_OPTIONAL_LOCKS=0 git -C "$cwd" diff --cached --numstat 2>/dev/null | wc -l | tr -d ' ')
  git_modified=$(GIT_OPTIONAL_LOCKS=0 git -C "$cwd" diff --numstat 2>/dev/null | wc -l | tr -d ' ')
fi

# Running under agent-launch (nono): the pi-agent-host profile sets AGENT_SANDBOX=nono; nono's
# proxy variable is the fallback. Presence checks only, never the value.
in_nono=false
if [ "${AGENT_SANDBOX:-}" = nono ] || [ -n "${NONO_PROXY_TOKEN+set}" ]; then in_nono=true; fi

# Colors (status line is shown dimmed)
bold_yellow=$'\033[1;33m'
bold_green=$'\033[1;32m'
cyan=$'\033[36m'
purple=$'\033[38;2;178;148;187m' # #b294bb lilac, same as the Starship branch
green=$'\033[32m'
yellow=$'\033[33m'
red=$'\033[31m'
reset=$'\033[0m'

# Colour a usage percentage: green < 50, yellow < 80, red >= 80
pct_color() {
  local p=${1%.*}
  if [ "$p" -ge 80 ]; then printf '%s' "$red"
  elif [ "$p" -ge 50 ]; then printf '%s' "$yellow"
  else printf '%s' "$green"; fi
}

sep=" · "

# Line 1, where: os [session] folder branch +staged ~modified
line1="${bold_yellow}${os_icon}${reset}"
[ -n "$session_name" ] && line1="$line1 🏷️ ${session_name}${sep}"
[ -z "$session_name" ] && line1="$line1 "
line1="${line1}📁 ${cyan}${short_cwd}${reset}"
if [ -n "$git_branch" ]; then
  line1="${line1}${sep}${purple}${branch_icon} ${git_branch}${reset}"
  [ "$git_staged" -gt 0 ] && line1="$line1 ${green}+${git_staged}${reset}"
  [ "$git_modified" -gt 0 ] && line1="$line1 ${yellow}~${git_modified}${reset}"
fi

# Line 2, what is running: model effort [nono]
line2=""
[ -n "$model" ] && line2="🤖 $model"
[ -n "$effort" ] && line2="${line2:+$line2$sep}$effort"
$in_nono && line2="${line2:+$line2$sep}${bold_green}🛡️ nono${reset}"

# Line 3, what it costs: context bar, cost, time, rate limits
line3=""
if [ -n "$used" ]; then
  pct=$(printf '%.0f' "$used")
  filled=$((pct / 10)); [ "$filled" -gt 10 ] && filled=10
  bar=""
  [ "$filled" -gt 0 ] && printf -v fill "%${filled}s" && bar="${fill// /▓}"
  [ "$filled" -lt 10 ] && printf -v pad "%$((10 - filled))s" && bar="${bar}${pad// /░}"
  line3="$(pct_color "$used")${bar} ${pct}%${reset}"
fi
[ -n "$cost" ] && line3="${line3:+$line3$sep}${yellow}💰 $(printf '$%.2f' "$cost")${reset}"
if [ -n "$duration_ms" ]; then
  secs=$((${duration_ms%.*} / 1000))
  if [ "$secs" -ge 3600 ]; then elapsed="$((secs / 3600))h $(printf '%02d' $((secs % 3600 / 60)))m"
  else elapsed="$((secs / 60))m $((secs % 60))s"; fi
  line3="${line3:+$line3$sep}⏱️ ${elapsed}"
fi

# Subscription limits (absent for API-key sessions and before the first response), each with its reset time
limits=""
if [ -n "$five_pct" ]; then
  limits="$(pct_color "$five_pct")5h $(printf '%.0f' "$five_pct")%${reset}"
  [ -n "$five_reset" ] && limits="$limits ↻ $(fmt_epoch "$five_reset" '%H:%M')"
fi
if [ -n "$week_pct" ]; then
  limits="${limits:+$limits$sep}$(pct_color "$week_pct")7d $(printf '%.0f' "$week_pct")%${reset}"
  [ -n "$week_reset" ] && limits="$limits ↻ $(fmt_epoch "$week_reset" '%a %H:%M')"
fi
[ -n "$limits" ] && line3="${line3:+$line3$sep}⌛ $limits"

printf '%s\n' "$line1"
[ -n "$line2" ] && printf '%s\n' "$line2"
[ -n "$line3" ] && printf '%s\n' "$line3"
exit 0
