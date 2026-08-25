---
name: oss-contribution
description: Open-source contribution workflow gate. Use whenever the user wants to contribute to an external OSS repository - claiming a GitHub issue, preparing a first PR, "let's submit a PR", "work on issue #N", or any push/PR against an upstream project. Enforces the critical flow (policy scan, claim before code, upstream branch, project verification gate, DCO sign-off, no AI attribution, no public actions without approval) so no step is skipped.
---

# OSS Contribution Flow

A checklist-driven workflow for contributing to open-source repositories.
Every step is a gate: do not proceed to the next until the current one is
done or the user explicitly waives it. Announce which step you are on.

## Step 0 - Policy scan (once per repo)

Before any work, establish the repo's rules:

1. Read `CONTRIBUTING.md` (repo-level, then org-level if the repo points to
   one), `AGENTS.md`, `.github/PULL_REQUEST_TEMPLATE.md`, and issue templates.
2. Answer explicitly: Are AI-assisted contributions allowed, and under what
   conditions? Is DCO sign-off required? Is there a pre-merge verification
   command (e.g. `make presubmit`, `make lint test`)? How are issues claimed
   (Prow `/assign`, plain comment, maintainer assignment)?
3. Report the findings to the user before writing anything.

## Step 1 - Issue first

- Non-trivial work must trace to an issue. If none exists, draft one for the
  user to file, or ask them to link one. Trivial typo fixes may skip this if
  the project allows it.
- Confirm the issue is OPEN and UNCLAIMED: read all comments and assignees.
  A comment saying "I'll take this" counts as a claim even without assignment.
- Use the firecrawl MCP for this (see the `firecrawl` skill): scrape the full
  issue thread and search for existing PRs referencing the issue. Generic web
  fetch truncates GitHub pages and has caused duplicate PRs.

## Step 2 - Claim before code

- Draft a short claim comment: what you intend to change and the planned
  approach, in one or two sentences.
- NEVER post it yourself. Public actions under the user's identity (comments,
  reviews, PR creation, reactions) require explicit per-action authorization.
  Default: hand the draft to the user as quoted text to post themselves.

## Step 3 - Fork and branch hygiene

```bash
git remote add upstream <upstream-clone-url>   # one-time
git fetch upstream
git checkout -b <type>/<short-topic> upstream/main
```

- Branch from fresh `upstream/main`, never from a stale local main.
- Branch name matches the change type: `docs/...`, `fix/...`, `feat/...`.

## Step 4 - Scoped change

- Every changed line traces to the issue. No drive-by refactors, renames,
  reformatting, or extra improvements.
- Verify every factual claim in docs against the code or existing docs. Check
  that every link target and anchor actually exists.
- Review the diff for patterns maintainers decline: speculative hardening,
  defensive abstractions with no caller, AI-generated filler comments.

## Step 5 - Verification gate

- Run the project's pre-merge command (found in Step 0) and confirm it passes
  with real output. "It should pass" is not evidence.
- If the change is user-facing behavior, reproduce/exercise it as an end user
  would where feasible.

## Step 6 - Commit

- DCO sign-off if required: `git commit -s`.
- Imperative subject, ~72 chars; body explains WHY, not what.
- NEVER add AI attribution: no agent co-author trailers, no "Generated with"
  lines. Sign-off is the only trailer.
- Only the intended files. Check `git status` for stray artifacts first.

## Step 7 - Push and PR (ask first)

- Pushing and opening the PR are public actions: get explicit user approval
  for each, per action, before running them.
- Use the project's PR template verbatim. Reference the issue
  (`Fixes #N`). Fill required blocks (e.g. `release-note`; write `NONE` for
  changes with no user-facing impact, if the project uses that convention).
- If a test plan section exists, mark only tests that actually ran and passed.

## Step 8 - After opening

- Watch CI; fix failures with new commits (respect the project's squash or
  fixup conventions).
- Respond to review on substance. The user is the author of record and must
  be able to defend every line - flag anything they should read closely
  before replying to reviewers.
