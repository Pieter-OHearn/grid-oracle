# Approved GridOracle UI direction

**Approved by the owner on 2026-09-28:** “Love it.” This approves the latest GridOracle dashboard concept: an understated OpenAI-platform-inspired layout with a distinctive F1 identity. The earlier Journal/Pitwall/Atlas studies and older Figma export are superseded for this rebuild.

The exact concept is preserved in [approved-dashboard.fragment.html](approved-dashboard.fragment.html) for agents working from this repository. It is a self-contained inline preview fragment, not a production application or a finished routing/component system. Its percentages, race context and team examples are synthetic. Treat it as a visual reference and split production work into proper React components.

## Preserve

- A quiet sidebar with race weekend, track record and seasons; compact breadcrumb/header and local forecast controls.
- Neutral light/dark surfaces, thin dividers, modest corner radii and precise spacing. The race data is the main content, without an oversized promotional hero.
- Condensed uppercase race/driver typography; readable sans-serif body copy; tabular monospaced probabilities and changes.
- Restrained race-red accents, numbered timing-table rows and team-color strips paired with team names. Theme-aware colors and accessible contrast take priority over exact sample colors.
- Pre-weekend/after-qualifying comparison; visible cutoff and data state; full-field totals; what-changed and uncertainty explanations; durable public track record.
- Responsive navigation and tables. Keep meaning visible on small screens rather than shrinking labels indefinitely.

## Starting tokens and boundaries

The approved default is the **understated, red-accent** treatment with device-following light/dark appearance. The stronger broadcast and purple controls are exploration alternatives, not an instruction to ship every option. No screenshot of a later toggle selection was provided.

The reference uses Inter for body/UI text, Barlow Condensed for race/driver headings and IBM Plex Mono for numbers. Surfaces start at light `#ffffff` / dark `#121416`, sidebar `#f7f7f8` / `#17191c`, and racing accent `#e44634`. Core panel radii are approximately 5–7px, with compact navigation and a roughly 178px desktop sidebar. These are implementation starting points, not exemptions from contrast, font-licensing or responsive tests. Production font hosting and fallbacks belong in WP10–11.

WP10 completes the token system, accessibility, all product screens and missing/loading/error/empty states. WP11 builds reusable components, navigation and API integration. WP12 connects explanations and public performance to real versioned forecasts. The preview's static navigation labels are not evidence that navigation has already been built. Approval of the concept does not mark these packages complete.

Changes necessary for accessibility, complete data coverage or responsive behavior are expected. Reopen the identity decision only for a material product-direction change; routine component work does not need renewed design approval.

## Reference integrity

The adjacent fragment is preserved byte-for-byte from the approved conversation concept. `SHA256SUMS` records its checksum. Keep this approval snapshot intact; subsequent implementation references should be versioned separately with their rationale.
