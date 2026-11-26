"""
TEKNOFEST 2026 Uluslararası İHA - Aviyonik ve Acil Durum (Failsafe) Yöneticisi
----------------------------------------------------------------------------
Resmi TÜBİTAK TEKNOFEST 2026 İHA Şartnamesi (V7 - Malatya Tulga) Uyumluluğu:
- Madde 7 & 8: Azami İrtifa: 120m AGL (Aşılması kural ihlali ve sıfır puan)
- Geofence Sınırı: 500m yarıçap
- LiPo Batarya Güvenliği: 4S LiPo hücre başı 3.70V (Uyarı), 3.50V / 14.0V (RTL/İniş), 3.30V / 13.2V (Acil İniş/FTS)
- Sinyal / Kalp Atışı (Heartbeat) Zaman Aşımı: 3.0 saniye (azami 5.0 saniye içinde fail-safe)
- 2 saniye içinde gücü kesebilen entegre emniyet anahtarı

Madde 9.2 Arıza Emniyet (Fail-Safe) Profilleri:
- Sabit Kanat (Fixed-Wing):
    1. Motor kesilmeli (cut throttle, 0% / 1000 us PWM)
    2. İrtifa dümeni tam yukarı (full elevator up, +100% / 2000 us PWM)
    3. İstikamet dümeni tam sağ (full rudder right, +100% / 2000 us PWM)
    4. Kanatçık tam sağ (full aileron right, +100% / 2000 us PWM)
    5. Varsa flaplar tam aşağı (full flaps down, +100% / 2000 us PWM)
    -> Amaç: İHA'yı kontrollü viril/sarmal çöküşe sokarak uçuş alanından uzaklaşmasını engellemek.

- Döner Kanat (Rotary-Wing):
    1. Yarım gaz kontrollü iniş / alçalma (half throttle descent, 50% / 1500 us PWM)
    2. Kesinlikle RTL yapılmamalıdır (NO RTL - rtl_allowed = False)!
    -> Amaç: GPS/link arızasında İHA'nın kontrolsüz kalkış noktasına yönelmesini engelleyip yerinde çöküşünü sağlamak.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, Optional, Tuple
import time


class VehicleType(str, Enum):
    FIXED_WING = "fixed_wing"
    ROTARY_WING = "rotary_wing"

    @classmethod
    def normalize(cls, val: Any) -> "VehicleType":
        if isinstance(val, cls):
            return val
        s = str(val).strip().lower()
        if s in ("fixed_wing", "fixed", "sabit", "sabit_kanat", "sabit-kanat"):
            return cls.FIXED_WING
        elif s in ("rotary_wing", "rotary", "doner", "döner", "doner_kanat", "döner_kanat", "döner-kanat"):
            return cls.ROTARY_WING
        return cls.FIXED_WING


class FailsafeLevel(str, Enum):
    NOMINAL = "NOMINAL"
    WARNING = "WARNING"
    RTL_REQUIRED = "RTL_REQUIRED"
    CONTROLLED_DESCENT = "CONTROLLED_DESCENT"
    LAND_IMMEDIATELY = "LAND_IMMEDIATELY"
    TERMINATE = "TERMINATE"


@dataclass
class FailSafeProfile:
    """TÜBİTAK 2026 Şartnamesi Madde 9.2 Uyumlu Arıza Emniyet Komut Profili."""
    vehicle_type: VehicleType
    throttle: str                    # "cut" veya "half_throttle_controlled_descent"
    throttle_pct: float              # 0.0 (cut) veya 50.0 (%50 yarım gaz)
    pitch: str                       # "full_up" veya "neutral"
    pitch_pct: float                 # 100.0 (tam yukarı) veya 0.0
    rudder: str                      # "full_right" veya "neutral"
    rudder_pct: float                # 100.0 (tam sağ) veya 0.0
    aileron: str                     # "full_right" veya "neutral"
    aileron_pct: float               # 100.0 (tam sağ) veya 0.0
    flaps: str                       # "full_down" veya "none"
    flaps_pct: float                 # 100.0 (tam aşağı) veya 0.0
    rtl_allowed: bool                # Döner kanatta KESİNLİKLE FALSE (NO RTL)
    pwm_channels: Dict[int, int]     # CH1: aileron, CH2: elevator, CH3: throttle, CH4: rudder, CH5: flaps
    description: str


@dataclass
class AvionicsHealth:
    voltage_v: float
    current_a: float
    altitude_agl_m: float
    distance_from_home_m: float
    last_heartbeat_time: float
    satellites_visible: int
    ekf_healthy: bool
    rc_signal_lost: bool = False


class FailsafeManager:
    """
    TEKNOFEST 2026 Aviyonik Güvenlik ve Şartname Uyumlu Fail-Safe Yöneticisi.
    Sabit ve Döner kanat konfigürasyonlarına göre emniyet profillerini yönetir.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None, vehicle_type: Optional[str] = None):
        cfg = config or {}
        fs_cfg = cfg.get("failsafe", {})
        comp_cfg = cfg.get("competition", {})

        # Araç Tipi Belirleme (Öncelik: parametre > failsafe.vehicle_type > competition.category > fixed_wing)
        raw_vtype = (
            vehicle_type
            or fs_cfg.get("vehicle_type")
            or comp_cfg.get("category")
            or "fixed_wing"
        )
        self.vehicle_type = VehicleType.normalize(raw_vtype)

        # RTL İzin Kuralı: Döner kanatta ŞARTNAME KURALI GEREĞİ KESİNLİKLE YASAKTIR (False)
        if self.vehicle_type == VehicleType.ROTARY_WING:
            self.rtl_allowed = False
        else:
            fixed_modes = fs_cfg.get("modes", {}).get("fixed_wing", {})
            self.rtl_allowed = fixed_modes.get("rtl_allowed", True)

        self.max_altitude_m = fs_cfg.get("max_altitude_agl_m", 120.0)
        self.geofence_radius_m = fs_cfg.get("geofence_radius_m", 500.0)
        self.battery_warning_v = fs_cfg.get("battery_warning_voltage", 14.8)
        self.battery_critical_v = fs_cfg.get("battery_critical_voltage", 14.0)
        self.battery_emergency_v = fs_cfg.get("battery_emergency_voltage", 13.2)
        self.heartbeat_timeout_s = fs_cfg.get("heartbeat_timeout_s", 3.0)
        self.signal_loss_delay_s = fs_cfg.get("signal_loss_failsafe_delay_s", 5.0)
        self.power_switch_max_cutoff_s = fs_cfg.get("power_switch_max_cutoff_s", 2.0)

        self.failsafe_triggered = False
        self.active_level = FailsafeLevel.NOMINAL
        self.trigger_reason = ""
        self.last_check_time = time.monotonic()
        self.active_profile: Optional[FailSafeProfile] = None

    def get_failsafe_profile(self) -> FailSafeProfile:
        """
        Şartname Madde 9.2 profiline göre aktüatör ve kontrol yüzeyi komutlarını üretir.
        - Sabit Kanat: Motor cut, tam yukarı irtifa, tam sağ rudder/aileron, tam açık flap.
        - Döner Kanat: Yarım gaz kontrollü iniş, RTL KESİNLİKLE YASAK.
        """
        if self.vehicle_type == VehicleType.FIXED_WING:
            return FailSafeProfile(
                vehicle_type=VehicleType.FIXED_WING,
                throttle="cut",
                throttle_pct=0.0,
                pitch="full_up",
                pitch_pct=100.0,
                rudder="full_right",
                rudder_pct=100.0,
                aileron="full_right",
                aileron_pct=100.0,
                flaps="full_down",
                flaps_pct=100.0,
                rtl_allowed=self.rtl_allowed,
                pwm_channels={
                    1: 2000,  # CH1 (Kanatçık / Aileron): Tam Sağ (2000 us)
                    2: 2000,  # CH2 (İrtifa / Elevator): Tam Yukarı (2000 us)
                    3: 1000,  # CH3 (Gaz / Throttle): Motor Kesildi (1000 us)
                    4: 2000,  # CH4 (İstikamet / Rudder): Tam Sağ (2000 us)
                    5: 2000   # CH5 (Flaplar / Flaps): Tam Aşağı (2000 us)
                },
                description="Sabit Kanat Fail-Safe: Motor susturuldu (cut throttle), irtifa tam yukarı, istikamet ve kanatçık tam sağ, flaplar tam açık."
            )
        else:
            return FailSafeProfile(
                vehicle_type=VehicleType.ROTARY_WING,
                throttle="half_throttle_controlled_descent",
                throttle_pct=50.0,
                pitch="neutral",
                pitch_pct=0.0,
                rudder="neutral",
                rudder_pct=0.0,
                aileron="neutral",
                aileron_pct=0.0,
                flaps="none",
                flaps_pct=0.0,
                rtl_allowed=False,  # Şartname gereği döner kanatta RTL yasaktır!
                pwm_channels={
                    1: 1500,  # CH1 (Roll): Nötr (1500 us)
                    2: 1500,  # CH2 (Pitch): Nötr (1500 us)
                    3: 1500,  # CH3 (Throttle): Yarım Gaz Kontrollü Alçalma (1500 us)
                    4: 1500,  # CH4 (Yaw): Nötr (1500 us)
                    5: 1000   # CH5: Nötr / Kullanılmıyor (1000 us)
                },
                description="Döner Kanat Fail-Safe: Yarım gaz kontrollü iniş (half throttle descent), RTL KESİNLİKLE YASAK (no RTL)."
            )

    def get_actuator_commands(self) -> Dict[str, Any]:
        """Aktif fail-safe profilinin aktüatör komut sözlüğünü döndürür."""
        prof = self.get_failsafe_profile()
        return {
            "vehicle_type": prof.vehicle_type.value,
            "throttle": prof.throttle,
            "throttle_pct": prof.throttle_pct,
            "pitch": prof.pitch,
            "rudder": prof.rudder,
            "aileron": prof.aileron,
            "flaps": prof.flaps,
            "rtl_allowed": prof.rtl_allowed,
            "pwm_channels": prof.pwm_channels,
            "description": prof.description
        }

    def evaluate(self, health: AvionicsHealth) -> Tuple[FailsafeLevel, str]:
        """
        Tüm telemetri ve donanım parametrelerini güvenlik limitlerine göre doğrular.
        Döner kanat konfigürasyonunda RTL yerine daima kontrollü iniş (half throttle descent) tetikler.
        """
        now = time.monotonic()
        self.last_check_time = now

        # Döner kanat için standart RTL seviyesi yerine kontrollü iniş seçilir
        default_fail_level = (
            FailsafeLevel.RTL_REQUIRED if self.rtl_allowed else FailsafeLevel.CONTROLLED_DESCENT
        )

        # 1. Acil Durum: Kritik Düşük Batarya (Hücre hasarı veya ani voltaj çökmesi <= 13.2V)
        if health.voltage_v <= self.battery_emergency_v:
            self._set_failsafe(
                FailsafeLevel.LAND_IMMEDIATELY,
                f"ACİL: Kritik Düşük Batarya! ({health.voltage_v:.2f}V <= {self.battery_emergency_v}V)"
            )
            return self.active_level, self.trigger_reason

        # 2. İrtifa İhlali (2026 Kuralı: 120m üstü diskalifiye)
        if health.altitude_agl_m > self.max_altitude_m:
            prefix = "KURAL İHLALİ TEHLİKESİ: İrtifa Limiti Aşıldı!"
            if not self.rtl_allowed:
                reason = f"{prefix} Döner Kanat Kuralı: RTL Yasak, Kontrollü İniş Başlatıldı ({health.altitude_agl_m:.1f}m > {self.max_altitude_m}m)"
            else:
                reason = f"{prefix} ({health.altitude_agl_m:.1f}m > {self.max_altitude_m}m)"
            self._set_failsafe(default_fail_level, reason)
            return self.active_level, self.trigger_reason

        # 3. Geofence Sınırı (500m)
        if health.distance_from_home_m > self.geofence_radius_m:
            prefix = "GEOFENCE AŞILDI: Güvenlik Alanı Dışında!"
            if not self.rtl_allowed:
                reason = f"{prefix} Döner Kanat Kuralı: RTL Yasak, Kontrollü İniş Başlatıldı ({health.distance_from_home_m:.1f}m > {self.geofence_radius_m}m)"
            else:
                reason = f"{prefix} ({health.distance_from_home_m:.1f}m > {self.geofence_radius_m}m)"
            self._set_failsafe(default_fail_level, reason)
            return self.active_level, self.trigger_reason

        # 4. Haberleşme Kaybı (Link Loss / Heartbeat Timeout > 3.0s veya RC sinyal kaybı)
        heartbeat_age = now - health.last_heartbeat_time
        if heartbeat_age > self.heartbeat_timeout_s or health.rc_signal_lost:
            prefix = f"HABERLEŞME KESİLDİ: GCS Kalp Atışı Alınamadı ({heartbeat_age:.1f}s)"
            if not self.rtl_allowed:
                reason = f"{prefix} -> Döner Kanat: RTL Yasak, Yarım Gaz Kontrollü İniş Devrede"
            else:
                reason = prefix
            self._set_failsafe(default_fail_level, reason)
            return self.active_level, self.trigger_reason

        # 5. Batarya RTL/Kritik Seviyesi (<= 14.0V)
        if health.voltage_v <= self.battery_critical_v:
            prefix = f"DÜŞÜK BATARYA: ({health.voltage_v:.2f}V)"
            if not self.rtl_allowed:
                reason = f"{prefix} Döner Kanat Kuralı: RTL Yasak, Güvenli İniş Başlatılıyor"
            else:
                reason = f"{prefix} Güvenli RTL Başlatılıyor"
            self._set_failsafe(default_fail_level, reason)
            return self.active_level, self.trigger_reason

        # 6. EKF / GPS Sağlığı
        if not health.ekf_healthy or health.satellites_visible < 6:
            self._set_failsafe(
                FailsafeLevel.WARNING,
                f"NAVİGASYON UYARISI: Yetersiz GPS/EKF (Uydu: {health.satellites_visible})"
            )
            return self.active_level, self.trigger_reason

        # Nominal durum
        if self.active_level == FailsafeLevel.WARNING:
            self.active_level = FailsafeLevel.NOMINAL
            self.trigger_reason = ""

        return FailsafeLevel.NOMINAL, "Sistem Parametreleri Nominal"

    def _set_failsafe(self, level: FailsafeLevel, reason: str):
        self.active_level = level
        self.trigger_reason = reason
        critical_levels = (
            FailsafeLevel.RTL_REQUIRED,
            FailsafeLevel.CONTROLLED_DESCENT,
            FailsafeLevel.LAND_IMMEDIATELY,
            FailsafeLevel.TERMINATE
        )
        if level in critical_levels:
            self.failsafe_triggered = True
            self.active_profile = self.get_failsafe_profile()
            print(f"[FAILSAFE KRİTİK] Araç: {self.vehicle_type.value} | Düzey: {level.value} | Sebep: {reason}")
            print(f"[FAILSAFE AKTÜATÖR] Profil: {self.active_profile.description}")
        else:
            print(f"[FAILSAFE UYARI] {reason}")

    def trigger_failsafe(self, reason: str = "Manuel veya Harici Failsafe Tetiklemesi") -> FailSafeProfile:
        """Fail-safe'i doğrudan tetikler ve aktüatör profilini döndürür."""
        level = FailsafeLevel.CONTROLLED_DESCENT if not self.rtl_allowed else FailsafeLevel.TERMINATE
        self._set_failsafe(level, reason)
        return self.get_failsafe_profile()

    def reset(self):
        """Güvenlik durumunu sıfırlar."""
        self.failsafe_triggered = False
        self.active_level = FailsafeLevel.NOMINAL
        self.trigger_reason = ""
        self.active_profile = None
