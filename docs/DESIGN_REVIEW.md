# Critical review of the ideal-state proposal

2026-09-28 · Review of [IDEAL_STATE](IDEAL_STATE.md), [DECISIONS](../DECISIONS.md), [WORKPLANS](../WORKPLANS.md) and [PLAN](../PLAN.md).

This is a separate critical self-review pass, not an independent external review or an executed model benchmark. It checks the proposal against the code findings, retrieved evidence, owner answers and implementation dependencies. The proposal is ready to guide development; deployment and accuracy claims remain gated by work that has not happened.

## Challenges raised and revisions incorporated

| Challenge                                                                                      | Resolution in the final proposal                                                                                                                                                                                                            |
| ---------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| “Use real ML” could prompt an unnecessary algorithm replacement.                               | Explicitly identify existing XGBoost. Prioritize evaluation/lineage defects and fairly compare improved trees with hierarchical/custom models.                                                                                              |
| A custom neural model could become a predetermined winner for learning reasons.                | Owner's later accuracy-first clarification is recorded. Custom-model work is a first-class experiment; it earns production selection through the same benchmark. Different horizons may select different models.                            |
| “Free homelab” could constrain all training to a small Pi.                                     | Separate public serving from experimentation. Record gaming PC/5060 and M1 Mac availability, with hardware/backend verification still required. Neither personal machine must be online to serve forecasts.                                 |
| Existing Proxmox guest allocations could be mistaken for spare physical RAM or actual usage.   | Record 17.5 GiB listed guest allocation against a 16 GB host without inferring exhaustion. Require measured RAM/IO headroom before placement.                                                                                               |
| Existing Traefik and wildcard certificates could be mistaken for public ingress authorization. | Public routing, access boundaries and backup destination remain explicit open deployment decisions. Wiki is read-only reference, with no runbook execution implied.                                                                         |
| Historical weather could introduce hidden hindsight even when called a forecast archive.       | Require issue, availability and valid times; note single-run coverage and hindcast provenance concerns. Weather-free cohorts are valid when provenance cannot be established.                                                               |
| A final starting grid is not necessarily available just after qualifying.                      | Separate qualifying/provisional/final grid snapshots and horizon-specific eligibility. The empirical final-grid baseline is explicitly retrospective.                                                                                       |
| A probability matrix could invent official ranks for DNS/DSQ.                                  | Distinguish internal total order from official classification and status. Matrix row/column invariants apply only to a fixed-field total-order distribution. WP02 must settle label policies before modeling.                               |
| Independently calibrated win/podium/top-ten models could produce impossible totals.            | Public marginals should come from a coherent joint model; independent heads need reconciliation and renewed evaluation. Calibration is measured after the full decoding process.                                                            |
| Six shadow races could be misrepresented as statistical proof.                                 | Six races are an operational observation minimum only. Promotion uses the locked evaluation protocol, proper-score comparisons, uncertainty and predeclared guardrails. Inconclusive challengers remain experimental.                       |
| Choosing by winner log loss alone might hide worse full-field forecasts.                       | Ranking/top-k/calibration guardrails and explicit predeclared tradeoffs are required. D12 is an adopted recommendation, not a confirmed owner preference for winner-only optimization; WP06 must resolve the exact objective before tuning. |
| Calling 2025 a pristine holdout would ignore existing experimentation and this audit.          | Treat inspected historical seasons as explored evidence; reserve a future/prospective block and record benchmark reuse.                                                                                                                     |
| Initial capacity and timing numbers could sound measured.                                      | Label all budgets and SLO/RPO/RTO proposals as targets awaiting host/load/restore tests. No accuracy percentage is promised.                                                                                                                |
| A season dashboard could double-count races across evaluation versions.                        | Final code cross-check found F36; add explicit cohort selection and deduplicated race coverage to WP12.                                                                                                                                     |
| Raw data could accidentally inherit the repository's MIT license.                              | Add separate attribution and CC BY-NC-SA notice for the archived Jolpica responses and derived data. Keep application code licensing separate.                                                                                              |

## Evidence cross-check

- The review records **36 actionable findings** with code locations, distinguishing confirmed behavior from the provider-status compatibility risk in F23.
- The archived empirical sample contains 40 responses, 92 races and 1,838 result rows. The qualifying-order benchmark excludes exactly one race with a missing qualifying entrant. It reports 91 races, 3.379 MAE, 57.14% winner hit rate and 65.93% podium overlap, with explicit hindsight/cohort limitations. It is not the current model's accuracy. See [reproduction](evidence/README.md).
- Existing local checks passed: 205 pipeline tests, 25 API tests, three frontend tests, relevant lint/format/type checks and frontend build. This does not test populated PostgreSQL migration, public hosting, real model performance or complete rendered UI accessibility.
- Primary sources support temporal evaluation, calibration, ranking capabilities, accessibility and deployment practices. They do not establish a winning F1 architecture or an uplift estimate. The latter requires WP06–09.
- Homelab facts come from the owner's input and read-only wiki. No live capacity measurements or changes to those systems were performed.

## Requirement-to-work traceability

| Owner requirement                                       | Specification                                      | Build/validation path                                                               |
| ------------------------------------------------------- | -------------------------------------------------- | ----------------------------------------------------------------------------------- |
| Reusable each season                                    | Ideal state §2–4; D07                              | WP02–05, WP11, WP14 season/field/entry fixtures                                     |
| Fix prediction quality; most accurate result            | Ideal state §5–6; D11–15                           | WP05–09; locked benchmark, custom comparison, prospective evidence                  |
| ML learning with extra resources                        | Ideal state custom curriculum/runtime; D05/D14/D16 | WP08 custom implementation and learning report using verified PC/Mac backend        |
| Fix UI; explore a new identity                          | Ideal state §1; D04/D23                            | Approved F1 dashboard reference; WP10–12 complete system, states and implementation |
| Public fan product, two horizons                        | Ideal state §1/4/6; D01–02                         | WP03–04 publication contract; WP11–12 transparent UI; WP15 shadow release           |
| Initially free, self-hosted                             | Ideal state §3/7; D03/D18/D20                      | WP13 capacity, rights, ingress and recovery design; serving independent of GPU      |
| Read wiki, do not write                                 | D06 and work agreement                             | Read-only evidence only; future platform work separately authorized                 |
| Review document and support it with data/best practices | This review; source register; evidence archive     | Offline reproduction and implementation acceptance gates                            |
| Future-agent incremental plans                          | PLAN / WORKPLANS / DECISIONS                       | Stable IDs, explicit dependencies, acceptance, rollback and handoff evidence        |

## Remaining uncertainty and limits

1. There is no trained-model bake-off yet. A claim that neural, Bayesian, boosted-tree or ensemble modeling is definitively most accurate would be unsupported.
2. Historical availability evidence may remain incomplete. The product must disclose reconstructed evidence and accumulate authentic issued forecasts going forward rather than fabricate old receipts.
3. Forecast target semantics, especially DNS/DSQ and changes to the known entry field, need an executable specification before dataset/model implementation. They are a WP02 gate, not a deferred afterthought.
4. Data quality and sample size may cap gains. More GPU time can improve search speed, not create new independent races or unavailable features. Research includes stopping criteria and negative results.
5. A small public homelab service can be reliable enough for this product, but capacity, internet access and recovery targets are unmeasured. The plan does not reserve resources or expose services.
6. The owner approved the revised OpenAI-platform-inspired F1 dashboard on 2026-09-28. The exact reference is preserved in `docs/design/`; WP10 still needs full state coverage, accessibility and responsive validation. Concept approval does not imply those checks passed, and synthetic forecasts are not real predictions or usability evidence.
7. Archive depth remains a provisional 2018+ detailed target, with older results-only history optional. Coverage may force different feature cohorts across eras.

**Review disposition:** proceed with WP01, then freeze the season/target/provenance contracts in WP02–03. The remaining questions are localized to named workplan gates, so they do not require stopping the initial implementation work.

## Agent-readiness review, 2026-09-28

The execution plan now separates start and completion gates for WP13/WP14, gives every package a state record, and reserves complete status for reviewed, integrated work. WP10 follows the approved concept rather than asking for the same decision again. The coordinator owns shared status/contracts to reduce conflicting edits; markdown tracking does not provide automatic locks. WP01 is the only ready implementation package. Planning files must be included in the selected base revision before fresh worktree dispatch. No implementation, live infrastructure measurement or predictive experiment was added by this readiness pass.
