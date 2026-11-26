"""
TEKNOFEST 2026 Uluslararası İHA - Otonom Rota ve Arama Deseni Üreteci
--------------------------------------------------------------------
TÜBİTAK TEKNOFEST 2026 V7 Şartnamesi ile tam uyumludur:
1. Görev: Malatya Tulga sahasında aralarında 150m mesafe bulunan iki direk
   etrafında ardışık 2 tur Bernoulli Lemniskatı (∞ Sonsuz Şekli) veya
   teğetsel yaylı dış dönüş rotası. 2. direğin dışından dönüş zorunluluğu
   ve direkler arası kırımsız iniş paternleri içerir.
2. Görev: 30x100m resmi tarama alanında kamera görüş açısı (FOV) ve irtifaya
   göre sıfır kör noktalı Boustrophedon (Çim Biçme) ve Arşimet Spirali deseni.
"""

from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict, Any
import math
import numpy as np


@dataclass
class Waypoint:
    x_m: float
    y_m: float
    z_m: float  # İrtifa (AGL)
    speed_mps: float
    heading_deg: Optional[float] = None
    action: Optional[str] = None
    pole_id: Optional[int] = None
    is_outer_turn: bool = False


class SearchPatternGenerator:
    """
    TEKNOFEST 2026 Uluslararası İHA yarışma rotaları ve tarama desenleri üreteci.
    """

    def __init__(self, fov_deg: float = 85.0, default_speed_mps: float = 8.0):
        self.fov_deg = fov_deg
        self.default_speed = default_speed_mps

    def generate_figure_eight(
        self,
        center_xy: Tuple[float, float] = (0.0, 0.0),
        scale_a_m: Optional[float] = None,
        altitude_m: float = 30.0,
        num_points: int = 40,
        pole_distance_m: float = 150.0,
        turn_radius_m: float = 30.0,
        enforce_outer_turn: bool = True
    ) -> List[Waypoint]:
        """
        1. Görev için Bernoulli Lemniskatı (∞ Sonsuz) rotası üretir.
        
        TÜBİTAK TEKNOFEST 2026 V7 kuralına göre 150m aralıklı iki direğin (x = ±75m)
        dışından dönülmeli ve 2. direğin dışından dönüş şartı sağlanmalıdır.
        
        x(t) = a * cos(t) / (1 + sin^2(t))
        y(t) = a * sin(t) * cos(t) / (1 + sin^2(t))
        """
        # Eğer scale_a_m belirtilmemişse 150m direkleri dıştan saracak ölçeği hesapla
        if scale_a_m is None:
            # Direkler x = -75m ve +75m konumlarındadır.
            # Dış dönüş emniyet yarıçapı ile a = (150/2) + 30 = 105m
            scale_a_m = (pole_distance_m / 2.0) + turn_radius_m

        waypoints: List[Waypoint] = []
        cx, cy = center_xy
        t_vals = np.linspace(0, 2 * np.pi, num_points + 1)[:-1]

        pole_half_dist = pole_distance_m / 2.0

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

            # Direk dış dönüş tespiti (V7 şartname kuralı)
            pole_id = None
            is_outer = False
            action = "FIGURE_8_CRUISE"

            if px >= (pole_half_dist - 5.0):
                pole_id = 2
                if px >= pole_half_dist:
                    is_outer = True
                    action = "POLE_2_OUTER_TURN"
            elif px <= -(pole_half_dist - 5.0):
                pole_id = 1
                if px <= -pole_half_dist:
                    is_outer = True
                    action = "POLE_1_OUTER_TURN"
            elif abs(px - cx) < 15.0:
                action = "CENTER_INTERSECTION_CROSSING"

            waypoints.append(Waypoint(
                x_m=round(px, 2),
                y_m=round(py, 2),
                z_m=altitude_m,
                speed_mps=self.default_speed,
                heading_deg=round(heading_deg, 1),
                action=action,
                pole_id=pole_id,
                is_outer_turn=is_outer
            ))

        return waypoints

    def generate_official_pole_eight(
        self,
        pole1_xy: Tuple[float, float] = (-75.0, 0.0),
        pole2_xy: Tuple[float, float] = (75.0, 0.0),
        turn_radius_m: float = 20.0,
        altitude_m: float = 30.0,
        points_per_turn: int = 12
    ) -> List[Waypoint]:
        """
        TÜBİTAK TEKNOFEST 2026 V7 Şartnamesi Direk Etrafı Sekiz (∞) Deseni.
        150m aralıklı iki direğin dışından dönüş yaparak toplam 2 * points_per_turn
        sayıda waypoint üretir. 2. direğin dışından dönüş kuralını garanti eder.
        """
        waypoints: List[Waypoint] = []
        p1_x, p1_y = pole1_xy
        p2_x, p2_y = pole2_xy

        # 1. Aşama: 2. Direğin dışından dönüş (x >= p2_x, -pi/2 -> +pi/2)
        thetas_p2 = np.linspace(-np.pi / 2.0, np.pi / 2.0, points_per_turn)
        for theta in thetas_p2:
            wx = p2_x + turn_radius_m * math.cos(theta)
            wy = p2_y + turn_radius_m * math.sin(theta)
            waypoints.append(Waypoint(
                x_m=round(wx, 2),
                y_m=round(wy, 2),
                z_m=altitude_m,
                speed_mps=self.default_speed,
                action="POLE_2_OUTER_TURN",
                pole_id=2,
                is_outer_turn=True
            ))

        # 2. Aşama: 1. Direğin dışından dönüş (x <= p1_x, +pi/2 -> +3*pi/2)
        thetas_p1 = np.linspace(np.pi / 2.0, 3.0 * np.pi / 2.0, points_per_turn)
        for theta in thetas_p1:
            wx = p1_x + turn_radius_m * math.cos(theta)
            wy = p1_y + turn_radius_m * math.sin(theta)
            waypoints.append(Waypoint(
                x_m=round(wx, 2),
                y_m=round(wy, 2),
                z_m=altitude_m,
                speed_mps=self.default_speed,
                action="POLE_1_OUTER_TURN",
                pole_id=1,
                is_outer_turn=True
            ))

        # Heading hesapla
        for i in range(len(waypoints)):
            next_wp = waypoints[(i + 1) % len(waypoints)]
            dx = next_wp.x_m - waypoints[i].x_m
            dy = next_wp.y_m - waypoints[i].y_m
            rad = math.atan2(dy, dx)
            waypoints[i].heading_deg = round((math.degrees(rad) + 360.0) % 360.0, 1)

        return waypoints

    def generate_v7_task1_full_route(
        self,
        pole_distance_m: float = 150.0,
        turn_radius_m: float = 25.0,
        altitude_m: float = 30.0,
        laps: int = 2,
        speed_mps: float = 10.0,
        center_xy: Tuple[float, float] = (0.0, 0.0),
        points_per_arc: int = 12
    ) -> List[Waypoint]:
        """
        TÜBİTAK TEKNOFEST 2026 V7 Şartnamesi Madde 6 Manevra Akışına Birebir Uyumlu Rota:
        1. Kalkış (Takeoff)
        2. Direk 2'ye düz uçuş (Straight to Pole 2)
        3. 2. Direğin dışından ilk dönüş (Outside turn around Pole 2)
        4. 150m direkler etrafında ardışık 2 tam tur '∞' (Sekiz) deseni (Two consecutive Figure-8 laps)
        5. 2. Direğin arkasından/dışından son dönüş (Final outside turn behind Pole 2)
        6. Bitiş çizgisini geçiş (Cross finish line between poles)
        7. Direkler arasına kırımsız otonom iniş (Crash-free landing between poles)
        """
        waypoints: List[Waypoint] = []
        cx, cy = center_xy
        p1_x = cx - (pole_distance_m / 2.0)  # -75m
        p2_x = cx + (pole_distance_m / 2.0)  # +75m
        p_y = cy                             # 0m
        r = turn_radius_m

        def add_wp(x: float, y: float, z: float, spd: float, act: str, p_id: Optional[int] = None, outer: bool = False):
            # Önceki noktadan heading türet
            hdg = None
            if waypoints:
                prev = waypoints[-1]
                dx = x - prev.x_m
                dy = y - prev.y_m
                if math.hypot(dx, dy) > 0.01:
                    rad = math.atan2(dy, dx)
                    hdg = round((math.degrees(rad) + 360.0) % 360.0, 1)
                    if prev.heading_deg is None:
                        prev.heading_deg = hdg

            waypoints.append(Waypoint(
                x_m=round(x, 2),
                y_m=round(y, 2),
                z_m=round(z, 2),
                speed_mps=spd,
                heading_deg=hdg,
                action=act,
                pole_id=p_id,
                is_outer_turn=outer
            ))

        # 1. Kalkış (Pist / Merkez)
        add_wp(cx, cy, 0.0, 0.0, "TAKEOFF_START")
        add_wp(cx, cy, altitude_m, spd=3.0, act="CLIMB_TO_CRUISE")

        # 2. Direk 2'ye düz uçuş
        # İHA Direk 2'nin dışından dolanacak şekilde -y yönünden yaklaşır
        add_wp(cx + 30.0, cy - r, altitude_m, spd=speed_mps, act="OUTBOUND_TO_POLE_2")
        add_wp(p2_x, cy - r, altitude_m, spd=speed_mps, act="APPROACH_POLE_2_ENTRY", p_id=2)

        # 3. 2. Direğin dışından ilk dönüş (Outside turn around Pole 2)
        # Yay: -pi/2 den +pi/2 ye (x >= p2_x, yani direğin DIŞINDA)
        angles_p2 = np.linspace(-np.pi / 2.0, np.pi / 2.0, points_per_arc)
        for ang in angles_p2:
            wx = p2_x + r * math.cos(ang)
            wy = p_y + r * math.sin(ang)
            add_wp(wx, wy, altitude_m, spd=speed_mps, act="POLE_2_FIRST_OUTER_TURN", p_id=2, outer=True)

        # 4. Ardışık Figure-8 Turları
        for lap in range(1, laps + 1):
            lap_tag = f"LAP_{lap}"

            # Direk 2'den çıkıp merkeze ve Direk 1'e çapraz geçiş
            add_wp(cx, cy, altitude_m, spd=speed_mps, act=f"{lap_tag}_CENTER_CROSS_TO_P1")
            add_wp(p1_x, cy - r, altitude_m, spd=speed_mps, act=f"{lap_tag}_APPROACH_POLE_1", p_id=1)

            # Direk 1 Dış Dönüşü: +pi/2 den 3*pi/2 ye (x <= p1_x, yani direğin DIŞINDA)
            angles_p1 = np.linspace(-np.pi / 2.0, -3.0 * np.pi / 2.0, points_per_arc)
            for ang in angles_p1:
                wx = p1_x + r * math.cos(ang)
                wy = p_y + r * math.sin(ang)
                add_wp(wx, wy, altitude_m, spd=speed_mps, act=f"{lap_tag}_POLE_1_OUTER_TURN", p_id=1, outer=True)

            # Direk 1'den çıkıp merkeze ve Direk 2'ye çapraz geçiş
            add_wp(cx, cy, altitude_m, spd=speed_mps, act=f"{lap_tag}_CENTER_CROSS_TO_P2")
            add_wp(p2_x, cy - r, altitude_m, spd=speed_mps, act=f"{lap_tag}_APPROACH_POLE_2", p_id=2)

            # Direk 2 Dış Dönüşü
            for ang in angles_p2:
                wx = p2_x + r * math.cos(ang)
                wy = p_y + r * math.sin(ang)
                add_wp(wx, wy, altitude_m, spd=speed_mps, act=f"{lap_tag}_POLE_2_OUTER_TURN", p_id=2, outer=True)

        # 5. 2. Direğin arkasından/dışından son dönüş (Final outside turn behind Pole 2)
        # Zaten tur sonunda 2. direk dış dönüşü yapıldı, bitiş hizasına yönel
        add_wp(p2_x, cy + r, altitude_m, spd=speed_mps, act="POLE_2_FINAL_TURN_EXIT", p_id=2, outer=True)

        # 6. Bitiş çizgisini geçiş (Direkler arası merkez çizgi x=0)
        add_wp(cx + 20.0, cy, altitude_m, spd=speed_mps, act="APPROACH_FINISH_LINE")
        add_wp(cx, cy, altitude_m * 0.6, spd=speed_mps * 0.7, act="CROSS_FINISH_LINE")

        # 7. Direkler arasına kırımsız otonom iniş
        add_wp(cx, cy, altitude_m * 0.2, spd=2.0, act="LANDING_FINAL_APPROACH")
        add_wp(cx, cy, 0.0, spd=0.5, act="TOUCHDOWN")

        return waypoints

    def calculate_camera_footprint(self, altitude_m: float) -> Tuple[float, float]:
        """
        Verilen irtifada kameranın yerde taradığı dikdörtgen alanın (Genişlik, Yükseklik) ölçüsü.
        16:9 en-boy oranı varsayımı.
        """
        fov_rad = math.radians(self.fov_deg)
        width = 2.0 * altitude_m * math.tan(fov_rad / 2.0)
        height = width * (9.0 / 16.0)
        return width, height

    def generate_boustrophedon_grid(
        self,
        area_width_m: float = 100.0,
        area_height_m: float = 30.0,
        altitude_m: float = 35.0,
        overlap_ratio: float = 0.25,
        origin_xy: Tuple[float, float] = (0.0, 0.0)
    ) -> List[Waypoint]:
        """
        2. Görev için sıfır kör noktalı ve örtüşmeli Boustrophedon (Çim Biçme) arama rotası.
        TÜBİTAK TEKNOFEST 2026 V7 Şartnamesinde belirlenen 30m x 100m resmi tarama alanı ile tam uyumludur.
        """
        cam_w, _ = self.calculate_camera_footprint(altitude_m)
        max_allowed_step = max(5.0, area_height_m / 2.0)
        lane_step = min(max(5.0, cam_w * (1.0 - overlap_ratio)), max_allowed_step)

        ox, oy = origin_xy
        waypoints: List[Waypoint] = []

        curr_y = oy
        moving_forward = True

        while curr_y <= oy + area_height_m + 0.1:
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
                speed_mps=self.default_speed,
                action="SEARCH_LANE_START"
            ))
            waypoints.append(Waypoint(
                x_m=round(x_end, 2),
                y_m=round(curr_y, 2),
                z_m=altitude_m,
                speed_mps=self.default_speed,
                action="SEARCH_LANE_END"
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
                speed_mps=self.default_speed * 0.7,
                action="SPIRAL_SEARCH"
            ))

            theta += d_theta
            r += (step_radius_m / points_per_turn)

        return waypoints

    def verify_figure_eight_clearance(
        self,
        waypoints: List[Waypoint],
        pole_distance_m: float = 150.0,
        min_outer_margin_m: float = 5.0
    ) -> Dict[str, Any]:
        """
        Üretilen figure-8 rotasının 150m aralıklı direkleri ve 2. direğin dışından dönüş
        kuralını sağlayıp sağlamadığını matematiksel olarak denetler.
        """
        if not waypoints:
            return {"valid": False, "reason": "Boş rota"}

        p_half = pole_distance_m / 2.0  # 75.0m
        xs = [wp.x_m for wp in waypoints]
        min_x = min(xs)
        max_x = max(xs)

        # 1. Direk (x = -75) dışından dönüş var mı? (x < -75)
        pole_1_cleared = min_x <= (-p_half - min_outer_margin_m)

        # 2. Direk (x = +75) dışından dönüş var mı? (x > +75)
        pole_2_cleared = max_x >= (p_half + min_outer_margin_m)

        # Dış dönüş bayrağı olan en az bir nokta var mı?
        outer_turns = [wp for wp in waypoints if wp.is_outer_turn and wp.pole_id == 2]
        pole_2_outer_verified = len(outer_turns) > 0 and pole_2_cleared

        is_valid = pole_1_cleared and pole_2_cleared and pole_2_outer_verified

        return {
            "valid": is_valid,
            "min_x": min_x,
            "max_x": max_x,
            "pole_1_cleared": pole_1_cleared,
            "pole_2_cleared": pole_2_cleared,
            "pole_2_outer_turn_verified": pole_2_outer_verified,
            "total_waypoints": len(waypoints)
        }
