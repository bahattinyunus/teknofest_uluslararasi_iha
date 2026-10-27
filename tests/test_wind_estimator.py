"""
Unit tests for Real-Time Wind Estimator Subsystem
"""
import pytest
from src.navigation.wind_estimator import WindEstimator


def test_wind_estimator_zero_wind():
    estimator = WindEstimator(filter_alpha=0.5)
    # Heading North (0 deg), Airspeed 10 m/s, Ground speed 10 m/s North
    wind = estimator.update(ground_speed_n=10.0, ground_speed_e=0.0, heading_deg=0.0, true_airspeed_mps=10.0)

    assert pytest.approx(wind.speed_mps, abs=0.2) == 0.0
    assert pytest.approx(wind.wind_x_mps, abs=0.2) == 0.0
    assert pytest.approx(wind.wind_y_mps, abs=0.2) == 0.0


def test_wind_estimator_direct_headwind():
    estimator = WindEstimator(filter_alpha=0.5)
    # Heading North (0 deg), Airspeed 12 m/s, but Ground speed only 8 m/s North (4 m/s headwind)
    wind = estimator.update(ground_speed_n=8.0, ground_speed_e=0.0, heading_deg=0.0, true_airspeed_mps=12.0)

    # Wind is blowing from North to South (wind_n = -4)
    assert pytest.approx(wind.speed_mps, abs=0.3) == 4.0
    assert wind.wind_y_mps < 0.0


def test_wind_estimator_crosswind():
    estimator = WindEstimator(filter_alpha=0.5)
    # Heading North (0 deg), Airspeed 10 m/s, Ground speed (10 N, 5 E) -> 5 m/s East crosswind
    wind = estimator.update(ground_speed_n=10.0, ground_speed_e=5.0, heading_deg=0.0, true_airspeed_mps=10.0)

    assert pytest.approx(wind.wind_x_mps, abs=0.3) == 5.0
    assert abs(wind.crosswind_mps) > 4.0


def test_wind_estimator_reset():
    estimator = WindEstimator()
    estimator.update(ground_speed_n=10.0, ground_speed_e=5.0, heading_deg=0.0)
    assert estimator.initialized is True

    estimator.reset()
    assert estimator.initialized is False
    assert estimator.sample_count == 0
