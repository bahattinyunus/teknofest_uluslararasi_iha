"""
Unit tests for Quintic Spline 3D Trajectory Optimizer Subsystem
"""
import pytest
import math
from src.navigation.trajectory_optimizer import (
    TrajectoryOptimizer,
    QuinticPolynomial,
    TrajectoryPoint,
    TrajectoryMetrics
)


def test_quintic_polynomial_boundary_conditions():
    poly = QuinticPolynomial(p0=0.0, v0=0.0, a0=0.0, p1=10.0, v1=0.0, a1=0.0, T=5.0)
    assert math.isclose(poly.pos(0.0), 0.0, abs_tol=1e-4)
    assert math.isclose(poly.vel(0.0), 0.0, abs_tol=1e-4)
    assert math.isclose(poly.acc(0.0), 0.0, abs_tol=1e-4)
    assert math.isclose(poly.pos(5.0), 10.0, abs_tol=1e-4)
    assert math.isclose(poly.vel(5.0), 0.0, abs_tol=1e-4)
    assert math.isclose(poly.acc(5.0), 0.0, abs_tol=1e-4)


def test_trajectory_planner_3d_waypoints():
    opt = TrajectoryOptimizer(max_velocity=15.0, max_acceleration=4.0)
    waypoints = [
        (0.0, 0.0, 10.0),
        (50.0, 20.0, 25.0),
        (100.0, 0.0, 30.0),
        (150.0, -30.0, 20.0)
    ]
    points, metrics = opt.plan_trajectory(waypoints, dt=0.1)

    assert len(points) > 10
    assert metrics.total_distance_m > 150.0
    assert metrics.total_duration_s > 5.0
    assert metrics.max_speed_mps <= 18.0
    # First point should start at initial waypoint
    assert math.isclose(points[0].x, 0.0, abs_tol=0.1)
    assert math.isclose(points[0].z, 10.0, abs_tol=0.1)
    # Last point should end near last waypoint
    assert math.isclose(points[-1].x, 150.0, abs_tol=0.1)
    assert math.isclose(points[-1].z, 20.0, abs_tol=0.1)


def test_figure_eight_trajectory_smoothness():
    opt = TrajectoryOptimizer(max_velocity=16.0, max_acceleration=4.0)
    points, metrics = opt.optimize_figure_eight(center=(0.0, 0.0, 30.0), radius=30.0, num_waypoints=16)

    assert metrics.num_samples > 20
    assert metrics.total_distance_m > 100.0
    # Curvature should be non-negative everywhere
    for pt in points:
        assert pt.curvature >= 0.0
        assert pt.speed >= 0.0


def test_trajectory_insufficient_waypoints_rejected():
    opt = TrajectoryOptimizer()
    with pytest.raises(ValueError):
        opt.plan_trajectory([(0.0, 0.0, 10.0)])
