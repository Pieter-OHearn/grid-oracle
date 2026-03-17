"""Unit tests for pipeline.ml.features."""

import pandas as pd
import pytest

from pipeline.ml.features import CIRCUIT_TYPE_ENCODING, prepare_features


def _make_df(circuit_types: list[str]) -> pd.DataFrame:
    n = len(circuit_types)
    return pd.DataFrame(
        {
            "driver_id": list(range(1, n + 1)),
            "circuit_type": circuit_types,
            "is_wet_race_forecast": [False] * n,
            "grid_position": [float(i) for i in range(1, n + 1)],
        }
    )


def test_circuit_type_encoding_known_types():
    """All three known circuit types map to their expected float codes."""
    df = _make_df(["high-speed", "road", "street"])
    result = prepare_features(df)
    assert result.loc[0, "circuit_type"] == float(CIRCUIT_TYPE_ENCODING["high-speed"])
    assert result.loc[1, "circuit_type"] == float(CIRCUIT_TYPE_ENCODING["road"])
    assert result.loc[2, "circuit_type"] == float(CIRCUIT_TYPE_ENCODING["street"])


def test_circuit_type_encoding_unknown_raises():
    """An unrecognised circuit type raises a descriptive ValueError."""
    df = _make_df(["oval"])
    with pytest.raises(ValueError, match="unknown circuit_type"):
        prepare_features(df)


def test_circuit_type_encoding_consistent_across_dataframe_sizes():
    """Single-row and multi-row DataFrames produce the same code for the same type.

    This is a direct regression test for the old dynamic .cat.codes encoding,
    which always returned 0 for single-race prediction data.
    """
    single_row = _make_df(["street"])
    multi_row = _make_df(["street", "road", "high-speed"])

    single_result = prepare_features(single_row)
    multi_result = prepare_features(multi_row)

    street_single = single_result.loc[0, "circuit_type"]
    street_multi = multi_result.loc[0, "circuit_type"]

    assert street_single == street_multi
    assert street_single == float(CIRCUIT_TYPE_ENCODING["street"])
