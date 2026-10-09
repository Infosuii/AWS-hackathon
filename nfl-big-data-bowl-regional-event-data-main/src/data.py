"""Data loading, preprocessing, and vector math for Rush Threat Explorer.

Owner module for vector math & preprocessing. All functions return DataFrames
that follow the schema contract in ``TRACKING_COLUMNS`` (plus any derived
columns they document).

Source files (under ``DATA_DIR``):
    tracking/tracking_<gameId>.csv:
        gameId, playId, nflId, frameId, time, jerseyNumber, team,
        playDirection, x, y, s, a, dis, o, dir, event
    pffScoutingData.csv:
        gameId, playId, nflId, pff_role, pff_positionLinedUp, pff_hit,
        pff_hurry, pff_sack, pff_beatenByDefender, pff_hitAllowed,
        pff_hurryAllowed, pff_sackAllowed, pff_nflIdBlockedPlayer,
        pff_blockType, pff_backFieldBlock
    players.csv:
        nflId, height, weight, birthDate, collegeName, officialPosition,
        displayName

Coordinate conventions (NGS tracking):
    x: 0-120 yards along the long axis; y: 0-53.3 yards along the short axis.
    s: speed in yards/second.
    o: player orientation in degrees, 0-360.
    dir: angle of player motion in degrees, 0-360.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

# Project root is the parent of the ``src`` package directory.
DATA_DIR: Path = Path(__file__).resolve().parent.parent / "data"

TRACKING_COLUMNS: list[str] = [
    "gameId",
    "playId",
    "frameId",
    "nflId",
    "x",
    "y",
    "s",
    "o",
    "dir",
    "club",
    "displayName",
    "pff_role",
]


def load_play_tracking(game_id: int, play_id: int) -> pd.DataFrame:
    """Load tracking data for a single play, conforming to the schema contract.

    Intended implementation:
        1. Read ``DATA_DIR / "tracking" / f"tracking_{game_id}.csv"`` and
           filter rows to ``playId == play_id``.
        2. Rename the raw ``team`` column to ``club`` (raw tracking files use
           ``team``; ball rows have ``team == "football"`` and ``nflId`` NA).
        3. Left-join ``pff_role`` from ``pffScoutingData.csv`` on
           ``['gameId', 'playId', 'nflId']``. Roles include ``"Pass"`` (QB),
           ``"Pass rush"``, ``"Pass block"``, ``"Pass route"``, ``"Coverage"``.
        4. Left-join ``displayName`` from ``players.csv`` on ``nflId``.
        5. Select ``TRACKING_COLUMNS`` and sort by ``frameId``, ``nflId``.

    Args:
        game_id: Game identifier (e.g. ``2021090900``).
        play_id: Play identifier within the game (not unique across games).

    Returns:
        DataFrame with columns ``TRACKING_COLUMNS``, one row per
        (frameId, nflId) for the play. Placeholder returns an empty DataFrame
        with those columns.
    """
    # TODO: Implement CSV loading, team -> club rename, and pff_role /
    # displayName joins as described above.
    return pd.DataFrame(columns=TRACKING_COLUMNS)


def compute_relative_closing_speed(df_play: pd.DataFrame) -> pd.DataFrame:
    """Compute each pass rusher's closing speed on the QB, per frame.

    Closing speed is the rate at which the distance between a pass rusher
    (``pff_role == "Pass rush"``) and the QB (``pff_role == "Pass"``)
    decreases. Positive values mean the rusher is closing in.

    Intended math (per frame):
        - Velocity vector from speed and direction. NGS ``dir`` is measured
          clockwise from the +y axis, so:
              vx = s * sin(radians(dir)),  vy = s * cos(radians(dir))
        - Relative position: r = p_qb - p_rusher, with p = (x, y).
        - Relative velocity: v_rel = v_rusher - v_qb.
        - closing_speed = dot(v_rel, r) / ||r||  (yards/second), i.e. the
          negative time derivative of ||r||.
        - Non-rusher rows (and frames with no QB) get NaN.

    Args:
        df_play: Single-play tracking DataFrame following ``TRACKING_COLUMNS``.

    Returns:
        Copy of ``df_play`` with an added float column ``closing_speed``.
        Placeholder fills it with NaN.
    """
    # TODO: Implement vectorized closing-speed calculation described above.
    df = df_play.copy()
    df["closing_speed"] = pd.Series(np.nan, index=df.index, dtype="float64")
    return df


def check_forward_sector(
    df_play: pd.DataFrame, sector_angle: float = 120
) -> pd.DataFrame:
    """Flag frames where the QB lies inside a pass rusher's forward sector.

    The forward sector is a wedge centered on the rusher's heading, spanning
    ``+/- sector_angle / 2`` degrees. Heading uses ``dir`` (motion) or ``o``
    (orientation); ``dir`` is preferred while the rusher is moving and ``o``
    can be used as a fallback at low speed.

    Intended math (per frame, per rusher):
        - Bearing to QB, in NGS convention (clockwise from +y):
              bearing = degrees(arctan2(x_qb - x_rusher, y_qb - y_rusher)) % 360
        - Smallest signed angle difference:
              delta = (bearing - heading + 180) % 360 - 180
        - in_forward_sector = |delta| <= sector_angle / 2
        - Non-rusher rows (and frames with no QB) get False.

    Args:
        df_play: Single-play tracking DataFrame following ``TRACKING_COLUMNS``.
        sector_angle: Full width of the forward wedge in degrees.

    Returns:
        Copy of ``df_play`` with an added bool column ``in_forward_sector``.
        Placeholder fills it with False.
    """
    # TODO: Implement bearing / heading comparison described above.
    df = df_play.copy()
    df["in_forward_sector"] = pd.Series(False, index=df.index, dtype="bool")
    return df
