"""Validation math on small SYNTHETIC fixtures (not analysis results)."""
import math

import numpy as np
import pandas as pd
import pytest

from rush_threat import validation as V


def test_auc_perfect_reversed_tied():
    assert V.auc([0.1, 0.2, 0.8, 0.9], [0, 0, 1, 1]) == 1.0
    assert V.auc([0.9, 0.8, 0.2, 0.1], [0, 0, 1, 1]) == 0.0
    assert V.auc([0.5] * 4, [0, 1, 0, 1]) == 0.5


def test_auc_partial_ties_hand_computed():
    # positives {0.5, 0.7}, negatives {0.5, 0.2}: pairs win 1+0.5 (0.5 vs 0.5) + 1 + 1 = 3.5 of 4
    assert V.auc([0.5, 0.7, 0.5, 0.2], [True, True, False, False]) == pytest.approx(0.875)


def test_auc_unavailable_cases():
    assert math.isnan(V.auc([0.1, 0.2], [1, 1]))
    assert math.isnan(V.auc([], []))
    assert math.isnan(V.auc([np.nan, np.nan, 0.3], [0, 1, 1]))  # only one class remains


def test_auc_drops_nan_and_parses_label_types():
    scores = [0.1, np.nan, 0.9, 0.4]
    assert V.auc(scores, pd.array([False, True, True, pd.NA], dtype="boolean")) == 1.0
    assert V.auc(scores, ["False", "True", "True", "nonsense"]) == 1.0


def test_parse_bool_dtypes():
    got = V.parse_bool(pd.Series(["True", " false ", "1", "0", "yes", "x", None, 1.0, np.nan, True]))
    assert [bool(v) for v in got.iloc[[0, 1, 2, 3, 4, 7, 9]]] == [True, False, True, False, True, True, True]
    assert got.isna().tolist() == [False, False, False, False, False, True, True, False, True, False]
    assert str(got.dtype) == "boolean"


def _summary():
    return pd.DataFrame({
        "gameId": [1] * 6, "playId": range(6), "season": 2021, "week": 1,
        "possessionTeam": "AAA", "defensiveTeam": "BBB",
        "passResult": ["C", "S", "I", "C", "C", "I"],
        "pressure": ["True", "True", "False", "False", "True", "False"],
        "validation_eligible": ["True", "True", "True", "True", "False", "True"],
        "exclusion_reasons": ["", "", "", "", "missing_snap;missing_terminal", ""],
        "score_any": [0.9, 0.8, 0.2, 0.3, 0.5, 0.4],
        "score_outside": [0.7, 0.6, 0.1, 0.2, 0.5, np.nan],
    })


def test_cohort_same_rows_for_both_features():
    s = V.normalize_summary(_summary())
    rows, info = V.cohort(s)
    assert list(rows["playId"]) == [0, 1, 2, 3]  # ineligible 4 and NaN-outside 5 dropped from both
    assert info["dropped_missing_score"] == 1
    r = V.compare(s)
    assert r["n"] == 4 and r["n_pressure"] == 2 and r["auc_any"] == 1.0 and r["auc_outside"] == 1.0


def test_sack_sensitivity_and_exclusions():
    s = V.normalize_summary(_summary())
    r = V.compare(s, exclude_sacks=True)
    assert r["n"] == 3 and r["n_pressure"] == 1
    counts = dict(V.exclusion_counts(s).itertuples(index=False))
    assert counts == {"missing_snap": 1, "missing_terminal": 1}
    assert V.split_reasons("a|b, c") == ["a", "b", "c"] and V.split_reasons(np.nan) == []


def test_csv_round_trip_parses_booleans(tmp_path):
    path = tmp_path / "play_summary.csv"
    _summary().to_csv(path, index=False)
    s = V.normalize_summary(pd.read_csv(path))
    assert str(s["pressure"].dtype) == "boolean"
    assert V.scope(s) == {"games": 1, "plays": 6, "eligible": 5, "weeks": [1], "seasons": [2021]}
