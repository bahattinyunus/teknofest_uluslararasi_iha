"""
TEKNOFEST 2026 Uluslararası İHA - Görev Planlayıcı ve Durum Makinesi
-------------------------------------------------------------------
1. Görev (∞ Şeklinde Otonom Uçuş ve Koordinasyon) ve 2. Görev (İki Ayrı
Hedefe Çift Renkli Hassas Yük Bırakma) senaryolarını adım adım
yöneten sonlu durum makinesi (Finite State Machine - FSM).
"""

from enum import Enum
from typing import Dict, Any, Optional, List
import time


class MissionTask(str, Enum):
    TASK_1_COORDINATION = "TASK_1_COORDINATION"  # Sonsuz (∞) Otonom Uçuş & İniş
    TASK_2_DUAL_PAYLOAD = "TASK_2_DUAL_PAYLOAD"  # Çift Hedefe Çift Renk Yük Bırakma
    COMBINED_FULL = "COMBINED_FULL"              # Tam Görev Dizisi


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
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.active_task = MissionTask.TASK_2_DUAL_PAYLOAD
        self.state = MissionState.IDLE
        self.previous_state = MissionState.IDLE

        self.state_enter_time = time.monotonic()
        self.payloads_dropped = 0
        self.max_payloads = 2
        self.figure_eight_laps_completed = 0
        self.required_figure_eight_laps = 1

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

    def update(
        self,
        altitude_agl: float,
        target_a_detected: bool,
        target_a_locked: bool,
        target_b_detected: bool,
        target_b_locked: bool,
        ballistics_ready: bool,
        failsafe_triggered: bool
    ) -> MissionState:
        """
        Durum geçiş mantığını çalıştırır ve yeni durumu döndürür.
        """
        if failsafe_triggered and self.state != MissionState.EMERGENCY_FAILSAFE:
            self.transition_to(MissionState.EMERGENCY_FAILSAFE, "Acil durum protokolü tetiklendi")
            return self.state

        elapsed = self.time_in_current_state()

        if self.state == MissionState.IDLE:
            pass  # Dışarıdan start_mission çağrısı beklenir

        elif self.state == MissionState.PREFLIGHT_CHECK:
            if elapsed > 1.5:  # Ön kontroller tamamlandı
                self.transition_to(MissionState.TAKEOFF, "Pre-flight kontrolleri başarılı")

        elif self.state == MissionState.TAKEOFF:
            # Belirlenen irtifaya ulaşıldı mı? (ör. 30m)
            if altitude_agl >= 25.0 or elapsed > 8.0:
                if self.active_task == MissionTask.TASK_1_COORDINATION:
                    self.transition_to(MissionState.FIGURE_EIGHT_NAV, "İrtifaya ulaşıldı, ∞ manevrası başlıyor")
                else:
                    self.transition_to(MissionState.SEARCHING_TARGET_A, "İrtifaya ulaşıldı, Hedef A taraması başlıyor")

        elif self.state == MissionState.FIGURE_EIGHT_NAV:
            # 1. Görev: ∞ manevrası simülasyonu / tamamlama
            if elapsed > 15.0:  # Manevra tamamlandı
                self.figure_eight_laps_completed += 1
                if self.active_task == MissionTask.COMBINED_FULL:
                    self.transition_to(MissionState.SEARCHING_TARGET_A, "∞ Manevrası bitti, Hedef A'ya geçiliyor")
                else:
                    self.transition_to(MissionState.RETURN_TO_LAUNCH, "1. Görev başarıyla tamamlandı")

        elif self.state == MissionState.SEARCHING_TARGET_A:
            if target_a_detected:
                self.transition_to(MissionState.LOCKING_TARGET_A, "Hedef A (Mavi Altıgen) tespit edildi")

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
                self.transition_to(MissionState.LOCKING_TARGET_B, "Hedef B (Kırmızı Üçgen) tespit edildi")

        elif self.state == MissionState.LOCKING_TARGET_B:
            if not target_b_detected and elapsed > 5.0:
                self.transition_to(MissionState.SEARCHING_TARGET_B, "Hedef B kilidi kayboldu, aramaya dön")
            elif target_b_locked and ballistics_ready:
                self.transition_to(MissionState.DROPPING_PAYLOAD_2, "Hedef B kilitlendi ve balistik bırakma penceresine girildi")

        elif self.state == MissionState.DROPPING_PAYLOAD_2:
            if elapsed > 1.0:
                self.payloads_dropped += 1
                self.transition_to(MissionState.MISSION_COMPLETE, "2. Yük (Mavi) bırakıldı, tüm görevler icra edildi")

        elif self.state == MissionState.MISSION_COMPLETE:
            if elapsed > 1.0:
                self.transition_to(MissionState.RETURN_TO_LAUNCH, "Otonom eve dönüş (RTL) başlatıldı")

        elif self.state == MissionState.RETURN_TO_LAUNCH:
            if elapsed > 10.0 or altitude_agl < 10.0:
                self.transition_to(MissionState.LANDING, "Kalkış noktasına varıldı, iniş fazı")

        elif self.state == MissionState.LANDING:
            if altitude_agl <= 0.5 or elapsed > 8.0:
                self.transition_to(MissionState.LANDED, "Kırımsız otonom iniş teyit edildi")

        elif self.state == MissionState.EMERGENCY_FAILSAFE:
            # Acil durum güvenli iniş kontrolü
            if altitude_agl <= 0.5:
                self.transition_to(MissionState.LANDED, "Acil iniş tamamlandı")

        return self.state
