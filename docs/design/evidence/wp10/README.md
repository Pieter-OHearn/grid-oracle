# WP10 validation evidence

Captured 2026-09-30 from the independent `wp10.html` reference using the Codex in-app browser. Bun 1.4.2, Node 26.10.0, React 18.3.1, Vite 6.4.1, Vitest 3.2.4. This is agent inspection and deterministic walkthrough evidence, not participant usability testing or a full assistive-technology audit.

- `wp10-desktop-{race,dark,comparison,scorecard,archive}.jpg`: 1440px viewport, full-page captures; dark is the race in dark appearance.
- `wp10-mobile-{race,comparison,scorecard,archive}.jpg`: 390px viewport; all four core layouts inspected.
- `wp10-320-comparison.jpg`: 320px field comparison; readable 470px table scrolls inside its 294px region.
- `wp10-mobile-{error,unknown}.jpg`: 320px race failure/partial-data states.
- `wp10-navigation.json`: six destinations, focused heading and 22 comparison rows.
- `wp10-responsive.json`: four core journeys at both 390/320px; document width equals viewport; only table regions overflow locally.
- `wp10-states.json`: all 24 core journey/state combinations; final journey-specific state copy, no NaN, no document overflow.
- `wp10-journeys.json`: sample archive selection/link, race → 22-entry comparison and distinct provenance cohort copy.
- `wp10-keyboard.json`: initial Enter/Space/skip walkthrough, including the initial retry focus-loss finding and its first repaired observation.
- `wp10-keyboard-final.json`: final retry focuses h1 and skip focuses main while retaining archive journey.
- `contrast.json`: 32 light/dark token pairs; normal-text minimum 5.25:1, all tested text ≥4.5:1 and control borders ≥3:1.
- `font-manifest.json`: retained font source URLs, licenses and SHA256s.

Reproduce with the commands in [the design-system reference](../../WP10_DESIGN_SYSTEM.md), visit each navigation destination, use the sample-state disclosure for each of six states, and select device/light/dark appearance. Set viewport to 1440×1000, 390×844 and 320×844. Verify page width, table scrolling, keyboard Enter/Space/Tab, focus outline, retry, skip link and browser history. The 22-entry fixture is wholly synthetic and is not an official roster.

Final automated checks: dashboard format/lint/typecheck pass, 8 tests pass (5 new WP10 tests plus 3 existing tests), production build passes, independent reference build passes, `git diff --check` passes. Production emits existing Browserslist age / >500kB chunk warnings; the reference has no large JS chunk warning. No Python/backend files changed; backend suites are outside this package.

During implementation: the first generated reference output folder was outside the existing lint ignore and caused lint to inspect generated JS. The output now uses existing ignored `dist/wp10`. An initial TypeScript filesystem test required unavailable Node type declarations; the final JavaScript contrast test reads actual CSS without dependency changes. Both issues were fixed before final checks. Native screen-reader, hardware-device and participant testing are not run and remain release verification.

Upstream OFL license text was normalized to LF with trailing whitespace removed; license terms and notices remain intact.
