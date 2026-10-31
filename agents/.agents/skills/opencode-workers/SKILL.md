---
name: opencode-workers
description: Use only when the user explicitly asks for opencode workers or names this skill. Starts, messages, waits for, reads, unblocks, interrupts, resumes and cleans up opencode v2 worker sessions from Claude Code, opencode or omp - headless (`opencode run` and the HTTP API) or visible in a Herdr pane - with a chosen agent, model and effort level and a brief in a markdown file. Lists the verified traps (client-side --auto, auto-rejected approvals and questions, symlinked agent files not reloading, `*` permission rules, Claude sandbox and guard rules) so workers do not stall.
---

# opencode-workers

Drive opencode v2 sessions as workers: you are the orchestrator, each worker is one opencode session on the shared background service. Every fact below was verified on the Pi with opencode 2.2.5 (2026-10-31) unless marked otherwise. Model tiering, briefs, verification and git rules still come from AGENTS.md and the `orchestrate` skill; visible-pane placement from `delegate-visibly`.

## Before the first call

- Health check: `opencode api get /api/info` prints JSON. If it fails, tell the user. Never stop, restart or reconfigure the service yourself: every session runs on it, including an opencode orchestrator's own (the agent host denies `opencode service stop|restart|set|unset`).
- **One plain command per call.** No pipe, `&&`, `;`, redirect, backtick or `$(`. Read the JSON output directly. In Claude Code on the agent host this is mandatory: chained or redirected `opencode`/`omp` calls run inside the sandbox and the guard blocks them. It costs nothing elsewhere, so do it in every harness.
- **Claude Code** needs `opencode *` in the sandbox `excludedCommands` (agent-permissions, installed by the owner with `bash regen-agent-host.sh`). Symptoms when it is missing: `PlatformError: ... FileSystem.open (.../opencode/log/opencode.log)` or `Doppler Error: you must provide a token` (the zsh alias `opencode` = `doppler run ... -- opencode` is snapshotted into Claude's shell). Tell the user; do not work around it.
- **omp** runs these through its bash tool. Before the agent-host regen they prompt for approval; after it `opencode` and `omp` are allowed.
- **opencode** as orchestrator: use the shell tool with `background: true` for anything long.

## Pick the worker

| Agent | Model (`provider/model#variant`) | Use |
|---|---|---|
| `worker-sonnet` | `github-copilot/claude-sonnet-5.5#high` | Clear spec: features, refactors, known-repro bugs, tests |
| `worker-opus` | `github-copilot/claude-opus-5.5#high` | Ambiguous or cross-cutting work, debugging with no known cause |
| `reviewer-fable` | `github-copilot/claude-fable-5.1#medium` | Read-only review. No shell, no edits, no web: attach the diff |

- The agent file sets model, effort and permissions. Override one run with `--model github-copilot/claude-sonnet-5.5#xhigh`. The Copilot Claude models offer `low|medium|high|xhigh|max`. Other models differ: `opencode api get /api/model` lists each model's `variants` (large output; `opencode models` lists IDs without variants).
- Unknown agent, model or variant: exit 1, `Error: Agent not found` / `Variant unavailable` on stderr.
- `opencode api get /api/agent` lists every agent, including the older `fixer`, `builder-*`, `code-reviewer`.
- Always pass `--agent` on the first call. On a new session without it you get the default `build` agent. Later calls without `--agent`/`--model` keep the session's.

## Names, briefs, reports

- **Choose the session ID yourself**: `ses_<repo>_<slug>`, e.g. `ses_redress_dev123`. It must start with `ses`; use lowercase letters, digits and underscores. `--session <id>` creates the session when it does not exist. Because you chose the name, you can find the worker again after your own compaction or a crash.
- Brief: `<repo>/.agent/briefs/<slug>.md`. Report: `<repo>/.agent/reports/<slug>.md` (the project's gitignored agent folder). Stay inside the project: on the agent host, writes elsewhere (e.g. `~/.cache`) ask for approval, which a headless worker without `--auto` cannot get. Avoid `/tmp` on the Pi: it is RAM and is wiped on reboot.
- Pass attachments by **absolute path**. `--file` can be repeated.
- The brief is self-contained (goal, scope and paths, constraints, acceptance criteria with exact checks, worktree and branch) and ends with:

      When finished, write your full report (what changed, how it was verified, open
      concerns, and a `## Remember` section) to <abs report path>, then reply with the
      same report and the word DONE. If you are blocked or need a decision, stop and end
      your reply with `BLOCKED: <your question>` - do not guess.

  The `BLOCKED:` line is needed because the question tool does not reach you in a headless run (see Unblock).

## 1. Start a headless worker (default)

From the repo the worker should work in:

```bash
opencode run --session ses_redress_dev123 --agent worker-sonnet --title "DEV-123 impl" --auto --file /home/ai/REPOS/redress/.agent/briefs/dev-123.md "Execute the attached brief (/home/ai/REPOS/redress/.agent/briefs/dev-123.md). If your context is compacted, re-read that file."
```

- **Run it in the background and let the process live until it ends** (Claude Code: `run_in_background: true`; opencode: `background: true`; omp: its background/async bash). The `run` process is what answers approvals with `--auto`.
- Output: stdout is only the final reply; stderr shows progress (one line per tool call). `--format json` streams events instead (every line carries `sessionID`; reply text is in `type=="text"` events): only use it when you need tool details, it gets big.

**Other directory (herdr worktree):** `opencode run` has no directory flag and Claude cannot `cd x && ...`. Create the session with its location first. A session keeps its directory whatever the caller's cwd:

```bash
opencode api post /api/session -d '{"id":"ses_redress_dev123","title":"DEV-123 impl","agent":"worker-sonnet","model":{"providerID":"github-copilot","id":"claude-sonnet-5.5","variant":"high"},"location":{"directory":"/home/ai/.herdr/worktrees/redress/dev-123"}}'
opencode run --session ses_redress_dev123 --auto --file /home/ai/.herdr/worktrees/redress/dev-123/.agent/briefs/dev-123.md "Execute the attached brief."
```

**`--auto` or not:**

| | Every rule that says `ask` | Use for |
|---|---|---|
| `--auto` | approved (`deny` rules still block) | writers |
| no `--auto` | rejected at once (stderr: `permission requested: shell (nproc); auto-rejecting`); the worker carries on without it | reviewers, research, anything that should only use already-allowed commands |

On the agent host every command that is not on the allow list asks. Never put `allow` rules into `POST /api/session` `permissions` or an agent file: they are applied after `/etc/opencode` and would override its denies.

## 2. Status and waiting

| Question | Command |
|---|---|
| Which sessions are running? | `opencode api get /api/session/active` - `{"data":{"<id>":{"type":"running"}}}` (your own opencode session appears here too: never interrupt it) |
| How did it end? | `opencode api get /api/session/<id>` - `.data.outcome` (`succeeded`, `interrupted`, ...), plus agent, model, cost, tokens |
| Wait until it is idle | `opencode api post /api/experimental/session/<id>/wait` - blocks, prints nothing, exit 0. A Bash timeout is not a failure: run it again |
| Is it stuck on me? | `opencode api get /api/session/<id>/permission` and `opencode api get /api/session/<id>/form`. An entry there while the session is active means it waits for an answer |

## 3. Read the result

```bash
opencode api get '/api/session/ses_redress_dev123/message?limit=4'
```

- Newest first. Query parameters go **in the path**; `--param` is silently ignored there.
- Message types: `user`, `assistant` (`content[]` items with `type:"text"` hold the reply, plus `agent`, `model`, `finish`, `cost`), `idle` (`outcome`), `agent-switched` (marks a new turn, not a real switch).
- The newest `assistant` message with text is the answer. For long tasks read the report file too.
- `opencode session list` lists sessions of the current project.

## 4. Send messages (agent to agent)

| You want | Do |
|---|---|
| Follow-up, and wait for the answer | `opencode run --session <id> --auto "..."` - blocks until the turn ends, prints the reply, keeps agent and model |
| Fire and forget | `opencode api post /api/session/<id>/prompt -d '{"text":"..."}'` - returns at once with the message id; then wait and read |
| Attach files | `run --file /abs/x.md` (repeatable), or `"files":[{"uri":"file:///abs/x.md","name":"x.md"}]` in the API body |
| Talk to a busy worker | `run --session` on a busy session steers its current turn (the worker sees the message at its next step; both clients get the combined reply). API: `"delivery":"steer"` (into the running turn) or `"delivery":"queue"` (after it) |
| Talk to a worker in a herdr pane | Same commands: the TUI shows messages sent through `run` or the API, and its replies are readable through the API |

API-sent prompts have no client, so nothing auto-approves: approvals and questions wait for you (section 5).

## 5. Unblock

- **Approval request** (`/permission` lists `{id, action, resources}`): ask the user unless the brief or the user already approved that kind of action, then
  `opencode api post /api/session/<id>/permission/<per_id>/reply -d '{"decision":"once"}'`
  Decisions: `once`, `always` (saves a project-wide allow: avoid), `reject` (rejects every pending request of that session; optional `"message"`).
- **Question** (`/form` lists forms with `fields[].key` and `options`): `opencode api post /api/session/<id>/form/<frm_id>/reply -d '{"answer":{"q0":"Green"}}'`. In a headless `run`, questions are cancelled automatically and the worker is told to assume and go on; only workers without a client (API prompts) leave forms pending.
- **`BLOCKED:` reply**: answer with `opencode run --session <id> --auto "<answer>"`.

## 6. Interrupt, resume, recover

- Stop a worker: `opencode api post /api/session/<id>/interrupt` - `{"interrupted":true}`, outcome `interrupted`. Killing the `run` process does **not** stop it: the service finishes the turn, but with no auto-approver, so its next `ask` waits forever.

| Symptom | Do |
|---|---|
| `run` died or timed out, session still active | Check `/permission` and `/form` and answer them, or wait. To restore auto-approval: `opencode run --session <id> --auto "Continue."` (steers the running turn) |
| Idle, outcome `interrupted` or work unfinished | `opencode run --session <id> --auto "You were interrupted. Re-read <brief path>, check git status, and continue."` |
| You lost your context | Your worker IDs are `ses_<repo>_<slug>`: `opencode session list`, `/api/session/active`, the last messages, the report files |
| Herdr pane closed | Start the TUI on the same session again (section 7) |
| Service down | Ask the user. Sessions are stored in the database; resume afterwards with `run --session`. Not verified: what happens to a turn that was running |

## 7. Visible worker in a Herdr pane

Placement, naming and cleanup follow `delegate-visibly`. The opencode TUI has **no `--agent` or `--model` flag** (`opencode --agent x` exits 1 and prints help), so:

1. Create the session through the API with agent, model, variant and location (section 1).
2. Start the TUI on it, as its own command:
   `herdr agent start <name> --kind opencode --pane <pane> --timeout 90000 -- --session <id>`
   The status bar shows agent, model and effort (e.g. `Worker-Sonnet · Claude Sonnet 5.5 GitHub Copilot · high`). Add `--auto` after `--session <id>` only when the user does not want to approve steps in the pane. A toast about an MCP server needing authentication can appear; it is harmless.
3. Prompt with `herdr agent prompt <name> 'Read <brief path> and follow it exactly.' --wait --timeout <ms>` or with section 4. Read the reply through the API (exact text) rather than from the screen.

Do not use `opencode mini`: it needs a TTY and its `--model` takes no variant.

## 8. Reviewer

Build the diff from the worker's actual changes, committed or not (one plain command each):

```bash
mkdir -p /home/ai/REPOS/redress/.agent/reviews
git merge-base main HEAD
git diff --output=/home/ai/REPOS/redress/.agent/reviews/dev-123.diff <merge-base sha>
git ls-files --others --exclude-standard
opencode run --session ses_redress_dev123_rev --agent reviewer-fable --title "DEV-123 review" --file /home/ai/REPOS/redress/.agent/briefs/dev-123.md --file /home/ai/REPOS/redress/.agent/reviews/dev-123.diff "Review the attached diff, plus these new untracked files: <list>, against the acceptance criteria in the attached brief."
```

- `git diff <merge-base>` compares the working tree with where the branch started, so it covers the worker's commits and its staged and unstaged edits. `main...HEAD` would miss uncommitted work, and plain `main` would include changes made on main since.
- `git diff` never shows untracked files: list them from `git ls-files --others --exclude-standard` in the prompt; the reviewer reads them itself.
- `git diff --output=` writes the file without a redirect.

The reviewer can read, glob and grep the repo, nothing else; its report is its reply. No `--auto` needed. Judge its findings yourself.

## 9. Clean up

When you have read the results: `opencode api delete /api/session/<id>` for each session you created, never anyone else's. Delete the brief and diff files you created; keep reports until your final answer. Close panes as `delegate-visibly` says.

## Traps (all verified)

1. `--auto` lives in the `run` process, not the session. Fire-and-forget or a killed client means approvals wait (section 5).
2. Headless approvals and questions do not reach you: asks are auto-rejected without `--auto`, questions are cancelled. Hence the `BLOCKED:` convention.
3. Agent files are symlinks into `~/dotfiles`; editing them does not trigger opencode's reload. After changing an agent file run `opencode api post /api/location/reload` and check `opencode api get /api/agent`. The reload restarts MCP connections in every session.
4. A permission rule whose resource is exactly `*` acts as that action's default and loses to any more specific allow (e.g. the managed `git status *`). Write `?*` to deny everything. Agent and session allows override managed denies, so add denies only.
5. Query parameters belong in the path: `'/api/...?limit=4'`.
6. A session keeps the directory it was created in; `run` from elsewhere does not move it.
7. Exit code 1 with `Error: ...` on stderr means the run never started (bad agent, model, variant, missing file).
8. Attachments (`--file`, `"files"` in an API body) are read before any permission check, even for paths the rules would deny or ask about. Never attach a path you would not read yourself; on the agent host the Claude guard refuses secret-store paths.
