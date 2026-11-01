---
name: delegate-visibly
description: Use inside Herdr (`agent-mux` prints herdr; in herdr-app use the herdr-app skill instead) when delegating work that will likely block on approvals or questions or that runs long - implementation, fixes from review feedback, builds, full test suites, servers. Starts the worker with herdr agent start in a delegation tab or a Herdr worktree (never the main tab, max 2x2 per tab), on Sonnet 5.5 at high effort by default, for Claude Code, opencode or omp. Waits with herdr agent wait, reads with herdr agent read, keeps a report file as a crash backup, and cleans up what it created. Overrides the herdr skill's "sibling pane in the current tab" default; load the herdr skill for CLI syntax. Do NOT use for quick edits you can do yourself or for read-only review, test or research agents - those stay hidden background subagents.
---

# delegate-visibly

Run delegated workers in Herdr panes the user can see, so approvals and questions are answerable, without cluttering the tab that hosts this conversation. You stay the delegator: you place, start, brief, monitor, judge and clean up. The `herdr` skill (or `herdr --skill`) is the CLI reference; these rules override its default layout.

Precondition: `agent-mux` prints `herdr`. If it prints `herdr-app`, use the herdr-app skill instead; if `none`, you are not inside Herdr: say so and delegate with the normal task tool instead. Do not trust `HERDR_ENV=1` alone: it leaks into herdr-app terminals.

## Does this task earn a pane?

| Work | Where it goes |
|---|---|
| Quick edit you can do and verify yourself | Do it yourself. No worker. |
| Read-only: code review, security review, research, lookups, a test or build run that only reports | Hidden background subagent (Agent tool, explicit `model`). No pane, no worktree. |
| Writer or long runner that will likely block (approvals, questions, judgment calls) or run long | A visible worker, placed per the topology below. |
| Fixer for review feedback, when the fix is long or needs permissions | Prefer the original worker's pane (same session keeps its context). Otherwise a new pane in the same tab or worktree as the work it fixes. |
| User asks to watch something | A visible worker, even if it would otherwise stay hidden. |

A pane must earn its existence. When in doubt, keep it inline.

## Topology

Hard rules:

1. **Main tab stays clean.** The main tab hosts this conversation (`$HERDR_TAB_ID`). Never split it or start workers in it, unless the user explicitly says "same tab" / "next to me" (then still max 2x2).
2. **Max 2x2 per tab.** At 4 panes (the user's panes count too), open a new tab. Check `pane_count` before splitting: `herdr tab list --workspace <ws> | jq -c '.result.tabs[] | {tab_id,label,pane_count}'`.
3. **Workers on the same work share a tab**, one per pane: e.g. implementer, its test runner and its fixer side by side.
4. **One writer per checkout.** While a worker writes in your checkout, you do not edit files it may touch.

| Situation | Placement |
|---|---|
| Single writer, nothing else editing the repo | A pane in a delegation tab in the current workspace, cwd = your checkout |
| Parallel writers on the same repo, or work that belongs on its own branch | A Herdr worktree (its own linked workspace, branch `agent/<slug>`); the worker runs in its root pane |
| More workers for that same worktree | 2x2 fill inside that worktree workspace's tab, then a new tab there |
| Unclear whether isolation is needed | Ask the user |

Fill order inside a tab (always `--no-focus`, parse every ID from the JSON):

```
+---------+---------+
| 1 root  | 2       |   2 = split 1 --direction right
+---------+---------+   3 = split 1 --direction down
| 3       | 4       |   4 = split 2 --direction down
+---------+---------+
```

```bash
# New delegation tab in the current workspace (pane 1 = .result.root_pane.pane_id)
herdr tab create --workspace "$HERDR_WORKSPACE_ID" --cwd "$PWD" --label agents --no-focus
# Panes 2-4 (.result.pane.pane_id)
herdr pane split <pane1> --direction right --cwd "$PWD" --no-focus
herdr pane split <pane1> --direction down  --cwd "$PWD" --no-focus
herdr pane split <pane2> --direction down  --cwd "$PWD" --no-focus

# Herdr worktree (check `herdr worktree list --cwd "$PWD"` first; reuse with `herdr worktree open`)
herdr worktree create --cwd "$PWD" --branch agent/<slug> --label <slug> --no-focus
# Then, as its own command, with the new worktree's `.path` from `herdr worktree list --cwd "$PWD"`
agent-worktree-setup <worktree-path>
```

Herdr sets nothing up in a new worktree, so it has no `.venv`. Run `agent-worktree-setup <worktree-path>` after every `herdr worktree create`, before the worker starts. It runs `uv sync --frozen` (locked dependencies only) when the project has a `uv.lock` and does nothing otherwise.

Label extra tabs by purpose (`agents-2`, `tests`). Use only Herdr worktrees inside Herdr: no `git worktree add`, no `EnterWorktree`. Pipes, `&&` and `jq` are fine with `herdr` commands.

## Start the worker

Default kind is the harness you are running in: `claude` in Claude Code, `opencode` in opencode, `omp` in omp. Use another kind only when the user asks; when the user asks for opencode workers, follow the `opencode-workers` skill instead of this section. Native arguments go after `--`. Default model is **Sonnet 5.5 at high effort**; use Haiku only for small-tier work per the tiering table in AGENTS.md, and always pass the model explicitly.

| Kind | Sonnet 5.5, high (default) | Haiku 5.5 |
|---|---|---|
| claude | `-- --agent <name> --model claude-sonnet-5-5 --effort high` | `-- --agent <name> --model claude-haiku-5-5` |
| omp | `-- --model claude-sonnet-5-5 --thinking high` | `-- --model claude-haiku-5-5` |
| opencode | `-- --session <id>` after creating the session with agent `worker-sonnet` (model `github-copilot/claude-sonnet-5.5#high`) | `-- --session <id>` after creating the session with agent `<name>` and model `github-copilot/claude-haiku-5.5` |

`<name>` is the subagent (e.g. `implementer`). The opencode TUI has no `--agent` or `--model` flag (`opencode --agent x` exits 1), so an opencode worker gets its agent, model and effort from a session created first, as its own command:

```bash
opencode api post /api/session -d '{"id":"ses_<repo>_<slug>","title":"<role>","agent":"worker-sonnet","model":{"providerID":"github-copilot","id":"claude-sonnet-5.5","variant":"high"},"location":{"directory":"<checkout or worktree path>"}}'
```

The pane's status bar then shows the agent, model and effort. Messaging, reading and unblocking that session through the opencode API are in the `opencode-workers` skill.

```bash
herdr pane rename <pane> "<role>"     # e.g. impl-auth, test-auth, fix-auth
herdr agent start <agent-name> --kind claude --pane <pane> --timeout 90000 -- --agent implementer --model claude-sonnet-5-5 --effort high
```

`<agent-name>` is unique and matches `[a-z][a-z0-9_-]{0,31}`. After `agent start` returns, read the pane once (`herdr agent read <agent-name> --source visible`): an update or trust dialog can sit on screen while Herdr still reports `idle`. If startup returns `agent_not_ready`/`blocked`, read the pane and ask the user. If the agent CLI fails to start, report the error; do not silently fall back.

## Brief it

Write the brief to a file, then send it. The brief is self-contained (the worker has none of this conversation): goal, scope and paths, constraints, acceptance criteria with exact checks, the worktree and branch if any, and this closing instruction:

    When finished, give your complete final report as your last reply, ending with a
    `## Remember` section (lessons the next worker should know, one line each, or "none").
    Also write it to /tmp/agent-reports/<slug>.md, then state DONE. If anything blocks you,
    ask in this session and wait.

```bash
mkdir -p /tmp/agent-prompts /tmp/agent-reports
rm -f /tmp/agent-reports/<slug>.md        # a stale report would look like completion
```

Then send a pointer to the brief as its own Bash command:

```bash
herdr agent prompt <agent-name> 'Read /tmp/agent-prompts/<slug>.md and follow it exactly.'
```

Never `"$(cat ...)"`, a backtick, a pipe or `&&` in a herdr command, not even inside single quotes: Claude Code then runs it inside the sandbox, which blocks the herdr socket (`PermissionDenied: Operation not permitted`). Short text works inline as one single-quoted argument (newlines are fine, write `'` as `'\''`).

The report file is deliberate, despite the herdr skill's advice against asking for file output up front: it is the backup if the worker crashes, its pane closes, or its answer scrolls out of reach.

## Wait and read

Submit every prompt first when running several workers. Then wait in background Bash calls (`run_in_background`) so you can keep talking with the user:

```bash
herdr agent wait <agent-name> --timeout 1800000          # returns on idle, done or blocked
herdr agent read <agent-name> --source recent-unwrapped --lines 200
```

For one short task, `herdr agent prompt ... --wait --timeout <ms>` replaces the separate wait. Then:

- **done / idle:** read the agent's output. That is the primary result. Use `/tmp/agent-reports/<slug>.md` when the read does not show the full report.
- **blocked:** read the pane, tell the user "`<role>` in tab `<label>` needs your input", and ask before answering approvals or questions on its behalf. Wait again afterwards.
- **timeout or stalled:** not proof the prompt was lost. Read the pane before resubmitting; wait again if it is still working.
- **agent or pane gone:** read the report file if it exists, and tell the user the worker exited.

## Judge, then clean up

1. Judge the work yourself against the brief. A worker's success claim is not evidence. Handle its `## Remember` section as the `orchestrate` skill's Verify step says.
2. **Accepted:** close the panes and tabs you created for it (`herdr pane close <pane>` / `herdr tab close <tab>`), and delete its `/tmp/agent-prompts/<slug>.*`. Keep the report until your final answer. For a worktree, merge and remove it per the `orchestrate` skill's "Integrate and clean up".
3. **Rejected or unclear:** keep the pane. Send the correction to the same session (`herdr agent prompt <agent-name> "..."`) and wait again. Tell the user where it lives and what is wrong.

## Track what you created

Keep a running list in the conversation of every tab, pane, agent name and worktree workspace you created, with its purpose. Use it to respect the 2x2 cap, to route follow-ups to the right worker, and for precise cleanup. After delegating, tell the user where each worker lives (tab label, pane role, worktree branch). When workers finish, summarize their results in the conversation; don't make the user read the panes.

Close only what you created. Never `workspace close --group` unless the user asked to close the whole worktree group.

## Troubleshooting

- `Operation not permitted` on a `herdr` command means the command sandbox blocked the Herdr socket. Rerun outside the sandbox or ask the user to allow it; Herdr is not down.
- IDs can change after `pane move`; prefer agent names, and re-read IDs from JSON rather than trusting old ones.
