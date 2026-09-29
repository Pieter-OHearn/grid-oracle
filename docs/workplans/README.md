# Assigning work and recording agent state

The work is ready to assign one package at a time. **WP01 is the only implementation package ready now.** Concept approval is complete; application implementation has not started.

## Sources of truth

| File                                       | Owns                                                                                 |
| ------------------------------------------ | ------------------------------------------------------------------------------------ |
| [PLAN](../../PLAN.md)                      | Dependency order, package overview, next assignment and release gates.               |
| [WORKPLANS](../../WORKPLANS.md)            | Canonical scope, tasks and acceptance criteria.                                      |
| [DECISIONS](../../DECISIONS.md)            | Confirmed requirements, adopted defaults and unresolved decisions.                   |
| `docs/workplans/WP01.md` through `WP16.md` | Each package's ownership, current state, evidence, blockers and resume instructions. |
| [HANDOFF](../../HANDOFF.md)                | Concise entry point for a fresh agent; not a second status database.                 |
| [Approved UI](../design/APPROVED_UI.md)    | Approved design direction and preserved reference.                                   |

Package state records are authoritative for detailed progress; PLAN is the coordinator-maintained summary. A record on a working branch describes unintegrated work and does not unlock a dependent package. Link durable reports and commits; never rely on task-chat history alone.

## Assignment and ownership

1. A coordinating agent or the owner checks the package's prerequisites on the integration `main`, then reserves it in PLAN and its state record with an owner/task identifier. Dispatch only after that reservation is visible to participating agents. Markdown files are a manual coordination system, not an atomic locking service.
2. Assign one package, or a named subtask with explicit boundaries. Large packages should produce focused changes. Record child tasks inside the parent record; the parent remains incomplete until every criterion is satisfied.
3. The implementer creates an isolated branch from the current integration `main` **before editing**. For non-ticket work use one of `feature/wp01-<description>`, `bugfix/wp01-<description>`, `docs/wp01-<description>`, `chore/wp01-<description>`, `test/wp01-<description>` or `research/wp01-<description>`, selected by primary change. Assigned ticket rules take precedence. Record the branch, base commit, dependency commits, intended files and next action in the state record. Do not implement directly on `main` unless the owner explicitly assigns a serialized direct-main change.
4. Concurrent implementations use isolated worktrees/branches. The coordinator allocates overlapping contracts, migrations and shared files. In particular, WP07 and WP08 consume the same frozen benchmark and must not independently retune or rewrite it.
5. Update the package record after meaningful milestones, changed scope, failed checks, blockers, and before pausing or ending a turn. Record what exists now, not only an intended plan. Avoid activity-only log spam.
6. Before review, run required checks, stage only package-owned files, and commit the complete review candidate using Conventional Commits. Use a focused message such as `chore(dev): establish reproducible development setup (WP01)`; include the workplan ID. Push the branch and create a ready-for-review GitHub PR to `main`, with a concise Conventional Commit-style title and a body covering scope, acceptance evidence, tests, migrations/rollback and remaining risks. Record the commit hash, PR number and URL. Commit intermediate safe milestones when a package spans multiple turns, but do not create unrelated cleanup commits.
7. Finish at `review_ready` only when acceptance evidence and reproducible checks exist **on a named commit with an open, ready-for-review GitHub PR**. Review may be performed by another assigned agent or the owner against that PR. The coordinator merges the approved PR into `main`, records the resulting integrated revision and marks it `complete` only when all acceptance criteria hold there. Integration into local `main` does not authorize a deployment.
8. The coordinator refreshes PLAN, unlocks newly eligible packages and chooses the next assignment. A subsequent fix must reopen the relevant record or create a bounded follow-up; do not silently erase the earlier review outcome.

If no coordinator has been named, the owner controls assignments and the single active agent may maintain the overview. Before worktree-based assignment, include the planning files, approved reference and reservation in the chosen base revision so fresh worktrees receive them. Do not sweep unrelated untracked files into that checkpoint. These files have not been committed by this planning task.

## Status vocabulary

| Status         | Meaning and transition                                                                                                         |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `waiting`      | A normal prerequisite is incomplete. Coordinator changes to `ready` after checking integrated evidence.                        |
| `ready`        | Start prerequisites are met and the package is available to assign.                                                            |
| `active`       | Claimed by one owner with a concrete next action.                                                                              |
| `blocked`      | Assigned work cannot proceed on its remaining scope. Record the exact blocker, who can resolve it, and what resumes afterward. |
| `review_ready` | Checks pass on a committed, named branch with an open ready-for-review GitHub PR; review/integration is outstanding.           |
| `complete`     | Acceptance passed, review recorded and changes integrated. This is not inferred from elapsed effort.                           |
| `deferred`     | Deliberately outside the current release scope; e.g. WP16 extensions pending individual selection.                             |

Typical flow: `waiting → ready → active → review_ready → complete`. A review can return work to `active`. A blocked package resumes only when its recorded blocker is resolved. Ordinary prerequisite waiting is not an incident. Dates and owners in the initial records are unset where no work has happened.

## Evidence and handoff

Use the package's existing record and fill all sections. On claim, map **every** acceptance clause from WORKPLANS into an evidence checklist; do not weaken or silently drop criteria. Save longer reports under `docs/workplans/reports/` when needed. Store large artifacts in the appropriate data/model store and record their durable location plus checksum; keep secrets and private data out of reports.

For each check record the command or manual procedure, environment, date, outcome and relevant report. Report `not run` honestly. Research records include dataset/split/config/code hashes, seeds, run IDs, compute budget, all meaningful failed trials and measured scores. Do not use an inspected test set to select a winner.

Before stopping, leave a next action precise enough for another agent to execute, including the file/function or command when known. Include unresolved questions, migration/backfill/rollback impact and what not to repeat. Review records need the reviewed revision, reviewer, findings, resolution and integrated revision; passing checks alone are not a review.

## Copyable assignment prompt

Replace `WP01` throughout with the chosen ready package. An assignment authorizes its local implementation, not every later package or external rollout.

```text
Implement WP01 in this GridOracle repository.

Read AGENTS.md, HANDOFF.md, PLAN.md, DECISIONS.md, the WP01 scope in
WORKPLANS.md, and docs/workplans/WP01.md. Follow docs/workplans/README.md.
Verify that this package is assigned to you and its prerequisites are
integrated. Preserve unrelated work. If the reservation is missing in a
single-agent session, record it before editing; coordinate rather than
overwriting another agent's ownership.

Before editing, create the conventional branch matching the work: for example,
`feature/wp01-short-description`, `bugfix/wp01-short-description` or
`docs/wp01-short-description`, from the current integration `main` (replace
WP01 with the assigned package). Record the base commit and branch in the
package state record. Do not edit on `main`.

Implement this package in focused changes. Update its state record at
milestones and before stopping, including acceptance evidence, checks,
blockers, changed files and an exact next action. Use the approved UI
reference when relevant. Record decision changes explicitly.

Before review_ready, stage only the assigned files, create a focused
Conventional Commit such as `feat(scope): short description (WP01)`, push the
branch, and open a ready-for-review GitHub PR to `main`. Record its number, URL
and commit hash. Stop at review_ready only when implementation and required
checks are done on that PR; leave review and integration evidence for the
coordinator. Do not start the next package automatically. Homelab wiki access
remains read-only.
```

## Copyable review prompt

```text
Review the completed WP01 change against WORKPLANS.md and its state
record. Confirm there is a named branch, implementation commit and open
ready-for-review GitHub PR; inspect that PR's diff against integration `main`
and its evidence; run checks needed to resolve material gaps. Record findings
and the reviewed revision in
docs/workplans/WP01.md. Return it to active if acceptance is incomplete.
Do not mark complete until review findings are resolved and the
coordinator merges the approved PR into `main`, records integration and
applicable verification.
```

No agents, GitHub issues or automations are launched by these documents.
