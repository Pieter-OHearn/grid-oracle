# GridOracle implementation workplans

2026-09-28 · All implementation packages are **not started**. The repository review, evidence experiment and planning documents are complete; they do not implement these packages.

Read [PLAN](PLAN.md) first. [DECISIONS](DECISIONS.md) controls adopted choices and open dependencies. Finding IDs refer to [REPOSITORY_REVIEW](docs/REPOSITORY_REVIEW.md). Each package can become several focused pull requests; do not treat a package as a mandate for one large change. [Agent execution guide](docs/workplans/README.md) defines assignment, state transitions and review. Each package has its own durable state record in `docs/workplans/WPxx.md`.

## Working agreement for future agents

Before editing, inspect current instructions, git status and the relevant files; preserve unrelated/untracked work. Reconcile any changed baseline with this review. Work on one assigned, ready package or named subtask; record ownership and progress in its state record. For a non-ticket package, create a conventional branch such as `feature/wpNN-short-description`, `bugfix/wpNN-short-description`, `docs/wpNN-short-description`, `chore/wpNN-short-description`, `test/wpNN-short-description`, or `research/wpNN-short-description` from integration `main` before editing. Run the required checks, commit only assigned changes using Conventional Commits, push the branch and open a ready-for-review GitHub PR to `main`. Record the branch, commit hash and PR URL before setting `review_ready`. The coordinating agent or owner maintains PLAN's overview and assigns shared-file ownership. Existing ticket-specific branch/PR instructions apply when a ticket is actually assigned; these new package IDs are not existing GitHub issue numbers.

Do not rewrite trustworthy history, run the legacy bootstrap against production, or reset the database to apply migrations. Do not edit the homelab wiki. Prepare any needed platform manifest changes as a separately scoped task in the source homelab repository, with authorization for that repository and deployment. Public release, paid resources and hardware purchases require their own instruction.

Every package handoff records: branch, implementation commit, GitHub PR number/URL and base revision; changed behavior and files; evidence/commands and outcomes; migration/backfill and rollback notes; experiment/run IDs where applicable; remaining risks; decisions updated; and the next ready package. Acceptance evidence belongs in a durable report, not only chat. A reviewer inspects the pull request before the coordinator merges it into `main` and records the integrated hash. Proposed CLI names and paths below describe interfaces to implement, not commands that already work.

## WP01 — Reproducible development and safe starting point

**Depends:** none. **Addresses:** F24, F32, F34–35. **Decisions:** D08, D16, D21. **Size:** medium.

**Outcome:** a fresh agent can run the application and checks with known dependencies and a safe development dataset.

**Tasks:** reconcile README/Bun/container installation; lock Python/runtime dependencies and Bun version; separate dev/test/train/serve dependencies; add documented environment validation; add a static sample dataset with provenance; remove upstream sklearn monkey-patching only after native compatibility tests. Record CPU/architecture and optional GPU/MPS detection without exposing credentials. Add frontend test/typecheck CI; run API/pipeline suites in supported Python environments. Document how to inventory and back up an existing installation before migration.

**Acceptance:** clean checkout installs reproducibly; all present checks pass; sample app runs without provider calls or scheduler side effects; model save/load smoke test succeeds on CPU; missing configuration produces a useful error. No real host changes occur during this package.

**Handoff/rollback:** setup report, dependency lock diffs, native compatibility limitations; no schema changes. Next: WP02 and contract/prototype work for WP10.

## WP02 — Season domain, targets and migration foundation

**Depends:** WP01. **Addresses:** F13, F15–17, F19, F23, F31. **Decisions:** D07, D19, D21–22. **Size:** large.

**Outcome:** a domain specification and additive database foundation that represents any supported season and an unambiguous prediction target.

**Tasks:** settle O07/O08 target/horizon semantics; define canonical status mappings, official rank versus internal result order, DNS/DSQ masking/ordering, scoring/countback and entry-change policy; specify stable driver/team/circuit/layout IDs and aliases; add versioned season/rules/session/entry contracts. Adopt a migration ledger (Alembic default) by recognizing existing databases, not blindly recreating them. Build a legacy identity mapping report before backfill; unresolved circuit/team merges are quarantined. Add CLI dry-run for season import and validated configuration schema.

**Acceptance:** upgrade a populated fixture and restore it; two seasons with different field sizes, sprint schedules, transferred/reserve drivers, renamed teams and changed venue identity remain correct. Cancellation/postponement and result revision are explicit states. Target policy tests cover classified retirements, `Lapped`, historical `+1 Lap`, DNS, DSQ and unknown status. New season preparation needs data/config only.

**Handoff/rollback:** domain/target spec, migration ledger and mapping report. Additive changes stay compatible until dual-read migration completes. Next: WP03/WP04.

## WP03 — Immutable provenance and forecast storage

**Depends:** WP02. **Addresses:** F02–05, F11, F14. **Decisions:** D09–10, D15. **Size:** large.

**Outcome:** every forecast can be traced and reproduced without changing earlier forecasts.

**Tasks:** implement raw snapshot manifests, result revisions, datasets, feature snapshots, model/calibrator manifests, forecast runs/entry outputs, evaluation runs and publication pointers. Store actual issue/cutoff/availability times and provenance grade. Artifact paths become content-addressed or immutable run paths, with verified checksums. Make field publication atomic and retries idempotent. Import old records as `legacy_unverified`, preserving original values and known timestamps; flag artifact mismatches rather than guessing which model was used.

**Acceptance:** two horizons using one model coexist; rerunning the same task does not duplicate/overwrite history; partial-field output cannot publish; wrong artifact hash fails; model ID/path mismatch fails; a post-race run cannot become a live pre-race forecast; evaluation can be revised without changing the forecast. Fresh-process reproduction produces the same outputs within declared tolerances.

**Handoff/rollback:** schema/API contracts and example manifests; leave old reads available until WP11 switch. Next: WP05/WP06 contract work.

## WP04 — Reliable ingestion and weekend orchestration

**Depends:** WP02–03. **Addresses:** F06–11, F15, F21, F23, F33. **Decisions:** D02, D17–19. **Size:** large.

**Outcome:** data arrives, jobs recover, and each horizon is issued only from eligible complete inputs.

**Tasks:** provider adapters with pagination, custom user agent, rate budget, retry/backoff/jitter, raw snapshots, contract validation and quarantines; persistent job ledger, lease/lock and reconciliation loop; periodic calendar refresh; explicit job dependency graph. Implement pre-weekend feature/predict/publish chain, post-Q ingest/feature/predict/publish chain, and independent result ingest/evaluate chain. Wire session/tyre ingestion when required. Select weather by race-valid interval, retain issue/release times, distinguish unavailable from dry. Retraining is separate and never prevents scoring. Upcoming forecasts rebuild their snapshots; schedule by timestamps, not date-only comparisons.

**Acceptance:** simulated restart before/after qualifying and after race; predictions already existing do not block result catch-up; partial qualifying cannot masquerade as a complete field; HTTP 429, timeout, malformed payload and revised start time recover or expose a visible blocked state. Duplicate workers cannot publish twice. Sprint and postponed-weekend fixtures produce correct horizon cutoffs.

**Handoff/rollback:** job-state diagram, operator dry-run/retry instructions and failure fixtures. Feature-flag new scheduler; keep only one writer active during switch. Next: WP05 and WP13 readiness planning.

## WP05 — Audited historical dataset and feature contracts

**Depends:** WP03–04. **Addresses:** F10–11, F16–24. **Decisions:** D10–11, D18–19, D22. **Size:** large.

**Outcome:** training datasets have explicit temporal provenance and measured coverage.

**Tasks:** resumable backfill by season/session; results/qualifying and entry reconciliation; classify each historical fact's availability quality; never backdate retrieval timestamps. Start with 2022–25 baseline cohort, then expand toward 2018 where justified. Implement horizon feature registry and vectorized/batched historical queries; correct constructor last-three-races aggregation and standings/sprint accounting. Add recency, normalized pace, reliability and missingness features in tiers. Rename questionable compound/degradation proxies or drop them until an ablation supports them. Document source delays and weather-free cohorts.

**Acceptance:** report all races/entries/sessions, duplicates, null rates, exclusions and identity conflicts; injecting a future fact cannot change an earlier feature snapshot; qualifying cannot appear in pre-weekend features; same live/replay cutoff yields the same features when source snapshots match. Entrant order does not change values. Source-status fixtures include the downloaded real records. Versioned Parquet/manifests can be reconstructed from raw snapshots.

**Handoff/rollback:** data card, coverage matrix, feature dictionary and immutable dataset hash; dataset versions are additive. Next: WP06.

## WP06 — Benchmark harness and baseline scorecards

**Depends:** WP05. **Addresses:** F01–02, F12–13, F30. **Decisions:** D11–13, D19, D25. **Size:** large.

**Outcome:** one reproducible test protocol determines whether a model improves the product.

**Tasks:** whole-race chronological outer/inner splits; separate calibration blocks; target-matched deterministic and probabilistic baselines by horizon; shared metric implementation; identical cohort enforcement; paired race/block uncertainty; fixed test manifest; slice reports and coverage; experiment registry with code/dependency/config/seeds/resource metadata. Reproduce the review's descriptive audit, then clearly separate it from the new as-of benchmark. Record primary metric, guardrails and promotion tolerances **before** challenger tuning. Treat 2022–25 as explored history and reserve a genuinely future/prospective evaluation block.

**Acceptance:** a deliberately leaked target/qualifying feature is rejected by temporal contracts; folds never split a race; calibration does not train on test data; missing evaluations display N/A; simple hand-computed metrics match; probabilities of zero/one are handled by a documented numerical policy. One command regenerates a report including baseline losses and uncertainty. No model can promote itself merely by being newest.

**Handoff/rollback:** benchmark protocol, frozen split/dataset manifests and baseline report. Never delete failed experiments. Next: WP07 and WP08.

## WP07 — Strong classical and hierarchical challengers

**Depends:** WP06. **Addresses:** F01, F12, F20, F22, F24. **Decisions:** D12–15. **Size:** large / experimental.

**Outcome:** establish the best defensible non-neural reference before judging the custom model.

**Tasks:** correct and regularize XGBoost regression; add race-grouped XGBoost ranking with documented label direction; compare a simple hierarchical dynamic skill/Plackett–Luce model. Optionally test another boosted-tree family if categorical handling or validation evidence motivates it. Tune within bounded inner folds; log all trials and compute. Ablate recency, era pooling, grid, weather, practice and tyre proxies; inspect cold-start failures and recent-era drift. Use a comparable calibrated decoder for proper-score comparisons.

**Acceptance:** reproducible champion/challenger report for each horizon; served-ranking metrics and probability metrics both present; all models see the same information and cohorts; no claims of future superiority based only on development folds. Small/no improvement is a valid experimental result.

**Handoff/rollback:** model cards, artifacts, data/config hashes and ranked experiment report; existing serving stays unchanged. Next: WP09.

## WP08 — Custom probabilistic model and accelerated research

**Depends:** WP06; compare to WP07 results before production selection. **Decisions:** D05, D12–16. **Size:** large / experimental.

**Outcome:** a trained, understandable custom model with evidence for or against its use. Product accuracy governs deployment; custom architecture is not a guaranteed winner.

**Tasks:** verify gaming PC GPU/VRAM/OS/driver and Mac memory; choose compatible CUDA/MPS packages from current official docs; retain CPU backend. Implement small-race likelihood reference and stable PyTorch ranking loss; learn regularized driver/team effects and optional circuit interactions, then a small nonlinear challenger. Add variable-field masks, unknown-entrant behavior and explicit horizon conditioning. Investigate Bayesian modeling if it better addresses uncertainty. Compare architecture sizes, history windows and feature groups; stop unproductive compute searches. Use saved configurations, checkpoints, loss curves and an experiment diary. Optional local MLflow/TensorBoard may aid analysis; no always-on paid tracker.

**Acceptance:** loss agrees with hand-computed tiny cases; gradients checked; tiny-data overfit sanity test; shuffled entry order equivariance; 20/22-driver masks; rookie/team cold-start behavior; clean-process save/load and CPU/backend parity within recorded tolerance. Bounded training survives interruption/resume. Report peak RAM/VRAM, runtime and validation scores; no test-set tuning. Learning report explains what failed as well as what worked.

**Handoff/rollback:** custom model code, research narrative, trained artifact and comparable benchmark report. GPU is not required for public serving. Next: WP09; keep research running independently if a classical model wins.

## WP09 — Coherent probabilities, selection and promotion

**Depends:** WP07–08 and WP03; custom experiment must be evaluated, but need not win. **Addresses:** F03–05, F14. **Decisions:** D12–15, D25. **Size:** large.

**Outcome:** select the most accurate validated candidate for each horizon and publish truthful uncertainty.

**Tasks:** train decoder/calibration from prior out-of-sample predictions; derive joint outcome marginals; validate uncertainty and sampling convergence; enforce target-specific probability constraints. Fit optional ensemble only from out-of-fold forecasts and only if complementary errors justify it. Compare incumbent, baselines and challengers on locked protocol; create explicit proposed/challenger/champion/retired states; add manual auditable promotion and rollback pointers. Document selected model's limits.

**Acceptance:** probabilities are finite/bounded/nested and field-coherent under the declared target; fixed-field rank draws are permutations; entry changes cannot silently alter a historical field. Reliability diagrams include counts. Locked proper-score improvement and guardrails meet the preregistered gate; if inconclusive, retain the incumbent/baseline and record that decision. Correlation-sensitive simulation tests precede any richer simulator release.

**Handoff/rollback:** selection report, model/calibration cards and promotion record. Rollback switches publication/model selection, preserving old runs. Next: WP12/WP15.

## WP10 — Approved design system and fan journeys

**Depends:** WP02 complete. The visual direction is already approved; this package completes the design system and state coverage. **Addresses:** F25–30. **Decisions:** D01–04, D23. **Size:** medium.

**Outcome:** turn the approved dashboard direction into a reusable, accessible design system and complete fan journeys.

**Tasks:** use the [approved design reference](docs/design/APPROVED_UI.md); preserve navigation destinations, information hierarchy, horizon comparison and explanation flow. Formalize the restrained dashboard shell, condensed race/driver type, timing numerals, team strips and racing accents as reusable tokens/components. Cover race page, full-field comparison, public scorecard, archive and actual loading/error/unknown states. Produce mobile/desktop variants; test probability comprehension and readability. Use the approved default treatment rather than reopening the identity decision. The stronger broadcast/purple alternatives are exploratory options, not a replacement for the approved default.

**Acceptance:** the design follows the approved reference and shows horizon, cutoff/freshness and uncertainty; navigation works on a 22-entry example; keyboard/focus and normal-text contrast are specified. No demo percentages are presented as real forecasts. Tokens, responsive layouts and component/state catalogue become the implementation reference. Owner approval of the concept does not substitute for accessibility and usability checks.

**Handoff/rollback:** approved design reference, tokens, journey acceptance examples and unresolved UX choices. No production UI change in this package. Next: WP11.

## WP11 — Season-aware public API and frontend foundation

**Depends:** WP03–04 and WP10. **Addresses:** F14, F25–29, F32. **Decisions:** D07–09, D24. **Size:** large.

**Outcome:** the new UI navigates all supported seasons and exposes the right published runs.

**Tasks:** versioned API with season/event/session/run resources, typed freshness/coverage/error states and publication selection; generated client types; shared query caching/cancellation. Implement season URLs and redirects for old race links; component system, responsive navigation and accessible data tables. Replace null-as-zero and swallowed errors with explicit states. Package static production assets; lazy-load large visualizations.

**Acceptance:** older-season deep link works on refresh and never shows current roster branding; selecting a season updates all context; inaccessible API produces retryable error distinct from absent forecast; empty arrays never show NaN. Keyboard/mobile journeys and 320px reflow pass; screenshot comparison for selected design; no public internal metadata or mutating endpoints.

**Handoff/rollback:** contract snapshots, component documentation and browser evidence; feature-flag old/new views until parity. Next: WP12.

## WP12 — Forecast explanations and honest public performance

**Depends:** WP06, WP09, WP11. **Addresses:** F04, F12–14, F29–30, F36. **Decisions:** D01–02, D10, D12, D15. **Size:** large.

**Outcome:** fans can compare both forecasts and understand the engine's measured performance.

**Tasks:** probability table/distributions, horizon/revision comparison, driver detail, public model card, result comparison, baseline scorecard, source/coverage status and metric glossary. Use server-calculated metrics; explain exact position versus set overlap. Show out-of-sample historical and live-issued results separately. Add result correction history and accessible text/table alternatives. Explanations state associations and input limitations; no fabricated narratives.

**Acceptance:** every visible percentage has a named outcome; “not available” stays distinct from 0%; poor races and exclusions remain visible; charts use true rounds and gaps; public score equals stored evaluation for the same run/result revision. Delta copy matches numerical examples. Users can identify when the forecast was issued and what was known.

**Handoff/rollback:** screenshot/journey evidence, metric/API contract and methodology copy; restore previous read views without altering forecast history. Next: WP15.

## WP13 — Homelab deployment design and recovery

**Depends to start:** WP01. **Depends to complete:** WP03, WP04 and WP11 integrated. Early work covers capacity and deployment design; staging/restore acceptance requires the implemented interfaces. **Addresses:** F31–33. **Decisions:** D03, D06, D16–17, D20–21. **Size:** medium/large.

**Outcome:** a concrete deployment and backup plan compatible with measured homelab capacity.

**Tasks:** read the existing homelab catalog and measure authorized resource telemetry; choose host/storage; verify native ARM64/AMD64 support; keep accelerator research outside the public request path. Establish the delivery boundary: GridOracle CI builds, tests and releases immutable multi-architecture OCI images to GHCR; the homelab repository owns the production Compose/service manifest and pins every approved application image by version and digest. A reviewed homelab PR promotes a released digest, and the existing deployer runner applies only merged homelab configuration; it never builds application code, trains models, or follows mutable tags. Prepare production Compose, non-root images, resource caps, private service networks, secrets and TLS/routing design. Define an explicit model-bundle contract that pins model, data, feature, calibration and artifact hashes, and make saved forecasts restartable while training machines are offline. Resolve O02–O04; integrate existing monitoring/logging/tracing with low-cardinality metrics. Define backup retention, consistent artifact/database recovery and off-primary-disk destination. Produce the application release workflow and platform manifest proposal in their authorized source repositories only; never edit generated wiki files.

**Acceptance:** a reproducible staging install and schema upgrade using a released image digest; promotion from application release to reviewed homelab manifest is documented and leaves an audit trail; restart serves saved forecasts with training machines offline; no public database/admin/metrics access; measured memory/latency/backfill limits; restore into a new environment from backups, verifying forecast hashes and selected model bundle. Public ingress is explicitly designed and reviewed rather than inferred from a wildcard certificate.

**Handoff/rollback:** deployment manifest proposal, capacity report, recovery runbook and release request. Actual homelab/public rollout is a separately authorized action. Next: WP15.

## WP14 — End-to-end regression and operational tests

**Depends to start:** WP04, WP06 and WP11 integrated (WP05 is transitive). **Depends to complete:** WP09, WP12 and WP13 also integrated. Early harness work is allowed; final regression evidence must cover the selected model and final UI/operations. **Addresses:** F34 and cross-system regressions. **Decisions:** D09–11, D21. **Size:** medium/large.

**Outcome:** CI protects domain meaning and forecasting integrity, not just helper function syntax.

**Tasks:** PostgreSQL migration/upgrade tests; recorded provider contracts with attribution; full weekend replay fixture; source outage/retry and duplicate-worker tests; model manifest/load tests; TypeScript/frontend/browser/accessibility checks; bounded native architecture smoke tests. Cover season rollover, sprints, reserves, 22 entrants, entry withdrawal, pit lane, missing weather, late qualifying, cancellations and result corrections. Keep provider live calls out of deterministic CI; separate scheduled/manual contract checks.

**Acceptance:** one representative pipeline flow ingests → snapshots → predicts → publishes → evaluates correctly; simulated future data cannot change old runs; failure tests retain last-good output; tests fail when intentional known defects are reintroduced. CI reports its coverage limitations and artifacts.

**Handoff/rollback:** fixture manifests and regression map linked to findings/decisions. Next: WP15.

## WP15 — Prospective shadowing and release

**Depends:** WP09, WP12–14. **Decisions:** D10–12, D25. **Size:** calendar-dependent.

**Outcome:** a release decision based on operational and predictive evidence.

**Tasks:** freeze prospective forecasts before each cutoff and retain them; shadow at least six eligible races across both horizons; track source lateness, publication completeness, loss/calibration, incidents and resource use. Rehearse rollback and restoration. Complete accessibility, native-runtime, privacy/attribution and public-ingress checks. Prepare concise release notes and outstanding limitations; request public deployment only when artifacts are reviewable and authorization is needed.

**Acceptance:** every eligible shadow race has a forecast or an explained missed issuance; no hindsight changes; operational readiness passed; model promotion follows WP06/WP09, not six-race anecdotal accuracy. Release can proceed with the best eligible baseline/model while custom research continues. No score is inflated by excluding missed or difficult weekends.

**Handoff/rollback:** release evidence and selected versions; reversible rollout with previous published outputs available. Next: WP16 and continuing evaluation.

## WP16 — Richer product and research extensions

**Depends:** WP15; select extensions by evidence and owner interest. **Size:** separately scoped.

Candidates: championship simulation with correlated team-strength evolution; earlier results-only seasons; sprint/qualifying forecasts; scenario comparison; deeper tyre/stint modeling; driver/circuit stories; favorites and notification preferences; license-aware exports and sharing; non-invasive usage measurement. Live in-race prediction is a new product with different latency/data/access requirements.

**Acceptance for each extension:** named fan/research benefit, source/rights/coverage contract, separate benchmark if predictive, cost/resource budget, coherent UX, and tests for its distinct failure modes. No extension silently changes a historical metric, forecast horizon or active baseline.
