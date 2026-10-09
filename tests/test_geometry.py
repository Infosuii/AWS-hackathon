"""Generic geometry tests (no dataset needed)."""

import numpy as np
import pandas as pd
import pytest

from rush_threat import geometry as geo


def test_unit_vec_convention_zero_is_plus_y_ninety_is_plus_x():
    ux, uy = geo.unit_vec([0.0, 90.0, 180.0, 270.0])
    np.testing.assert_allclose(ux, [0, 1, 0, -1], atol=1e-12)
    np.testing.assert_allclose(uy, [1, 0, -1, 0], atol=1e-12)


def test_bearing_clockwise_from_plus_y_and_wraps_into_0_360():
    b = geo.bearing_deg(0, 0, [0, 1, 0, -1, -1e-3], [1, 0, -1, 0, 1])
    np.testing.assert_allclose(b[:4], [0, 90, 180, 270], atol=1e-9)
    assert 359.9 < b[4] < 360.0  # just west of +y: wraps, never negative


def test_bearing_round_trips_with_unit_vec():
    angles = np.array([0.0, 33.0, 135.0, 225.0, 359.0])
    ux, uy = geo.unit_vec(angles)
    np.testing.assert_allclose(geo.bearing_deg(10, 20, 10 + 4 * ux, 20 + 4 * uy), angles,
                               atol=1e-9)


def test_zero_distance_bearing_is_undefined_not_zero():
    b = geo.bearing_deg([5.0, 5.0], [5.0, 5.0], [5.0, 6.0], [5.0, 5.0])
    assert np.isnan(b[0])
    assert b[1] == pytest.approx(90.0)


def test_angular_difference_wraps_to_0_180():
    np.testing.assert_allclose(geo.angular_diff_deg([350, 10, 0, 90, 270], [10, 350, 180, 270, 90]),
                               [20, 20, 180, 180, 180])


def test_outside_sector_boundary_wrap_and_unknowns():
    # QB faces 350; a 120-degree sector spans 290..50 through north.
    bearing = np.array([50.0, 51.0, 289.0, 290.0, 10.0, np.nan, 100.0])
    orient = np.array([350.0, 350.0, 350.0, 350.0, 350.0, 350.0, np.nan])
    out = geo.outside_sector(bearing, orient, 120.0)
    assert isinstance(out, pd.arrays.BooleanArray)
    assert out[:5].tolist() == [False, True, True, False, False]
    assert out[5] is pd.NA and out[6] is pd.NA  # undefined bearing / missing orientation


def test_sector_angle_is_respected():
    assert geo.outside_sector([40.0], [0.0], 60.0).tolist() == [True]
    assert geo.outside_sector([40.0], [0.0], 120.0).tolist() == [False]


def test_constant_distance_gives_zero_closing_speed():
    v = geo.closing_speed_raw([6.0] * 5, [1, 2, 3, 4, 5])
    assert np.isnan(v[0])
    np.testing.assert_allclose(v[1:], 0.0)


def test_head_on_closing_speed_and_frame_gap_denominator():
    # distance falls 1 yd per frame (10 yd/s); frame 4 is missing -> 2 yd over 0.2 s.
    v = geo.closing_speed_raw([10.0, 9.0, 8.0, 6.0], [1, 2, 3, 5])
    np.testing.assert_allclose(v[1:], [10.0, 10.0, 10.0])


def test_non_positive_frame_delta_is_nan_not_infinite():
    v = geo.closing_speed_raw([10.0, 9.0], [3, 3])
    assert np.isnan(v[1])


def test_centered_three_sample_smoothing_ignores_nan():
    s = geo.smooth_centered([np.nan, 2.0, 4.0, 6.0])
    np.testing.assert_allclose(s, [2.0, 3.0, 4.0, 5.0])
