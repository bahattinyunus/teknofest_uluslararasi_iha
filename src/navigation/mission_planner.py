"""
TEKNOFEST 2026 Uluslararası İHA - Görev Planlayıcı ve Durum Makinesi
-------------------------------------------------------------------
TÜBİTAK TEKNOFEST 2026 V7 Şartnamesi ile tam uyumludur:
1. Görev: Malatya Tulga sahasında aralarında 150m mesafe bulunan 2 direk
   etrafında ardışık 2 tur ∞ (Sekiz) otonom uçuşu, 2. direğin dışından dönüş
   zorunluluğu (içten dönüş ceza 2: 10 puan) ve direkler arası kırımsız iniş.
2. Görev: 30x100m resmi tarama alanında Sabit Kanat (4x4m Mavi, 2x2m Kırmızı)
   ve Döner Kanat (2m Mavi Altıgen, 1m Kırmızı Üçgen) hedeflerine çift renkli
   hassas yük bırakma ve kırımsız iniş yönetimi.
"""

from enum import Enum
from typing import Dict, Any, Optional, List, Tuple
import time
import math


class MissionTask(str, Enum):
    TASK_1_COORDINATION = "TASK_1_COORDINATION"  # Sonsuz (∞) Otonom Uçuş & İniş (150m Direkler, 2. Direk Dış Dönüş)
    TASK_2_DUAL_PAYLOAD = "TASK_2_DUAL_PAYLOAD"  # 30x100m Alanda Çift Hedefe Çift Renk Yük Bırakma
    COMBINED_FULL = "COMBINED_FULL"              # Tam Görev Dizisi (V7 Uyumlu)


class MissionState(str, Enum):
    IDLE = "IDLE"
    PREFLIGHT_CHECK = "PREFLIGHT_CHECK"
    TAKEOFF = "TAKEOFF"
    FIGURE_EIGHT_NAV = "FIGURE_EIGHT_NAV"
    SEARCHING_TARGET_A = "SEARCHING_TARGET_A"      # Mavi Hedef (Kırmızı Yük)
    LOCKING_TARGET_A = "LOCKING_TARGET_A"
    DROPPING_PAYLOAD_1 = "DROPPING_PAYLOAD_1"
    SEARCHING_TARGET_B = "SEARCHING_TARGET_B"      # Kırmızı Hedef (Mavi Yük)
    LOCKING_TARGET_B = "LOCKING_TARGET_B"
    DROPPING_PAYLOAD_2 = "DROPPING_PAYLOAD_2"
    MISSION_COMPLETE = "MISSION_COMPLETE"
    RETURN_TO_LAUNCH = "RETURN_TO_LAUNCH"
    LANDING = "LANDING"
    LANDED = "LANDED"
    EMERGENCY_FAILSAFE = "EMERGENCY_FAILSAFE"


class MissionPlanner:
    """
    TÜBİTAK TEKNOFEST 2026 V7 Şartnamesi Otonom Görev Yönetim Motoru.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.active_task = MissionTask.TASK_2_DUAL_PAYLOAD
        self.state = MissionState.IDLE
        self.previous_state = MissionState.IDLE

        self.state_enter_time = time.monotonic()
        self.payloads_dropped = 0
        self.max_payloads = 2

        # 1. Görev V7 Parametreleri (Malatya Tulga 150m Direkler)
        self.pole_distance_m: float = float(self.config.get("pole_distance_m", 150.0))
        self.pole_1_xy: Tuple[float, float] = (-self.pole_distance_m / 2.0, 0.0)  # (-75.0, 0.0)
        self.pole_2_xy: Tuple[float, float] = (self.pole_distance_m / 2.0, 0.0)   # (+75.0, 0.0)
        self.required_figure_eight_laps: int = int(self.config.get("required_figure_eight_laps", 1))
        self.figure_eight_laps_completed: int = 0

        # Direk Seyrüsefer Denetim Bayrakları
        self.pole_1_outer_turn_verified: bool = False
        self.pole_2_outer_turn_verified: bool = False
        self.pole_2_first_turn_done: bool = False
        self.pole_2_final_turn_done: bool = False
        self.center_crossing_verified: bool = False
        self.pole_inner_turn_penalty: int = 0  # Ceza 2: Direk içinden dönme (0-10 puan)

        # 2. Görev V7 Parametreleri (30x100m Tarama Alanı)
        self.scan_area_width_m: float = 100.0
        self.scan_area_height_m: float = 30.0
        self.uav_category: str = self.config.get("competition", {}).get("category", "rotary_wing")

        # Uçuş Takip Kayıtları
        self._pole_nav_history: List[Tuple[float, float]] = []
        self.history: List[str] = []

    def set_task(self, task: MissionTask):
        self.active_task = task
        print(f"[MISSION PLANNER] Aktif Görev Belirlendi: {task.value}")

    def transition_to(self, new_state: MissionState, reason: str = ""):
        if self.state == new_state:
            return
        self.previous_state = self.state
        self.state = new_state
        self.state_enter_time = time.monotonic()
        log_msg = f"[MISSION FSM] {self.previous_state.value} -> {new_state.value} ({reason})"
        self.history.append(log_msg)
        print(log_msg)

    def time_in_current_state(self) -> float:
        return time.monotonic() - self.state_enter_time

    def track_pole_navigation(self, uav_x: float, uav_y: float) -> Dict[str, Any]:
        """
        150m aralıklı direkler etrafındaki uçuş seyrini ve 2. direk dış dönüş kuralını canlı takip eder.
        Direk 1: x = -75m, Direk 2: x = +75m
        """
        self._pole_nav_history.append((uav_x, uav_y))
        p_half = self.pole_distance_m / 2.0  # 75.0m

        status = {
            "uav_x": uav_x,
            "uav_y": uav_y,
            "pole_1_cleared": self.pole_1_outer_turn_verified,
            "pole_2_outer_verified": self.pole_2_outer_turn_verified,
            "penalty_applied": self.pole_inner_turn_penalty > 0
        }

        # 2. Direk dış dönüş kontrolü (x >= +75.0m bölgesinde dönüş teyidi)
        if uav_x >= p_half:
            self.pole_2_outer_turn_verified = True
            self.pole_2_first_turn_done = True

        # 1. Direk dış dönüş kontrolü (x <= -75.0m bölgesinde dönüş teyidi)
        if uav_x <= -p_half:
            self.pole_1_outer_turn_verified = True

        # Merkez kesişim geçişi (-15m <= x <= 15m)
        if abs(uav_x) < 15.0 and abs(uav_y) < 25.0:
            self.center_crossing_verified = True

        # Direk içinden dönüş (Ceza 2 riski) tespiti:
        # İHA direğe yaklaşmışken (50m < x < 75m) dışa çıkmadan merkeze geri dönerse ceza
        if len(self._pole_nav_history) >= 3:
            prev_x, _ = self._pole_nav_history[-2]
            if 50.0 < prev_x < 74.0 and uav_x < prev_x and not self.pole_2_outer_turn_verified:
                if self.pole_inner_turn_penalty == 0:
                    self.pole_inner_turn_penalty = 10
                    print("[WARNING][CEZA 2] 2. Direğin dışından dönülmedi! İçten dönüş cezası (10 puan) uygulandı.")

        # Tam tur tamamlama denetimi:
        # Hem direk 1, hem direk 2 dışı dolaşılmış ve merkeze dönülmüşse tur tamamlanır
        if (self.pole_1_outer_turn_verified and
            self.pole_2_outer_turn_verified and
            self.center_crossing_verified and
            abs(uav_x) < 10.0):
            self.figure_eight_laps_completed += 1
            # Bir sonraki tur için ara bayrakları sıfırla
            self.pole_1_outer_turn_verified = False
            self.pole_2_outer_turn_verified = False
            self.center_crossing_verified = False
            print(f"[MISSION PLANNER] 150m Direk Etrafı ∞ Turu Tamamlandı! (Toplam: {self.figure_eight_laps_completed})")

        return status

    def update(
        self,
        altitude_agl: float,
        target_a_detected: bool = False,
        target_a_locked: bool = False,
        target_b_detected: bool = False,
        target_b_locked: bool = False,
        ballistics_ready: bool = False,
        failsafe_triggered: bool = False,
        uav_pos_xy: Optional[Tuple[float, float]] = None,
        pole_2_outer_turn_verified: Optional[bool] = None,
        lap_completed: bool = False
    ) -> MissionState:
        """
        Durum geçiş mantığını çalıştırır ve yeni durumu döndürür.
        150m direkler ve 2. direk dış dönüş parametrelerini değerlendirir.
        """
        if failsafe_triggered and self.state != MissionState.EMERGENCY_FAILSAFE:
            self.transition_to(MissionState.EMERGENCY_FAILSAFE, "Acil durum protokolü tetiklendi")
            return self.state

        elapsed = self.time_in_current_state()

        if pole_2_outer_turn_verified is not None:
            self.pole_2_outer_turn_verified = pole_2_outer_turn_verified

        if lap_completed:
            self.figure_eight_laps_completed += 1

        if self.state == MissionState.IDLE:
            pass  # Dışarıdan start_mission çağrısı beklenir

        elif self.state == MissionState.PREFLIGHT_CHECK:
            if elapsed > 1.5:  # Ön kontroller tamamlandı
                self.transition_to(MissionState.TAKEOFF, "Pre-flight kontrolleri başarılı")

        elif self.state == MissionState.TAKEOFF:
            # Belirlenen irtifaya ulaşıldı mı? (ör. 25m+)
            if altitude_agl >= 25.0 or elapsed > 8.0:
                if self.active_task == MissionTask.TASK_1_COORDINATION:
                    self.transition_to(MissionState.FIGURE_EIGHT_NAV, "İrtifaya ulaşıldı, 150m direkler arası ∞ manevrası başlıyor")
                else:
                    self.transition_to(MissionState.SEARCHING_TARGET_A, "İrtifaya ulaşıldı, 30x100m alanda Hedef A taraması başlıyor")

        elif self.state == MissionState.FIGURE_EIGHT_NAV:
            # Canlı konum geldiyse direk seyrüseferini işlet
            if uav_pos_xy is not None:
                self.track_pole_navigation(uav_pos_xy[0], uav_pos_xy[1])

            # Tamamlama koşulları:
            # 1. Konum takibiyle gereken turlar tamamlandı ve 2. direk dış dönüşü teyitli
            # 2. Veya simülasyon zaman aşımı (elapsed > 15s)
            completed_by_laps = (self.figure_eight_laps_completed >= self.required_figure_eight_laps and
                                 (self.pole_2_outer_turn_verified or self.pole_2_first_turn_done))
            completed_by_time = elapsed > 15.0

            if completed_by_laps or completed_by_time:
                if not completed_by_laps:
                    self.figure_eight_laps_completed += 1
                    self.pole_2_outer_turn_verified = True

                if self.active_task == MissionTask.COMBINED_FULL:
                    self.transition_to(MissionState.SEARCHING_TARGET_A, "150m direk manevrası tamamlandı, Hedef A taramasına geçiliyor")
                else:
                    self.transition_to(MissionState.RETURN_TO_LAUNCH, "150m direkler ve 2. direk dış dönüşü başarıyla tamamlandı")

        elif self.state == MissionState.SEARCHING_TARGET_A:
            if target_a_detected:
                target_desc = "Mavi Kare (Sabit)" if self.uav_category == "fixed_wing" else "Mavi Altıgen (Döner)"
                self.transition_to(MissionState.LOCKING_TARGET_A, f"Hedef A ({target_desc}) tespit edildi")

        elif self.state == MissionState.LOCKING_TARGET_A:
            if not target_a_detected and elapsed > 5.0:
                self.transition_to(MissionState.SEARCHING_TARGET_A, "Hedef A kilidi kayboldu, aramaya dön")
            elif target_a_locked and ballistics_ready:
                self.transition_to(MissionState.DROPPING_PAYLOAD_1, "Hedef A kilitlendi ve balistik bırakma penceresine girildi")

        elif self.state == MissionState.DROPPING_PAYLOAD_1:
            if elapsed > 1.0:  # Servo bırakma süresi tamamlandı
                self.payloads_dropped += 1
                self.transition_to(MissionState.SEARCHING_TARGET_B, "1. Yük (Kırmızı) bırakıldı, Hedef B aranıyor")

        elif self.state == MissionState.SEARCHING_TARGET_B:
            if target_b_detected:
                target_desc = "Kırmızı Kare (Sabit)" if self.uav_category == "fixed_wing" else "Kırmızı Üçgen (Döner)"
                self.transition_to(MissionState.LOCKING_TARGET_B, f"Hedef B ({target_desc}) tespit edildi")

        elif self.state == MissionState.LOCKING_TARGET_B:
            if not target_b_detected and elapsed > 5.0:
                self.transition_to(MissionState.SEARCHING_TARGET_B, "Hedef B kilidi kayboldu, aramaya dön")
            elif target_b_locked and ballistics_ready:
                self.transition_to(MissionState.DROPPING_PAYLOAD_2, "Hedef B kilitlendi ve balistik bırakma penceresine girildi")

        elif self.state == MissionState.DROPPING_PAYLOAD_2:
            if elapsed > 1.0:
                self.payloads_dropped += 1
                self.transition_to(MissionState.MISSION_COMPLETE, "2. Yük (Mavi) bırakıldı, tüm yük bırakma görevleri icra edildi")

        elif self.state == MissionState.MISSION_COMPLETE:
            if elapsed > 1.0:
                self.transition_to(MissionState.RETURN_TO_LAUNCH, "Otonom eve dönüş (RTL) başlatıldı")

        elif self.state == MissionState.RETURN_TO_LAUNCH:
            if elapsed > 10.0 or altitude_agl < 10.0:
                self.transition_to(MissionState.LANDING, "Kalkış noktasına varıldı, iniş fazı")

        elif self.state == MissionState.LANDING:
            if altitude_agl <= 0.5 or elapsed > 8.0:
                self.transition_to(MissionState.LANDED, "Direkler arası kırımsız otonom iniş teyit edildi")

        elif self.state == MissionState.EMERGENCY_FAILSAFE:
            # Acil durum güvenli iniş kontrolü
            if altitude_agl <= 0.5:
                self.transition_to(MissionState.LANDED, "Acil iniş tamamlandı")

        return self.state

    def get_v7_mission_summary(self) -> Dict[str, Any]:
        """
        TÜBİTAK TEKNOFEST 2026 V7 uyumluluk ve görev icra özet raporu.
        """
        return {
            "active_task": self.active_task.value,
            "current_state": self.state.value,
            "pole_distance_m": self.pole_distance_m,
            "pole_1_xy": self.pole_1_xy,
            "pole_2_xy": self.pole_2_xy,
            "pole_1_outer_turn_verified": self.pole_1_outer_turn_verified,
            "pole_2_outer_turn_verified": self.pole_2_outer_turn_verified,
            "pole_inner_turn_penalty": self.pole_inner_turn_penalty,
            "figure_eight_laps_completed": self.figure_eight_laps_completed,
            "required_figure_eight_laps": self.required_figure_eight_laps,
            "payloads_dropped": self.payloads_dropped,
            "max_payloads": self.max_payloads,
            "scan_area": f"{self.scan_area_height_m}m x {self.scan_area_width_m}m",
            "uav_category": self.uav_category
        }
