import math
import pytest
from src.avionics.gimbal_controller import GimbalController, GimbalAngles, GimbalMode


def test_nadir_stabilization_opposes_roll_and_pitch():
    gimbal = GimbalController(max_slew_rate_deg_s=360.0)  # Yüksek slew rate ile anlık tepki
    # İHA sağa 20° yatmış, burnu 5° yukarıda
    angles = gimbal.update_nadir_stabilization(
        uav_roll_deg=20.0,
        uav_pitch_deg=5.0,
        uav_yaw_deg=0.0,
        timestamp=1.0
    )
    # Gimbal sola yatmalı (-20°) ve pitch -95° olmalı
    assert abs(angles.roll_deg - (-20.0)) < 1.0
    assert abs(angles.pitch_deg - (-95.0)) < 1.0
    assert angles.mode == GimbalMode.NADIR_STABILIZED


def test_target_tracking_los_angles():
    gimbal = GimbalController(max_slew_rate_deg_s=360.0)
    # İHA (0, 0, -30m), Hedef doğrudan kuzeyde (30m, 0, 0)
    # dx=30, dy=0, dz=30 -> distance_h=30, delta_d=30
    # Pitch = atan2(30, 30) = -45°, Yaw = 0°
    angles = gimbal.update_target_tracking(
        uav_pos_ned=(0.0, 0.0, -30.0),
        uav_attitude_rpy_deg=(0.0, 0.0, 0.0),
        target_pos_ned=(30.0, 0.0, 0.0),
        timestamp=1.0
    )
    assert abs(angles.pitch_deg - (-45.0)) < 1.0
    assert abs(angles.yaw_deg - 0.0) < 1.0
    assert angles.mode == GimbalMode.TARGET_LOCK_LOS


def test_slew_rate_limiting():
    # Azami 60 deg/s hız sınırı
    gimbal = GimbalController(max_slew_rate_deg_s=60.0)
    # İlk adımı başlangıçta latch et (t=0.0, pitch=-90)
    gimbal.update_nadir_stabilization(0.0, 0.0, 0.0, timestamp=0.0)
    assert gimbal.current_angles.pitch_deg == -90.0

    # 0.1 saniye sonra büyük bir komut gelsin (t=0.1, max delta = 60 * 0.1 = 6.0 deg)
    angles = gimbal.update_visual_servo(norm_error_x=0.0, norm_error_y=10.0, timestamp=0.1)
    # Pitch -90'dan 6° daha az (-84.0) olmalı, ani sıçrama yapmamalı
    assert angles.pitch_deg >= -90.0 - 6.0
    assert angles.pitch_deg <= -90.0 + 6.0


def test_visual_servo_proportional():
    gimbal = GimbalController(max_slew_rate_deg_s=360.0)
    gimbal.current_angles = GimbalAngles(pitch_deg=-45.0, yaw_deg=0.0)

    # Hedef kameranın sağ üstünde (ex = 0.5, ey = -0.5)
    angles = gimbal.update_visual_servo(
        norm_error_x=0.5,
        norm_error_y=-0.5,
        timestamp=1.0,
        gain_p=10.0
    )
    # Yaw sağa artmalı, pitch yukarı (daha az negatif) olmalı
    assert angles.yaw_deg > 0.0
    assert angles.pitch_deg > -45.0
    assert angles.mode == GimbalMode.VISUAL_SERVO


def test_mavlink_mount_control_encoding():
    gimbal = GimbalController()
    gimbal.current_angles = GimbalAngles(roll_deg=10.5, pitch_deg=-45.0, yaw_deg=15.0)
    payload = gimbal.generate_mavlink_mount_control()
    assert len(payload) == 13  # 3 * int32 (12B) + 1 uint8 (1B)
