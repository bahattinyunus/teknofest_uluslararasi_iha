"""
Unit tests for Search Pattern & Waypoint Generators
"""
import pytest
from src.navigation.search_patterns import SearchPatternGenerator


def test_figure_eight_generation():
    gen = SearchPatternGenerator()
    waypoints = gen.generate_figure_eight(scale_a_m=30.0, altitude_m=25.0, num_points=20)
    assert len(waypoints) == 20

    # Altitudes should match requested altitude
    for wp in waypoints:
        assert wp.z_m == 25.0
        assert wp.speed_mps > 0.0


def test_camera_footprint_calculation():
    gen = SearchPatternGenerator(fov_deg=85.0)
    # At 35m AGL, horizontal FOV width should be 2 * 35 * tan(42.5 deg) ~ 64m
    w, h = gen.calculate_camera_footprint(35.0)
    assert w > 50.0
    assert h > 25.0


def test_boustrophedon_grid_generation():
    gen = SearchPatternGenerator()
    waypoints = gen.generate_boustrophedon_grid(area_width_m=80.0, area_height_m=50.0, altitude_m=30.0)
    assert len(waypoints) >= 4

    # Waypoints must stay within area boundaries
    for wp in waypoints:
        assert 0.0 <= wp.x_m <= 85.0
        assert 0.0 <= wp.y_m <= 65.0


def test_expanding_spiral_generation():
    gen = SearchPatternGenerator()
    waypoints = gen.generate_expanding_spiral(max_radius_m=30.0, altitude_m=20.0)
    assert len(waypoints) > 10

    # Final waypoint radius should approach max radius
    last_wp = waypoints[-1]
    radius = (last_wp.x_m**2 + last_wp.y_m**2)**0.5
    assert radius >= 25.0
