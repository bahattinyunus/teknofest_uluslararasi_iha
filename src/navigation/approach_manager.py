"""
TEKNOFEST 2026 Uluslararası İHA - Otonom Pas Geçme ve Yeniden Yaklaşma Yöneticisi
---------------------------------------------------------------------------------
Hedef yaklaşma açısı, rüzgar vektörü veya hedef kilidinin son anda bozulması
durumunda gereksiz veya isabetsiz yük bırakmayı engelleyen; İHA'yı güvenle tırmandırıp
rüzgarı karşıdan alacak şekilde (Headwind Approach) yeniden yaklaştıran (Go-Around)
otonom taktik yöneticisi.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Tuple, List, Optional
import math


class ApproachPhase(str, Enum):
    SEARCH_INTERCEPT = "SEARCH_INTERCEPT"
    INBOUND_ALIGNMENT = "INBOUND_ALIGNMENT"
    FINAL_RELEASE_RUN = "FINAL_RELEASE_RUN"
    GO_AROUND_CLIMB = "GO_AROUND_CLIMB"
    CIRCUIT_REPOSITION = "CIRCUIT_REPOSITION"


@dataclass
class ApproachCommand:
    phase: ApproachPhase
    target_heading_deg: float
    target_altitude_m: float
    target_speed_mps: float
    should_abort_drop: bool
    reposition_waypoints: Optional[List[Tuple[float, float]]] = None


class ApproachManager:
    def __init__(
        self,
        approach_altitude_m: float = 20.0,
        go_around_altitude_m: float = 32.0,
        circuit_radius_m: float = 35.0,
        max_attempts: int = 3
    ):
        self.approach_altitude = approach_altitude_m
        self.go_around_altitude = go_around_altitude_m
        self.circuit_radius = circuit_radius_m
        self.max_attempts = max_attempts

        self.current_phase = ApproachPhase.SEARCH_INTERCEPT
        self.attempt_count = 1
        self.phase_start_time = 0.0

    def calculate_ideal_inbound_heading(self, wind_direction_deg: float) -> float:
        """
        Rüzgarı doğrudan burundan (Headwind) almak için ideal yaklaşma açısını hesaplar.
        İdeal baş açısı = Rüzgarın estiği yön (Rüzgarın kaynağına doğru uçuş)
        """
        return (wind_direction_deg + 180.0) % 360.0

    def evaluate_approach(
        self,
        uav_pos_xy: Tuple[float, float],
        target_pos_xy: Tuple[float, float],
        uav_heading_deg: float,
        wind_direction_deg: float,
        miss_distance_m: float,
        hit_probability_pct: float,
        is_closing_in: bool
    ) -> ApproachCommand:
        """
        Anlık yaklaşma geometrisini değerlendirir ve devam veya pas geçme (Go-around) komutu üretir.
        """
        dx = target_pos_xy[0] - uav_pos_xy[0]
        dy = target_pos_xy[1] - uav_pos_xy[1]
        dist_to_target = math.hypot(dx, dy)
        bearing_to_target = (math.degrees(math.atan2(dy, dx)) + 360.0) % 360.0

        ideal_heading = self.calculate_ideal_inbound_heading(wind_direction_deg)
        angle_off = abs((bearing_to_target - uav_heading_deg + 180.0) % 360.0 - 180.0)

        # 1. Aşırı sapma veya hedef arkada kaldıysa (Overshoot) -> GO AROUND
        if not is_closing_in and dist_to_target > 8.0 and self.current_phase == ApproachPhase.FINAL_RELEASE_RUN:
            self.current_phase = ApproachPhase.GO_AROUND_CLIMB
            self.attempt_count += 1
            circuit_pts = self._generate_circuit_waypoints(target_pos_xy, ideal_heading)
            return ApproachCommand(
                phase=ApproachPhase.GO_AROUND_CLIMB,
                target_heading_deg=ideal_heading,
                target_altitude_m=self.go_around_altitude,
                target_speed_mps=7.0,
                should_abort_drop=True,
                reposition_waypoints=circuit_pts
            )

        # 2. Final Koşusu
        if dist_to_target <= 18.0 and angle_off < 25.0:
            self.current_phase = ApproachPhase.FINAL_RELEASE_RUN
            return ApproachCommand(
                phase=ApproachPhase.FINAL_RELEASE_RUN,
                target_heading_deg=bearing_to_target,
                target_altitude_m=self.approach_altitude,
                target_speed_mps=3.5,
                should_abort_drop=False
            )

        # 3. Giriş Hattı Hizalama
        self.current_phase = ApproachPhase.INBOUND_ALIGNMENT
        return ApproachCommand(
            phase=ApproachPhase.INBOUND_ALIGNMENT,
            target_heading_deg=bearing_to_target,
            target_altitude_m=self.approach_altitude,
            target_speed_mps=5.0,
            should_abort_drop=False
        )

    def _generate_circuit_waypoints(
        self,
        target_xy: Tuple[float, float],
        inbound_heading_deg: float
    ) -> List[Tuple[float, float]]:
        """Hedef çevresinde yeniden yaklaşma için gözyaşı (Teardrop/Racetrack) rotası oluşturur."""
        tx, ty = target_xy
        rad = math.radians(inbound_heading_deg)
        # Giriş yönünün gerisinde 45m başlangıç noktası
        entry_x = tx - 45.0 * math.cos(rad)
        entry_y = ty - 45.0 * math.sin(rad)

        # Yan ayrılma noktası
        perp_rad = rad + math.pi / 2.0
        turn_x = tx + 30.0 * math.cos(perp_rad)
        turn_y = ty + 30.0 * math.sin(perp_rad)

        return [(turn_x, turn_y), (entry_x, entry_y)]

    def reset(self):
        self.current_phase = ApproachPhase.SEARCH_INTERCEPT
        self.attempt_count = 1
