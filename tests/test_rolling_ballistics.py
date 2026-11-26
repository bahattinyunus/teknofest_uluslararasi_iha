import pytest
import math
from src.navigation.rolling_ballistics import RestingBallisticsOptimizer, PayloadPhysicalParams


def test_ballistics_free_fall_time_approximation():
    optimizer = RestingBallisticsOptimizer()
    # 30 metre AGL'den serbest düşüş süresi: t ~ sqrt(2 * 30 / 9.81) ~ 2.47 sn
    pred = optimizer.simulate_flight_and_roll(
        release_altitude_agl_m=30.0,
        uav_ground_speed_ms=0.0
    )
    expected_tof = math.sqrt(2.0 * 30.0 / 9.80665)
    assert abs(pred.time_of_flight_s - expected_tof) < 0.25
    assert pred.impact_distance_forward_m < 0.1
    assert pred.roll_distance_m < 0.1


def test_rolling_distance_increases_with_velocity():
    optimizer = RestingBallisticsOptimizer()

    pred_slow = optimizer.simulate_flight_and_roll(
        release_altitude_agl_m=30.0,
        uav_ground_speed_ms=10.0
    )
    pred_fast = optimizer.simulate_flight_and_roll(
        release_altitude_agl_m=30.0,
        uav_ground_speed_ms=20.0
    )

    # 20 m/s hızla vuran yükün durma mesafesi 10 m/s'ye göre belirgin şekilde fazla olmalıdır (v^2 orantısı)
    assert pred_fast.roll_distance_m > pred_slow.roll_distance_m * 2.5
    assert pred_fast.total_lead_distance_m > pred_slow.total_lead_distance_m


def test_wind_along_track_effect():
    optimizer = RestingBallisticsOptimizer()

    # Rüzgarsız
    pred_calm = optimizer.simulate_flight_and_roll(
        release_altitude_agl_m=30.0,
        uav_ground_speed_ms=18.0,
        wind_along_track_ms=0.0
    )
    # Kafa rüzgarı (-5 m/s)
    pred_headwind = optimizer.simulate_flight_and_roll(
        release_altitude_agl_m=30.0,
        uav_ground_speed_ms=18.0,
        wind_along_track_ms=-5.0
    )

    # Kafa rüzgarında aerodinamik sürüklenme artar, yere çarpma mesafesi azalır
    assert pred_headwind.impact_distance_forward_m < pred_calm.impact_distance_forward_m


def test_release_window_trigger():
    optimizer = RestingBallisticsOptimizer()
    req_lead = optimizer.calculate_release_lead(
        uav_alt_agl_m=25.0,
        uav_ground_speed_ms=16.0
    )

    # Hedefe mesafe tam gereken lead kadarken pencere açılmalı
    in_win, err, telem = optimizer.is_in_release_window(
        current_distance_to_target_m=req_lead,
        uav_alt_agl_m=25.0,
        uav_ground_speed_ms=16.0,
        gate_tolerance_m=0.5
    )
    assert in_win is True
    assert abs(err) < 1e-3

    # Hedefe henüz 100m varken pencere kapalı olmalı
    out_win, _, _ = optimizer.is_in_release_window(
        current_distance_to_target_m=req_lead + 30.0,
        uav_alt_agl_m=25.0,
        uav_ground_speed_ms=16.0
    )
    assert out_win is False
