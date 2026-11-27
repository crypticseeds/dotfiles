---
name: herdr-app
description: Use when `agent-mux` prints herdr-app (Herdr Core, `hc`) and you are about to delegate to a subagent, scout, reviewer or implementer, start a background or long-running job (test suite, build, dev server, server, watcher, local CI), or operate Herdr Core terminals. Delegated agents and long jobs run as `hc run --bg` children, never through the harness's own subagent or background features, which are blocked there. Read `hc --skill` for terminal operations and `herdr-app --skill` for optional window controls. Use `delegate-visibly` only for the legacy Herdr TUI.
---

# herdr-app

The Herdr desktop app (`herdr-app`) shows spaces, tabs and panes. herdr-core (`hc`) runs the terminals and agents in them and keeps them alive when the window closes. It is not `herdr`, the terminal multiplexer: the `herdr` CLI and its pane IDs do not apply here.

Precondition: `agent-mux` prints `herdr-app`. It checks the terminal process against your shell's ancestors so stale environment variables cannot select the wrong host. If it prints `herdr`, use the `herdr` and `delegate-visibly` skills. If it prints `none` with Herdr variables present, report that the host could not be verified before falling back.

## Load the manuals first

Read the live manual for the operation you need:

```sh
hc --skill          # run, read, message, wait on and clean up programs and agents
herdr-app --skill   # optional, for programmatic control of spaces, tabs and panes
```

`hc` is for the work, `herdr-app` only for the window. Your address is `$HC_TERMINAL_ID` (a terminal like `t9`), not a pane ID.

## Delegating

The global rules (tiers, explicit model, one writer per checkout, `agent/<slug>` branches) still apply. In herdr-app they map like this:

- **Start a worker.** Check `hc templates` first, then `hc run --bg --name <slug> --cwd <dir> <template-or-agent> "<task>"`. Use an explicit model and an interactive launch for every delegated worker, including scouts, reviewers and implementers. Use `--no-daemon` for Codex, including in templates. Give the worker a scope, write boundaries and your actual terminal address for `hc send <parent-id> "<result or blocker>"`. Require explicit authorization before it delegates further.
- **GitHub access on the Pi.** Inside `agent-launch`, `gh` and `git push` over HTTPS work: nono's proxy injects the GitHub PAT, and the agent only sees a placeholder `GH_TOKEN`. Not for opencode: proxy mode blocks the localhost server it needs, so a normal opencode client runs its tools in the shared server outside nono (with your login), and a standalone one (`-s`) has no GitHub credentials. Start delegated coding workers with `hc run --bg --cwd <worktree> agent-launch --subagent <harness> -- <native args>`. For Claude, nono is its only sandbox under `agent-launch` (once `regen-agent-host.sh` has installed `/etc/claude-code/nono/managed-settings.json`); there `aws`, `doppler`, `terraform` and `kubectl` have no credentials, so give work that needs them to a plain `claude` session instead. OpenCode's shared server may execute outside the client sandbox; its scoped environment and filesystem protections are unverified. Leave commits, pushes, and merges to the parent or operator. If a worker needs a special secret, put `--doppler PROJECT/CONFIG --secret NAME` before the harness name.
- **Wait and read.** Use `hc wait <child>` and `hc read --lines 80 <child>`. For a blocked worker, read its output and let the user handle the prompt. Preserve permission and trust prompts.
- **Show a child.** Workers appear beneath their parent in the Herdr sidebar. Open a child from that list. Click **Keep** in the upper right to retain that same terminal in a dedicated tab. Leave routine workers in the child list.
- **Worktrees:** herdr-app has no worktree command. Create one with `git worktree add .worktrees/<slug> -b agent/<slug>`, run `agent-worktree-setup .worktrees/<slug>`, then start the worker with `--cwd` there.

## Running jobs

- Start dev servers, watchers, slow builds, test suites and local CI from the agent that owns them with `hc run --bg --name <job> --cwd <dir> -- <command>`. This makes the job a child of that agent. Report a launch failure before switching execution methods. Avoid shell background mode for these jobs.
- Use `hc wait <job>` for a one-off job and `hc read --lines 80 <job>` to inspect output. For server readiness, `hc wait <job> --output <marker>` matches output printed after the wait starts. Use `hc read` if the marker has already appeared.
- Leave active servers available. Use `--outlive-parent` explicitly if a job needs to survive its owning session. Once you have collected a completed one-off job's output, use `hc rm <job>`. For an interactive worker that has finished its assignment, use `hc kill <child>` before removing its terminal if the agent is still running. Clean up only terminals you started and no longer need, and check with the user before closing a tab they kept.

## Never

- Never stop, restart or update the person's core or app (`hc server stop|restart`, `hc update`) unless asked.
- Never launch bare `herdr-app` to inspect. Use `herdr-app ls` or `herdr-app status` when the app CLI is available.
- Use `hc` for Core terminals. A leaked `HERDR_PANE_ID` can point to an unrelated legacy pane.
