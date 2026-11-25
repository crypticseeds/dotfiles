# Codex hooks (mux routing)

`hooks.json` is `~/.codex/hooks.json` (owned at runtime by moshi-hook, so it is not stowed) with two extra entries
merged in: a `SessionStart` hook running `agent-route session-start` and a `PreToolUse` hook (matcher
`^spawn_agent$`) running `agent-route check`. The moshi entries are unchanged. Paths are absolute for the
`ai` user; edit them on another account. Install (replaces the live file; re-merge if moshi-hook rewrote it):

    cp ~/dotfiles/templates/codex-hooks/hooks.json ~/.codex/hooks.json
