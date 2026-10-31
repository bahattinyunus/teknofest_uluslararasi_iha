"""
TEKNOFEST 2026 Uluslararası İHA - GPS Kesintisi & Dead Reckoning Navigatörü
--------------------------------------------------------------------------
GPS sinyalinin zayıfladığı, karıştırıldığı (GPS Jamming/Spoofing) veya
uydu sayısının 6'nın altına düştüğü durumlarda Optik Akış (Optical Flow),
Barometrik İrtifa ve IMU ivmeölçer verilerini kaynaştırarak (Sensor Fusion)
kesintisiz konum ve hız tahmini üretir.
"""

from dataclasses import dataclass
from typing import Tuple, Optional
import math
import time
import numpy as np


@dataclass
class DeadReckoningState:
    pos_x_m: float           # Kalkış noktasına göre X konumu (metre)
    pos_y_m: float           # Kalkış noktasına göre Y konumu (metre)
    vel_x_mps: float         # Doğu/Kuzey ekseninde hız X (m/s)
    vel_y_mps: float         # Doğu/Kuzey ekseninde hız Y (m/s)
    drift_error_m: float     # Birikimli sürüklenme belirsizliği (1-sigma metre)
    gps_active: bool         # GPS kaynağı güvenilir mi?
    navigation_source: str   # "GPS_EKF", "OPTICAL_FLOW_DEAD_RECKONING", "IMU_INTEGRAL"


class DeadReckoningNavigator:
    def __init__(
        self,
        optical_flow_weight: float = 0.85,
        accel_weight: float = 0.15,
        drift_rate_mps: float = 0.08,
        min_satellites: int = 6
    ):
        self.w_flow = optical_flow_weight
        self.w_acc = accel_weight
        self.drift_rate = drift_rate_mps
        self.min_sats = min_satellites

        # Dahili durum
        self.pos_x = 0.0
        self.pos_y = 0.0
        self.vel_x = 0.0
        self.vel_y = 0.0
        self.accumulated_drift = 0.0

        self.last_update_time: Optional[float] = None
        self.gps_lost_time: Optional[float] = None
        self.is_initialized = False

    def update(
        self,
        gps_pos_xy: Optional[Tuple[float, float]],
        gps_vel_xy: Optional[Tuple[float, float]],
        satellites_visible: int,
        flow_rad_s_xy: Tuple[float, float],
        altitude_agl_m: float,
        body_accel_xy: Tuple[float, float],
        heading_deg: float,
        dt: Optional[float] = None
    ) -> DeadReckoningState:
        """
        Sensör verilerini kaynaştırarak anlık İHA konum ve hızını günceller.
        """
        now = time.monotonic()
        if dt is None:
            dt = 0.05 if self.last_update_time is None else max(0.001, now - self.last_update_time)
        self.last_update_time = now

        gps_reliable = (
            gps_pos_xy is not None and
            gps_vel_xy is not None and
            satellites_visible >= self.min_sats
        )

        heading_rad = math.radians(heading_deg)
        cos_hdg = math.cos(heading_rad)
        sin_hdg = math.sin(heading_rad)

        # 1. Optik Akıştan Doğrusal Hız Çıkarımı: V = Flow_rad * Altitude
        h = max(0.5, altitude_agl_m)
        flow_vx_body = flow_rad_s_xy[0] * h
        flow_vy_body = flow_rad_s_xy[1] * h

        # Gövde ekseninden Dünya (NED) eksenine dönüşüm
        flow_vx_world = flow_vx_body * cos_hdg - flow_vy_body * sin_hdg
        flow_vy_world = flow_vx_body * sin_hdg + flow_vy_body * cos_hdg

        # 2. Gövde İvmesinden Dünya Eksenine İvme
        acc_x_world = body_accel_xy[0] * cos_hdg - body_accel_xy[1] * sin_hdg
        acc_y_world = body_accel_xy[0] * sin_hdg + body_accel_xy[1] * cos_hdg

        if gps_reliable:
            # GPS verisi güvenilir: Konum ve hızı GPS ile senkronize et
            assert gps_pos_xy is not None and gps_vel_xy is not None
            self.pos_x = gps_pos_xy[0]
            self.pos_y = gps_pos_xy[1]
            self.vel_x = gps_vel_xy[0]
            self.vel_y = gps_vel_xy[1]
            self.accumulated_drift = 0.3  # Nominal GPS belirsizliği
            self.gps_lost_time = None
            nav_source = "GPS_EKF"
        else:
            # GPS kesildi veya yetersiz: Dead Reckoning moduna geç
            if self.gps_lost_time is None:
                self.gps_lost_time = now
                self.accumulated_drift = max(0.5, self.accumulated_drift)

            # Hız füzyonu: Optik Akış + İvme İntegrali
            est_vx = self.w_flow * flow_vx_world + self.w_acc * (self.vel_x + acc_x_world * dt)
            est_vy = self.w_flow * flow_vy_world + self.w_acc * (self.vel_y + acc_y_world * dt)

            self.vel_x = float(est_vx)
            self.vel_y = float(est_vy)

            # Konum integrasyonu
            self.pos_x += self.vel_x * dt
            self.pos_y += self.vel_y * dt

            # Belirsizlik büyümesi
            self.accumulated_drift += self.drift_rate * dt
            nav_source = "OPTICAL_FLOW_DEAD_RECKONING"

        self.is_initialized = True

        return DeadReckoningState(
            pos_x_m=round(self.pos_x, 3),
            pos_y_m=round(self.pos_y, 3),
            vel_x_mps=round(self.vel_x, 3),
            vel_y_mps=round(self.vel_y, 3),
            drift_error_m=round(self.accumulated_drift, 3),
            gps_active=gps_reliable,
            navigation_source=nav_source
        )

    def reset(self, init_x: float = 0.0, init_y: float = 0.0):
        self.pos_x = init_x
        self.pos_y = init_y
        self.vel_x = 0.0
        self.vel_y = 0.0
        self.accumulated_drift = 0.0
        self.last_update_time = None
        self.gps_lost_time = None
        self.is_initialized = False
