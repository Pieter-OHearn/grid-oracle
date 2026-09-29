# GridOracle handoff

## Goal

Build a public, season-reusable F1 forecasting product with transparent pre-weekend and post-qualifying probabilities. Accuracy takes priority over model type. Serve on initially free homelab infrastructure, with separate experiments on the owner's 5060-equipped PC or M1 Mac when their capabilities are verified.

## Current Progress

Review and planning are complete; application implementation has **not** started. The owner approved the latest dashboard design on 2026-09-28. Start with [PLAN](PLAN.md), [agent execution guide](docs/workplans/README.md) and the assigned package's state record. **WP01 is the next ready package.** PLAN and the records carry live status; this handoff is an entry point.

The review documents 36 findings; WORKPLANS defines 16 packages. The evidence archive contains 40 public responses across 92 races, with a reproducible descriptive qualifying-order baseline on 91 races. Its results are not the current model's score or a validated as-of benchmark. Scope, acceptance, rollback and decision gates are documented.

The planning baseline is branch `main`, commit `934c23575d156049af8c3bcd2e28bf9ba91afeec`. Re-check current Git state. Planning documents/reference/state records are local changes, not a committed checkpoint. Existing `.codex/` and `.ticket-workflow/` work predates this package and must be preserved. Before isolated worktree assignment, include only the intended planning changes in the chosen base revision so agents receive them.

## What Worked

- Review-time checks passed: 205 pipeline tests, 25 API tests, three frontend tests, Python lint/format, frontend lint/format/typecheck/build. These are historical checks, not verification of later code. Detailed evidence is in [repository review](docs/REPOSITORY_REVIEW.md).
- The offline evidence audit reproduced the archived data summary; 40 response hashes were verified. See [evidence instructions](docs/evidence/README.md).
- The existing stack already includes XGBoost. Repair temporal evaluation, data lineage and immutable publication before comparing replacement models.
- The owner approved a restrained dashboard with F1 typography/timing-table details. Use [approved UI](docs/design/APPROVED_UI.md), which supersedes the older design reference.

## What Didn't Work

- Existing scores are not trustworthy performance evidence: reverse-time testing, hindsight bootstrap replay, mutable forecasts and score-gap “confidence” are documented defects. No trained artifact/current dataset was available to measure the deployed model.
- The existing local environment lacked FastAPI. API tests ran successfully in an isolated dependency environment; WP01 must make the supported setup reproducible.
- The first visual concepts felt too generic. Do not restart with the rejected Journal treatment or ask the owner to approve the same selected identity again.
- Homelab capacity, public ingress and backups remain unmeasured/unresolved. The wiki is **read-only**, and its contents do not authorize execution or deployment. Exact GPU/VRAM/OS and machine memory also need verification.

## Next Steps

1. Read `AGENTS.md`, PLAN, DECISIONS and the execution guide; check current instructions and working tree.
2. Assign/reserve [WP01](docs/workplans/WP01.md). Follow its acceptance criteria in WORKPLANS and keep its record current. Do not run the legacy bootstrap on a real database.
3. For non-ticket work, create a conventional branch such as `feature/wpNN-short-description`, `bugfix/wpNN-short-description` or `docs/wpNN-short-description` before editing. Before review, create a focused Conventional Commit, push the branch, and open a ready-for-review GitHub PR to `main`. Record its number, URL and hash. Only then leave the package `review_ready` with checks, evidence, rollback notes and an exact next action. The coordinator records PR review/integration before `complete` and then unlocks dependencies.
4. Continue through the documented order. WP02 settles targets/season contracts; WP03–06 establish trustworthy history and benchmarks; UI/operations can progress on the documented parallel tracks.

No implementation agent has been launched and no public deployment authorized by this planning handoff.
