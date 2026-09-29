# Season and target contract

Contract version: `2026.1`. This document is the WP02 source of truth for
season data, race labels and provider-result interpretation. A forecast run
persists both this version and its horizon; a later policy is a new version,
not a reinterpretation of earlier scores.

## Horizons

`pre_weekend` is issued before the event's first scheduled competitive
session. Its input cutoff is the verified weekend publication cutoff. It cannot
include practice, sprint, qualifying, grid or any fact first available after
that cutoff.

`post_qualifying` is issued only after the final qualifying classification and
race grid have been verified for the intended field and before the race start.
Sprint results never substitute for Grand Prix qualifying. A delayed qualifying
or a revised race start creates a revised event/session schedule and a new run;
it never changes a historical run's cutoff.

Both horizons predict the same target but are separate products, training
cohorts and scorecards.

## Result target and provider status

The target is the officially classified Grand Prix finishing order, normalized
to a contiguous **internal rank** for model labels. `official_rank` is the
provider/FIA classification rank and is never adjusted, filled or replaced.
`internal_rank` orders only target-eligible rows by `official_rank`, so it may
differ when excluded rows create an official-rank gap.

| Canonical status | Provider examples | Target treatment |
| --- | --- | --- |
| `finished` | `Finished` | include when `official_rank` is positive |
| `lapped` | `Lapped`, `+1 Lap`, `+N Laps` | include when `official_rank` is positive |
| `classified_retirement` | `Retired`/`DNF` with an official rank | include; it remains visibly a retirement |
| `retired_unclassified` | `Retired`/`DNF` without official rank | preserve, exclude from target |
| `dns` | `DNS`, `Did not start`, withdrawn | preserve, exclude/mask from target |
| `dsq` | `DSQ`, `Disqualified`, excluded | preserve, exclude/mask from target |
| `unknown` | any unrecognized or absent status | preserve raw value, exclude and quarantine coverage |

Duplicate official ranks are invalid for target construction and block scoring.
Unknown status never becomes a DNF. Official points and countback are stored as
official facts and are not inferred from `internal_rank`; championship scoring
and promotion policies are independently versioned ruleset concerns.

## Stable identities and changes

Every durable entity has an immutable string `identity_key`, distinct from a
provider ID and display name. The migration assigns existing rows
`legacy:<kind>:<numeric-id>` without merging them. Provider IDs and old names
belong in aliases with a source and validity range.

| Entity | Stable identity | Change policy |
| --- | --- | --- |
| Driver | person-level key | code, number, transliteration and provider IDs are aliases; a reserve remains the same driver |
| Team | legal/competitive entrant key | display/brand rename is an alias; a successor needs explicit curated mapping, never name-based auto-merge |
| Circuit | venue key | venue renames are aliases; a material relocation/new venue gets a new key |
| Layout | circuit + configuration key | layout changes are separate layouts under a venue |
| Season | calendar year + ruleset version | no yearly application fork |
| Session | event + session kind + revision | sprint, sprint qualifying, qualifying and race are distinct kinds |
| Entry | event + driver + competition role + revision | primary, reserve, transferred and withdrawn entries are explicit; a transfer closes one entry and opens another |

Event lifecycle is `scheduled`, `postponed`, `cancelled` or `completed`.
Results have numbered revisions; corrected results append a revision rather than
overwriting the prior source fact. Field size is the set of active event entries
for the relevant session, never an assumed 20 or 22.

## Import and migration safety

The default migration ledger is Alembic. It recognizes a populated legacy
schema and stamps the legacy baseline before applying only additive WP02
revisions. It refuses an empty or unrecognized database rather than recreating
or resetting it. A database backup is required before non-dry-run upgrades.
For rollback, first run `python -m scripts.db_migrate --downgrade-wp02`, then
restore that backup, then run `python -m scripts.db_migrate
--finalize-legacy-restore`. The final command removes the baseline ledger only
after it verifies that additive WP02 tables are gone and the restored database
is at the recognized baseline. The Alembic downgrade does not attempt to
reverse identity backfills.

`python -m scripts.season_import --dry-run --config path/to/season.json`
validates a self-contained configuration and prints the planned calendar and
entries. It makes no database/provider calls. New-season preparation is adding
that validated configuration/data; no code fork is required.

[`season-import-example.json`](season-import-example.json) is a complete
schema-valid example. Use `--print-schema` with the command to emit the exact
machine-readable configuration schema.
