"""precompute.py tests: exclusion counting anywhere, two-game run with local data."""

import pandas as pd
import pytest

import precompute
from rush_threat import data as rd


def test_exclusion_counts_are_explicit():
    s = pd.DataFrame({"validation_eligible": [True, False, False],
                      "replay_available": [True, True, False],
                      "exclusion_reasons": ["", "missing_snap;missing_terminal", "qb_untracked"]})
    c = precompute.exclusion_counts(s).set_index("reason")["plays"]
    assert (c["ALL_PLAYS"], c["ELIGIBLE"], c["EXCLUDED"], c["REPLAY_UNAVAILABLE"]) == (3, 1, 2, 1)
    assert (c["missing_snap"], c["qb_untracked"], c["missing_orientation"]) == (1, 1, 0)


def _data_dir():
    try:
        return rd.resolve_data_dir(None)
    except FileNotFoundError:
        return None


@pytest.mark.skipif(_data_dir() is None, reason="local NFL dataset not found (set RUSH_DATA_DIR)")
def test_two_game_run(tmp_path):
    code = precompute.run(["--games", "2", "--data-dir", str(_data_dir()),
                           "--output-dir", str(tmp_path), "--format", "csv"])
    assert code == 0
    s = pd.read_csv(tmp_path / "play_summary.csv")
    assert list(s.columns) == rd.SUMMARY_COLUMNS
    assert s["gameId"].nunique() == 2 and not s.duplicated(["gameId", "playId"]).any()
    e = pd.read_csv(tmp_path / "exclusions.csv").set_index("reason")["plays"]
    assert e["ALL_PLAYS"] == len(s) and e["ELIGIBLE"] == int(s["validation_eligible"].sum())
    row = s[(s["gameId"] == 2021090900) & (s["playId"] == 97)].iloc[0]
    assert (row["snap_frame"], row["terminal_frame"], row["validation_end_frame"]) == (6, 38, 31)
    assert bool(row["pressure"]) and bool(row["validation_eligible"])
