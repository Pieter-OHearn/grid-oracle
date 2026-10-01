# GridOracle handoff

## Goal

Build a public, season-reusable F1 forecasting product with transparent pre-weekend and post-qualifying probabilities. Accuracy takes priority over model type. Initially use free data and homelab infrastructure, with separately authorized research compute and deployment.

## Current Progress

WP01–11 are complete as confirmed by the owner on 2026-10-01. WP01–08 and WP10 are integrated; owner-approved WP09 and WP11 completion takes effect when PR #104 and PR #105, respectively, merge into `main`. These branch records do not claim those merges have already happened. [PLAN](PLAN.md) and [WP11](docs/workplans/WP11.md) carry the matching completion entry and integration condition. PR #105's merge commit is the integration identity; no hash is invented before merge.

WP11 implements the approved WP10 design with season-aware public API resources, publication-only forecasts, generated DTOs, caching/cancellation, historical labels, explicit data/error states, accessible responsive tables and static packaging. Its final application repair is `11cabbfa6448add1e7b914cc19912d0327f1b797` (equivalent to originally tested `5fcf06c`). The owner accepted original reviewed head `b2e7c32`, whose checks pass; the equivalent remotely rebased head is `d584524` before this final documentation commit. Branch: `feature/wp11-season-aware-public-app`; worktree: `/private/tmp/grid-oracle-wp11`; original base: `d0a13d0`; current rebased integration base: `a79766cead5dd90849d5884a86508cab45485e27`. The newer deployment-promotion contract from PR #106 is preserved.

WP09 is owner-approved complete on PR #104, with its measured baseline-retention result and limitations retained. WP12, WP13 and WP14 are ready for assignment once their approved prerequisites integrate; their own completion/release gates remain. None is assigned by this wrap-up. Public model explanations and performance scorecards remain WP12 work.

## What Worked

- WP11 validation: 67 API/script tests, 16 frontend tests, lint/format/typecheck, generated-contract checks and production build. GitHub checks pass at the accepted head.
- Retained evidence covers a 22-entry field, historical refresh/season switching, 33 browser checks, seven native PostgreSQL contract checks and nine screenshots. Eight additional disposable Compose checks prove migration ordering, frontend startup with no API and proxy recovery after an API IP change without restarting the frontend.
- Nginx resolves the API through Docker DNS at request time. A separate sample migration service upgrades only the committed disposable demo before API startup; legacy demo predictions remain unpublished.
- Contracts: [PUBLIC_V1](docs/api/PUBLIC_V1.md), [lineage](docs/provenance/FORECAST_LINEAGE_CONTRACT.md), [season/target](docs/domain/SEASON_AND_TARGET_CONTRACT.md). Evidence: [WP11 captures and reports](docs/design/evidence/wp11/README.md).
- The owner-approved restrained F1 design remains the UI source of truth. The preserved approval snapshot is unchanged.

## What Didn't Work

- Clean Docker image builds still time out fetching Nginx registry metadata. Current source/config/assets passed startup/recovery tests using cached exact-version runtimes; a clean image build remains release verification.
- Historical team colors have no temporal schema contract, so strips remain neutral with date-valid names. Unknown values remain null; no forecast or historical branding is invented.
- Native screen-reader/device/participant tests and live published-data verification remain release checks. No deployment or real-data migration occurred; all WP11 test services and disposable volumes are removed.
- Legacy model scores and the archived qualifying baseline are not validated prospective model performance. WP09/WP12 and the later integration/release packages must establish that evidence.

## Next Steps

1. Merge owner-accepted [WP09 PR #104](https://github.com/Pieter-OHearn/grid-oracle/pull/104) and [WP11 PR #105](https://github.com/Pieter-OHearn/grid-oracle/pull/105) into `main` with required checks passing. Their completion entries then become integrated; verify the GitHub merge revisions before consuming them as prerequisites.
2. The owner/coordinator may then reserve WP12, WP13 or WP14 in their state records and create isolated branches. Read the delivery contract introduced by PR #106 before operational work.
3. Recheck clean image packaging, native assistive technology/devices and operational recovery under the later release workplans. The homelab wiki remains read-only; infrastructure mutation and deployment need their applicable authorization.
4. Read `AGENTS.md`, PLAN, DECISIONS, the execution guide and the assigned package before editing. Preserve unrelated `.codex/` and `.ticket-workflow/` work. Package state records and integrated commits, not old planning prose, establish implementation status.
