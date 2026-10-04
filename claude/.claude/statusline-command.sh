#!/usr/bin/env bash

input=$(cat)

cwd=$(echo "$input" | jq -r '.workspace.current_dir // .cwd // empty')
model=$(echo "$input" | jq -r '.model.display_name // empty')
# Reasoning effort; absent when the model does not support it
effort=$(echo "$input" | jq -r '.effort.level // empty')
case "$effort" in
  low) effort="Low" ;; medium) effort="Medium" ;; high) effort="High" ;;
  xhigh) effort="xHigh" ;; max) effort="Max" ;;
esac
used=$(echo "$input" | jq -r '.context_window.used_percentage // empty')
five_pct=$(echo "$input" | jq -r '.rate_limits.five_hour.used_percentage // empty')
five_reset=$(echo "$input" | jq -r '.rate_limits.five_hour.resets_at // empty')
week_pct=$(echo "$input" | jq -r '.rate_limits.seven_day.used_percentage // empty')
week_reset=$(echo "$input" | jq -r '.rate_limits.seven_day.resets_at // empty')

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

# Git branch (skip optional locks to avoid contention)
git_branch=""
if git -C "$cwd" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git_branch=$(GIT_OPTIONAL_LOCKS=0 git -C "$cwd" symbolic-ref --short HEAD 2>/dev/null)
fi

# Git dirty marker
git_dirty=""
if [ -n "$git_branch" ] && [ -n "$(GIT_OPTIONAL_LOCKS=0 git -C "$cwd" status --porcelain 2>/dev/null | head -n 1)" ]; then
  git_dirty="*"
fi

# Colors (status line is shown dimmed)
bold_yellow=$'\033[1;33m'
cyan=$'\033[36m'
purple=$'\033[35m'
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

# Build: os dir branch | model | ctx | 5h | 7d
parts="${bold_yellow}${os_icon}${reset} ${cyan}${short_cwd}${reset}"

if [ -n "$git_branch" ]; then
  parts="$parts ${purple}${branch_icon} ${git_branch}${git_dirty}${reset}"
fi

if [ -n "$model" ]; then
  parts="$parts | $model"
  [ -n "$effort" ] && parts="$parts ($effort)"
fi

if [ -n "$used" ]; then
  parts="$parts | $(pct_color "$used")ctx: $(printf '%.0f' "$used")%${reset}"
fi

# Subscription usage limits (absent for API-key sessions and before the first response)
if [ -n "$five_pct" ]; then
  parts="$parts | $(pct_color "$five_pct")5h: $(printf '%.0f' "$five_pct")%${reset}"
  [ -n "$five_reset" ] && [ "${five_pct%.*}" -ge 50 ] && parts="$parts ($(fmt_epoch "$five_reset" '%H:%M'))"
fi

if [ -n "$week_pct" ]; then
  parts="$parts | $(pct_color "$week_pct")7d: $(printf '%.0f' "$week_pct")%${reset}"
  [ -n "$week_reset" ] && [ "${week_pct%.*}" -ge 50 ] && parts="$parts ($(fmt_epoch "$week_reset" '%a %H:%M'))"
fi

printf "%s" "$parts"
