# WP12 validation and visual evidence

Captured 2026-10-01 on macOS, Python 3.12.14, Node 26.10.0, Bun 1.4.2,
React 18.3.1, Vite 6.4.1, Vitest 3.2.4, headless native Chrome and axe-core 4.10.3.
Production Vite assets were served through localhost Vite preview with its API
proxy. This is local validation, not a deployment or live-provider result.
Forecast/correction data is explicitly synthetic; the historical scorecard is
the exact retained WP09 stored report, not fixture model-quality evidence.

`browser.json` records 32 passing checks, eight axe WCAG 2/2.1 A/AA audits with
zero violations and zero page exceptions. Mobile audits retain axe's incomplete
color-contrast items where cells are outside the scrolled viewport. The shared
token contrast test passes in both themes; desktop audits cover the same
foreground/background pairs. Native screen-reader and real-device checks are
not claimed and remain release verification.

| Screenshot | Evidence |
| --- | --- |
| `forecast-comparison.jpg` | 22-entry full field, source/cutoff/issuance, driver detail, both immutable horizons, named win-probability deltas |
| `forecast-dark.jpg` | Approved dark surfaces, readable numeric values and matching context |
| `historical-scorecard.jpg` | All pre-weekend models/ablations/baselines, honest cohort label, exact stored summary, reliability table and separate live evidence |
| `post-qualifying-scorecard.jpg` | Different horizon, qualifying fallback and scores, no winner-by-lowest-loss promotion |
| `result-corrections.jpg` | Original run, two stored result evaluations and an unscored latest correction |
| `methodology.jpg` | Model/target limitations, calibration scope, exact-position versus set-overlap glossary |
| `mobile-390.jpg`, `mobile-320.jpg` | Page reflow with named, keyboard-scrollable full-field comparison tables |
| `evaluation-error.jpg` | Retryable evaluation failure without retained scores |

Visual inspection compared final desktop/light/dark and mobile captures with
APPROVED_UI.md and the preserved WP10/WP11 references. The restrained sidebar,
red accents, condensed race typography, neutral date-valid team cues, compact
spacing and semantic tables remain. Inspection caught inherited 42px rank-column
styling squeezing trust-table text headers; a dedicated text-header width rule
fixed it. Final captures supersede those preliminary layouts; a browser geometry
assertion covers the repaired width. The preserved approved fragment is unchanged.

## Stored numerical and wording examples

- Race-only standings winner log loss: `1.9033984769473842`, rendered `1.903398`.
  Winner-pick hit rate: `0.42857142857142855`, rendered `42.9%`, with 70 observed races.
- After-qualifying baseline winner log loss: `1.7375783035040486` (public rendering
  `1.737578`); winner-pick hit rate `0.6142857142857143`, rendered `61.4%`, 70 races.
- Exact source values for **every** summary, race and winner reliability bin are
  compared in `api/tests/test_trust.py`; the generator separately verifies the
  retained report hash and the committed public projection bytes.
- Synthetic forecast change `0.20 → 0.25` gives `+5.0 percentage points` in win
  chance. Stored zero remains `0%`; unavailable remains Unknown/Not available.
- Synthetic correction histories preserve stored losses and revision identities;
  an unscored revision 3 never inherits revision 2's score. Generic legacy
  evaluation records and unpublished-run scores are withheld.
- Historical rows retain the stored `season:round` keys, classification counts and
  missing-feature counts. There is no renumbering or interpolation of a trend.

The screenshot examples are display-rounded values, not a new evaluation. No
browser calculation establishes a performance score. The exact report hash is
`e1c5d0fd6b002e48a10a428b27f64348b72be217cd86e97720d4a9cc4d9c99c7`;
`python -m docs.models.wp09.verify_artifacts` verified all 116 retained files and
both identical final reports without changing research code or evidence.

## Reproduce

```sh
UV_CACHE_DIR=/tmp/gridoracle-uv-cache uv sync --frozen --extra api --extra pipeline --group dev
.venv/bin/python -m api.tests.trust_fixture --database /tmp/wp12-browser.sqlite
DATABASE_URL=sqlite:////tmp/wp12-browser.sqlite .venv/bin/uvicorn api.main:app --host 127.0.0.1 --port 8000
# In a separate terminal:
cd dashboard
bun install --frozen-lockfile
bun run build
bun run preview --host 127.0.0.1 --port 4173
# In another terminal at the repository root, with Playwright resolvable:
AXE_PATH=/path/to/axe-core/axe.min.js NODE_PATH=/path/to/node_modules node scripts/wp12_browser.cjs
```

The fixture builder refuses existing schemas. axe was installed only in a
disposable `/private/tmp/wp12-browser-tools` directory; project dependency locks
are unchanged. Local API/preview processes are stopped after capture.

Checks: API/scripts 76 tests; dashboard 20 tests, including theme contrast;
typecheck/lint/format; Python Ruff; generated DTO/performance drift checks;
108 focused benchmark/provenance tests; production build and whitespace checks.
Full pipeline regression result is recorded in WP12.md. The source contracts
and checks are in [WP12_PUBLIC_TRUST.md](../../../api/WP12_PUBLIC_TRUST.md).
