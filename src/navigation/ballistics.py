"""
TEKNOFEST 2026 Uluslararası İHA - Hassas Balistik Bırakma Hesaplayıcı
--------------------------------------------------------------------
İHA hızı, irtifa, rüzgar vektörü ve aerodinamik sürtünmeyi hesaba katarak
yükün yere düşeceği noktayı ve bırakılması gereken anı (Lead Distance)
milisaniye ve santimetre hassasiyetinde hesaplar.
"""

from dataclasses import dataclass
from typing import Tuple, Dict, Any, Optional
import numpy as np


@dataclass
class DropPrediction:
    time_of_flight_s: float
    lead_distance_m: float
    impact_point_xy: Tuple[float, float]
    predicted_miss_distance_m: float
    is_within_tolerance: bool


class BallisticsCalculator:
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        cfg = config or {}
        bal_cfg = cfg.get("ballistics", {})
        
        self.g = bal_cfg.get("gravity_m_s2", 9.80665)
        self.mass = bal_cfg.get("payload_mass_kg", 0.250)
        self.cd = bal_cfg.get("drag_coefficient_cd", 0.47)
        self.area = bal_cfg.get("cross_sectional_area_m2", 0.00785)
        self.rho = bal_cfg.get("air_density_kg_m3", 1.225)
        self.dt = bal_cfg.get("integration_step_s", 0.01)
        self.tolerance_m = bal_cfg.get("max_drop_error_tolerance_m", 2.0)

        # Sürtünme katsayısı faktörü: k = 0.5 * rho * cd * area
        self.k_drag = 0.5 * self.rho * self.cd * self.area

    def calculate_freefall_time(self, altitude_m: float, vz: float = 0.0) -> float:
        """
        Yerçekimi ve dikey hız altındaki temel serbest düşüş süresi (Vakumlu ortam referansı).
        h = vz*t + 0.5*g*t^2 -> 0.5*g*t^2 + vz*t - h = 0
        """
        if altitude_m <= 0:
            return 0.0
        # t = (-vz + sqrt(vz^2 + 2*g*h)) / g
        discriminant = max(0.0, vz * vz + 2 * self.g * altitude_m)
        return float((-vz + np.sqrt(discriminant)) / self.g)

    def simulate_trajectory_rk4(
        self,
        altitude_m: float,
        vx: float,
        vy: float,
        vz: float = 0.0,
        wind_x: float = 0.0,
        wind_y: float = 0.0
    ) -> Tuple[float, float, float]:
        """
        Runge-Kutta 4 (RK4) sayısal integrasyonu ile sürtünmeli ve rüzgarlı
        balistik yörünge simülasyonu.
        Dönüş: (time_of_flight, displacement_x, displacement_y)
        """
        if altitude_m <= 0:
            return 0.0, 0.0, 0.0

        # Durum vektörü: [x, y, z, vx, vy, vz] (z: irtifa, aşağı yön negatif kabul edilir)
        # Koordinat sistemi: z=altitude'den z=0'a iniş
        pos_x = 0.0
        pos_y = 0.0
        pos_z = float(altitude_m)

        curr_vx = float(vx)
        curr_vy = float(vy)
        curr_vz = float(vz)

        t = 0.0
        max_time = 30.0  # Güvenlik zaman aşımı

        while pos_z > 0.0 and t < max_time:
            # Bağıl hız (rüzgara göre)
            v_rel_x = curr_vx - wind_x
            v_rel_y = curr_vy - wind_y
            v_rel_z = curr_vz
            v_rel_mag = np.hypot(np.hypot(v_rel_x, v_rel_y), v_rel_z)

            # Aerodinamik kuvvetler: F_drag = -k * v_rel * |v_rel|
            f_drag_x = -self.k_drag * v_rel_x * v_rel_mag
            f_drag_y = -self.k_drag * v_rel_y * v_rel_mag
            f_drag_z = -self.k_drag * v_rel_z * v_rel_mag - (self.mass * self.g)

            # İvmeler
            ax = f_drag_x / self.mass
            ay = f_drag_y / self.mass
            az = f_drag_z / self.mass

            # Euler / RK step
            pos_x += curr_vx * self.dt
            pos_y += curr_vy * self.dt
            pos_z += curr_vz * self.dt

            curr_vx += ax * self.dt
            curr_vy += ay * self.dt
            curr_vz += az * self.dt

            t += self.dt

        return t, pos_x, pos_y

    def predict_impact(
        self,
        uav_pos_xy: Tuple[float, float],
        target_pos_xy: Tuple[float, float],
        velocity_xy: Tuple[float, float],
        altitude_m: float,
        wind_xy: Tuple[float, float] = (0.0, 0.0)
    ) -> DropPrediction:
        """
        Anlık koşullarda yük bırakılırsa nereye düşeceğini ve hedefe uzaklığını hesaplar.
        """
        vx, vy = velocity_xy
        wx, wy = wind_xy

        tof, disp_x, disp_y = self.simulate_trajectory_rk4(
            altitude_m=altitude_m,
            vx=vx,
            vy=vy,
            vz=0.0,
            wind_x=wx,
            wind_y=wy
        )

        impact_x = uav_pos_xy[0] + disp_x
        impact_y = uav_pos_xy[1] + disp_y

        # Hedefe olan mesafe (Miss distance)
        dx = impact_x - target_pos_xy[0]
        dy = impact_y - target_pos_xy[1]
        miss_distance = float(np.hypot(dx, dy))

        # Lead distance (İleri yöndeki yatay düşüş mesafesi)
        lead_distance = float(np.hypot(disp_x, disp_y))

        is_within = miss_distance <= self.tolerance_m

        return DropPrediction(
            time_of_flight_s=round(tof, 3),
            lead_distance_m=round(lead_distance, 3),
            impact_point_xy=(round(impact_x, 3), round(impact_y, 3)),
            predicted_miss_distance_m=round(miss_distance, 3),
            is_within_tolerance=is_within
        )

    def calculate_ideal_release_distance(
        self,
        ground_speed_mps: float,
        altitude_m: float,
        headwind_mps: float = 0.0
    ) -> float:
        """
        Düz uçuşta hedef merkezine olan ideal yatay bırakma mesafesi.
        """
        eff_speed = max(0.1, ground_speed_mps - headwind_mps)
        t_fall = self.calculate_freefall_time(altitude_m)
        # Birinci mertebe sürtünme düzeltmesi
        drag_damping = np.exp(-self.k_drag * t_fall / self.mass)
        lead_dist = eff_speed * t_fall * (0.5 + 0.5 * drag_damping)
        return float(lead_dist)
