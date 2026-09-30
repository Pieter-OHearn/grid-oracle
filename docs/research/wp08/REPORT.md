# WP08 custom probabilistic race model — learning report

2026-09-30. Offline experiment; no promotion, production selection or deployment.

The reference model works mathematically and operationally, but loses to the standings/qualifying baselines on diagnostic winner loss. A small nonlinear model improves these explored-history scores. The pre-weekend nonlinear-versus-standings block interval still includes zero. Neither model has as-of, prospective or operational shadow evidence; WP09 review and fresh future evidence remain mandatory.

## Frozen inputs and experiment design

Base main: `345eb1e321917e2cb22ce7a19b21de1e04a1c945`; WP06 complete through merged PR #99 (`b9439e7`). Measured clean implementation: `91e34f0227b4450db6963cacc5b1962b1b83e0e5`. Source SHA-256: `c98743dc994682b2808579a8fa3cde2bc2acbf45989907f4f9a9d2c333a1e53c`.

WP06 v2 protocol, dataset, split, dependency lock and scoring code remain byte-identical. Only the explored 2022–2025 archive is used: 70 frozen outer races, 18 consecutive within-fold blocks, whole intended fields, both horizons. As-of eligibility is **0/70**; prospective scores/coverage are **N/A**. No WP07 branch, source or report is read or edited for model selection.

Seed 6062026, one PyTorch thread, 160 full-batch Adam epochs per fit. Five registered reference variants and two challenger widths produce 42 train-only trials and 12 selected train+tune refits. Dictionaries and transforms never fit calibration/evaluation. Four tuning races select each fold/horizon/family configuration; four calibration races choose a registered temperature through the WP06 adapter. Every decision is retained before outer scoring. No changes to registered settings were made after diagnostic evaluation.

The nonlinear experiments were executed only after reference correctness/lifecycle tests and the development reference run passed. Trial parameter counts range from 86 to 778. Driver/team effects are shrunk, not causally identifiable. Circuit interactions are an optional team×circuit table; unobserved pairs/identities have zero prior effect. The small nonlinear challenger is a shared-entry tanh network. See [implementation and likelihood explanation](README.md).

## Diagnostic outer scores

| Horizon | Family | Winner loss | Brier | ECE | Rank MAE | Rank rho | Winner hit | Top-3 | Top-10 | Coverage |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| post_qualifying | nonlinear | 1.254299 | 0.593430 | 0.009227 | 2.551269 | 0.750959 | 0.557143 | 0.647619 | 0.784286 | 70/70 |
| post_qualifying | reference | 1.866059 | 0.707809 | 0.013938 | 2.869927 | 0.700936 | 0.471429 | 0.552381 | 0.754286 | 70/70 |
| pre_weekend | nonlinear | 1.710246 | 0.741297 | 0.016737 | 3.096116 | 0.667436 | 0.485714 | 0.547619 | 0.732857 | 70/70 |
| pre_weekend | reference | 2.100011 | 0.768984 | 0.015860 | 3.281217 | 0.625541 | 0.471429 | 0.504762 | 0.714286 | 70/70 |

Same WP06 baseline winner losses: standings 1.903398 (both horizons), recent form 1.954942, post-qualifying order 1.737578, uniform 2.994267. These are fixed reference comparisons, not promotion-comparator selection from evaluation.

| Diagnostic contrast (reference minus candidate) | Mean improvement | Paired block 95% interval |
| --- | ---: | --- |
| pre_weekend: linear reference − nonlinear | 0.389765 | 0.025299 to 0.789225 |
| pre_weekend: standings − nonlinear | 0.193153 | -0.006203 to 0.383334 |
| post_qualifying: linear reference − nonlinear | 0.611760 | 0.281479 to 0.987706 |
| post_qualifying: qualifying − nonlinear | 0.483279 | 0.206478 to 0.744874 |

Intervals use the unchanged WP06 2,000 seeded race/block draws. Full JSON reports retain all baselines, both units of uncertainty, per-fold and per-race values, reliability bins, metric denominators and overlapping circuit/season/era/driver/team/field/missingness/weather slices. Small slices are descriptive. No winner is selected by searching slices.

## Inner validation — all meaningful trials retained

Each cell is equal-race winner log loss on its frozen four-race tuning block. Selection is within each family; nonlinear and reference remain separate reported contenders.

| Candidate | Pre 2023 | Pre 2024 | Pre 2025 | Post 2023 | Post 2024 | Post 2025 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| linear | 1.698115 | 1.402120 | 2.494993 | 1.623683 | 1.261465 | 2.179930 |
| strong_shrinkage | 1.740617 | 1.421195 | 2.495791 | 1.681999 | 1.287148 | 2.203593 |
| recent_history | 1.698115 | 1.189820 | 2.383489 | 1.623683 | 0.972008 | 2.091213 |
| standings_only | 1.758370 | 1.408428 | 2.588744 | 1.758370 | 1.408428 | 2.588744 |
| circuit | 1.459649 | 0.757288 | 3.176294 | 1.414265 | 0.705677 | 2.812278 |
| nonlinear8 | 1.480945 | 1.371021 | 2.301712 | 1.255616 | 1.040561 | 1.846008 |
| nonlinear16 | 1.477638 | 1.366353 | 2.242794 | 1.164348 | 0.991628 | 1.873854 |

| Horizon / family / fold | Selected trial | Calibration temperature |
| --- | --- | ---: |
| pre_weekend / reference / 2023 | circuit | 0.7 |
| pre_weekend / reference / 2024 | circuit | 1.0 |
| pre_weekend / reference / 2025 | recent_history | 0.7 |
| pre_weekend / nonlinear / 2023 | nonlinear16 | 0.7 |
| pre_weekend / nonlinear / 2024 | nonlinear16 | 0.7 |
| pre_weekend / nonlinear / 2025 | nonlinear16 | 0.7 |
| post_qualifying / reference / 2023 | circuit | 0.7 |
| post_qualifying / reference / 2024 | circuit | 1.0 |
| post_qualifying / reference / 2025 | recent_history | 0.7 |
| post_qualifying / nonlinear / 2023 | nonlinear16 | 0.7 |
| post_qualifying / nonlinear / 2024 | nonlinear16 | 0.7 |
| post_qualifying / nonlinear / 2025 | nonlinear8 | 0.7 |

## What failed and what we learned

- The initial MPS loss failed because torch 2.7.0 lacks native `aten::_logcumsumexp` on MPS. The first acceptance run had 14 passes, one MPS failure and one CUDA skip. Equivalent O(field²) logsumexp risk sets fixed this without CPU fallback or a change in the likelihood. Final CPU/MPS gradient and update parity passes.
- The linear reference is too restrictive for winner probability even when its ranking loss decreases. Its pre-weekend winner loss regresses 0.196612 versus standings and its post-qualifying loss regresses 0.128481 versus qualifying. Lower training loss is not a quality gate.
- Circuit interactions help the 2023/2024 inner blocks but fail the 2025 inner block: 3.176294 pre and 2.812278 post, worse than the simpler reference variants. A small four-race tuning block is noisy and the optional table can memorize sparse combinations; the chosen recent-history variant is retained instead for 2025.
- Stronger shrinkage and standings-only features fail to beat the registered alternative in these inner blocks. The last-24 window duplicates full history where fewer than 24 fitting races exist, but is useful in 2025. No extra history-window or epoch search was launched.
- The 16-unit challenger does not win every inner block: post-2025 selects eight units (1.846009 versus 1.873850). Capacity is selected before evaluation, not increased because an outer score looks promising.
- An explicitly requested CUDA run failed with `ValueError: unavailable backend: cuda`; its started/failed events are preserved. No CUDA fallback or remote PC execution is claimed.

The development reference run is retained as development-only: dirty source, before the final committed-source guard, with edits made during the session. It is not the reproduction evidence. Two later clean committed-source full runs provide that evidence. Reported chronological reconstruction can still contain source/entry availability uncertainty and hindsight in cohort reconstruction; all as-of and prospective promotion claims remain excluded.

## Compute, hardware and numerical evidence

Tested Mac: Apple M1, 16 GiB unified memory, macOS-26.5.2-arm64-arm-64bit, Python 3.12.14, PyTorch 2.7.0. CPU and MPS are available; CUDA build/devices are absent. Owner-reported PC: Ryzen 7 5700X, RTX 5060, 32 GB RAM, Windows 11 Pro. Exact PC VRAM, driver and CUDA compatibility are unverified; no host connection is established.

The two complete CPU runs took 16.460 and 17.619 seconds, with process peak RSS 382.266 and 361.219 MiB. Maximum batched CPU inference time across selected fold/horizon models was 0.000582 seconds/race. These are offline diagnostic measurements, not service/shadow qualification.

| Synthetic backend probe | 30 training epochs (s) | Inference s/race | Peak RSS MiB | Sampled MPS allocator / driver MiB |
| --- | ---: | ---: | ---: | --- |
| cpu | 0.766956 | 0.000031 | 337.234 | N/A |
| mps | 0.522066 | 0.000614 | 475.203 | 0.028076 / 26.765625 |

MPS maximum absolute discrepancies: scores 2.98e-08, loss 0, gradient 4.77e-07, winner probabilities 1.12e-08. Declared tolerances: scores abs/rel 2e-5; loss abs 2e-4/rel 2e-5; gradients and one SGD update abs/rel 2e-4. MPS memory is unified and its allocator peak is sampled before backward/after optimizer steps; it is not physical VRAM. CUDA peak VRAM/parity is N/A, with the skip and exact unavailable error retained.

## Checks and reproducibility

- `make check`: passed Python/dashboard lint, formatting and type checks (isolated environment, no sync).
- `make test`: 28 API tests, 362 pipeline tests passed; one unavailable-CUDA skip; 3 dashboard tests and dashboard type checks passed.
- Targeted committed-source acceptance: 17 passed, one unavailable-CUDA skip. Hand loss, double-precision gradcheck, tiny overfit, shuffle equivariance for reference/challenger, 20/22 masks, cold starts, isolated process save/load, forced child-process interruption/resume and immutable checkpoint checks all passed. Frozen fit-boundary/value regressions and failed-attempt retention passed.
- Resume after 11 epochs equals uninterrupted 30-epoch weights and loss curves bit for bit on CPU. Resume rejects changed data/config/vocabulary/backend/version/source. Random initialization is CPU-seeded; training uses no stochastic GPU operations.
- Retained artifact verification: four attempts checked, every original checkpoint/report/event hash verified, current and committed measured source bytes verified. Both clean runs have identical semantic report hashes.
- `git diff --check` passed. Existing SQLite/Starlette deprecation warnings remain; no cleanup is included.

Identical semantic result hash: `2f803356501a3ff58f690107281c13b30029d8e79c29e2fd4ae93bfc4cbd59d6`. Runtime metadata lives outside semantic hashes. Initial report and every model artifact are small enough for this evidence archive; all epoch checkpoint bytes are packed without changes in `checkpoints.tar.gz`, and the initial clean run also exposes 12 selected final model files under `models/`. Original `finished.json` fingerprints resolve to files or archive members; `retention.json` hashes the archive and aliases.

Reproduce commands and resume API: [README](README.md). Verify retained artifacts with `python -m docs.research.wp08.verify_artifacts` from the repo root. Backend evidence: [hardware.json](hardware.json). Correctness evidence: [acceptance.xml](acceptance.xml).

## Retained attempts

| Experiment ID | Role |
| --- | --- |
| `wp08-102c448a77374d9f87bc8d0f434f9605` | Clean committed-source full comparison and trained model aliases |
| `wp08-462781d0c3264070bf20622c2121ab9f` | Identical clean reproduction; all checkpoints retained |
| `wp08-6d6006f90db64c298fd7294c5bd62f32` | Development-only reference diagnostic; dirty source |
| `wp08-bf4fa5ae1e834ffc85d6cd1fd7d18a2d` | Explicit unavailable-CUDA failure |

## Limits and exact next action

The four-race tuning/calibration blocks are small, learned circuit interactions are sparse, driver/team effects are confounded, and this conditional ranking likelihood does not model retirement/DSQ/DNS mechanisms. Temperature often reaches 0.7, the lower registered bound; no extension of that grid was made after viewing results. Larger searches are not justified by this diagnostic track. No classical incumbent artifact is assessed here; WP07 comparison belongs to the independent WP09 review after integration.

Exact next action: reviewer evaluates the ready WP08 PR against main, verifies retained hashes/tests, and records findings in `docs/workplans/WP08.md`. The coordinator alone may merge after approval. No WP09 implementation, prospective enrollment, promotion, homelab mutation, real bootstrap, deployment or PR merge is authorized by this report. Rollback is removal from offline experiment use; no stored data or serving behavior changed.

## Selected artifact fingerprints

- Research configuration: `eeb030014b571fa976a8b8be7de9e3e454854f28da1e055db8b03631215191e5` (`config.json`).
- Research dependency pins: `bb12045b89acf3f7e04f02d6e029257329ab960590553da2adb2da776990e9ee` (`requirements-macos.txt`).
- Hardware/backend evidence: `79ba29febc73e538ea336b6c1a64b4946828f7321e7dfb33f70bbd0e5472a208` (`hardware.json`).
- Initial full report: `2fde576b88ab1ed0de36aa15f2347ccb9aab28a8b2586811265ae6a7884f759f` (`runs/wp08-102c448a77374d9f87bc8d0f434f9605/report.json.gz`).
- Initial checkpoint archive: `8bb764db76ed4d23d966555ec136be395720bb51280ebeb1e4928dfac7e950bf` (`runs/wp08-102c448a77374d9f87bc8d0f434f9605/checkpoints.tar.gz`).
- Selected post-2025 nonlinear model: `04ad5dba8128385530be12f2dad0bef6fbf8abc03ef33a284f2e3c8be9822695` (`runs/wp08-102c448a77374d9f87bc8d0f434f9605/models/post_qualifying-nonlinear-2025.pt`).
