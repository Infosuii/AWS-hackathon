"""Dataset-free replay tests. The development example is explicitly synthetic."""

import numpy as np
import pandas as pd
import pytest

from rush_threat.figure import build_figure, select_alert


@pytest.fixture
def synthetic_bundle():
    """Small exact-contract bundle, including roles, NaNs, and missing rows."""
    players, threats = [], []
    for frame in (6, 7, 8):
        now = (frame - 6) / 10
        for nfl_id, role, jersey, x, y in (
            (1, "qb", 12, 40, 26), (2, "rusher", 90, 44 - now * 2, 26),
            (3, "rusher", 91, 40, 30 - now), (4, "blocker", 70, 42, 27),
            (5, "route", 11, 49 + now, 35), (6, "coverage", 21, 49, 36),
            (7, "other", 55, 45, 21), (None, "ball", None, 40, 26.5),
        ):
            if frame == 7 and nfl_id == 3:
                continue
            players.append(dict(frameId=frame, nflId=nfl_id, x=x, y=y,
                                o=90 if frame != 8 else np.nan,
                                jerseyNumber=jersey, displayName=f"Synthetic {role} {nfl_id}",
                                role=role, time_from_snap=now))
            if role == "rusher":
                distance = np.hypot(x - 40, y - 26)
                threats.append(dict(frameId=frame, nflId=nfl_id,
                    displayName=f"Synthetic rusher {nfl_id}", jerseyNumber=jersey,
                    x=x, y=y, qb_x=40, qb_y=26, qb_o=90 if frame != 8 else np.nan,
                    time_from_snap=now, distance=distance,
                    closing_speed=np.nan if frame == 6 else (2 if nfl_id == 2 else -1),
                    bearing_deg=np.degrees(np.arctan2(x - 40, y - 26)) % 360,
                    outside_sector=pd.NA if frame == 8 else nfl_id == 3,
                    in_validation=frame < 8))
    return dict(players=pd.DataFrame(players), threats=pd.DataFrame(threats), metadata=dict(
        gameId=0, playId=97, playDescription="SYNTHETIC development fixture · no real play data",
        possessionTeam="SYN", defensiveTeam="DEV", passResult="C", down=1,
        yardsToGo=10, offenseFormation="SHOTGUN", dropBackType="TRADITIONAL",
        pff_playAction=False, blockers=1, rushers=2, routes=1, pressure=False,
        snap_frame=6, terminal_frame=8, terminal_event="synthetic_release",
        validation_end_frame=7, sector_deg=120.0, validation_eligible=False,
        exclusion_reasons=["synthetic"], replay_available=True, replay_note="Synthetic only"))


def _update(fig, frame_index, key):
    frame = fig.frames[frame_index]
    target = fig.layout.meta["dynamic_traces"][key]
    return frame.data[list(frame.traces).index(target)]


def _annotation(frame):
    return " ".join(annotation.text for annotation in frame.layout.annotations)


def test_alert_fastest_within_radius():
    threats = pd.DataFrame(dict(nflId=[3, 2, 1, 4], distance=[5, 4, 5.01, 2],
                                closing_speed=[3, 4, 100, -3], outside_sector=[False, True, True, False]))
    alert = select_alert(threats)
    assert isinstance(alert, pd.Series)
    assert alert.nflId == 2
    assert bool(alert.outside_sector)  # Sector is descriptive, never a gate.
    assert list(alert.index) == list(threats.columns)
    assert select_alert(threats, radius_yd=3) is None


@pytest.mark.parametrize("speed", [0, -1, np.nan, np.inf, -np.inf, pd.NA])
def test_alert_rejects_invalid_speed(speed):
    assert select_alert(pd.DataFrame([dict(nflId=1, distance=2, closing_speed=speed)])) is None


@pytest.mark.parametrize("distance", [-1, np.nan, np.inf, pd.NA, 5.01])
def test_alert_rejects_invalid_distance(distance):
    assert select_alert(pd.DataFrame([dict(nflId=1, distance=distance, closing_speed=2)])) is None


def test_alert_ties_use_numeric_id():
    threats = pd.DataFrame(dict(nflId=[10, 2, 3], distance=[4, 5, 3], closing_speed=[2, 2, 2]))
    for seed in range(5):
        assert select_alert(threats.sample(frac=1, random_state=seed)).nflId == 2


def test_empty_alert():
    assert select_alert(pd.DataFrame()) is None


def test_frame_count_and_stable_mapping(synthetic_bundle):
    fig = build_figure(synthetic_bundle)
    assert len(fig.frames) == synthetic_bundle["players"].frameId.nunique() == 3
    dynamic = fig.layout.meta["dynamic_traces"]
    static = set(range(len(fig.data))) - set(dynamic.values())
    assert static
    for frame in fig.frames:
        assert list(frame.traces) == list(dynamic.values())
        assert len(frame.data) == len(dynamic)
        assert not static.intersection(frame.traces)
    assert len(fig.layout.sliders[0].steps) == 3
    assert "SYNTHETIC" in fig.layout.title.text
    assert fig.layout.yaxis.scaleanchor == "x"
    assert fig.layout.yaxis.scaleratio == 1
    assert fig.layout.xaxis2.range == fig.layout.xaxis3.range
    assert fig.layout.xaxis3.matches == "x2"


@pytest.mark.parametrize("orientation,delta", [(0, (0, 7)), (90, (7, 0)), (180, (0, -7)), (270, (-7, 0))])
def test_wedge_sin_cos_convention(synthetic_bundle, orientation, delta):
    synthetic_bundle["players"].loc[synthetic_bundle["players"].role == "qb", "o"] = orientation
    fig = build_figure(synthetic_bundle)
    wedge = _update(fig, 0, "wedge")
    np.testing.assert_allclose([wedge.x[31], wedge.y[31]], [40 + delta[0], 26 + delta[1]], atol=1e-10)
    angles = [orientation - 60, orientation + 60]
    np.testing.assert_allclose([wedge.x[1], wedge.x[-2]], 40 + 7 * np.sin(np.deg2rad(angles)))
    assert fig.data[fig.layout.meta["dynamic_traces"]["wedge"]].fill == "toself"


def test_sector_angle_reads_metadata(synthetic_bundle):
    synthetic_bundle["metadata"]["sector_deg"] = 60.0
    wedge = _update(build_figure(synthetic_bundle), 0, "wedge")
    assert wedge.x[1] == pytest.approx(40 + 7 * np.sin(np.deg2rad(60)))


def test_cursor_and_alert_updates(synthetic_bundle):
    fig = build_figure(synthetic_bundle)
    for index, time in enumerate((0, 0.1, 0.2)):
        for key in ("distance_cursor", "speed_cursor"):
            assert list(_update(fig, index, key).x) == [time, time]
    assert list(_update(fig, 0, "alert").x) == []
    assert list(_update(fig, 1, "alert").x) == [40, 43.8]
    assert "No qualifying alert" in _annotation(fig.frames[0])
    assert "Inside assumed forward sector" in _annotation(fig.frames[1])
    assert "Unknown assumed forward sector" in _annotation(fig.frames[2])
    for step in fig.layout.sliders[0].steps:
        assert step.args[1]["transition"]["duration"] == 0
        assert step.args[1]["frame"]["redraw"]
    assert fig.layout.updatemenus[0].buttons[0].args[1]["transition"]["duration"] == 0


def test_missing_rows_are_cleared_and_timeline_gaps(synthetic_bundle):
    fig = build_figure(synthetic_bundle)
    key = next(key for key in fig.layout.meta["dynamic_traces"] if key.startswith("rusher:3"))
    assert len(_update(fig, 0, key).x) == 1
    assert len(_update(fig, 1, key).x) == 0
    assert len(_update(fig, 2, key).x) == 1
    timeline = [trace for trace in fig.data if trace.name == "Rusher #91" and trace.xaxis == "x2"][0]
    assert pd.isna(timeline.y[1])
    assert timeline.connectgaps is False


def test_missing_orientation_and_no_alert_paths(synthetic_bundle):
    synthetic_bundle["players"].loc[synthetic_bundle["players"].role == "qb", "o"] = np.nan
    synthetic_bundle["threats"]["closing_speed"] = np.nan
    fig = build_figure(synthetic_bundle)
    assert not any(trace.name == "Peak qualifying alert" for trace in fig.data)
    for index, frame in enumerate(fig.frames):
        assert len(_update(fig, index, "wedge").x) == 0
        assert len(_update(fig, index, "alert").x) == 0
        assert "sector unknown" in _annotation(frame)
        assert "No qualifying alert" in _annotation(frame)


def test_empty_replay(synthetic_bundle):
    synthetic_bundle["players"] = synthetic_bundle["players"].iloc[:0]
    synthetic_bundle["threats"] = synthetic_bundle["threats"].iloc[:0]
    synthetic_bundle["metadata"].update(replay_available=False, replay_note="Missing QB", terminal_frame=None)
    fig = build_figure(synthetic_bundle)
    assert len(fig.frames) == 0
    assert any(annotation.text == "Missing QB" for annotation in fig.layout.annotations)


def test_peak_marker_matches_actual_qualifying_alert(synthetic_bundle):
    fig = build_figure(synthetic_bundle)
    peak = [trace for trace in fig.data if trace.name == "Peak qualifying alert"]
    assert len(peak) == 2
    assert list(peak[0].x) == [0.1]  # Earliest equal peak; no fake first-frame peak.
    assert list(peak[1].y) == [2]


def test_field_and_timeline_colors_agree(synthetic_bundle):
    fig = build_figure(synthetic_bundle)
    for key, index in fig.layout.meta["dynamic_traces"].items():
        if not key.startswith("rusher:"):
            continue
        trace = fig.data[index]
        timelines = [curve for curve in fig.data if curve.legendgroup == trace.legendgroup
                     and curve.mode == "lines"]
        assert len(timelines) == 2
        assert all(curve.line.color == trace.marker.color for curve in timelines)
