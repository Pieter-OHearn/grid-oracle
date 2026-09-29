# Reproducible baseline audit

Retrieved 2026-09-28 from the public [Jolpica API](https://github.com/jolpica/jolpica-f1). This is a small descriptive experiment supporting the repository review, not a model leaderboard or a validated historical forecasting experiment.

## Results

Predict each entrant's result order using qualifying order alone:

| Season                    | Races evaluated | Mean absolute position error | Exact position hit rate | Winner hit rate | Podium set overlap |
| ------------------------- | --------------: | ---------------------------: | ----------------------: | --------------: | -----------------: |
| 2022                      |              22 |                        3.691 |                  12.05% |          45.45% |             63.64% |
| 2023                      |              22 |                        3.691 |                  12.95% |          68.18% |             62.12% |
| 2024                      |              24 |                        2.846 |                  15.42% |          50.00% |             62.50% |
| 2025                      |              23 |                        3.338 |                  17.89% |          65.22% |             75.36% |
| Pooled, equal race weight |              91 |                        3.379 |                  14.63% |          57.14% |             65.93% |

The full results sample contains **92 races and 1,838 entrant-result rows**. The qualifying baseline excludes 2025 round 21 because Bortoleto has a race-result record but no qualifying record in the retrieved data. This is a source-coverage exclusion, not exclusion for prediction difficulty. Keep that race in the coverage report.

For comparison, sorting by the **final recorded starting grid** gives 3.468 MAE, 15.07% exact positions, 55.43% winner hits and 67.39% podium overlap over 92 races. The populations differ, so these aggregate numbers do not establish which baseline is better. Final-grid data can include information unavailable immediately after qualifying and must not be substituted into a post-qualifying backtest without timestamp evidence.

## Exact method and limitations

- `baseline_audit.py` downloads both endpoints for 2022–2025, paginates at 100 records, paces requests, asserts reported row counts and unique driver IDs per race, and records response SHA-256 hashes. The archive contains the 40 JSON responses used.
- Predictions are unique ranks among the drivers present in the race results. Qualifying positions are sorted and reranked within that population; extra qualifying-only entrants are omitted. This population is known retrospectively, so this experiment is not a complete operational entry-list replay.
- The target is the provider's numeric `position` for every result row, including retirement, DNS and DSQ rows. This is a **provider result-order target**, not a claim that every such driver has an official classified finishing position. No filtering based on finishing status is applied.
- Grid value zero is sorted behind positive grid slots, with stable driver-ID tie-breaking. This is a reproducible baseline convention, not a claim about physical pit-lane starting order.
- MAE = mean absolute predicted-minus-target order per race. Exact hit rate = matching ranks / that race's result rows. Winner = predicted first equals actual numeric first. Podium overlap = intersection of predicted first three and actual numeric first three / 3. Top-ten overlap is analogous. Season and pooled scores weight each race equally.
- Historical records may include revisions, disqualifications and corrected qualifying results published after a forecast cutoff. No feature publication timestamps were reconstructed. There are no probability scores because these baselines return deterministic orders.
- This is not a score for the current XGBoost model, a model uplift estimate, a performance ceiling, or a future accuracy promise. Sprint formats, eras and different forecast horizons need separate evaluation in the production research system.
- Raw status values visibly change between seasons: `+1 Lap`/`+2 Laps` in 2022 versus `Lapped` in later records. Treat string patterns as provider-specific inputs, not universal DNF definitions. Full distributions are in `baseline-summary.json`.

## Reproduce without network access

From the repository root:

```sh
mkdir -p /tmp/gridoracle-evidence
tar -xzf docs/evidence/jolpica-2022-2025.tar.gz -C /tmp/gridoracle-evidence
python3 docs/evidence/baseline_audit.py --cache /tmp/gridoracle-evidence --offline --output /tmp/gridoracle-baseline-reproduced.json
```

Compare all fields except `retrieved_at` with the committed summary. `retrieved_at` records the script run time; the original retrieval date is documented above. Omit `--offline` with a new cache directory to retrieve current records; revisions may change numbers and response hashes. The script fails visibly on HTTP errors; production ingestion needs more extensive retry/recovery behavior.

## Attribution and license

Source: Jolpica-F1, retrieved from the URLs listed in `baseline-summary.json`, 2026-09-28. The original response data in `jolpica-2022-2025.tar.gz` and the derived data in `baseline-summary.json` are provided under the provider's **[CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)** terms. Changes: responses compressed into an archive; derived metrics and metadata calculated by the accompanying script. No provider endorsement is implied. See [Jolpica terms](https://github.com/jolpica/jolpica-f1/blob/main/TERMS.md). This data attribution does not relicense the repository's application code.
