import math
import pytest
from src.navigation.georeference import PinholeGeoReferencer, CameraIntrinsics, GimbalOrientation


def test_camera_intrinsics_derivation():
    intr = CameraIntrinsics(image_width=1920, image_height=1080, hfov_deg=90.0)
    # tan(45 deg) = 1.0, fx = (1920 / 2) / 1.0 = 960.0
    assert abs(intr.fx - 960.0) < 1e-3
    assert intr.cx == 960.0
    assert intr.cy == 540.0


def test_nadir_camera_optical_axis_projection():
    geo = PinholeGeoReferencer(CameraIntrinsics(image_width=1920, image_height=1080, hfov_deg=90.0))
    uav_lat, uav_lon = 40.000000, 29.000000
    uav_alt = 30.0

    # Tam merkez piksel (960, 540), İHA düz uçuyor (roll=0, pitch=0, yaw=0), gimbal tam aşağı (-90 deg)
    res = geo.pixel_to_gps(
        u=960.0,
        v=540.0,
        uav_lat=uav_lat,
        uav_lon=uav_lon,
        uav_alt_agl=uav_alt,
        uav_roll_deg=0.0,
        uav_pitch_deg=0.0,
        uav_yaw_deg=0.0
    )

    assert res is not None
    t_lat, t_lon, t_alt = res
    # Tam merkeze baktığı için İHA'nın izdüşüm noktasında olmalı
    assert abs(t_lat - uav_lat) < 1e-6
    assert abs(t_lon - uav_lon) < 1e-6


def test_off_center_pixel_direction():
    geo = PinholeGeoReferencer(CameraIntrinsics(image_width=1920, image_height=1080, hfov_deg=90.0))
    uav_lat, uav_lon = 40.000000, 29.000000
    uav_alt = 30.0

    # Piksel sağa doğru kaydırılmış (u > cx). Yaw=0 iken gövde Y ekseni Doğudur.
    res = geo.pixel_to_gps(
        u=1440.0,
        v=540.0,
        uav_lat=uav_lat,
        uav_lon=uav_lon,
        uav_alt_agl=uav_alt,
        uav_roll_deg=0.0,
        uav_pitch_deg=0.0,
        uav_yaw_deg=0.0
    )

    assert res is not None
    t_lat, t_lon, _ = res
    assert t_lon > uav_lon  # Doğu yönünde boylam artmalı
    assert abs(t_lat - uav_lat) < 1e-6  # Enlem sabit kalmalı


def test_ray_above_horizon_returns_none():
    geo = PinholeGeoReferencer(CameraIntrinsics(image_width=1920, image_height=1080, hfov_deg=90.0))
    # Gimbal yukarı ufka veya gökyüzüne bakıyorsa (pitch = +10 deg)
    res = geo.pixel_to_gps(
        u=960.0,
        v=540.0,
        uav_lat=40.0,
        uav_lon=29.0,
        uav_alt_agl=30.0,
        gimbal=GimbalOrientation(pitch_deg=15.0)
    )
    assert res is None


def test_gps_to_pixel_roundtrip():
    geo = PinholeGeoReferencer(CameraIntrinsics(image_width=1920, image_height=1080, hfov_deg=90.0))
    uav_lat, uav_lon = 40.123456, 29.654321
    uav_alt = 40.0

    # 1. Pikselden GPS'e git
    orig_u, orig_v = 1100.0, 600.0
    gps = geo.pixel_to_gps(
        u=orig_u,
        v=orig_v,
        uav_lat=uav_lat,
        uav_lon=uav_lon,
        uav_alt_agl=uav_alt,
        uav_roll_deg=2.0,
        uav_pitch_deg=-3.0,
        uav_yaw_deg=35.0
    )
    assert gps is not None
    t_lat, t_lon, _ = gps

    # 2. GPS'ten tekrar piksele dön
    rev = geo.gps_to_pixel(
        target_lat=t_lat,
        target_lon=t_lon,
        target_alt_agl=0.0,
        uav_lat=uav_lat,
        uav_lon=uav_lon,
        uav_alt_agl=uav_alt,
        uav_roll_deg=2.0,
        uav_pitch_deg=-3.0,
        uav_yaw_deg=35.0
    )
    assert rev is not None
    calc_u, calc_v, is_visible = rev
    assert is_visible is True
    assert abs(calc_u - orig_u) < 1.0
    assert abs(calc_v - orig_v) < 1.0
