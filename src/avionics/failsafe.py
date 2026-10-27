"""
TEKNOFEST 2026 Uluslararası İHA - Aviyonik ve Acil Durum (Failsafe) Yöneticisi
----------------------------------------------------------------------------
2026 Yarışma Kural Kısıtlamaları:
- Azami İrtifa: 120m AGL (Aşılması durumunda kural ihlali)
- Geofence Sınırı: 500m yarıçap
- LiPo Batarya Sağlığı: 4S hücre başı 3.50V (RTL), 3.30V (Acil İniş)
- MavLink / GCS Kalp Atışı (Heartbeat) Zaman Aşımı: 3.0 saniye
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any, Optional, Tuple
import time


class FailsafeLevel(str, Enum):
    NOMINAL = "NOMINAL"
    WARNING = "WARNING"
    RTL_REQUIRED = "RTL_REQUIRED"
    LAND_IMMEDIATELY = "LAND_IMMEDIATELY"
    TERMINATE = "TERMINATE"


@dataclass
class AvionicsHealth:
    voltage_v: float
    current_a: float
    altitude_agl_m: float
    distance_from_home_m: float
    last_heartbeat_time: float
    satellites_visible: int
    ekf_healthy: bool


class FailsafeManager:
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        cfg = config or {}
        fs_cfg = cfg.get("failsafe", {})

        self.max_altitude_m = fs_cfg.get("max_altitude_agl_m", 120.0)
        self.geofence_radius_m = fs_cfg.get("geofence_radius_m", 500.0)
        self.battery_warning_v = fs_cfg.get("battery_warning_voltage", 14.8)
        self.battery_critical_v = fs_cfg.get("battery_critical_voltage", 14.0)
        self.battery_emergency_v = fs_cfg.get("battery_emergency_voltage", 13.2)
        self.heartbeat_timeout_s = fs_cfg.get("heartbeat_timeout_s", 3.0)

        self.failsafe_triggered = False
        self.active_level = FailsafeLevel.NOMINAL
        self.trigger_reason = ""
        self.last_check_time = time.monotonic()

    def evaluate(self, health: AvionicsHealth) -> Tuple[FailsafeLevel, str]:
        """
        Tüm telemetri ve donanım parametrelerini güvenlik limitlerine göre doğrular.
        """
        now = time.monotonic()
        self.last_check_time = now

        # 1. Acil Durum: Kritik Düşük Batarya (Hücre hasarı veya ani voltaj çökmesi)
        if health.voltage_v <= self.battery_emergency_v:
            self._set_failsafe(FailsafeLevel.LAND_IMMEDIATELY, f"ACİL: Kritik Düşük Batarya! ({health.voltage_v:.2f}V <= {self.battery_emergency_v}V)")
            return self.active_level, self.trigger_reason

        # 2. İrtifa İhlali (2026 Kuralı: 120m üstü diskalifiye)
        if health.altitude_agl_m > self.max_altitude_m:
            self._set_failsafe(FailsafeLevel.RTL_REQUIRED, f"KURAL İHLALİ TEHLİKESİ: İrtifa Limiti Aşıldı! ({health.altitude_agl_m:.1f}m > {self.max_altitude_m}m)")
            return self.active_level, self.trigger_reason

        # 3. Geofence Sınırı
        if health.distance_from_home_m > self.geofence_radius_m:
            self._set_failsafe(FailsafeLevel.RTL_REQUIRED, f"GEOFENCE AŞILDI: Güvenlik Alanı Dışında! ({health.distance_from_home_m:.1f}m > {self.geofence_radius_m}m)")
            return self.active_level, self.trigger_reason

        # 4. Haberleşme Kaybı (Link Loss)
        heartbeat_age = now - health.last_heartbeat_time
        if heartbeat_age > self.heartbeat_timeout_s:
            self._set_failsafe(FailsafeLevel.RTL_REQUIRED, f"HABERLEŞME KESİLDİ: GCS Kalp Atışı Alınamadı ({heartbeat_age:.1f}s)")
            return self.active_level, self.trigger_reason

        # 5. Batarya RTL Seviyesi
        if health.voltage_v <= self.battery_critical_v:
            self._set_failsafe(FailsafeLevel.RTL_REQUIRED, f"DÜŞÜK BATARYA: Güvenli RTL Başlatılıyor ({health.voltage_v:.2f}V)")
            return self.active_level, self.trigger_reason

        # 6. EKF / GPS Sağlığı
        if not health.ekf_healthy or health.satellites_visible < 6:
            self._set_failsafe(FailsafeLevel.WARNING, f"NAVİGASYON UYARISI: Yetersiz GPS/EKF (Uydu: {health.satellites_visible})")
            return self.active_level, self.trigger_reason

        # Nominal durum
        if self.active_level == FailsafeLevel.WARNING:
            self.active_level = FailsafeLevel.NOMINAL
            self.trigger_reason = ""

        return FailsafeLevel.NOMINAL, "Sistem Parametreleri Nominal"

    def _set_failsafe(self, level: FailsafeLevel, reason: str):
        self.active_level = level
        self.trigger_reason = reason
        if level in (FailsafeLevel.RTL_REQUIRED, FailsafeLevel.LAND_IMMEDIATELY, FailsafeLevel.TERMINATE):
            self.failsafe_triggered = True
            print(f"[FAILSAFE KRİTİK] Düzey: {level.value} | Sebep: {reason}")
        else:
            print(f"[FAILSAFE UYARI] {reason}")

    def reset(self):
        """Güvenlik durumunu sıfırlar."""
        self.failsafe_triggered = False
        self.active_level = FailsafeLevel.NOMINAL
        self.trigger_reason = ""
