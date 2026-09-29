# WP04 job-state and operator notes

The database ledger is the scheduler authority. Calendar refresh creates a
timestamped graph: `pre.feature → pre.predict → pre.publish`,
`qualifying.ingest → post.feature → post.predict → post.publish`, and the
independent `result.ingest → evaluate` chain. A Grand Prix qualifying record
must contain the verified grid and exact active-entry count before post-horizon
publication; sprint qualifying cannot satisfy that gate.

States are `pending`, `running` (with an expiring lease), `succeeded`,
`blocked`, and `superseded`. Reconciliation returns expired leases to pending,
and a revised calendar supersedes pending old-schedule work before rebuilding
the graph. A blocked job exposes its stored error; retry only after correcting
the provider/input problem. A second worker cannot claim an already leased job.

Provider adapters identify GridOracle, obey a local rate budget, retry
429/timeouts with bounded exponential backoff plus jitter, write valid raw
snapshots, and quarantine exhausted malformed/failed responses. Weather is
selected only from records valid during the actual race interval. `unavailable`
is distinct from a 0% (dry) forecast, and captured/issue/release timestamps
remain part of the raw snapshot/provenance contracts.

Migration `20260929_05` is additive. Enable this scheduler only behind the
WP04 feature flag and keep one writer during switchover. Roll back by disabling
the feature flag; retain the ledger for diagnosis. An Alembic downgrade drops
the ledger, so it requires a verified pre-upgrade backup and is not routine.
