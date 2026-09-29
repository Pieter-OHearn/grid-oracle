# WP05 audited historical dataset data card

## Identity

Dataset contract: `2026.1-wp05`
Versioned dataset: `dataset-2026.1-wp05-87d0a99ef821`
Immutable manifest SHA-256: `3b73e717b0cf52f93df145f46f9dff32f91f72b1b68c57acfb2442402bd1be20`

The committed [manifest](versions/dataset-2026.1-wp05-87d0a99ef821/manifest.json)
lists every input response digest, output Parquet digest and per-season/session
checkpoint. The `manifest.sha256` sidecar is the verification value for that
manifest.

## Intended use and non-use

This is an audited reconstruction contract for WP06's future benchmark work,
not evidence of forecasts issued during 2022–2025. It produces separate
pre-weekend and post-qualifying frames, enforces their feature gates, and
records provenance in each output. No model is trained, evaluated or published
by this package.

All rows in this initial cohort have `asof_eligible=false`. Jolpica responses
were archived on `2026-09-28T16:04:29.674132+00:00`, but neither the archive
nor its individual responses establishes when a source first made each
historical fact available. `source_available_at` therefore remains null and
the fact-quality label is `archived_retrieval_known_asof_unknown`. The
reconstruction does not backdate that timestamp or assert that its records
were known at an original forecast cutoff.

## Source and construction

The only raw source is the committed 40-response Jolpica result/qualifying
archive at `docs/evidence/jolpica-2022-2025.tar.gz`, with its recorded archive
retrieval time in `docs/evidence/baseline-summary.json`. The source manifest
SHA-256 is `87d0a99ef821403e3dbfec95af29fcefd21252f8080f0d0fcd589a99d8f15a1e`.
The reconciliation key is the provider-scoped WP02-safe identity form
`provider:jolpica:<kind>:<provider-id>`; names are never used to merge people
or constructors. A curated WP02 alias map can later replace these provisional
provider identities without changing raw evidence.

Run the fully offline reconstruction:

```sh
uv run --extra pipeline --group dev python -m pipeline.dataset.backfill \
  --archive docs/evidence/jolpica-2022-2025.tar.gz \
  --output /tmp/gridoracle-datasets
```

Repeat `--season 2024` to build or resume only a season's `pre_weekend` and
`post_qualifying` partitions. A checkpoint is tied to the complete raw-source
manifest hash; changed source snapshots make a new versioned output root.

## Limitations and exclusions

- The baseline is 2022–2025. No 2018–2021 source snapshot set with comparable
  result and qualifying coverage was supplied, so expansion toward 2018 is
  deferred rather than filled with weaker data.
- Entry fields are reconstructed from result rows and labelled
  `reconstructed_from_result_entry`; they are not a historical entry-list
  release. This is intentionally not a complete live entry replay.
- The archive contains no sprint result/points feed. Standings are explicitly
  `*_race_only`, not silently presented as full championship standings.
- This is a weather-free cohort: no weather field or proxy is registered.
- `circuit_tyre_degradation_index`, hard-compound performance and FP2/sector
  proxy features are excluded pending a preregistered ablation. The legacy
  feature path is not the WP05 training contract.
- Provider revisions, late classifications and qualifying corrections may be
  present. They are visible as archived historical facts, never upgraded into
  as-of availability evidence.

## Rollback

Dataset versions are additive and content-addressed. To roll back consumption,
pin a previous manifest/hash or stop selecting this version; do not overwrite
an existing manifest or partition. The raw archive remains the recovery input.
