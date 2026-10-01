# WP13 application review and fixes

Owner requested `$review-agent`, all findings fixed, then rebase onto main.
The skill's read-only review covered the full branch diff at
`5e1b88c0b00db51c64513a6b18fc64a5b90446ee` against fetched `origin/main`
`897ff95772c822f3fac5c08d38357c0a9dd51f36` (merge base
`60c5376c5639f7fcab7db38b218ea44d48ec140d`). Code edits began only after the
review findings were reported. This is a task-local review, not independent
approval or integration. Homelab changes are outside the corrected assignment.

| Finding (original diff location) | Reproduction and consequence | Fix and regression evidence |
| --- | --- | --- |
| P1: verify replacement runtime mounts (`scripts/wp13_recovery.py:93`) | Compare passed with healthy `/recovery/artifacts` while the configured live artifact and bundle mounts were missing. A restore could pass its gate then fail serving. | Compare hashes the actual configured runtime tree and selected bundle against the externally pinned receipt, then checks DB bindings. Unit tests corrupt a live raw snapshot, remove the live root, select another bundle hash and corrupt its manifest while the backup remains intact. Native drill restores to separate live mounts and rejects deliberate live corruption before its positive comparison. |
| P2: reject removed migration ledger (`scripts/wp13_migrate.py:29`) | Dropping `alembic_version` after sealing a migrated database bypassed the conditional revision check and called upgrade. | Always compare the current revision, including missing/null, with the sealed revision before DDL. Unit test removes the ledger and asserts upgrade is never called; native drill temporarily renames it and verifies rejection before restoring it. |
| P2: support pre-ledger restore comparison (`scripts/wp13_recovery.py:93`) | Empty/legacy backups have null schema/lineage, but compare queried missing provenance and ledger tables and raised OperationalError. | Inspect schema presence; compare null pre-ledger metadata without querying missing tables. Partial provenance still fails closed. Unit coverage exercises empty and legacy-core targets and subsequent revision drift; native drill compares the empty pre-bootstrap recovery set. |
| P2: block legacy model-selector evaluation (`gridoracle/ops/runtime.py:56`) | EVALUATE delegated to the legacy scheduler handler, which selected the newest legacy model and invoked evaluation rather than the declared bundle. | Block EVALUATE through the durable ledger until a bundle-aware evaluation adapter exists. Regression proves the legacy handler is never called and the ledger receives JobBlocked. |
| P2: stream lineage inventory within tools memory (`gridoracle/ops/recovery.py:33`) | A 24 MiB synthetic evaluation payload needed 74.4 MiB of Python allocations from whole-table copies; a modest larger table could exhaust the 256 MiB tools cap. | New v2 receipts stream primary-key ordered canonical rows with a PostgreSQL server-side batch of 100. Regression inventories 6,000 4 KiB rows with peak Python allocation below 8 MiB. Existing v1 receipts retain their original algorithm for compatibility; large v1 sets need sufficient memory or their original pinned tools image. |

The released `.3` images predate these corrections. They remain historical
artifacts and must not be promoted as the corrected candidate. The replacement
`v0.1.0-wp13.4` on rebased source `9e726efa1ffac737bc35c645e6d52841a0205a3a`
passed both native candidate and released-digest recovery reports (12 checks
each) in run 36884062642. See `evidence/README.md` and the WP13 state record.
