"""Pure geometry helpers for Rush Threat Explorer (SHARED_CONTRACT v1).

Angle convention: 0 degrees points +y, 90 degrees points +x, increasing clockwise.
unit_vec(angle) = (sin(angle), cos(angle)); bearing = degrees(atan2(dx, dy)) mod 360.

All functions are pure (no I/O, no shared state) and accept scalars or array-likes.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

FPS = 10.0
# Separation at or below this many yards is treated as zero: the bearing is undefined.
ZERO_DISTANCE_EPS = 1e-9


def unit_vec(angle_deg):
    """Return (ux, uy) for an angle in the contract convention (0 = +y, 90 = +x)."""
    a = np.radians(np.asarray(angle_deg, dtype=float))
    return np.sin(a), np.cos(a)


def distance(x1, y1, x2, y2):
    """Euclidean distance in yards between (x1, y1) and (x2, y2)."""
    dx = np.asarray(x2, dtype=float) - np.asarray(x1, dtype=float)
    dy = np.asarray(y2, dtype=float) - np.asarray(y1, dtype=float)
    return np.hypot(dx, dy)


def bearing_deg(from_x, from_y, to_x, to_y, eps: float = ZERO_DISTANCE_EPS):
    """Bearing from (from_x, from_y) to (to_x, to_y) in [0, 360).

    NaN when the separation is <= eps (zero-distance bearing is undefined) or
    when any coordinate is missing.
    """
    dx = np.asarray(to_x, dtype=float) - np.asarray(from_x, dtype=float)
    dy = np.asarray(to_y, dtype=float) - np.asarray(from_y, dtype=float)
    with np.errstate(invalid="ignore"):
        b = np.mod(np.degrees(np.arctan2(dx, dy)), 360.0)
        b = np.where(b >= 360.0, b - 360.0, b)  # guard float rounding to exactly 360
        undefined = ~(np.hypot(dx, dy) > eps)  # also True for NaN separation
    return np.where(undefined, np.nan, b)


def angular_diff_deg(a, b):
    """Wrapped absolute angular difference in [0, 180]. NaN propagates."""
    with np.errstate(invalid="ignore"):
        d = np.mod(np.asarray(a, dtype=float) - np.asarray(b, dtype=float), 360.0)
        return np.minimum(d, 360.0 - d)


def outside_sector(bearing, orientation, sector_deg: float = 120.0) -> pd.arrays.BooleanArray:
    """Nullable Boolean: True when the bearing is outside the centred forward sector.

    Outside means wrapped difference > sector_deg / 2. Missing orientation or an
    undefined bearing gives <NA> (unknown), never "inside".
    """
    diff = np.atleast_1d(angular_diff_deg(bearing, orientation))
    known = np.isfinite(diff)
    with np.errstate(invalid="ignore"):
        values = np.where(known, diff > (float(sector_deg) / 2.0), False)
    return pd.arrays.BooleanArray(values.astype(bool), ~known)


def closing_speed_raw(dist, frame_id, fps: float = FPS) -> np.ndarray:
    """-delta(distance) / (delta(frameId) / fps) for one ordered entity track.

    The first sample is NaN. Real frame gaps enlarge the denominator. Non-positive
    frame deltas yield NaN rather than an infinite speed.
    """
    d = np.asarray(dist, dtype=float)
    f = np.asarray(frame_id, dtype=float)
    out = np.full(d.shape, np.nan)
    if d.size > 1:
        dt = np.diff(f) / fps
        with np.errstate(divide="ignore", invalid="ignore"):
            v = -np.diff(d) / dt
        v[~(dt > 0)] = np.nan
        out[1:] = v
    return out


def smooth_centered(values, window: int = 3) -> np.ndarray:
    """Centred rolling mean over `window` observations, ignoring NaN (min_periods=1)."""
    s = pd.Series(np.asarray(values, dtype=float))
    return s.rolling(window, center=True, min_periods=1).mean().to_numpy()
