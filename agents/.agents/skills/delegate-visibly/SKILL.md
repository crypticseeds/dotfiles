---
name: delegate-visibly
description: Use when delegating a task to another agent that is likely to block on permission approvals or clarifying questions, or that runs long (test suites, builds, scanners, servers, implementation work). Spawns the agent in a visible herdr pane via "claude --agent" (or "opencode --agent" when running in opencode) so the user can watch and unblock it, monitors its status, collects its report, and closes the pane on success. Requires HERDR_ENV=1. Do NOT use for quick read-only lookups, scans, or web research - keep those inline via the normal task tool.
---

# delegate-visibly

Run a delegated agent in its own herdr pane instead of an invisible background task, so blocking prompts (permission approvals, clarifying questions) are visible and answerable by the user. You remain the delegator: you spawn, monitor, judge the result, and clean up.

## Preconditions

- `HERDR_ENV` is `1`. If not, this skill does not apply - delegate with the normal task tool and say so.
- Spawn one pane per delegated agent. Never run two writing agents in the same worktree at once; read-only agents may run in parallel in current pane.

## Decide first: does this task earn a pane?

Default to the normal inline task tool. Spawn a pane ONLY when at least one blocking or long-running signal applies:

- The target agent will likely hit an approval prompt (its permissions use `ask` for bash/edit and the task needs those tools - running tests, builds, scanners, git operations, file edits).
- The task is ambiguous enough that the agent will likely need to ask the user a clarifying question.
- Expected runtime is long: full test suites, builds, servers, repository-wide audits, implementation work.
- The user explicitly wants to watch.

Keep inline (NO pane): quick/medium read-only codebase research, inspect-only reviews, web lookups, anything expected to finish in about a minute without prompts. Panes are for unblocking, not for spectacle - unnecessary panes are clutter.

## Spawn

1. Find your own pane id (ids look like `w7:p1` in herdr 0.9, not `1-1`; take the pane marked `focused`):

       herdr pane list

2. Write the delegation prompt to a file (avoids shell-quoting bugs). Include: objective, scope and boundaries, expected output format, and this mandatory closing instruction:

       When finished, write your complete final report to /tmp/agent-reports/<slug>.md
       then state DONE. If anything blocks you, ask in this session and wait.

       mkdir -p /tmp/agent-prompts /tmp/agent-reports
       rm -f /tmp/agent-reports/<slug>.md   # stale report = instant false completion signal
       # write the prompt to /tmp/agent-prompts/<slug>.md

   **Run every `herdr` command as a plain command of its own.** On the agent host, herdr only runs outside the sandbox that way; inside a pipe, `&&` chain, loop, or `$(...)` it hits the sandbox and fails with `PermissionDenied`. Read the JSON it prints and copy the ids into the next command literally (shell variables do not persist between tool calls anyway).

3. If the agent will write files, give it its own worktree (read-only agents skip this and use your cwd). `.worktrees/` lives inside the repo so it stays sandbox-writable; the exclude line keeps it out of `git status`. Run from the repo root, each git command on its own:

       grep -qx '.worktrees/' .git/info/exclude || echo '.worktrees/' >> .git/info/exclude
       git worktree add -b agent/<slug> <repo-root>/.worktrees/<slug>

   Pick the model per the tiering table in AGENTS.md and always pass it: `--model haiku` or `--model sonnet` (`--model` with the provider's equivalent in opencode). Never omit it.

4. Write a launcher script, so the herdr command itself stays plain (no `$(...)` in it):

       # /tmp/agent-prompts/<slug>.sh
       #!/bin/sh
       # Claude Code (default permissions, so the user can approve in the pane):
       exec claude --agent <agent-name> --model <haiku|sonnet> "$(cat /tmp/agent-prompts/<slug>.md)"
       # opencode instead:
       # exec opencode --agent <agent-name> --model <provider/model> --prompt "$(cat /tmp/agent-prompts/<slug>.md)"

5. Choose placement:
   - **Grid pane** - the worker will likely need the user (approvals it cannot avoid, clarifying questions, a spec with judgment calls) or the user wants to watch. Use the 2x2 grid below, splitting with `--cwd <worktree-path>`.
   - **Background workspace** - well-specified autonomous work. It does not use a grid slot. herdr's sidebar and notifications surface it if it blocks, and you still check for blocked status:

         herdr workspace create --cwd <worktree-path> --label agent/<slug> --no-focus

     The new pane id is `.result.root_pane.pane_id` and the workspace id is `.result.workspace.workspace_id`. Then `herdr pane run <pane-id> "sh /tmp/agent-prompts/<slug>.sh"`. If a background worker blocks on something you cannot answer, tell the user its workspace label.

6. Grid placement: place the helper using the 2x2 grid protocol, then launch the agent interactively. Helpers live in a 2x2 grid beside the main pane so every pane stays readable - never chain right-splits, which shrink panes into unreadable slivers:

       +--------+------+------+
       |        |  H1  |  H3  |
       |  main  +------+------+
       |        |  H2  |  H4  |
       +--------+------+------+

   Slot sequence (split source and direction depend on which helpers are already open - count your open helper panes first via `herdr pane list`):

   - H1 (first helper): split MAIN pane, `--direction right`
   - H2 (second): split H1, `--direction down`
   - H3 (third): split H1, `--direction right`
   - H4 (fourth): split H2, `--direction right`

       herdr pane split <source-pane-id> --direction <right|down> --cwd <worktree-path> --no-focus
       # new pane id: .result.pane.pane_id
       herdr pane run <new-pane-id> "sh /tmp/agent-prompts/<slug>.sh"

   The main pane gives up width once (H1) and is never split again. Track which slots you opened; when a helper pane closes, ids can shift and slots free up - re-run `herdr pane list` before every split and fill the freed slot using the same sequence logic.

   HARD CAP: a delegator may have at most 4 helper panes open at once - the grid is the limit. If all 4 slots are busy, do not open a 5th pane or a new tab; wait for a running helper to finish and free its slot, or run the remaining delegations sequentially. If a task genuinely needs more than 4 concurrent helpers, stop and ask the user how to proceed.

## Monitor

The completion signal is the REPORT FILE appearing - not pane text, and not agent status. Wait on the file (a plain file check works inside the sandbox, so it may loop; in Claude Code use the Monitor tool with an until-loop rather than foreground sleep):

    until [ -f /tmp/agent-reports/<slug>.md ]; do sleep 30; done

Check status only to detect blockage, with a standalone `herdr pane list` (never inside the loop) and read `agent_status` for your pane id:
- Report file exists: the deliverable is ready. Optionally confirm the pane's status has settled (`idle`), then proceed to Collect.
- `blocked`: tell the user immediately - "Pane <pane-id> needs your input (approval or question)" - then keep polling. Do not spam repeat alerts for the same blockage.
- `working`: keep polling; extend the loop for long tasks.
- `gone`: the pane closed unexpectedly - report this to the user.
- Pane `idle` for a while and still no report file: the agent likely finished without writing the report or is sitting at a prompt - read the pane (`herdr pane read <pane-id> --source recent-unwrapped --lines 60`) and judge from there.
- Do NOT use `herdr wait output --match` on a completion token: the TUI echoes the delegation prompt, so any token you mandated can match on the echo before the work is done. Do NOT use `wait agent-status --status done` as the completion signal either: a finished TUI session often reports `idle`. Status is for blocked-detection; the file is for completion.
- While waiting you may continue your own independent read-only work, but never edit files the delegated agent may also touch.

Pane ids can shift when panes close: re-read ids from `herdr pane list` rather than trusting old ones.

## Collect and judge

1. Read `/tmp/agent-reports/<slug>.md`. If it is missing, fall back to:

       herdr pane read <pane-id> --source recent-unwrapped --lines 150

2. Judge the work yourself against the delegation spec. You own the quality bar; a subagent's success claim is not evidence.

## Lifecycle: close on success, keep on failure

- Accepted result: close the pane and remove the prompt file.

      herdr pane close <pane-id>         # background worker: herdr workspace close <workspace-id>
      rm -f /tmp/agent-prompts/<slug>.md /tmp/agent-prompts/<slug>.sh

  Keep the report file as evidence for your own final response. If the worker had a worktree, merge and remove it per the orchestrate skill's "Integrate and clean up" section.
- Rejected, failed, or still unclear: KEEP the pane open, tell the user the pane id and what is wrong. For rework, reuse the same session instead of respawning:

      herdr pane send-text <pane-id> "<corrective follow-up instruction>"
      herdr pane send-keys <pane-id> Enter

  then monitor again.

## Rules

- Be conservative: when in doubt, delegate inline. A pane must earn its existence.
- Always split with `--no-focus`; never steal the user's focus.
- Close only panes you spawned; never close or write to panes that are not yours.
- One agent per pane; one writer per worktree; never more than 4 helper panes open at once (background workspaces do not count toward the grid cap, but keep their number reasonable and close each one when done).
- If the agent CLI fails to start in the pane (read the pane to check), report the error to the user; do not silently fall back.
