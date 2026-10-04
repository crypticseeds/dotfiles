---
name: orchestrate
description: Use when a task is big enough to plan and split - multi-step features, refactors, or fixes where work should be delegated, independently reviewed, and verified against concrete acceptance criteria. You act as orchestrator - you plan, delegate to implementer/reviewer agents (in visible herdr panes for write or long work), verify results yourself, and loop fixes until every criterion passes. Skip for small single-file edits you can do and verify directly.
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
4. Get the user's approval of the plan before delegating. Tasks that touch the same files run sequentially; independent tasks may run in parallel in separate worktrees.

## 2. Delegate

- Research and read-only review: inline via the Agent tool (`codebase-researcher`, `code-reviewer`, `security-reviewer`). Subagents cannot spawn subagents, so you coordinate all of them.
- Implementation, test runs, builds, long or approval-prone work: own herdr pane via the `delegate-visibly` skill (`claude --agent implementer`). One writer per worktree.
- Each delegation prompt contains: the task spec with acceptance criteria verbatim, scope, the report path, and the contract below.

## 3. Verify (never skip)

After a worker reports:

1. Run the acceptance checks yourself. Do not accept the worker's output as evidence.
2. Request independent review: `code-reviewer` with the plan and the diff range; add `security-reviewer` when the change touches auth, secrets, IAM, network, input handling, or CI. Pass the acceptance criteria so the review is judged against them.
3. Build a criteria table: each criterion PASS / FAIL / UNVERIFIED with evidence.

## 4. Heal

- Any FAIL, UNVERIFIED, or Critical/Important review finding goes back to the implementer (same pane, same session) as a corrective task that names the failing criteria and findings.
- Re-verify from step 3. Maximum 3 heal rounds per task. Then stop, summarize what was tried and learned, and ask the user.
- Never weaken a criterion or a test to get a pass. If a criterion is wrong, say so and ask.

## 5. Finish

Report: what changed, the criteria table with evidence, review verdicts, open concerns. Run the pane sweep (see Pane lifecycle) first. Do not commit, push, or open a PR unless the user asks.

## Pane lifecycle (you decide; panes are shared space)

After each verification pass, decide for every pane you spawned. Never touch panes you did not spawn.

- **Close** when the task is verified PASS on every criterion and its review is clean, and the agent has no further role in this plan. Read its report first (`herdr pane read`), then `herdr pane close`, so the space returns to you and the 4-pane grid stays usable.
- **Keep** when the agent will plausibly be needed again for the same task: a FAIL, UNVERIFIED criterion, or review finding is going back to it (its loaded context makes the fix cheaper), the user is mid-conversation with it, or it is blocked on an approval. Tell the user the pane id and why it stays open.
- **Free a slot early** if you need a pane and all 4 are held: close the pane whose task is verified and least likely to need rework, never one that is blocked or mid-heal.
- **Sweep at finish**: before your final report, list your panes (`herdr pane list`) and close every one still open that you no longer need. Anything left open must be named in the report with the reason.
- A pane that is `idle` is not automatically done. Only your own verification result closes it.

## Worker contract (include in every delegation)

Report each acceptance criterion as PASS/FAIL/UNVERIFIED with evidence. Write the final report to the given path, then state DONE. If blocked by an approval or a question, ask in your session and wait. Report out-of-scope problems; do not fix them. Never commit.
