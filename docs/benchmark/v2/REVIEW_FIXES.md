# PR #99 review corrections

The owner's partial review of `cf8162a` was received 2026-09-30. The attachment
ends at B3's heading. The scope below covers all supplied findings; it does not
claim the four omitted independent review angles ran.

| Finding | Resolution | Regression evidence |
| --- | --- | --- |
| A1 unequal strengths for tied scores | Owner explicitly approved mean tied ranks on 2026-09-30; v2 preregistered in `6ae63cd`. Only deterministic order uses driver-ID tie-breaking. V1 remains intact. | Tied-winner tests for standings/form/qualifying; partial ties; uniform log loss; driver renaming |
| A2 caller-defined inputs bypass lock | Public evaluation and both fitting adapters compare against the registered lock. Evaluation records fingerprints. Feature values and winner/rank labels are checked against verified WP05 data. | Altered epsilon/blocks/seed/replicates/temperature, reduced/empty cohorts, relabelled winners, recut calibration, false fitting labels |
| A3 duplicate fold IDs | Structural split validation requires unique nonempty string IDs and nonempty folds. | Duplicated, empty and non-string ID tests |
| A4 features fit on calibration | `fit_in_block` permits train/refit only; probability calibration goes through `fit_calibrator`. | All four block types reject calibration-purpose feature fitting |
| A5 caller-chosen label deadline | Deadline derives from the pinned earliest evaluation race. Any availability column is always checked; supplied cutoffs must equal the deadline. | Both adapters reject 2098 labels with absent or extended caller cutoffs |
| A6 StopIteration on unknown fold | Shared `fold_by_id` raises ValueError. | Both adapters reject integer, whitespace and misspelled IDs |
| A7 proof unbound to race time | As-of checks require dataset context and exact pinned race/first-session times. Missing first-session metadata fails closed. | Later-race proof copied to an earlier row rejected; missing dataset rejected |
| A8 substring exemption | Current qualifying exemption is an explicit three-feature allowlist. | Historical feature containing “qualifying” cannot use the exemption |
| B1 zero-byte immutable artifacts | Serialize before creating files, fsync a temporary file and atomically link without overwriting. Gzip/Markdown outputs use the same publication helper. Failure logging cannot mask the original exception. | NaN/NumPy serialization failures, retryable failed completion, interrupted publication, existing file preservation, original exception survives logging failure |
| B2 duplicate/overwritten feature columns | Reject duplicate names; fitting checks supplied values against checksum-verified partitions. | Duplicate target-like columns and overwritten registered values rejected before callback |
| B3 failures before registry start | Write a minimal requested event first; config parsing, hashes and dependency discovery run inside the recorded attempt. Full provenance is appended in prepared.json. | Config, checksum and metadata exceptions all retain started+failed events |

Archived rows remain ineligible for as-of evaluation. The dataset does not contain
verified first-competitive-session times, so this work does not manufacture them.
Present `available_at` labels are checked even in exploratory fitting, but absent
historical availability cannot become prospective evidence. Registry I/O failures
can leave an explicit unfinished attempt; they never become an invented success.

All protocol metrics, guardrails, tolerances, seeds and resampling settings are
unchanged. V2 corrects an artificial tie-breaking advantage after review; its
changed exploratory scores cannot be claimed as model skill or promotion evidence.
The locked 2027–2028 prospective policy remains in force.
