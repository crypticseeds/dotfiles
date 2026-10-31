---
name: herdr-app
description: Use when `agent-mux` prints herdr-app (you run in a terminal of the Herdr desktop app, driven by herdr-core `hc`) and you need to inspect or control terminals, agents, spaces, tabs or panes, or delegate to a visible worker. Loads the live manuals (`hc --skill`, `herdr-app --skill`) and maps the herdr delegation rules onto hc. Do NOT use the herdr or delegate-visibly skills here, even if HERDR_ENV=1 is set - in herdr-app that variable can be stale.
---

# herdr-app

The Herdr desktop app (`herdr-app`) shows spaces, tabs and panes. herdr-core (`hc`) runs the terminals and agents in them and keeps them alive when the window closes. It is not `herdr`, the terminal multiplexer: the `herdr` CLI and its pane IDs do not apply here.

Precondition: `agent-mux` prints `herdr-app`. If it prints `herdr`, use the herdr and delegate-visibly skills instead; if `none`, you are in neither, so delegate with the normal task tool.

## Load the manuals first

They ship with the binaries and stay current, so read them instead of guessing syntax:

```sh
hc --skill          # run, read, message, wait on and clean up programs and agents
herdr-app --skill   # change what the person sees: spaces, tabs, panes, focus
```

`hc` is for the work, `herdr-app` only for the window. Your address is `$HC_TERMINAL_ID` (a terminal like `t9`), not a pane ID.

## Delegating

The global rules (tiers, explicit model, one writer per checkout, `agent/<slug>` branches) still apply. In herdr-app they map like this:

- **Start a worker:** check `hc templates` first, then `hc run --bg --name <slug> --cwd <dir> <template-or-agent> "<task>"`, with the model set explicitly on the agent's command line. Tell it to report with `hc send $HC_TERMINAL_ID` when done or stuck.
- **Wait and read:** `hc wait <name>`, `hc read <name> --lines 80`. Never poll in a loop.
- **Show it to the person:** only when the work earns a visible worker (it will block on approvals or questions, or runs long). Open it in its own tab, never the tab hosting this conversation: `herdr-app do tab.new --name <slug> --argv '[...]'`. Use IDs from `herdr-app ls`, never the focused pane by default.
- **Worktrees:** herdr-app has no worktree command. Create one with `git worktree add .worktrees/<slug> -b agent/<slug>`, run `agent-worktree-setup .worktrees/<slug>`, then start the worker with `--cwd` there.
- **Clean up** only what you started: `hc kill <t>`, `hc rm <t>`, close the tab you opened, and `agent-clean <worktree-path>` after merging.

## Never

- Never stop, restart or update the person's core or app (`hc server stop|restart`, `hc update`) unless asked.
- Never launch bare `herdr-app` to inspect: it opens or raises the window. Use `herdr-app ls` and `herdr-app status`.
- Never use `herdr ...` commands from here: a leaked `HERDR_PANE_ID` points at an unrelated herdr pane.
