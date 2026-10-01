"""WP03-compatible immutable research storage; no publication side effect."""

from dataclasses import replace

from gridoracle.provenance.store import ForecastEntry

from pipeline.benchmark.artifacts import digest
from pipeline.selection.outputs import Field, validate_output


def store_research_output(store, run, output: dict, field: Field):
    validate_output(output, field)
    if run.input_manifest.get("race_key") != field.race:
        raise ValueError("stored run requires the same explicit provider race key")
    if run.horizon != field.horizon or run.expected_entry_count != len(field.entries):
        raise ValueError("stored run horizon or entry count differs from frozen output")
    entries = [
        ForecastEntry(
            e,
            {
                "win_probability": output["winner"][e],
                "conditional_top3_probability": output["conditional_top3"][e],
                "conditional_top10_probability": output["conditional_top10"][e],
                "rank_marginals": output["rank_marginals"][e],
                "field_sha256": field.sha256,
                "target": output["target"],
            },
        )
        for e in field.entries
    ]
    # The historical dataset's cutoffs are markers, not authenticated timestamps.
    # Never convert them into a verified live run, even if a caller supplies one.
    research = replace(
        run,
        provenance_grade="legacy_unverified",
        input_cutoff_at=None,
        source_available_at=None,
        input_manifest={
            **run.input_manifest,
            "wp09_output_sha256": digest(output),
            # Keep the entire envelope, including sampler settings and predicted order.
            "wp09_output": output,
            "field": output["field"],
            "lineage": output["lineage"],
            "expected_outputs": {e.entry_key: e.output for e in entries},
        },
    )
    identifier = store.create_forecast_run(research)
    store.add_entry_outputs(identifier, entries)
    return identifier
