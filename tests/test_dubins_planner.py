"""
TEKNOFEST 2026 - 3B Dubins Kinodinamik Rota Planlayıcı Testleri
"""

import math
from src.navigation.dubins_planner import DubinsPathPlanner, DubinsPose


def test_min_turn_radius_formula():
    r = DubinsPathPlanner.compute_min_turn_radius(airspeed_mps=16.0, max_bank_deg=35.0)
    expected = (16.0 ** 2) / (9.80665 * math.tan(math.radians(35.0)))
    assert abs(r - expected) < 1e-3


def test_dubins_path_reaches_goal_pose_and_respects_radius():
    planner = DubinsPathPlanner(max_climb_angle_deg=18.0)
    start = DubinsPose(-75.0, -25.0, 30.0, 0.0)
    goal = DubinsPose(75.0, 25.0, 35.0, math.pi)
    path = planner.plan(start, goal, turn_radius_m=30.0, step_size_m=5.0)

    assert path.path_type in ("LSL", "RSR", "LSR", "RSL")
    assert path.total_length_2d_m >= math.hypot(150.0, 50.0)
    assert path.glide_slope_feasible is True
    assert len(path.samples) >= 10

    last = path.samples[-1]
    assert math.hypot(last.x_m - goal.x_m, last.y_m - goal.y_m) < 0.5
    assert abs(last.z_m - goal.z_m) < 0.1


def test_steep_climb_flags_glide_slope_infeasible():
    planner = DubinsPathPlanner(max_climb_angle_deg=12.0)
    start = DubinsPose(0.0, 0.0, 10.0, 0.0)
    goal = DubinsPose(40.0, 0.0, 60.0, 0.0)
    path = planner.plan(start, goal, turn_radius_m=15.0)
    assert path.glide_slope_feasible is False
    assert path.climb_angle_deg > 12.0
