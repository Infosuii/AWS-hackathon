"""Data-engine tests: synthetic fixtures (run anywhere) + real play 97 (skips without data)."""

import numpy as np
import pandas as pd
import pytest

from rush_threat import data as rd

G, QB, RA, RB, CB = 1, 10, 20, 30, 40


def _tracking(pid, qb_o=90.0, b_off=(0.0, 5.0), snap=True):
    """QB drifts +y 0.25/frame; rusher A closes head-on 1 yd/s (frame 6 missing, burst at
    terminal frame 9); rusher B moves with the QB's velocity (constant distance)."""
    rows = []
    for f in range(1, 11):
        ev = {2: "ball_snap" if snap else None, 9: "pass_forward"}.get(f)
        qy = 25.0 + 0.25 * f
        rows.append((pid, QB, f, 50.0, qy, qb_o, 12, ev))
        if f != 6:
            ax = 55.0 - 0.1 * min(f, 8) - (0.5 + 0.1 * (f - 9) if f >= 9 else 0.0)
            rows.append((pid, RA, f, ax, qy, 270.0, 90, ev))
        rows.append((pid, RB, f, 50.0 + b_off[0], qy + b_off[1], 180.0, 94, ev))
        rows.append((pid, pd.NA, f, 52.0, 25.0, np.nan, pd.NA, ev))  # football
    df = pd.DataFrame(rows, columns=["playId", "nflId", "frameId", "x", "y", "o",
                                     "jerseyNumber", "event"])
    df.insert(0, "gameId", G)
    return df.astype({"nflId": "Int64", "jerseyNumber": "Int64", "event": "string"})


def _context(pids, flags):
    plays = pd.DataFrame({"gameId": G, "playId": pids, "playDescription": "synthetic",
                          "possessionTeam": "AAA", "defensiveTeam": "BBB", "passResult": "C",
                          "down": 1, "yardsToGo": 10, "offenseFormation": "SHOTGUN",
                          "dropBackType": "TRADITIONAL", "pff_playAction": 0})
    sc = []
    for pid in pids:
        hit, hurry, sack = flags[pid]
        sc += [(G, pid, QB, "Pass", np.nan, np.nan, np.nan),
               (G, pid, RA, " pass  RUSH ", 0, hurry, 0),  # normalisation
               (G, pid, RB, "Pass Rush", 0, 0, 0),
               (G, pid, CB, "Coverage", hit, 0, sack)]
    scouting = pd.DataFrame(sc, columns=["gameId", "playId", "nflId", "pff_role", "pff_hit",
                                         "pff_hurry", "pff_sack"])
    scouting["pff_role_norm"] = scouting["pff_role"].map(rd.normalize_role)
    scouting["role"] = scouting["pff_role_norm"].map(rd.ROLE_MAP).fillna("other")
    scouting["nflId"] = scouting["nflId"].astype("Int64")
    players = pd.DataFrame({"nflId": pd.array([QB, RA, RB, CB], dtype="Int64"),
                            "displayName": ["Q B", "Rush A", "Rush B", "Cover C"]})
    games = pd.DataFrame({"gameId": [G], "season": [2021], "week": [1]})
    return {"games": games, "plays": plays, "players": players, "scouting": scouting}


@pytest.fixture
def synthetic():
    trk = pd.concat([_tracking(1), _tracking(2, qb_o=np.nan), _tracking(3, snap=False),
                     _tracking(4, b_off=(4.0, 1.0))], ignore_index=True)
    ctx = _context([1, 2, 3, 4], {1: (0, 0, 1), 2: (0, 0, 0), 3: (0, 1, 0), 4: (0, 0, 0)})
    return trk, ctx


def test_bundle_schema_and_math(synthetic):
    trk, ctx = synthetic
    b = rd.build_play_bundle(trk, ctx, G, 1)
    th, pl, m = b["threats"], b["players"], b["metadata"]
    assert list(th.columns) == rd.THREAT_COLUMNS and list(pl.columns) == rd.PLAYER_COLUMNS
    assert set(m) == set(rd.METADATA_KEYS)
    assert not th.duplicated(["frameId", "nflId"]).any()
    assert (m["snap_frame"], m["terminal_frame"], m["validation_end_frame"]) == (2, 9, 8)
    assert m["rushers"] == 2 and m["validation_eligible"] and m["exclusion_reasons"] == []
    assert set(pl["role"]) == {"qb", "rusher", "ball"} and pl["frameId"].between(2, 9).all()
    a = th[th["nflId"] == RA].set_index("frameId")
    # head-on 1 yd/s including the frame-6 gap (0.2 yd over 0.2 s), QB motion included
    np.testing.assert_allclose(a.loc[[2, 3, 4, 5, 7], "closing_speed"], 1.0, atol=1e-9)
    assert a.loc[9, "closing_speed"] == pytest.approx(3.0)  # mean(1, 5) at window edge
    bb = th[th["nflId"] == RB]
    np.testing.assert_allclose(bb["closing_speed"], 0.0, atol=1e-9)  # equal velocity, no crossover
    assert a["outside_sector"].eq(False).all() and bb["outside_sector"].eq(True).all()
    assert th.loc[th["in_validation"], "frameId"].max() == 8
    assert th["time_from_snap"].min() == 0.0


def test_sector_angle_changes_bundle_only(synthetic):
    trk, ctx = synthetic
    b = rd.build_play_bundle(trk, ctx, G, 4, sector_deg=20.0)
    assert b["metadata"]["sector_deg"] == 20.0
    assert b["threats"].loc[b["threats"]["nflId"] == RB, "outside_sector"].eq(True).all()


def test_missing_orientation_is_unknown_and_excluded(synthetic):
    trk, ctx = synthetic
    b = rd.build_play_bundle(trk, ctx, G, 2)
    assert b["threats"]["outside_sector"].isna().all()
    assert "missing_orientation" in b["metadata"]["exclusion_reasons"]


def test_missing_snap_gives_flagged_fallback_replay(synthetic):
    trk, ctx = synthetic
    m = rd.build_play_bundle(trk, ctx, G, 3)["metadata"]
    assert m["replay_available"] and not m["validation_eligible"]
    assert m["snap_frame"] is None and m["validation_end_frame"] is None
    assert {"missing_snap", "missing_terminal"} <= set(m["exclusion_reasons"])


def test_missing_qb_is_unavailable_not_a_crash(synthetic):
    trk, ctx = synthetic
    m = rd.build_play_bundle(trk[trk["nflId"] != QB], ctx, G, 1)["metadata"]
    assert not m["replay_available"] and "qb_untracked" in m["exclusion_reasons"]
    assert m["replay_note"]


def test_summaries_rules(synthetic):
    trk, ctx = synthetic
    raw = rd.build_game_summaries(trk, ctx)
    assert list(raw.columns) == rd.SUMMARY_COLUMNS
    s = raw.set_index("playId")
    assert not s.index.duplicated().any() and len(s) == 4
    # play-level OR pressure, including a coverage defender's sack
    assert s["pressure"].tolist() == [True, False, True, False]
    assert s["validation_eligible"].tolist() == [True, False, False, True]
    # minima use the capped validation window (frame 8), peaks use the replay (frame 9)
    assert s.loc[1, "d_min_any"] == pytest.approx(4.2)
    assert (s.loc[1, "peak_frame"], s.loc[1, "peak_close_5yd"]) == (9, pytest.approx(3.0))
    assert s.loc[1, "peak_rusher_id"] == RA
    assert s.loc[1, "d_min_outside"] == pytest.approx(5.0)
    assert s.loc[1, "score_outside"] == pytest.approx(1 / 6)
    # zero only for valid orientation with no outside observations
    assert s.loc[4, "score_outside"] == 0.0 and np.isnan(s.loc[4, "d_min_outside"])
    assert np.isnan(s.loc[2, "score_outside"])
    assert "missing_orientation" in s.loc[2, "exclusion_reasons"]
    assert np.isnan(s.loc[3, "peak_close_5yd"]) and pd.isna(s.loc[3, "validation_end_frame"])


# ------------------------------------------------------------------ real data

def _data_dir():
    try:
        return rd.resolve_data_dir(None)
    except FileNotFoundError:
        return None


DATA = _data_dir()
needs_data = pytest.mark.skipif(DATA is None, reason="local NFL dataset not found "
                                "(set RUSH_DATA_DIR)")


@needs_data
def test_real_play_97_anchors():
    ctx = rd.load_context(DATA)
    trk = rd.load_game_tracking(DATA, 2021090900)
    b = rd.build_play_bundle(trk, ctx, 2021090900, 97)
    m = b["metadata"]
    assert (m["rushers"], m["pressure"], m["snap_frame"], m["terminal_frame"],
            m["terminal_event"], m["validation_end_frame"]) == (
        5, True, 6, 38, "autoevent_passforward", 31)
    assert m["validation_eligible"] and m["replay_available"]
    th = b["threats"]
    assert th["nflId"].nunique() == 5 and not th.duplicated(["frameId", "nflId"]).any()
    assert th.loc[th["in_validation"], "frameId"].agg(["min", "max"]).tolist() == [6, 31]
    assert (b["players"]["role"] == "ball").any()
