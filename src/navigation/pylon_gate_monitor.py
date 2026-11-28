"""
TEKNOFEST 2026 Uluslararası İHA - 150m Referans Direkleri & Dış Dönüş Kapı İzleyici
===================================================================================
Şartname Referansları:
  - Madde 8.3.1: 1. Direk (+75m, 0m) ve 2. Direk (-75m, 0m) arası 150 metre.
  - Madde 10.1 & 10.2:
      * Görev 1: 2. direğe düz uçuş -> 2. direk dış dönüşü -> 2 tam tur yatay ∞
        (iki direği içeride bırakarak) -> son dış dönüş -> bitiş çizgisi & iniş.
      * Görev 2: 2. direk dışından dönüldükten sonra 30m x 100m tarama alanında
        görüntü işleme hedef tespiti başlar (`detect_after_pole_2_outer_turn`).
  - Ceza Puanı 2 (0-10 puan): Direği içten dönme / dıştan dönmeme ihlali.

Bu modül, İHA'nın gerçek zamanlı (x, y) koordinatlarından:
  1) Direk 1 ve Direk 2 etrafındaki işaretli sarım açılarını (winding angle) hesaplar,
  2) Direk 2 dış dönüşü tamamlanmadan tarama alanına girilmesini (Ceza 2 riski) tespit eder,
  3) Görev 1 için tamamlanan ∞ tur sayısını ve bitiş çizgisi geçişini izler,
  4) Görev 2 için görüntü işleme tarama yetkisini (`vision_scan_authorized`) deterministik
     olarak açar.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple


class TurnComplianceState(Enum):
    PRE_POLE_2 = "PRE_POLE_2"
    POLE_2_OUTER_VERIFIED = "POLE_2_OUTER_VERIFIED"
    FIGURE_EIGHT_IN_PROGRESS = "FIGURE_EIGHT_IN_PROGRESS"
    TASK_1_LAPS_COMPLETE = "TASK_1_LAPS_COMPLETE"
    INSIDE_TURN_VIOLATION = "INSIDE_TURN_VIOLATION"


@dataclass
class PylonGateStatus:
    """Referans direkleri ve tarama kapısı anlık uyumluluk durumu."""
    compliance_state: TurnComplianceState
    pole_2_outer_turn_verified: bool
    pole_1_outer_turn_count: int
    pole_2_outer_turn_count: int
    figure_eight_laps_completed: int
    vision_scan_authorized: bool
    inside_scan_zone: bool
    finish_line_crossed: bool
    estimated_penalty_2_pts: float
    violations: List[str] = field(default_factory=list)


class PylonGateMonitor:
    """
    Malatya Tulga 150m Referans Direkleri Dış Dönüş ve ∞ Tur İzleyicisi.
    Koordinat sistemi (yerel saha merkezi 0,0):
      - Direk 1 (Pole 1): (+75.0, 0.0)
      - Direk 2 (Pole 2): (-75.0, 0.0)
      - Tarama Alanı    : x in [-50, +50], y in [-15, +15] (100m x 30m)
      - Başlangıç/Bitiş : x = 0.0 çizgisi
    """

    def __init__(
        self,
        pole_1_xy: Tuple[float, float] = (75.0, 0.0),
        pole_2_xy: Tuple[float, float] = (-75.0, 0.0),
        scan_zone_bounds: Tuple[float, float, float, float] = (-50.0, 50.0, -15.0, 15.0),
        required_figure_eight_laps: int = 2,
    ):
        self.pole_1_xy = pole_1_xy
        self.pole_2_xy = pole_2_xy
        self.scan_x_min, self.scan_x_max, self.scan_y_min, self.scan_y_max = scan_zone_bounds
        self.required_laps = max(1, int(required_figure_eight_laps))

        self.reset()

    def reset(self) -> None:
        self._prev_pos: Optional[Tuple[float, float]] = None
        self._pole_1_outer_side_visited = False
        self._pole_2_outer_side_visited = False
        self._pole_1_outer_turns = 0
        self._pole_2_outer_turns = 0
        self._pole_1_cum_angle = 0.0
        self._pole_2_cum_angle = 0.0
        self._prev_angle_p1: Optional[float] = None
        self._prev_angle_p2: Optional[float] = None
        self._pole_2_verified = False
        self._finish_crossed = False
        self._violations: List[str] = []
        self._penalty_2_pts = 0.0
        self._approached_pole_2 = False
        self._min_x_reached = 0.0

    @staticmethod
    def _angle_diff(a: float, b: float) -> float:
        """[-pi, pi] aralığında sarılmış açı farkı."""
        d = a - b
        while d > math.pi:
            d -= 2.0 * math.pi
        while d < -math.pi:
            d += 2.0 * math.pi
        return d

    def is_in_scan_zone(self, x: float, y: float) -> bool:
        return (
            self.scan_x_min <= x <= self.scan_x_max
            and self.scan_y_min <= y <= self.scan_y_max
        )

    def update(self, x_m: float, y_m: float) -> PylonGateStatus:
        """Yeni İHA yerel saha konumu (x_m, y_m) ile direk dış dönüşlerini ve ∞ turlarını günceller."""
        p1x, p1y = self.pole_1_xy
        p2x, p2y = self.pole_2_xy

        self._min_x_reached = min(self._min_x_reached, x_m)
        if x_m <= p2x + 25.0:
            self._approached_pole_2 = True

        # Direk 1 ve Direk 2 dış bölge kontrolü
        # Direk 2 dış tarafı: x < p2x (direğin arkası/dışı)
        if x_m < p2x - 1.0:
            self._pole_2_outer_side_visited = True
        # Direk 1 dış tarafı: x > p1x (direğin arkası/dışı)
        if x_m > p1x + 1.0:
            self._pole_1_outer_side_visited = True

        # Açısal sarım takibi (yalnızca direğe yakın bölgede: r < 65m)
        dist_p1 = math.hypot(x_m - p1x, y_m - p1y)
        dist_p2 = math.hypot(x_m - p2x, y_m - p2y)

        if dist_p2 < 65.0:
            ang2 = math.atan2(y_m - p2y, x_m - p2x)
            if self._prev_angle_p2 is not None:
                self._pole_2_cum_angle += abs(self._angle_diff(ang2, self._prev_angle_p2))
            self._prev_angle_p2 = ang2
            # En az ~150 derece dönülüp dış bölgeye çıkıldıysa dış dönüş doğrulanır
            if self._pole_2_outer_side_visited and self._pole_2_cum_angle >= math.radians(150.0):
                self._pole_2_outer_turns += 1
                self._pole_2_verified = True
                self._pole_2_cum_angle = 0.0
                self._pole_2_outer_side_visited = False
        else:
            self._prev_angle_p2 = None

        if dist_p1 < 65.0:
            ang1 = math.atan2(y_m - p1y, x_m - p1x)
            if self._prev_angle_p1 is not None:
                self._pole_1_cum_angle += abs(self._angle_diff(ang1, self._prev_angle_p1))
            self._prev_angle_p1 = ang1
            if self._pole_1_outer_side_visited and self._pole_1_cum_angle >= math.radians(150.0):
                self._pole_1_outer_turns += 1
                self._pole_1_cum_angle = 0.0
                self._pole_1_outer_side_visited = False
        else:
            self._prev_angle_p1 = None

        # Direk 2'ye yaklaşıp dışından dönmeden (x > p2x) geri doğuya dönerek tarama alanına girme ihlali
        in_scan = self.is_in_scan_zone(x_m, y_m)
        if (
            self._prev_pos is not None
            and self._approached_pole_2
            and not self._pole_2_verified
            and x_m > self._prev_pos[0] + 1.0
            and in_scan
            and self._min_x_reached >= p2x
        ):
            msg = (
                f"CEZA 2 İHLALİ: 2. Direk ({p2x:.0f}m) dışından dönülmeden tarama alanına girildi "
                f"(Min X={self._min_x_reached:.1f}m)!"
            )
            if msg not in self._violations:
                self._violations.append(msg)
                self._penalty_2_pts = min(10.0, self._penalty_2_pts + 5.0)

        # Tamamlanan ∞ turu: her tam tur 1 adet Direk 1 dış dönüşü + 1 adet Direk 2 dış dönüşü gerektirir
        laps_completed = min(self._pole_1_outer_turns, max(0, self._pole_2_outer_turns - 1))

        # Bitiş çizgisi geçişi (x = 0 çizgisi, gerekli turlar bittikten sonra)
        if self._prev_pos is not None and laps_completed >= self.required_laps:
            prev_x = self._prev_pos[0]
            if (prev_x < 0.0 <= x_m) or (prev_x > 0.0 >= x_m):
                self._finish_crossed = True

        self._prev_pos = (x_m, y_m)

        # Uyumluluk durumunu belirle
        if self._violations:
            state = TurnComplianceState.INSIDE_TURN_VIOLATION
        elif laps_completed >= self.required_laps:
            state = TurnComplianceState.TASK_1_LAPS_COMPLETE
        elif self._pole_1_outer_turns > 0 or self._pole_2_outer_turns > 1:
            state = TurnComplianceState.FIGURE_EIGHT_IN_PROGRESS
        elif self._pole_2_verified:
            state = TurnComplianceState.POLE_2_OUTER_VERIFIED
        else:
            state = TurnComplianceState.PRE_POLE_2

        return PylonGateStatus(
            compliance_state=state,
            pole_2_outer_turn_verified=self._pole_2_verified,
            pole_1_outer_turn_count=self._pole_1_outer_turns,
            pole_2_outer_turn_count=self._pole_2_outer_turns,
            figure_eight_laps_completed=laps_completed,
            vision_scan_authorized=self._pole_2_verified and in_scan,
            inside_scan_zone=in_scan,
            finish_line_crossed=self._finish_crossed,
            estimated_penalty_2_pts=round(self._penalty_2_pts, 2),
            violations=list(self._violations),
        )
