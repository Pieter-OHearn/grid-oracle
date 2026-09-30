# GridOracle design system and fan journeys — WP10

This is the implementation reference for the owner-approved [dashboard direction](APPROVED_UI.md). The approval snapshot and its checksum remain unchanged. The executable React reference is **synthetic** and separate from the production application. No API integration, prediction logic, public deployment or season-aware delivery is included.

## Run and build

From `dashboard`, run `bun install --frozen-lockfile`, then `bunx vite --config vite.wp10.config.ts`. Open `http://127.0.0.1:3010/wp10.html`. Hash destinations support reference navigation and browser history; they are not WP11 season URLs. Build with `bunx vite build --config vite.wp10.config.ts` (output `dist/wp10`). Production `index.html`, its entry point and its build remain unchanged.

Run `bun run format:check`, `bun run lint`, `bun run typecheck`, `bun run test`, `bun run build`, and the separate reference build. The reference code lives in `dashboard/src/design-system/`; production does not import it. WP11 may extract/import the reusable components after adapting their data contracts and URL ownership.

## Tokens and typography

`tokens.css` is the canonical token source, scoped under `.go-system`. Its default follows device appearance; light/dark preview overrides are local to the reference. Preserve the restrained red identity, thin separators, modest panels and compact 178px sidebar. No broadcast or purple variation is shipped.

| Token | Light | Dark | Usage |
| --- | --- | --- | --- |
| surface | `#ffffff` | `#121416` | Main canvas and selected controls |
| sidebar | `#f7f7f8` | `#17191c` | Navigation, metadata, timing headers |
| subtle | `#f5f5f6` | `#1c1f23` | Control grouping |
| ink | `#202226` | `#eeeff2` | Normal body text |
| muted | `#62666e` | `#a2a8b1` | Supporting text; still meets normal-text contrast |
| accent | `#bd2e22` | `#ff7568` | Links, focus, sample labels |
| racing | `#e44634` | `#e44634` | Decorative mark / racing stripe; never normal text |
| border | `#e6e7e9` | `#2b2f35` | Decorative dividers; not control identification |
| control-border | `#737980` | `#858d98` | Interactive outlines, ≥3:1 against their surfaces |
| highlight | `#fdf2f0` | `#2c1b19` | State notices |

Spacing scale: 4, 8, 12, 18, 26px (`--go-space-1` through `5`); panel radius 6px, control radius 4px. Race headings use Barlow Condensed Medium, 38px desktop / 34px mobile, uppercase, 1.1 line height. Driver labels use 21px / 1.15 condensed display type; explanatory race text uses 24px / 1.25. Body uses Inter, 14px / 1.55; supplementary text is 12px. Timing numerals use IBM Plex Mono Regular and tabular figures. Do not condense prose or shrink mobile probability labels.

All three fonts are self-hosted in `fonts/` using Google Fonts’ official repositories with their individual SIL Open Font Licenses retained. `font-display: swap` and Arial / Arial Narrow / Impact / monospace fallbacks allow readable loading. No runtime Google Fonts request or external font service is required. [Font manifest](evidence/wp10/font-manifest.json) records source URLs and SHA256s. WP11 can subset/convert to WOFF2 for production with the same licensing and fallback policy.

Team strips are decorative cues, paired with visible team names. Color alone never communicates team, horizon, movement or status. Sample team colors are not canonical season branding; WP11 must obtain branding from the selected season’s entries.

## Component and state catalogue

| Component | Inputs / states | Behavior and handoff |
| --- | --- | --- |
| Dashboard shell (`DesignReference`) | Journey, device/light/dark appearance | Sidebar becomes wrapping mobile navigation; current link has `aria-current`; breadcrumb and sample notice persist |
| `Panel` | Title, note, content | Consistent border, heading and panel spacing; headings retain hierarchy |
| `SampleNotice` | Always visible in header/footer | Synthetic data and “Not a real forecast”; independent table captions preserve context when copied |
| `HorizonControl` | `pre`, `post`, pressed/unpressed/focused | Two native toggle buttons in labelled group, `aria-pressed`; switching changes probabilities, ordering, cutoff and uncertainty |
| `ForecastContext` | Known or unknown timestamps | Horizon, input cutoff, issue time and freshness; missing timestamps become Unknown, never an invented date |
| `TimingTable` | Complete/partial field, selected horizon, comparison/leading subset | Semantic caption and row/column headers; ordering is win chance, not predicted finishing position; full-field total only for complete probabilities |
| `DataNotice` | Loading/unavailable/error/unknown/empty | Distinct copy for forecasts, scorecards and archives; polite status except error alert; retry restores sample and focuses heading |
| Race explanation panels | Known / unknown | Sample +6 pp change and 72% other-winner explanation; unknown data does not infer movement or uncertainty |
| Scorecard layout | Horizon, provenance, unmeasured metrics | Live-issued, historical reconstruction and legacy-unverified cohorts remain distinct; no invented score or calibration diagram |
| Archive layout | Example season, available/cancelled/results-only event cards | Control changes example selection label; explicit July 2026 sample links; cancellation differs from missing forecast |

Controls have hover/native interaction, selected and keyboard-focus states. Do not disable horizon navigation simply because a run is unavailable: let the fan select it and see why. No disabled control is needed for this offline reference; production pending actions must retain explanation and avoid focus loss. State preview controls are a reference tool, not a production feature.

| Data state | Race / full field | Scorecard | Archive |
| --- | --- | --- | --- |
| ready | Sample rows and complete totals | Explicitly unmeasured scorecard | Synthetic event cards |
| loading | No percentages; busy container | No metrics until cohort loads | No inferred event coverage |
| unavailable | No published horizon/run | No validated artifact, not zero loss | No published archive, not a race-free season |
| error | Retryable transport failure | Retryable scorecard failure | Retryable index failure, not empty calendar |
| unknown | Null cells, unverified timestamps/totals/deltas | Performance/coverage unknown | Provenance/availability unverified |
| empty | No entries, no ranking/total | No evaluated races, no loss/calibration | No events in index, no historical claim |

Freshness contract for WP11: show the immutable input cutoff and issued time, then a labelled freshness state (verified as of cutoff / source late / stale / unknown). Explain stale/source-late data in text and keep the original snapshot visible with its warning; do not automatically replace it with a newer horizon. Missing metadata must not imply “up to date.” This reference uses a **Frozen sample** freshness label; it makes no live freshness claim.

## Journeys and acceptance examples

1. **Race → full field → race.** Start at British GP sample, after qualifying. Norris is 28%; other winners collectively are 72%. Compare all 22 entries. Pre-weekend leads with Piastri at 25%; both fields total 100%. Compare the paired columns; 22% → 28% is +6 percentage points. Back returns to the selected horizon. Numbered rows indicate probability ordering only.
2. **Race → uncertainty → methodology.** A favorite is still more likely to lose than win. Read the frequency interpretation, cutoff rules and immutable-snapshot explanation. Never substitute ranker gaps for probability confidence. Back returns to the race.
3. **Track record → provenance → archive → sample race.** Select a horizon and provenance cohort. The scorecard says Not measured / 0 evaluated / Unknown, with coverage and sample-size caveats. Open the archive and inspect a labelled sample snapshot. Historical reconstructions and legacy-unverified outputs cannot silently count as live-issued performance.
4. **Archive → season/control → cancellation or results-only event.** Keep explicit coverage states. Changing the example season changes its label; opening the British GP explicitly opens the July 2026 synthetic reference. Real season/event URL context, roster changes, refresh-safe deep links and archived publication selection belong to WP11.
5. **Failure recovery.** On any core journey, choose error, activate Retry sample by keyboard, and return focus to the page heading. Unavailable explains absence; empty explains a zero-sized collection; unknown retains missing values. Loading and errors never expose previous percentages as if current.

The 22-entry fixture has five named illustrative contenders and 17 deliberately fictional entries. It makes no claim about a season roster. Null is Unknown; actual zero is 0%; empty totals are Unknown. The two synthetic win fields sum to 100%. Forecasts, scorecard metrics and archive provenance are never connected to production data.

## Responsive and accessibility specifications

Desktop: 178px quiet sidebar, compact header, ≤1200px content region, two explanation columns. At ≤780px explanations/metrics stack. At ≤570px navigation wraps above the page, no mobile destination is hidden, and body panels retain readable sizes. At 320px the page itself reflows; genuinely two-dimensional tables retain a 470px minimum width in a named, keyboard-focusable horizontal scroll region with a visible mobile hint. Headers/labels remain intact; no ellipsis hides probability meaning. Table scrolling is the only intended horizontal overflow.

Native links/buttons/selects/details provide keyboard behavior: Tab and Shift+Tab traverse; Enter activates links and retry; Enter/Space toggle horizon/buttons; arrows operate selects; Enter/Space opens state disclosure. The skip link focuses main without changing the current journey. Destination changes focus the h1, including browser history. Retry focuses the h1 after its button disappears. No positive tabindex, focus trap, custom arrow-key tab pattern or animation dependency. Controls/navigation provide ≥44px height; inline explanatory links retain native text behavior. Focus uses a 3px accent outline with 3px offset; avoid clipping rings in production containers. Reduced-motion users receive no motion-dependent meaning.

Normal text must meet **4.5:1** in both themes, including 12px notes; never invoke large-text exemptions for display labels. Ink, muted and accent are tested against surface/sidebar/subtle/highlight. Interactive boundaries and focus must meet **3:1**. [Contrast measurements](evidence/wp10/contrast.json) enumerate actual token pairs; `contrast.test.js` reads the real CSS rather than a copied palette. Thin decorative separators and team strips are not required to identify controls or convey meaning by themselves.

Tables use native `<table>`, visible captions, `scope=col` and `scope=row`. Missing data is text, not a dash with hidden meaning. Loading sets `aria-busy`; state text uses status/alert roles. Horizon controls expose selected state; navigation exposes current page. Contrast and keyboard checks are evidence, not a claim of full assistive-technology certification.

## Validation and remaining decisions

Browser evidence is retained under [evidence/wp10](evidence/wp10/): 1440px light/dark race and comparison/scorecard/archive; 390px race/comparison; 320px comparison and failure/unknown states; navigation, state and keyboard observations. The scripted walkthrough exercised all six destinations, 22 rows, both horizons, four core journeys × six data states, focus transitions and page overflow. Inspect the screenshots alongside the approved reference, not as pixel-identical copies.

Probability-comprehension/readability review used these deterministic prompts: “Who leads each horizon?” (Piastri 25% pre / Norris 28% post); “Is the favorite more likely than all others together?” (No: 72% others post); “What is 22 to 28?” (+6 pp, not +6%); “Is Unknown zero?” (No); “Are these real forecasts or measured accuracy?” (No). Displayed copy and tests support these answers. This is an agent walkthrough, **not participant usability testing**. Participant testing and native screen-reader/device testing remain release verification; no results are invented.

No unresolved identity or WP10-blocking UX decision. WP11 owns real season URLs, freshness thresholds from source contracts, provider attribution and client integration. WP12 owns real uncertainty/calibration artifacts and verified scorecards. Archive depth remains the existing O05 product decision; sample years do not resolve it. These boundaries must not become implicit accuracy or historical-coverage claims.

Rollback: remove the independent reference entry/config and design-system directory; no production entry point, database, stored forecast or serving behavior changes. No migration or backfill is needed.
