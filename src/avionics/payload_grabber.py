"""
TEKNOFEST 2026 Uluslararası İHA - Döner Kanat Yük Alma ve Taşıma Kıskaç Mekanizması
---------------------------------------------------------------------------------
Resmi 2026 V7 Şartnamesi Görev 3 Bonus (+20 Puan: AY=10, BY=10) isterleri için:
- Hedef A (Mavi Altıgen) üzerindeki yükü otonom kavrama (AY: +10 Puan)
- Hedef B (Kırmızı Üçgen) üzerine taşıyıp hassas bırakma (BY: +10 Puan)
için servo-mekanik veya elektro-manyetik tutucu mekanizma sürücüsüdür.
Akım geri bildirimi, temas anahtarı (microswitch) ve optik doğrulama ile
yükün güvenle kavrandığını doğrular.
"""

from dataclasses import dataclass
from enum import Enum
import time
from typing import Optional, Dict, Any


class GrabberState(str, Enum):
    DISARMED = "DISARMED"            # Güç kesik / emniyetli
    OPEN = "OPEN"                    # Kıskaç açık, yük kavramaya hazır
    GRASPING = "GRASPING"            # Kapanma manevrası icra ediliyor
    LOCKED_LOAD = "LOCKED_LOAD"      # Yük tam kavrandı, kilitlendi (AY tamam)
    RELEASING = "RELEASING"          # Bırakma komutu işleniyor
    RELEASED = "RELEASED"            # Yük hedefe bırakıldı (BY tamam)
    FAULT = "FAULT"                  # Mekanik sıkışma veya akım aşımı


@dataclass
class GrabberTelemetry:
    state: GrabberState
    servo_pwm_us: int
    current_ma: float
    contact_detected: bool
    payload_secured: bool
    ay_bonus_eligible: bool
    by_bonus_eligible: bool
    cycles_completed: int
    last_actuation_time: float


class PayloadGrabberController:
    # Standart PWM Eşikleri
    PWM_OPEN_US = 1100      # Tam açık
    PWM_CLOSE_US = 1900     # Tam kapalı / kavrama
    CURRENT_THRESHOLD_MA = 850.0  # Yük direnci akım eşiği (kavrama teyidi)
    OVERCURRENT_LIMIT_MA = 1600.0 # Sıkışma / arıza akım eşiği

    def __init__(
        self,
        pwm_open: int = PWM_OPEN_US,
        pwm_close: int = PWM_CLOSE_US,
        grasp_hold_time_s: float = 1.2
    ):
        self.pwm_open = pwm_open
        self.pwm_close = pwm_close
        self.grasp_hold_time_s = grasp_hold_time_s

        self.state = GrabberState.DISARMED
        self.current_pwm = pwm_open
        self.current_ma = 0.0
        self.contact_detected = False
        self.payload_secured = False
        self.ay_bonus_eligible = False
        self.by_bonus_eligible = False
        self.cycles_completed = 0
        self.last_actuation_time = 0.0
        self._grasp_start_time: Optional[float] = None

    def arm(self) -> bool:
        """Kıskaç mekanizmasını enerjilendirir ve açık pozisyona getirir."""
        self.state = GrabberState.OPEN
        self.current_pwm = self.pwm_open
        self.last_actuation_time = time.time()
        return True

    def disarm(self) -> bool:
        """Kıskaç mekanizmasını pasif konuma alır."""
        self.state = GrabberState.DISARMED
        self.current_pwm = self.pwm_open
        return True

    def trigger_grasp(self, timestamp: Optional[float] = None) -> bool:
        """
        Hedef A (Altıgen) üzerinde alçalış sonrası yükü kavramayı başlatır.
        AY Bonus (+10 Puan) sürecini tetikler.
        """
        if self.state not in (GrabberState.OPEN, GrabberState.DISARMED):
            return False

        t = timestamp or time.time()
        self.state = GrabberState.GRASPING
        self.current_pwm = self.pwm_close
        self.last_actuation_time = t
        self._grasp_start_time = t
        return True

    def trigger_release(self, timestamp: Optional[float] = None) -> bool:
        """
        Hedef B (Üçgen) üzerinde yükü bırakmayı başlatır.
        BY Bonus (+10 Puan) sürecini tamamlar.
        """
        if self.state != GrabberState.LOCKED_LOAD:
            return False

        t = timestamp or time.time()
        self.state = GrabberState.RELEASING
        self.current_pwm = self.pwm_open
        self.last_actuation_time = t
        self.payload_secured = False
        self.by_bonus_eligible = True
        self.cycles_completed += 1
        self.state = GrabberState.RELEASED
        return True

    def update_sensors(
        self,
        current_ma: float,
        contact_switch: bool,
        optical_presence: bool,
        timestamp: Optional[float] = None
    ) -> GrabberTelemetry:
        """
        Donanımsal sensörlerden (akım, switch, optik) gelen verilerle durum makinesini günceller.
        """
        t = timestamp or time.time()
        self.current_ma = current_ma
        self.contact_detected = contact_switch or optical_presence

        # Aşırı akım koruması
        if current_ma > self.OVERCURRENT_LIMIT_MA:
            self.state = GrabberState.FAULT
            self.current_pwm = self.pwm_open  # Güvenli açılma
            self.payload_secured = False
            return self.get_telemetry()

        # Kavrama süreci değerlendirmesi
        if self.state == GrabberState.GRASPING:
            elapsed = t - (self._grasp_start_time or t)
            # Yük kavrandı şartı: Belirli süre kapanma + (fiziksel temas veya akım direnci)
            has_resistance = current_ma >= self.CURRENT_THRESHOLD_MA
            if elapsed >= self.grasp_hold_time_s and (self.contact_detected or has_resistance):
                self.state = GrabberState.LOCKED_LOAD
                self.payload_secured = True
                self.ay_bonus_eligible = True  # AY Bonus kazanıldı!
            elif elapsed > (self.grasp_hold_time_s * 2.5):
                # Süre doldu ama yük kavranamadı
                self.state = GrabberState.OPEN
                self.current_pwm = self.pwm_open
                self.payload_secured = False

        return self.get_telemetry()

    def get_telemetry(self) -> GrabberTelemetry:
        return GrabberTelemetry(
            state=self.state,
            servo_pwm_us=self.current_pwm,
            current_ma=round(self.current_ma, 1),
            contact_detected=self.contact_detected,
            payload_secured=self.payload_secured,
            ay_bonus_eligible=self.ay_bonus_eligible,
            by_bonus_eligible=self.by_bonus_eligible,
            cycles_completed=self.cycles_completed,
            last_actuation_time=self.last_actuation_time
        )
