"""
TEKNOFEST 2026 Uluslararası İHA - Döner Kanat Görev 3 Bonus Transfer Planlayıcısı
---------------------------------------------------------------------------------
Resmi 2026 V7 Şartnamesi Madde 8.3 Tablo 3:
- AY (+10 Puan): Hedef A (Altıgen) üzerindeki yükü yerden kavrama
- BY (+10 Puan): Kavranan yükü Hedef B (Üçgen) üzerine taşıyıp bırakma
Toplam +20 Bonus Puan kazandıran otonom seyrüsefer ve transfer planlayıcısıdır.
"""

from dataclasses import dataclass
from enum import Enum
import math
from typing import List, Tuple, Optional, Dict, Any
from src.avionics.payload_grabber import PayloadGrabberController, GrabberState


class TransferPhase(str, Enum):
    STANDBY = "STANDBY"
    NAVIGATE_TO_TARGET_A = "NAVIGATE_TO_TARGET_A"  # Hedef A'ya intikal
    PRECISION_DESCENT_A = "PRECISION_DESCENT_A"    # Altıgen merkezine hassas dikey alçalış
    GRASP_PAYLOAD = "GRASP_PAYLOAD"                # Kıskaçla yükü kavrama (AY süreci)
    CLIMB_TRANSIT = "CLIMB_TRANSIT"                # Güvenli transfer irtifasına tırmanış
    NAVIGATE_TO_TARGET_B = "NAVIGATE_TO_TARGET_B"  # Hedef B'ye intikal
    PRECISION_DESCENT_B = "PRECISION_DESCENT_B"    # Üçgen merkezine alçalış
    RELEASE_PAYLOAD = "RELEASE_PAYLOAD"            # Yükü bırakma (BY süreci)
    COMPLETED = "COMPLETED"                        # Görev 3 başarıyla tamamlandı
    ABORTED = "ABORTED"                            # Güvenlik nedeniyle iptal


@dataclass
class TransferStatus:
    phase: TransferPhase
    target_a_coords: Tuple[float, float]
    target_b_coords: Tuple[float, float]
    distance_to_current_target_m: float
    current_altitude_m: float
    target_altitude_m: float
    ay_bonus_awarded: bool
    by_bonus_awarded: bool
    total_bonus_points: int  # 0, 10 veya 20
    is_active: bool


class PayloadTransferPlanner:
    def __init__(
        self,
        target_a_xy: Tuple[float, float] = (-20.0, 45.0),
        target_b_xy: Tuple[float, float] = (25.0, 45.0),
        transit_altitude_m: float = 15.0,
        pickup_hover_altitude_m: float = 0.35,
        drop_hover_altitude_m: float = 1.20,
        acceptance_radius_m: float = 0.40,
        grabber_controller: Optional[PayloadGrabberController] = None
    ):
        self.target_a_xy = target_a_xy
        self.target_b_xy = target_b_xy
        self.transit_altitude_m = transit_altitude_m
        self.pickup_hover_altitude_m = pickup_hover_altitude_m
        self.drop_hover_altitude_m = drop_hover_altitude_m
        self.acceptance_radius_m = acceptance_radius_m

        self.grabber = grabber_controller or PayloadGrabberController()
        self.phase = TransferPhase.STANDBY
        self.ay_awarded = False
        self.by_awarded = False

    def start_transfer_mission(self) -> bool:
        """Görev 3 (Yerden Alma ve Taşıma) sürecini başlatır."""
        self.grabber.arm()
        self.phase = TransferPhase.NAVIGATE_TO_TARGET_A
        self.ay_awarded = False
        self.by_awarded = False
        return True

    def abort_mission(self) -> bool:
        """Görev 3'ü acil durdurur ve kıskacı güvenli pozisyona alır."""
        self.phase = TransferPhase.ABORTED
        self.grabber.disarm()
        return True

    def update(
        self,
        uav_xy: Tuple[float, float],
        uav_alt_m: float,
        optical_lock_offset: Optional[Tuple[float, float]] = None,
        contact_switch: bool = False,
        motor_current_ma: float = 0.0,
        timestamp: Optional[float] = None
    ) -> TransferStatus:
        """
        Her kontrol adımında İHA pozisyonunu ve sensörleri işleyerek durum makinesini ilerletir.
        """
        ux, uy = uav_xy
        target_alt = self.transit_altitude_m

        # 1. HEDEF A'YA SEYİR
        if self.phase == TransferPhase.NAVIGATE_TO_TARGET_A:
            dist = math.hypot(self.target_a_xy[0] - ux, self.target_a_xy[1] - uy)
            target_alt = self.transit_altitude_m
            if dist <= 2.5:  # Hedef A bölgesine varıldı
                self.phase = TransferPhase.PRECISION_DESCENT_A

        # 2. HASSAS ALÇALIŞ (HEDEF A - ALTIĞEN)
        elif self.phase == TransferPhase.PRECISION_DESCENT_A:
            dist = math.hypot(self.target_a_xy[0] - ux, self.target_a_xy[1] - uy)
            target_alt = self.pickup_hover_altitude_m
            # Yük hizalandı ve irtifa kavrama seviyesine indi
            alt_ok = abs(uav_alt_m - self.pickup_hover_altitude_m) <= 0.20
            pos_ok = dist <= self.acceptance_radius_m
            if alt_ok and pos_ok:
                self.grabber.trigger_grasp(timestamp)
                self.phase = TransferPhase.GRASP_PAYLOAD

        # 3. YÜKÜ KAVRAMA VE AY BONUS KONTROLÜ
        elif self.phase == TransferPhase.GRASP_PAYLOAD:
            target_alt = self.pickup_hover_altitude_m
            # Sensörleri güncelle
            telem = self.grabber.update_sensors(
                current_ma=motor_current_ma,
                contact_switch=contact_switch,
                optical_presence=True,
                timestamp=timestamp
            )
            if telem.state == GrabberState.LOCKED_LOAD and telem.payload_secured:
                self.ay_awarded = True  # +10 PUAN AY KAZANILDI!
                self.phase = TransferPhase.CLIMB_TRANSIT

        # 4. GÜVENLİ İRTİFAYA TIRMANIŞ
        elif self.phase == TransferPhase.CLIMB_TRANSIT:
            target_alt = self.transit_altitude_m
            if uav_alt_m >= (self.transit_altitude_m - 1.5):
                self.phase = TransferPhase.NAVIGATE_TO_TARGET_B

        # 5. HEDEF B'YE SEYİR (ÜÇGEN)
        elif self.phase == TransferPhase.NAVIGATE_TO_TARGET_B:
            dist = math.hypot(self.target_b_xy[0] - ux, self.target_b_xy[1] - uy)
            target_alt = self.transit_altitude_m
            if dist <= 2.5:
                self.phase = TransferPhase.PRECISION_DESCENT_B

        # 6. HASSAS ALÇALIŞ (HEDEF B)
        elif self.phase == TransferPhase.PRECISION_DESCENT_B:
            dist = math.hypot(self.target_b_xy[0] - ux, self.target_b_xy[1] - uy)
            target_alt = self.drop_hover_altitude_m
            alt_ok = abs(uav_alt_m - self.drop_hover_altitude_m) <= 0.30
            pos_ok = dist <= self.acceptance_radius_m
            if alt_ok and pos_ok:
                self.grabber.trigger_release(timestamp)
                self.phase = TransferPhase.RELEASE_PAYLOAD

        # 7. BIRAKMA VE BY BONUS
        elif self.phase == TransferPhase.RELEASE_PAYLOAD:
            target_alt = self.drop_hover_altitude_m
            if self.grabber.state == GrabberState.RELEASED:
                self.by_awarded = True  # +10 PUAN BY KAZANILDI!
                self.phase = TransferPhase.COMPLETED

        # 8. TAMAMLANDI
        elif self.phase == TransferPhase.COMPLETED:
            target_alt = self.transit_altitude_m

        current_tgt = self.target_b_xy if "B" in self.phase.value else self.target_a_xy
        current_dist = math.hypot(current_tgt[0] - ux, current_tgt[1] - uy)

        bonus_total = (10 if self.ay_awarded else 0) + (10 if self.by_awarded else 0)

        return TransferStatus(
            phase=self.phase,
            target_a_coords=self.target_a_xy,
            target_b_coords=self.target_b_xy,
            distance_to_current_target_m=round(current_dist, 2),
            current_altitude_m=round(uav_alt_m, 2),
            target_altitude_m=round(target_alt, 2),
            ay_bonus_awarded=self.ay_awarded,
            by_bonus_awarded=self.by_awarded,
            total_bonus_points=bonus_total,
            is_active=self.phase not in (TransferPhase.STANDBY, TransferPhase.COMPLETED, TransferPhase.ABORTED)
        )
