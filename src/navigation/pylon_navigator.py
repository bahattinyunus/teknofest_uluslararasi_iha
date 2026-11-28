"""
TEKNOFEST 2026 Uluslararası İHA - 150m Direk (Pylon) Dış Dönüş ve Engel Sakınma Güdümü
======================================================================================
TÜBİTAK TEKNOFEST 2026 V7 Şartnamesi (Madde 8.3.1, 10.1 & 10.2) Uyumlu:
- Malatya Tulga sahasında 150m aralıklı 1. Direk (-75m, 0) ve 2. Direk (+75m, 0)
- Rüzgar sürüklenmesi ve azami yatış açısı (phi_max) kısıtlı dinamik dönüş yarıçapı:
      R_turn = V_ground^2 / (g * tan(phi_max))
- 2. Direk (ve 1. Direk) etrafında %100 DIŞTAN DÖNÜŞ (Outer Turn) garantili teğet/yay rota üretimi
- İşaretli sarım açısı (Signed Winding Angle) ile içten dönüş (Ceza 2: 10 puan) önleme kalkanı
- Dinamik silindirik engel / yasak bölge teğet sapma vektörü
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Any
import math


@dataclass
class PylonObstacle:
    """Silindirik engel veya direk tanımı."""
    name: str
    x_m: float
    y_m: float
    safety_radius_m: float = 12.0


@dataclass
class PylonGuidanceState:
    """Anlık direk dış dönüş güdüm ve sarım açısı durumu."""
    active_pylon: str
    distance_to_pylon_m: float
    recommended_turn_radius_m: float
    pole_1_winding_deg: float
    pole_2_winding_deg: float
    pole_1_outer_cleared: bool
    pole_2_outer_cleared: bool
    inner_turn_risk: bool
    completed_laps: int
    deflection_velocity_xy: Tuple[float, float]


class PylonNavigator:
    """
    150m aralıklı yarışma direkleri etrafında rüzgar kompanzasyonlu dış dönüş
    rotası üreten ve içten dönüş (Ceza 2) ihlalini gerçek zamanlı önleyen güdüm motoru.
    """

    GRAVITY = 9.80665

    def __init__(
        self,
        pole_distance_m: float = 150.0,
        min_turn_radius_m: float = 18.0,
        max_bank_angle_deg: float = 35.0,
        pylon_clearance_m: float = 14.0
    ):
        self.pole_distance_m = pole_distance_m
        self.pole_1_xy: Tuple[float, float] = (-pole_distance_m / 2.0, 0.0)
        self.pole_2_xy: Tuple[float, float] = (pole_distance_m / 2.0, 0.0)
        self.min_turn_radius_m = min_turn_radius_m
        self.max_bank_angle_deg = max_bank_angle_deg
        self.pylon_clearance_m = pylon_clearance_m

        self.obstacles: List[PylonObstacle] = [
            PylonObstacle("POLE_1", self.pole_1_xy[0], self.pole_1_xy[1], pylon_clearance_m),
            PylonObstacle("POLE_2", self.pole_2_xy[0], self.pole_2_xy[1], pylon_clearance_m),
        ]

        # Sarım açısı (winding angle) takip değişkenleri
        self._prev_angle_p1: Optional[float] = None
        self._prev_angle_p2: Optional[float] = None
        self.pole_1_winding_deg: float = 0.0
        self.pole_2_winding_deg: float = 0.0
        self.pole_1_outer_cleared: bool = False
        self.pole_2_outer_cleared: bool = False
        self.completed_laps: int = 0
        self._visited_outer_p1: bool = False
        self._visited_outer_p2: bool = False

    def compute_dynamic_turn_radius(self, airspeed_mps: float, wind_speed_mps: float = 0.0) -> float:
        """
        Hava hızı, arka rüzgar payı ve maksimum yatış açısından güvenli dönüş yarıçapını hesaplar.
        R = (V_a + V_w)^2 / (g * tan(phi_max))
        """
        v_worst = max(4.0, airspeed_mps + abs(wind_speed_mps))
        tan_phi = math.tan(math.radians(max(10.0, min(60.0, self.max_bank_angle_deg))))
        r_dyn = (v_worst ** 2) / (self.GRAVITY * tan_phi)
        return round(max(self.min_turn_radius_m, r_dyn), 2)

    def generate_outer_turn_figure_eight(
        self,
        altitude_m: float = 30.0,
        airspeed_mps: float = 16.0,
        wind_speed_mps: float = 0.0,
        laps: int = 2,
        arc_points: int = 12
    ) -> List[Tuple[float, float, float]]:
        """
        1. ve 2. direği kesinlikle DIŞARIDAN dönen (inner-turn imkansız) pürüzsüz
        2 turluk ∞ (sekiz) geçiş noktalarını (x, y, z) üretir.
        """
        r = self.compute_dynamic_turn_radius(airspeed_mps, wind_speed_mps)
        p1x, p1y = self.pole_1_xy
        p2x, p2y = self.pole_2_xy

        waypoints: List[Tuple[float, float, float]] = []

        for _ in range(max(1, laps)):
            # 1) Merkezden 2. Direğin güney-dış teğetine yaklaşma ve dış yay (-90° -> +90°, x >= p2x)
            for i in range(arc_points + 1):
                theta = -math.pi / 2.0 + math.pi * (i / arc_points)
                wx = p2x + r * math.cos(theta)
                wy = p2y + r * math.sin(theta)
                waypoints.append((round(wx, 2), round(wy, 2), round(altitude_m, 2)))

            # 2) Çapraz geçiş (Merkezden geçerek 1. Direğin güney-dış teğetine)
            waypoints.append((0.0, 0.0, round(altitude_m, 2)))

            # 3) 1. Direk etrafında dış yay (-90° -> -270° yani sol dıştan, x <= p1x)
            for i in range(arc_points + 1):
                theta = -math.pi / 2.0 - math.pi * (i / arc_points)
                wx = p1x + r * math.cos(theta)
                wy = p1y + r * math.sin(theta)
                waypoints.append((round(wx, 2), round(wy, 2), round(altitude_m, 2)))

            # 4) Merkeze dönüş
            waypoints.append((0.0, 0.0, round(altitude_m, 2)))

        return waypoints

    def add_obstacle(self, name: str, x_m: float, y_m: float, safety_radius_m: float = 12.0):
        """Ek silindirik engel (direk, kule, yasak bölge) tanımlar."""
        self.obstacles.append(PylonObstacle(name, x_m, y_m, safety_radius_m))

    def compute_obstacle_deflection(
        self,
        uav_xy: Tuple[float, float],
        desired_vel_xy: Tuple[float, float]
    ) -> Tuple[float, float]:
        """
        İHA herhangi bir direk/engel güvenlik yarıçapına girdiğinde dışa itici +
        teğet kaydırıcı sakınma hız vektörü üretir.
        """
        ux, uy = uav_xy
        vx, vy = desired_vel_xy
        deflect_x, deflect_y = 0.0, 0.0

        for obs in self.obstacles:
            dx = ux - obs.x_m
            dy = uy - obs.y_m
            dist = math.hypot(dx, dy)
            influence_r = obs.safety_radius_m * 1.4
            if dist < influence_r:
                if dist < 1e-3:
                    nx, ny = 1.0, 0.0
                else:
                    nx, ny = dx / dist, dy / dist
                # Mesafe azaldıkça artan dışa itme + saat yönü tersi teğet
                strength = ((influence_r - dist) / influence_r) * 6.0
                tx, ty = -ny, nx
                deflect_x += (nx * 1.2 + tx * 0.5) * strength
                deflect_y += (ny * 1.2 + ty * 0.5) * strength

        return (round(vx + deflect_x, 3), round(vy + deflect_y, 3))

    @staticmethod
    def _angle_delta_deg(prev_rad: float, curr_rad: float) -> float:
        diff = curr_rad - prev_rad
        while diff > math.pi:
            diff -= 2.0 * math.pi
        while diff < -math.pi:
            diff += 2.0 * math.pi
        return math.degrees(diff)

    def update(
        self,
        uav_xy: Tuple[float, float],
        uav_vel_xy: Tuple[float, float],
        airspeed_mps: float = 16.0,
        wind_speed_mps: float = 0.0
    ) -> PylonGuidanceState:
        """
        Canlı İHA konumundan direk dış dönüş sarım açılarını, içten dönüş riskini
        ve engel sakınma hız vektörünü günceller.
        """
        ux, uy = uav_xy
        p1x, p1y = self.pole_1_xy
        p2x, p2y = self.pole_2_xy

        d1 = math.hypot(ux - p1x, uy - p1y)
        d2 = math.hypot(ux - p2x, uy - p2y)

        # Direk 1 ve 2 etrafında sarım açısı biriktirme
        ang1 = math.atan2(uy - p1y, ux - p1x)
        ang2 = math.atan2(uy - p2y, ux - p2x)

        if d1 < 65.0:
            if self._prev_angle_p1 is not None:
                self.pole_1_winding_deg += self._angle_delta_deg(self._prev_angle_p1, ang1)
            self._prev_angle_p1 = ang1
            if ux <= p1x - 2.0:
                self._visited_outer_p1 = True
        else:
            self._prev_angle_p1 = None

        if d2 < 65.0:
            if self._prev_angle_p2 is not None:
                self.pole_2_winding_deg += self._angle_delta_deg(self._prev_angle_p2, ang2)
            self._prev_angle_p2 = ang2
            if ux >= p2x + 2.0:
                self._visited_outer_p2 = True
        else:
            self._prev_angle_p2 = None

        if self._visited_outer_p1 and abs(self.pole_1_winding_deg) >= 135.0:
            self.pole_1_outer_cleared = True
        if self._visited_outer_p2 and abs(self.pole_2_winding_deg) >= 135.0:
            self.pole_2_outer_cleared = True

        # Tam tur kontrolü
        if self.pole_1_outer_cleared and self.pole_2_outer_cleared and abs(ux) < 12.0:
            self.completed_laps += 1
            self.pole_1_outer_cleared = False
            self.pole_2_outer_cleared = False
            self._visited_outer_p1 = False
            self._visited_outer_p2 = False
            self.pole_1_winding_deg = 0.0
            self.pole_2_winding_deg = 0.0

        # İçten dönüş (Ceza 2) riski: 2. direğe yaklaşıp dışına çıkmadan geri dönüyorsa
        inner_turn_risk = False
        if (45.0 < ux < p2x - 1.0) and uav_vel_xy[0] < -1.0 and not self._visited_outer_p2:
            inner_turn_risk = True
        elif (p1x + 1.0 < ux < -45.0) and uav_vel_xy[0] > 1.0 and not self._visited_outer_p1:
            inner_turn_risk = True

        active_pylon = "POLE_2" if d2 <= d1 else "POLE_1"
        dist_active = min(d1, d2)
        turn_r = self.compute_dynamic_turn_radius(airspeed_mps, wind_speed_mps)
        deflected_vel = self.compute_obstacle_deflection(uav_xy, uav_vel_xy)

        return PylonGuidanceState(
            active_pylon=active_pylon,
            distance_to_pylon_m=round(dist_active, 2),
            recommended_turn_radius_m=turn_r,
            pole_1_winding_deg=round(self.pole_1_winding_deg, 1),
            pole_2_winding_deg=round(self.pole_2_winding_deg, 1),
            pole_1_outer_cleared=self.pole_1_outer_cleared,
            pole_2_outer_cleared=self.pole_2_outer_cleared,
            inner_turn_risk=inner_turn_risk,
            completed_laps=self.completed_laps,
            deflection_velocity_xy=deflected_vel
        )

    def reset(self):
        self._prev_angle_p1 = None
        self._prev_angle_p2 = None
        self.pole_1_winding_deg = 0.0
        self.pole_2_winding_deg = 0.0
        self.pole_1_outer_cleared = False
        self.pole_2_outer_cleared = False
        self._visited_outer_p1 = False
        self._visited_outer_p2 = False
        self.completed_laps = 0
