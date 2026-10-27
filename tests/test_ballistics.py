"""
Unit tests for Ballistics and Trajectory Prediction Subsystem
"""
import pytest
import numpy as np
from src.navigation.ballistics import BallisticsCalculator, DropPrediction


def test_freefall_time_zero_altitude():
    calc = BallisticsCalculator()
    t = calc.calculate_freefall_time(0.0)
    assert t == 0.0


def test_freefall_time_analytical():
    calc = BallisticsCalculator()
    # h = 0.5 * g * t^2 -> t = sqrt(2 * h / g)
    h = 20.0
    expected_t = np.sqrt(2.0 * h / 9.80665)
    calc_t = calc.calculate_freefall_time(h)
    assert pytest.approx(expected_t, rel=1e-3) == calc_t


def test_rk4_trajectory_simulation():
    calc = BallisticsCalculator()
    altitude = 25.0
    vx = 5.0
    vy = 0.0
    t, dx, dy = calc.simulate_trajectory_rk4(altitude_m=altitude, vx=vx, vy=vy)

    assert t > 0.0
    assert dx > 0.0  # Horizontal displacement in x direction
    assert pytest.approx(dy, abs=0.01) == 0.0


def test_rk4_with_crosswind():
    calc = BallisticsCalculator()
    altitude = 20.0
    vx = 5.0
    vy = 0.0
    wind_y = 3.0  # Crosswind
    t, dx, dy = calc.simulate_trajectory_rk4(altitude_m=altitude, vx=vx, vy=vy, wind_x=0.0, wind_y=wind_y)

    assert t > 0.0
    assert dx > 0.0
    assert dy > 0.0  # Wind drifted payload in +y


def test_predict_impact_within_tolerance():
    calc = BallisticsCalculator()
    # If target is placed exactly at predicted displacement, miss distance should be ~0
    alt = 30.0
    vx = 4.0
    t, dx, dy = calc.simulate_trajectory_rk4(altitude_m=alt, vx=vx, vy=0.0)

    prediction = calc.predict_impact(
        uav_pos_xy=(0.0, 0.0),
        target_pos_xy=(dx, dy),
        velocity_xy=(vx, 0.0),
        altitude_m=alt
    )

    assert prediction.is_within_tolerance is True
    assert prediction.predicted_miss_distance_m < 0.1
