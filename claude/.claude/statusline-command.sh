#!/usr/bin/env bash

input=$(cat)

cwd=$(echo "$input" | jq -r '.workspace.current_dir // .cwd // empty')
model=$(echo "$input" | jq -r '.model.display_name // empty')
used=$(echo "$input" | jq -r '.context_window.used_percentage // empty')

# Shorten home directory to ~
home="$HOME"
short_cwd="${cwd/#$home/\~}"

# Git branch (skip optional locks to avoid contention)
git_branch=""
if git -C "$cwd" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git_branch=$(GIT_OPTIONAL_LOCKS=0 git -C "$cwd" symbolic-ref --short HEAD 2>/dev/null)
fi

# Build status line parts
parts=""

# Directory
parts=" $short_cwd"

# Git branch
if [ -n "$git_branch" ]; then
  parts="$parts  $git_branch"
fi

# Model
if [ -n "$model" ]; then
  parts="$parts | $model"
fi

# Context usage
if [ -n "$used" ]; then
  parts="$parts | ctx: $(printf '%.0f' "$used")%"
fi

printf "%s" "$parts"
