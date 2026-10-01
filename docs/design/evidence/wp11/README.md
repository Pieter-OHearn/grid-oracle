# WP11 acceptance evidence

Captured 2026-10-01 using Node 26.10.0, Bun 1.4.2, React 18.3.1,
Vite 6.4.1, Vitest 3.2.4, isolated headless Chrome and local Nginx 1.28.2.
All displayed forecast outputs are explicitly synthetic acceptance fixtures;
no real forecast, provider ingestion or public deployment is claimed.

`browser.json` records 33 passing checks and zero browser exceptions through
`http://127.0.0.1:4300`, serving the production build with the exact
`dashboard/nginx.conf`. The local Nginx runtime came from a cached image;
compiled assets/config were mounted read-only. The normal Dockerfile build
could not retrieve remote base-image metadata (registry timeout), so no clean
registry-based image-build result is claimed. Refresh fallback, API proxying,
asset cache headers and runtime configuration syntax were independently verified.

| Evidence | Coverage |
| --- | --- |
| `desktop-full-field.jpg`, `desktop-dark.jpg` | 1440px approved light/dark shell, local fonts, 22 typed API entries, cutoff/coverage |
| `mobile-390.jpg`, `mobile-320.jpg` | Wrapped navigation and season control; local horizontal table scrolling, page reflow |
| `absent-forecast.jpg`, `api-unavailable.jpg` | Successful no-publication state versus retryable 503, no retained percentages |
| `loading.jpg`, `empty.jpg`, `unknown.jpg` | Pending request, zero-size collection and unknown values without false totals/ranks |
| `browser.json` | Historical refresh, main-journey season switches, legacy links/results/404, lazy visualization, error retry focus, keyboard/history, all main pages at 390/320px |
| `postgres.json` | Seven PostgreSQL 16 native JSON/timestamp/alias/publication/session/season checks |
| `packaging.json` | Nginx syntax/proxy/SPA/cache checks and external image-build limitation |

Visual inspection compared desktop/full-field and mobile captures against
WP10's `wp10-desktop-comparison.jpg` and `wp10-320-comparison.jpg`, plus
APPROVED_UI.md. The restrained neutral sidebar, race-red control/focus states,
condensed headings/drivers, timing numerals, dividers and readable tables are
preserved. Public data replaces synthetic reference controls. Team strips are
neutral because the integrated domain has no historical color contract;
visible date-valid team names remain. No new design identity was introduced.

The browser script is `scripts/wp11_browser.cjs`; fixture setup and commands
are documented in `docs/api/PUBLIC_V1.md`. The PostgreSQL check script refuses
non-empty databases via the shared fixture builder. The scripts retain no
credentials, raw database dump or model artifact in this evidence directory.

Checks: 41 API tests plus 22 script/domain/migration tests pass (63 combined);
376 pipeline tests pass, one pre-existing optional backend test skips;
16 dashboard tests pass. Python lint/format, frontend format/lint/typecheck,
generated-contract drift check, production build and independent WP10 reference
build pass. Browser verification also confirms the visualization chunk is
absent until explicitly requested. The production entry is ~208kB JS, lazy
chart ~331kB, and legacy rollback view ~244kB. The existing Browserslist age
warning remains. Self-hosted font files remain ~1.1MB and their SIL licenses
are included in production `font-licenses/` assets.

Native screen-reader, hardware-device and participant usability testing were
not run. There is no deployed endpoint, real published forecast or migration/
backfill performed here. These checks verify the public foundation, not model
quality, a WP12 scorecard or operational release readiness.

CI dependency repair: the first API CI run failed collection because its minimal
requirements omitted Alembic. The API development requirements now include the
already-adopted `1.14.1` pin. A fresh requirements-only environment passed all
41 API tests and the generated-contract/lint checks. Replacement [Backend CI
36825792784](https://github.com/Pieter-OHearn/grid-oracle/actions/runs/36825792784)
passed the API and Ruff jobs at repair revision `d813b7e`. No application
behavior or screenshot changed in that repair.
