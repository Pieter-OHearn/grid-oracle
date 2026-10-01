# GridOracle handoff

## Goal

Build a public, season-reusable F1 forecasting product with transparent pre-weekend and post-qualifying probabilities. Accuracy takes priority over model type. Initially use free data and homelab infrastructure, with separately authorized research compute and deployment.

## Current Progress

WP01–11 are integrated, including WP09 `60c5376` and WP11 `1994c6e`. WP12
is owner-approved after independent review found no actionable issues at
`86bade92e4fd2abf1d903080a5fdc4108e34c2ae`. Its completion takes effect on
[PR #107](https://github.com/Pieter-OHearn/grid-oracle/pull/107) merge into `main`; the PR's [GitHub merge revision](https://api.github.com/repos/Pieter-OHearn/grid-oracle/pulls/107) (`merge_commit_sha`) records the actual
integration identity. An open PR remains review-ready. [PLAN](PLAN.md) and
[WP12](docs/workplans/WP12.md) carry the completion condition and dependency gates.

WP12 adds driver/full-field winner probabilities, horizon comparison, source and
coverage context, public model/calibration/methodology cards, exact stored
historical/baseline scorecards and live-issued event/correction history. It keeps
reconstructed out-of-sample history separate from prospective performance;
unsupported probabilities and missing stored evaluations remain unavailable.
Implementation: `e837c9586f7b5a5b4d8e893d201a3c0ce5008bb2`; branch:
`feature/wp12-public-forecast-trust`; worktree: `/private/tmp/grid-oracle-wp12`;
base: `60c5376`. The preserved approved UI snapshot and frozen research evidence
remain unchanged.

WP13/WP14 are ready to assign. WP14 final acceptance needs WP13 after WP12
integrates; WP15 still waits for WP13/WP14. No dependent implementation is claimed.
WP13 must follow the immutable GHCR image/model-bundle and reviewed homelab digest
promotion contract introduced by PR #106. Integration does not deploy the product.

## What Worked

- WP12 validation: 76 API/script tests, 411 pipeline tests (one optional torch module skipped), 20 frontend tests, lint/typecheck/build and both generator drift checks. Browser: 32 checks, eight axe audits with zero violations and nine retained screenshots. Review reran 22 API and 11 frontend tests; all GitHub checks passed at reviewed head. Evidence: [WP12 captures/report](docs/design/evidence/wp12/README.md); contract: [public trust](docs/api/WP12_PUBLIC_TRUST.md).
- WP11 validation: 67 API/script tests, 16 frontend tests, lint/format/typecheck, generated-contract checks and production build. GitHub checks pass at the accepted head.
- Retained evidence covers a 22-entry field, historical refresh/season switching, 33 browser checks, seven native PostgreSQL contract checks and nine screenshots. Eight additional disposable Compose checks prove migration ordering, frontend startup with no API and proxy recovery after an API IP change without restarting the frontend.
- Nginx resolves the API through Docker DNS at request time. A separate sample migration service upgrades only the committed disposable demo before API startup; legacy demo predictions remain unpublished.
- Contracts: [PUBLIC_V1](docs/api/PUBLIC_V1.md), [lineage](docs/provenance/FORECAST_LINEAGE_CONTRACT.md), [season/target](docs/domain/SEASON_AND_TARGET_CONTRACT.md). Evidence: [WP11 captures and reports](docs/design/evidence/wp11/README.md).
- The owner-approved restrained F1 design remains the UI source of truth. The preserved approval snapshot is unchanged.

## What Didn't Work

- Clean Docker image builds still time out fetching Nginx registry metadata. Current source/config/assets passed startup/recovery tests using cached exact-version runtimes; a clean image build remains release verification.
- Historical team colors have no temporal schema contract, so strips remain neutral with date-valid names. Unknown values remain null; no forecast or historical branding is invented.
- Native screen-reader/device/participant tests and live published-data verification remain release checks. No deployment or real-data migration occurred; all WP11 test services and disposable volumes are removed.
- WP09 retained scores are explored chronological reconstruction, not pristine holdout/as-of/prospective evidence. WP12 exposes those limitations and stored metrics without selecting a new champion. No valid prospective aggregate is stored; release work must collect honest live-issued evidence. Production evaluations need the explicit `wp12-v1` stored-metric semantics; generic legacy records remain withheld. Per-feature attribution and unsupported outcomes remain unavailable.

## Next Steps

1. Owner will merge approved [PR #107](https://github.com/Pieter-OHearn/grid-oracle/pull/107) after final checks pass; verify its actual GitHub merge revision is on `origin/main`. The completion docs are included in the same PR.
2. Reserve WP13 with the owner/coordinator and create an isolated branch. Start capacity/ingress/recovery evidence under its delivery contract. WP14 may start its harness after reservation; final acceptance waits for WP13 integration. WP15 remains waiting for WP13/WP14.
3. Recheck clean image packaging, native assistive technology/devices and operational recovery under release workplans. The homelab wiki remains read-only; infrastructure mutation and deployment need applicable authorization.
4. Read `AGENTS.md`, PLAN, DECISIONS, the execution guide and the assigned package before editing. Preserve unrelated `.codex/` and `.ticket-workflow/` work. Package state records and integrated commits establish implementation status.
