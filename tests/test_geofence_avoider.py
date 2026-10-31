"""
Unit tests for Geofence & No-Fly Zone (NFZ) Avoidance Subsystem
"""
import pytest
from src.navigation.geofence_avoider import GeofenceManager, GeofenceStatus


def test_point_in_polygon_ray_casting():
    square = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    assert GeofenceManager.is_point_in_polygon((5.0, 5.0), square) is True
    assert GeofenceManager.is_point_in_polygon((15.0, 5.0), square) is False


def test_geofence_nominal_flight():
    mgr = GeofenceManager(outer_radius_m=500.0, max_altitude_m=120.0)
    # UAV at (10.0, 10.0), 30m altitude, far from boundary and default NFZ
    status = mgr.evaluate_geofence(uav_pos_xy=(10.0, 10.0), altitude_agl_m=30.0)

    assert status.is_inside_flight_boundary is True
    assert status.is_inside_nfz is False
    assert status.is_altitude_violation is False
    assert status.requires_avoidance is False


def test_geofence_nfz_violation_triggers_repulsion():
    mgr = GeofenceManager()
    # Default NFZ is at (70..110, -90..-60)
    # UAV inside the NFZ at (80.0, -75.0)
    status = mgr.evaluate_geofence(uav_pos_xy=(80.0, -75.0), altitude_agl_m=20.0)

    assert status.is_inside_nfz is True
    assert status.requires_avoidance is True
    vx, vy, vz = status.avoidance_velocity_ned
    assert (abs(vx) > 0.0 or abs(vy) > 0.0)


def test_geofence_altitude_ceiling_avoidance():
    mgr = GeofenceManager(max_altitude_m=120.0)
    # Altitude at 118m (approaching 120m hard ceiling)
    status = mgr.evaluate_geofence(uav_pos_xy=(0.0, 0.0), altitude_agl_m=118.0)

    assert status.requires_avoidance is True
    assert status.avoidance_velocity_ned[2] > 0.0  # +Z is downward in NED (descend)
