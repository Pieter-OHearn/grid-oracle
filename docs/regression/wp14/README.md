# Weekend and operational regression

WP14 exercises an independently authored, synthetic 22-entry sprint weekend
through the **integrated** PostgreSQL schema, provider snapshot adapter, durable
job ledger, retained standings/qualifying baselines, immutable forecast store,
public API, stored evaluator and new-database recovery. It does not substitute
the older saved-publication fixture for a pipeline run.

The production job adapter still blocks feature/predict/publish/evaluate, as
recorded by WP04/WP13. `scripts/regression/replay.py` supplies **test-only**
handlers that call the real contracts. Thus this is end-to-end synthetic
integration/recovery evidence, not evidence that an unattended production
scheduler or real provider-driven issuance is ready. A production adapter and
approved production bundle remain release prerequisites. WP14 does not promote
a model, refit weights, change locked benchmark rules or deploy anything.

## Fixture lineage

[`fixtures/manifest.json`](fixtures/manifest.json) pins the exact weekend bytes,
retained Jolpica archive and two response members, and the unchanged WP06 v2
lock. [`fixtures/weekend.json`](fixtures/weekend.json) is synthetic throughout:
session/availability times, 22 entrants, standings, qualifying, results and
corrections are authored scenarios, not actual 2026/2027 observations. The
season-rollover test advances session/issue dates with the season. Raw synthetic
observations retain their capture time and race identity in their immutable
envelope; the provider response snapshot remains separate.
The envelope freezes the ingested qualifying feature values as well. A feature
retry reuses this verified observation and its original cutoff, even when source
payloads or qualifying SQL change after the first raw-snapshot commit.

The two unmodified Jolpica response members were recorded on 2026-09-28 in
`docs/evidence/jolpica-2022-2025.tar.gz`. Attribution and CC BY-NC-SA 4.0 terms
are preserved in [the original archive data card](../../evidence/README.md#attribution-and-license).
The recording contract verifies decoded response shape, season/round and result/
qualifying identity through the integrated provider snapshot boundary. It
does not invent historical source-availability times. Recorded and synthetic
transports never open sockets; a pytest guard rejects ordinary `requests`
provider calls. Database/loopback browser and package/image registry access are
separate from provider access.

The executable fixed-model bundle is explicitly `wp14-fixed-baseline-v1`:
standings pre-weekend, qualifying post-qualifying, temperature 4 and identity
calibration, exactly the baselines retained by WP09. Its WP13 closure and WP03
DB bindings are checked before load. It is a test bundle, not a released
production champion. Two additional checks load actual, hash-pinned WP07
XGBoost artifacts selected from WP09's immutable input lock and execute them on
reconstructed WP05 fields. No frozen input, split, metric, tolerance, protocol,
experiment, promotion rule or dependency lock is rewritten.

## Regression map

All names below are in `scripts/tests/test_wp14_postgres.py`.

| Contract / regression | Test evidence |
| --- | --- |
| D09/D17/D21, full lifecycle | `test_every_lifecycle_stage_persists_and_is_public`: all nine durable jobs succeed; real interval/upsert SQL, snapshots, baseline predictions, 44 outputs, two publications and computed evaluations |
| D21 populated migrations | `test_migration_populated_legacy_repeat_and_unknown_refusal`, `test_wp04_to_head_upgrade_preserves_issued_forecast`: all historical SQL → Alembic head, populated identity sentinel, repeat upgrade, WP03→WP04 upgrade retains issued hashes |
| Unknown schema refusal | `test_unknown_postgresql_schema_is_refused_without_reset`: sentinel survives rejected upgrade |
| D09 publication completeness | `test_partial_publish_keeps_last_good`: incomplete new horizon cannot publish or replace saved output |
| D09 future data | `test_future_availability_is_rejected`, `test_future_sources_results_and_newer_model_cannot_change_issued_forecast`: mutable sources/new model/results change; both horizons compare every reproduced order/probability and entry output with original predictions/persisted outputs, original public bytes/table hashes survive |
| D17 outages/retry | `test_outage_retry_quarantine_and_last_good`, 12 before/after-write `test_worker_stage_failure_preserves_last_good_and_recovers` cases: qualifying ingest/features/inference/publication and result ingest/evaluation recover through the ledger while preserving last-good reads |
| D17 partial commits | Two `test_feature_retry_reuses_partially_committed_observation` cases retain raw observations/cutoffs/features after a raw-only commit and subsequent source changes; `test_evaluation_retry_preserves_first_commit_and_finishes_missing_horizon` preserves the first evaluation and finishes the second |
| D17 duplicate worker/restart | `test_duplicate_workers_claim_once_and_recover_lost_lease`: concurrent PostgreSQL claims, durable feature work before acknowledgment loss, lease expiry, replacement worker, unchanged observation and idempotent publication |
| WP06 known tie defect | `test_season_opening_ties_never_favor_identity`: all 22 probabilities equal 1/22 |
| WP02 sprint/late/weather/domain | `test_sprint_late_qualifying_weather_withdrawal_reserve_transfer`: sprint first-competitive cutoff, final qualifying delay, null weather, full intended denominator including withdrawal, reserve and transferred-team entry; partial qualifying/forbidden current qualifying rejected |
| Pit-lane start | Lifecycle test preserves final grid 0 in real result SQL; qualifying model uses recorded qualifying, never final grid |
| Cancellation | `test_cancellation_supersedes_pending_but_retains_last_good`: pending work superseded, no new horizon, old publication remains |
| Season rollover | `test_season_rollover_preserves_event_context`: date/season/race identity isolation and cross-season 404 |
| Corrections | Future-data test appends result revision/evaluations without changing forecast; browser verifies unscored latest revision cannot reuse earlier score |
| WP13 bundle/load | Four component tamper cases, manifest/DB-binding test, two retained trained-model checks |
| D09 SQL immutability/hash verification | `test_sql_trigger_prevents_issued_history_mutation`, `test_corrupt_stored_output_hash_is_rejected`: actual PG triggers reject updates; explicit DBA corruption injection in a disposable DB is rejected by recovery inventory |
| WP13 restore | `test_new_database_restore_verifies_bundle_and_all_lineage`: custom PG16 dump/restore to a new random DB, externally pinned sealed receipt, all ten table hashes, actual replacement artifact tree/bundle and identical public response; corrupt live tree fails |
| Public UI/accessibility | `scripts/wp14_browser.cjs`: built React, real persisted PG/API, refresh, 22-field horizons, computed scores/corrections, season switch/unpublished, delayed HTTP, real 503 and keyboard retry, light/dark/390/320px axe and screenshots |
| Bounded native images | `scripts/wp14_smoke.py`: native architecture equality, non-root offline API/worker scientific imports, 768MiB/one CPU/PID128 caps, immutable WP13 image pins |

## Reproduction and CI

The `Weekend regression` workflow runs the PostgreSQL suite and six opt-in
defect controls on native Ubuntu AMD64 and ARM64. It uses the same PG16 index
digest as WP13. No emulation counts as native evidence. It additionally runs
hash/contract drift checks and bounded offline image smoke. AMD64 builds and
checks the frontend, then runs pinned Playwright 1.62.1 and axe-core 4.10.3
against loopback. Normal backend/frontend workflows remain independent gates.
Current acceptance requires 39 cases, six Python defect controls, and one browser
keyboard defect control. Initial 28-case/four-control receipts are retained as
historical evidence; follow-up receipts live under `evidence/fixes/`.

Local reproduction after installing the frozen API/pipeline/dev environment:

```sh
# Supply only a disposable PostgreSQL server; tests create/drop wp14_<uuid> DBs.
export WP14_POSTGRES_URL=postgresql://postgres@127.0.0.1:55414/postgres
export WP14_POSTGRES_CONTAINER=wp14-postgres-local
python -m pytest scripts/tests/test_wp14_postgres.py -q --junitxml=/tmp/wp14-evidence/postgres.xml
python -m scripts.wp14_report --junit /tmp/wp14-evidence/postgres.xml --output /tmp/wp14-evidence/coverage.json
python -m scripts.wp14_mutations --output /tmp/wp14-evidence/mutations
python -m scripts.wp14_smoke --output /tmp/wp14-evidence/native.json
```

The container ID is required for the matching PG16 dump/restore client. The
restore test fails if it is absent. Without the URL, standalone pytest explicitly
skips PG cases; **this is not acceptance**. `wp14_report` requires zero skips,
errors and failures and a full case count. CI's database is disposable with
trust authentication, runner-local port and bounded memory; never reuse this
configuration for production. The local shared Docker VM filled after image
pulls; only WP14's own failed DB/anonymous volume was replaced with bounded
tmpfs. Unrelated images, caches and infrastructure were preserved.

For the browser, build `dashboard`, run
`python -m scripts.wp14_preview --output /tmp/wp14-preview`, then set
`NODE_PATH` to pinned Playwright, `AXE_PATH` to axe's script,
`WP14_PREVIEW_OUTPUT=/tmp/wp14-preview`, and run
`node scripts/wp14_browser.cjs`. An optional `CHROME_EXECUTABLE` selects native
local Chrome. The test server wraps the real API with local filesystem-controlled
HTTP delay/503 injection; it does not intercept or fabricate browser responses.
It serves compiled assets without Nginx; WP13 retains Nginx/container proxy
recovery evidence. The server drops only its own random DB on graceful exit.

`wp14_mutations` compiles four exact production function mutations and two replay
mutations in isolated pytest processes: bypass completeness, bypass future availability, restore the
known first-rank tie advantage, bypass stored output hashing, reread live
qualifying on reproduction, and recapture a committed observation on retry.
Each must produce one failure in the named assertion, exit 1, zero skips and zero collection/setup
errors. Drift in a mutation target fails closed. Source files are never edited.
`node scripts/wp14_browser_mutations.cjs` additionally prevents Space activation
of After qualifying in the actual browser. It must fail the named horizon check
after the first two successful checks. The positive test waits for the new URL,
pressed state and selected forecast's exact stored run ID, outside the separate
comparison panel. Both native CI jobs check six Python controls; AMD64 checks the
browser control and retains its failure screenshot/trace/JSON/log.

Both native CI jobs upload coverage limits, source/fixture hashes, JUnit, logs,
mutation failure evidence and smoke receipts for 30 days, including on failure.
The browser saves screenshots, JSON and a Playwright trace on success/failure.
Artifacts contain only synthetic/public test data. Do not include credentials,
real provider bodies with separate rights, dumps or model files. Commit the
small acceptance receipts/screenshots; CI retains larger traces/logs.

## Coverage limits and release handoff

- No live providers run in deterministic CI. Current Jolpica/FastF1/F1/weather
  contracts, source terms, rate limits, real source timing and availability need
  a separately authorized manual/scheduled contract check. This package creates
  no live-provider monitor.
- No production adapter, approved production bundle, real prospective forecast
  or promotion is supplied. Research history remains explored reconstruction;
  synthetic metrics never enter the locked benchmark or public aggregate.
- Native CPU Linux AMD64/ARM64 and local macOS ARM64 are covered. CUDA/MPS,
  physical Pi headroom, representative throughput and all image builds are not
  qualified here. Image smoke tests the pinned historical WP13 release; it does
  not publish/promote a new image or claim current-source release builds.
- Automated Chromium and WCAG A/AA axe scans do not replace native screen-reader,
  keyboard/device/participant and manual contrast checks. Axe incomplete items
  are retained for review, not treated as passes.
- New-DB restore proves small-fixture byte/lineage identity. Physical off-primary
  backup transfer, secrets recovery, WAN/IPv6 access separation, production
  RPO/RTO and loaded-host SLOs remain WP13/WP15 activation gates.
- No homelab mutation, public listener/deployment, paid resource, release/tag or
  external status message is created. CI/read-only image pulls are test inputs.

Rollback is reverting this test/CI package. No schema revision, production data,
model pointer, public serving code or migration/backfill changes are introduced.
WP15 must consume these limits and collect genuine prospective/release evidence.
