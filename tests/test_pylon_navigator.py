"""
Unit tests for PylonNavigator (TEKNOFEST 2026 150m Pylon Outer-Turn & Obstacle Guidance)
"""
import math
from src.navigation.pylon_navigator import PylonNavigator


def test_dynamic_turn_radius_scales_with_wind_and_speed():
    nav = PylonNavigator(pole_distance_m=150.0, min_turn_radius_m=18.0, max_bank_angle_deg=35.0)
    r_calm = nav.compute_dynamic_turn_radius(airspeed_mps=15.0, wind_speed_mps=0.0)
    r_windy = nav.compute_dynamic_turn_radius(airspeed_mps=15.0, wind_speed_mps=6.5)
    assert r_calm >= 18.0
    assert r_windy > r_calm


def test_outer_turn_figure_eight_waypoints_never_cut_inside():
    nav = PylonNavigator(pole_distance_m=150.0, min_turn_radius_m=20.0)
    wps = nav.generate_outer_turn_figure_eight(altitude_m=30.0, airspeed_mps=16.0, wind_speed_mps=3.0, laps=2)
    assert len(wps) > 40
    max_x = max(w[0] for w in wps)
    min_x = min(w[0] for w in wps)
    # Must pass strictly outside both Pole 2 (+75m) and Pole 1 (-75m)
    assert max_x >= 95.0
    assert min_x <= -95.0
    assert all(w[2] == 30.0 for w in wps)


def test_winding_angle_completes_full_outer_lap():
    nav = PylonNavigator(pole_distance_m=150.0)
    wps = nav.generate_outer_turn_figure_eight(altitude_m=30.0, airspeed_mps=16.0, laps=1, arc_points=16)

    prev = (0.0, 0.0)
    state = None
    for wx, wy, _ in wps:
        vx, vy = wx - prev[0], wy - prev[1]
        state = nav.update(uav_xy=(wx, wy), uav_vel_xy=(vx, vy), airspeed_mps=16.0)
        prev = (wx, wy)

    assert state is not None
    assert state.completed_laps == 1


def test_inner_turn_risk_flagged_before_pole_2():
    nav = PylonNavigator(pole_distance_m=150.0)
    # UAV approaches Pole 2 (+75m) at x=60m, then turns back toward center (vx < -1) without clearing x=+75m
    state = nav.update(uav_xy=(60.0, 5.0), uav_vel_xy=(-8.0, 0.0), airspeed_mps=15.0)
    assert state.inner_turn_risk is True


def test_obstacle_deflection_pushes_away_from_pylon():
    nav = PylonNavigator(pole_distance_m=150.0, pylon_clearance_m=15.0)
    # Place UAV very close to Pole 2 (75, 0) at (75, 5)
    vx_out, vy_out = nav.compute_obstacle_deflection(uav_xy=(75.0, 5.0), desired_vel_xy=(0.0, -5.0))
    # Repulsive vector must push +y (away from pole)
    assert vy_out > -5.0
