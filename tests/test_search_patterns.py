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


def test_official_pole_eight_generation():
    gen = SearchPatternGenerator()
    waypoints = gen.generate_official_pole_eight(
        pole1_xy=(-75.0, 0.0),
        pole2_xy=(75.0, 0.0),
        turn_radius_m=20.0,
        altitude_m=30.0,
        points_per_turn=12
    )
    assert len(waypoints) == 24
    # Ensure points visit near both poles
    p1_visited = any(wp.x_m < -50.0 for wp in waypoints)
    p2_visited = any(wp.x_m > 50.0 for wp in waypoints)
    assert p1_visited and p2_visited

def test_figure_eight_wraps_150m_poles_and_outer_turn():
    gen = SearchPatternGenerator()
    # Default without scale_a_m should auto-compute scale to wrap 150m poles (a = 75 + 30 = 105m)
    waypoints = gen.generate_figure_eight(altitude_m=30.0, num_points=40)
    assert len(waypoints) == 40

    xs = [wp.x_m for wp in waypoints]
    assert max(xs) >= 100.0  # Wraps well outside Pole 2 (+75m)
    assert min(xs) <= -100.0  # Wraps well outside Pole 1 (-75m)

    # Verify that outer turn on Pole 2 is tagged and validated
    pole_2_outer_points = [wp for wp in waypoints if wp.pole_id == 2 and wp.is_outer_turn]
    assert len(pole_2_outer_points) > 0
    for wp in pole_2_outer_points:
        assert wp.x_m >= 75.0

    # Clearance verification
    clearance = gen.verify_figure_eight_clearance(waypoints, pole_distance_m=150.0)
    assert clearance["valid"] is True
    assert clearance["pole_1_cleared"] is True
    assert clearance["pole_2_cleared"] is True
    assert clearance["pole_2_outer_turn_verified"] is True


def test_v7_task1_full_route_sequence():
    gen = SearchPatternGenerator()
    route = gen.generate_v7_task1_full_route(pole_distance_m=150.0, laps=2)
    assert len(route) > 30

    # First point should be takeoff start
    assert route[0].action == "TAKEOFF_START"
    assert route[0].z_m == 0.0

    # Last point should be touchdown
    assert route[-1].action == "TOUCHDOWN"
    assert route[-1].z_m == 0.0

    # Actions must include outbound, outer turns, center crosses, finish line and landing
    actions = [wp.action for wp in route]
    assert any("OUTBOUND_TO_POLE_2" in a for a in actions)
    assert any("POLE_2_FIRST_OUTER_TURN" in a for a in actions)
    assert any("LAP_1_POLE_1_OUTER_TURN" in a for a in actions)
    assert any("LAP_2_POLE_2_OUTER_TURN" in a for a in actions)
    assert any("CROSS_FINISH_LINE" in a for a in actions)
    assert any("TOUCHDOWN" in a for a in actions)


def test_boustrophedon_v7_30x100m_grid():
    gen = SearchPatternGenerator()
    # Default should be official 30x100m scan area
    waypoints = gen.generate_boustrophedon_grid()
    assert len(waypoints) >= 4
    for wp in waypoints:
        assert 0.0 <= wp.x_m <= 100.0
        assert 0.0 <= wp.y_m <= 35.0
