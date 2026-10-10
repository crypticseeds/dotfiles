---
name: orchestrate
description: Use when a task is big enough to plan and split - multi-step features, refactors, or fixes where work should be delegated, independently reviewed, and verified against concrete acceptance criteria. You act as orchestrator - you plan, route each task to the cheapest capable model tier (Haiku, Sonnet, or yourself), delegate to implementer/reviewer agents in their own worktrees (in visible herdr panes for write or long work), verify results yourself, and loop fixes until every criterion passes. Skip for small single-file edits you can do and verify directly.
---

# orchestrate

You are the orchestrator. You do not trust a worker's success claim: you verify it. Work is done only when every acceptance criterion has a PASS backed by evidence.

## 1. Spec and plan (before any delegation)

1. Clarify the goal. Ask unresolved questions inline with AskUserQuestion, not in a document.
2. Write the plan as markdown in `docs/plans/<slug>.md` (specs in `docs/specs/`). Use HTML only if the plan needs a diagram or preview the user must judge (see `html-deliverable`).
3. Every task in the plan carries:
   - **Scope**: files or areas it may touch, and what it must not touch.
   - **Acceptance criteria**: numbered, each with the exact check (command and expected result, or observable behavior). "Works correctly" is not a criterion.
   - **Out of scope**: what a worker must report, not fix.
   - **Tier**: Haiku, Sonnet, or orchestrator (Opus), per the tiering table in AGENTS.md, with one line of reasoning. Split a task further if part of it fits a cheaper tier.
4. Get the user's approval of the plan before delegating. Tasks that touch the same files run sequentially; independent tasks may run in parallel in separate worktrees.

## 2. Delegate

- Research and read-only review: inline via the Agent tool in your own checkout, always with an explicit `model`. Subagents cannot spawn subagents, so you coordinate all of them.
  - `codebase-researcher`: `haiku` for quick lookups, `sonnet` for medium or very thorough.
  - `code-reviewer`: `sonnet`; `opus` when the diff touches auth, IAM, secrets, Terraform, or exposes a service.
  - `security-reviewer`: `opus`.
- Implementation, test runs, builds, long or approval-prone work: `claude --agent implementer --model <haiku|sonnet>` in its own git worktree on branch `agent/<slug>`, launched via the `delegate-visibly` skill. It picks grid pane (worker likely needs the user) or background workspace (autonomous). One writer per worktree.
- Each delegation prompt contains: the task spec with acceptance criteria verbatim, scope, the worktree path and branch, the report path, and the contract below.
- Do not do mid- or small-tier work yourself to save a round trip. Your tokens go to planning, specs, verification, and the tasks the table reserves for the top tier.

## 3. Verify (never skip)

After a worker reports:

1. Run the acceptance checks yourself, inside the worker's worktree. Do not accept the worker's output as evidence.
2. Request independent review: `code-reviewer` with the plan and the diff range; add `security-reviewer` when the change touches auth, secrets, IAM, network, input handling, or CI. Pass the acceptance criteria so the review is judged against them.
3. Build a criteria table: each criterion PASS / FAIL / UNVERIFIED with evidence.

## 4. Heal

- Any FAIL, UNVERIFIED, or Critical/Important review finding goes back to the implementer (same pane, same session) as a corrective task that names the failing criteria and findings.
- Escalate the tier instead of looping: a Haiku worker that fails once moves to a fresh Sonnet worker in the same worktree (close the Haiku pane first); a Sonnet worker that fails two heal rounds hands the task back to you.
- Re-verify from step 3. Maximum 3 heal rounds per task across all tiers. Then stop, summarize what was tried and learned, and ask the user.

## Integrate and clean up (after a task is verified)

Run from your own checkout, one task at a time:

    git merge agent/<slug>                 # stop and ask on any conflict you cannot resolve trivially
    # re-run the task's acceptance checks on the merged result
    # close its pane or workspace first (see Pane lifecycle): a process inside keeps the worktree
    agent-clean .worktrees/<slug>          # removes worktree, branch and its /tmp dir; "keep ..." = not safe yet

Without `agent-clean`: `git worktree remove .worktrees/<slug>` (never --force) and `git branch -d agent/<slug>` (never -D). You own this cleanup; do not leave it to the user. Never remove a worktree or branch whose work is unmerged, unverified, or still needed for a heal round.
- Never weaken a criterion or a test to get a pass. If a criterion is wrong, say so and ask.

## 5. Finish

Report: what changed, the criteria table with evidence, review verdicts, which tier ran each task (and any escalations), open concerns. Run the pane sweep (see Pane lifecycle) first, then `agent-clean`, and confirm `git worktree list` shows no leftover `agent/*` worktrees. Your merges of `agent/*` branches are local; do not commit further, push, or open a PR unless the user asks.

## Pane lifecycle (you decide; panes are shared space)

After each verification pass, decide for every pane you spawned. Never touch panes you did not spawn.

- **Close** when the task is verified PASS on every criterion and its review is clean, and the agent has no further role in this plan. Read its report first (`herdr pane read`), then `herdr pane close`, so the space returns to you and the 4-pane grid stays usable.
- **Keep** when the agent will plausibly be needed again for the same task: a FAIL, UNVERIFIED criterion, or review finding is going back to it (its loaded context makes the fix cheaper), the user is mid-conversation with it, or it is blocked on an approval. Tell the user the pane id and why it stays open.
- **Free a slot early** if you need a pane and all 4 are held: close the pane whose task is verified and least likely to need rework, never one that is blocked or mid-heal.
- **Sweep at finish**: before your final report, list your panes (`herdr pane list`) and close every one still open that you no longer need. Anything left open must be named in the report with the reason.
- A pane that is `idle` is not automatically done. Only your own verification result closes it.

## Worker contract (include in every delegation)

Work only inside the given worktree. Report each acceptance criterion as PASS/FAIL/UNVERIFIED with evidence. When every criterion passes, commit your change to the given `agent/<slug>` branch (Conventional Commits, no AI attribution); never push, never touch other branches. Write the final report to the given path, then state DONE. If blocked by an approval or a question, ask in your session and wait. Report out-of-scope problems; do not fix them.
