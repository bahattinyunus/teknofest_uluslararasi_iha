"""
Unit tests for Statistical Drop Envelope & Probability Engine
"""
import pytest
from src.navigation.drop_envelope import DropEnvelopeCalculator, DropEnvelopeStatus


def test_drop_envelope_zero_miss_high_probability():
    calc = DropEnvelopeCalculator(scoring_radius_m=10.0, min_probability_threshold_pct=80.0)
    # Impact point matches target exactly at (10.0, 10.0)
    status = calc.evaluate_envelope(
        impact_xy=(10.0, 10.0),
        target_xy=(10.0, 10.0),
        time_of_flight_s=2.0,
        ground_speed_mps=4.0,
        altitude_m=20.0
    )

    assert status.miss_distance_m == 0.0
    assert status.hit_probability_pct > 90.0
    assert status.is_authorized is True
    assert status.recommendation == "RELEASE_AUTHORIZED"


def test_drop_envelope_dispersion_scales_with_altitude_and_speed():
    calc = DropEnvelopeCalculator()
    # Higher speed and longer time of flight -> wider dispersion
    maj1, min1 = calc.calculate_dispersion(time_of_flight_s=1.0, ground_speed_mps=2.0, altitude_m=10.0)
    maj2, min2 = calc.calculate_dispersion(time_of_flight_s=3.0, ground_speed_mps=8.0, altitude_m=40.0)

    assert maj2 > maj1
    assert min2 >= min1


def test_drop_envelope_large_miss_triggers_abort():
    calc = DropEnvelopeCalculator(scoring_radius_m=10.0)
    # Impact point is 25m away from target
    status = calc.evaluate_envelope(
        impact_xy=(35.0, 10.0),
        target_xy=(10.0, 10.0),
        time_of_flight_s=2.5,
        ground_speed_mps=6.0,
        altitude_m=25.0
    )

    assert status.miss_distance_m == 25.0
    assert status.hit_probability_pct < 20.0
    assert status.is_authorized is False
    assert status.recommendation == "ABORT_GO_AROUND"
