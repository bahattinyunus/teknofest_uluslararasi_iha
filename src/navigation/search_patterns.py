"""
TEKNOFEST 2026 Uluslararası İHA - Otonom Rota ve Arama Deseni Üreteci
--------------------------------------------------------------------
1. Görev için Bernoulli Lemniskatı (∞ Sonsuz Şekli) otonom uçuş rotası,
2. Görev için kamera görüş açısı (FOV) ve irtifaya göre sıfır kör noktalı
Boustrophedon (Çim Biçme) ve Genişleyen Spiral arama paternleri üretir.
"""

from dataclasses import dataclass
from typing import List, Tuple, Optional
import math
import numpy as np


@dataclass
class Waypoint:
    x_m: float
    y_m: float
    z_m: float  # İrtifa (AGL)
    speed_mps: float
    heading_deg: Optional[float] = None


class SearchPatternGenerator:
    def __init__(self, fov_deg: float = 85.0, default_speed_mps: float = 8.0):
        self.fov_deg = fov_deg
        self.default_speed = default_speed_mps

    def generate_figure_eight(
        self,
        center_xy: Tuple[float, float] = (0.0, 0.0),
        scale_a_m: float = 40.0,
        altitude_m: float = 30.0,
        num_points: int = 40
    ) -> List[Waypoint]:
        """
        1. Görev için Bernoulli Lemniskatı (∞ Sonsuz) rotası üretir.
        x(t) = a * cos(t) / (1 + sin^2(t))
        y(t) = a * sin(t) * cos(t) / (1 + sin^2(t))
        """
        waypoints: List[Waypoint] = []
        cx, cy = center_xy
        t_vals = np.linspace(0, 2 * np.pi, num_points + 1)[:-1]

        for i, t in enumerate(t_vals):
            sin_t = math.sin(t)
            cos_t = math.cos(t)
            denom = 1.0 + sin_t * sin_t

            px = cx + (scale_a_m * cos_t) / denom
            py = cy + (scale_a_m * sin_t * cos_t) / denom

            # Sonraki noktaya göre yönelim (Heading)
            next_t = t_vals[(i + 1) % len(t_vals)]
            next_sin = math.sin(next_t)
            next_cos = math.cos(next_t)
            next_denom = 1.0 + next_sin * next_sin
            next_px = cx + (scale_a_m * next_cos) / next_denom
            next_py = cy + (scale_a_m * next_sin * next_cos) / next_denom

            heading_rad = math.atan2(next_py - py, next_px - px)
            heading_deg = (math.degrees(heading_rad) + 360.0) % 360.0

            waypoints.append(Waypoint(
                x_m=round(px, 2),
                y_m=round(py, 2),
                z_m=altitude_m,
                speed_mps=self.default_speed,
                heading_deg=round(heading_deg, 1)
            ))

        return waypoints

    def calculate_camera_footprint(self, altitude_m: float) -> Tuple[float, float]:
        """
        Verilen irtifada kameranın yerde taradığı dikdörtgen alanın (Genişlik, Yükseklik) ölçüsü.
        16:9 en-boy oranı varsayımı.
        """
        fov_rad = math.radians(self.fov_deg)
        # Yatay iz düşüm
        width = 2.0 * altitude_m * math.tan(fov_rad / 2.0)
        # 16:9 oranı
        height = width * (9.0 / 16.0)
        return width, height

    def generate_boustrophedon_grid(
        self,
        area_width_m: float = 120.0,
        area_height_m: float = 70.0,
        altitude_m: float = 35.0,
        overlap_ratio: float = 0.25,
        origin_xy: Tuple[float, float] = (0.0, 0.0)
    ) -> List[Waypoint]:
        """
        2. Görev için sıfır kör noktalı ve örtüşmeli Boustrophedon (Çim Biçme) arama rotası.
        """
        cam_w, _ = self.calculate_camera_footprint(altitude_m)
        lane_step = max(5.0, cam_w * (1.0 - overlap_ratio))

        ox, oy = origin_xy
        waypoints: List[Waypoint] = []

        curr_y = oy
        moving_forward = True

        while curr_y <= oy + area_height_m:
            if moving_forward:
                x_start = ox
                x_end = ox + area_width_m
            else:
                x_start = ox + area_width_m
                x_end = ox

            waypoints.append(Waypoint(
                x_m=round(x_start, 2),
                y_m=round(curr_y, 2),
                z_m=altitude_m,
                speed_mps=self.default_speed
            ))
            waypoints.append(Waypoint(
                x_m=round(x_end, 2),
                y_m=round(curr_y, 2),
                z_m=altitude_m,
                speed_mps=self.default_speed
            ))

            curr_y += lane_step
            moving_forward = not moving_forward

        return waypoints

    def generate_expanding_spiral(
        self,
        center_xy: Tuple[float, float] = (0.0, 0.0),
        max_radius_m: float = 40.0,
        altitude_m: float = 25.0,
        step_radius_m: float = 6.0,
        points_per_turn: int = 12
    ) -> List[Waypoint]:
        """
        Hedef temasının kaybolduğu durumlarda yerel arama için Arşimet Spirali.
        """
        waypoints: List[Waypoint] = []
        cx, cy = center_xy

        theta = 0.0
        r = 5.0
        d_theta = (2 * math.pi) / points_per_turn

        while r <= max_radius_m:
            px = cx + r * math.cos(theta)
            py = cy + r * math.sin(theta)

            waypoints.append(Waypoint(
                x_m=round(px, 2),
                y_m=round(py, 2),
                z_m=altitude_m,
                speed_mps=self.default_speed * 0.7
            ))

            theta += d_theta
            r += (step_radius_m / points_per_turn)

        return waypoints
