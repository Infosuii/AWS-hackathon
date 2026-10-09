"""App wiring tests. Synthetic fixtures are for crash/flow checks only."""
import importlib.util
import os
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

import app
from rush_threat import validation as V

ROOT = Path(__file__).resolve().parents[1]
APP = str(ROOT / "app.py")
REAL_DATA = os.environ.get("RUSH_DATA_DIR")
HAS_MODULES = all(importlib.util.find_spec(m) for m in ("rush_threat.data", "rush_threat.figure"))


def _summary():
    return pd.DataFrame({
        "gameId": [2021090900, 2021090900, 2021091200], "playId": [97, 137, 55], "season": 2021,
        "week": 1, "playDescription": "synthetic", "possessionTeam": ["TB", "TB", "BUF"],
        "defensiveTeam": ["DAL", "DAL", "PIT"], "passResult": ["C", "S", "I"], "down": 1, "yardsToGo": 10,
        "pressure": [True, True, False], "validation_eligible": [True, True, True],
        "exclusion_reasons": "", "score_any": [0.3, 0.2, 0.1], "score_outside": [0.2, 0.1, 0.0],
    })


def test_filter_and_default_fallback():
    s = V.normalize_summary(_summary())
    assert app.default_index(app.filter_plays(s, "All", "All", [])) == (0, True)
    filtered = app.filter_plays(s, "BUF", "All", [])
    assert app.default_index(filtered) == (0, False) and len(filtered) == 1
    assert app.filter_plays(s, "All", "No", ["C"]).empty


def test_app_without_artifacts_stops_cleanly(tmp_path, monkeypatch):
    monkeypatch.setenv("RUSH_ARTIFACT_DIR", str(tmp_path))
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    assert any("precompute.py" in e.value for e in at.error)


def test_app_validation_without_tracking(tmp_path, monkeypatch):
    _summary().to_csv(tmp_path / "play_summary.csv", index=False)
    monkeypatch.setenv("RUSH_ARTIFACT_DIR", str(tmp_path))
    monkeypatch.setenv("RUSH_DATA_DIR", str(tmp_path / "missing"))
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    assert any("Replay unavailable" in w.value for w in at.warning)
    assert any("Partial data" in w.value for w in at.warning)


@pytest.mark.skipif(not (HAS_MODULES and REAL_DATA), reason="needs teammate modules and RUSH_DATA_DIR")
def test_real_play_97_bundle_and_figure():
    from rush_threat.data import build_play_bundle, load_context, load_game_tracking
    from rush_threat.figure import build_figure
    bundle = build_play_bundle(load_game_tracking(REAL_DATA, 2021090900), load_context(REAL_DATA),
                               2021090900, 97, 120.0)
    m = bundle["metadata"]
    assert (m["rushers"], m["snap_frame"], m["terminal_frame"], m["validation_end_frame"]) == (5, 6, 38, 31)
    assert len(build_figure(bundle).frames) > 0


@pytest.mark.skipif(not (HAS_MODULES and REAL_DATA and os.environ.get("RUSH_ARTIFACT_DIR")),
                    reason="needs teammate modules, RUSH_DATA_DIR and real RUSH_ARTIFACT_DIR")
def test_real_app_run():
    at = AppTest.from_file(APP, default_timeout=120).run()
    assert not at.exception and not at.error
