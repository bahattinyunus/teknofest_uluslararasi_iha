"""
Autonomous Flight Termination System (FTS) & Emergency Recovery Manager
========================================================================
TEKNOFEST 2026 Havacılık Emniyeti ve Uçuş Kırım Önleme Sistemi (V7 Şartnamesi Madde 7 & 9.2 Uyumlu).

Resmi Şartname ve Arıza Emniyet Standartları:
Yarışma esnasında İHA'nın kontrolsüz viril/spin taklaya girmesi, 120m tavan veya harici geofence sınırını
mutlak ihlal etmesi ya da motor/batarya çöküşünde İHA'nın yere serbest düşmesini önlemek ve çevre
güvenliğini sağlamak amacıyla araç türüne göre özel acil durum profilleri uygulanır.

Madde 9.2 Arıza Emniyet Profilleri:
1. Sabit Kanat (Fixed-Wing):
   - Motor durdurma (cut throttle, 0% / 1000 us)
   - İrtifa dümeni tam yukarı (full elevator up, +100% / 2000 us)
   - İstikamet ve kanatçık tam sağ (full rudder & aileron right, +100% / 2000 us)
   - Flaplar tam aşağı (full flaps down, +100% / 2000 us)
   - Balistik yaylı/piroteknik paraşüt fırlatma (V_sink ~ 4.2 m/s)

2. Döner Kanat (Rotary-Wing):
   - Yarım gazla kontrollü alçalma / iniş (half throttle descent, 50% / 1500 us)
   - RTL KESİNLİKLE YASAKTIR (no RTL - rtl_allowed = False)
   - Katastrofik gövde/viril kırılmalarında motor susturma + balistik paraşüt

Modül İşlevleri:
1. Uçuş Dinamiği Anomali Gözetimi (Tumble / Uncontrolled Spin / Excessive G-load / Geofence breach)
2. Otomatik Motor Durdurma veya Yarım Gaz Kontrollü Alçalma
3. Balistik Paraşüt Fırlatma Tetikleyicisi (MAVLink MAV_CMD_DO_PARACHUTE #208)
4. Paraşütlü Süzülme ve Rüzgar Sürüklenme Tahmini (Touchdown Drift Estimator):
   V_sink = sqrt(2 * m * g / (rho * S_chute * Cd)) ~ 4.2 m/s
5. Kaza Kırım Konum Tahmini (GPS Touchdown Point)
"""

import math
from typing import Tuple, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

from src.avionics.failsafe import VehicleType


class RecoveryStatus(Enum):
    STANDBY = "STANDBY"
    ARMED = "ARMED"
    TRIGGERED = "TRIGGERED"
    PARACHUTE_DEPLOYED = "PARACHUTE_DEPLOYED"
    MOTOR_KILLED = "MOTOR_KILLED"
    CONTROLLED_DESCENT = "CONTROLLED_DESCENT"
    TOUCHDOWN = "TOUCHDOWN"


class TriggerReason(Enum):
    NONE = "NONE"
    MANUAL_GCS_COMMAND = "MANUAL_COMMAND"
    UNCONTROLLED_SPIN = "UNCONTROLLED_SPIN"       # Açısal hız > 180 deg/s
    CRITICAL_DESCENT_RATE = "EXCESSIVE_DIVE"      # Düşey hız > 13 m/s (kontrolsüz dalış)
    EXCESSIVE_ACCELERATION = "HIGH_G_OVERLOAD"    # G yükü > 5.2G (yapısal zorlanma)
    GEOFENCE_HARD_BREACH = "GEOFENCE_BREACH"      # Dış sınır aşımı (>25m)
    COMPLETE_POWER_LOSS = "TOTAL_POWER_FAILURE"   # Kritik voltaj çöküşü
    FAILSAFE_ENGAGED = "FAILSAFE_ENGAGED"         # Şartname Madde 9.2 Failsafe Tetiklemesi


@dataclass
class ParachuteParams:
    """Paraşüt fiziksel boyut ve aerodinamik parametreleri."""
    chute_area_m2: float = 1.25       # 1.25 m^2 dairesel kubbe paraşüt
    drag_coefficient_cd: float = 1.45 # Yarı küresel paraşüt Cd ~ 1.45
    deployment_delay_s: float = 0.35  # Fırlatma yayının tam açılma gecikmesi
    motor_kill_lead_s: float = 0.15   # Paraşütten 150ms önce motoru sustur


@dataclass
class EmergencyStatusReport:
    """Acil durum durum raporu."""
    is_triggered: bool
    status: RecoveryStatus
    trigger_reason: TriggerReason
    trigger_altitude_m: float
    sink_rate_mps: float
    estimated_drift_distance_m: float
    estimated_touchdown_time_s: float
    vehicle_type: str = "fixed_wing"
    throttle_command: str = "cut"
    elevator_pitch: str = "full_up"
    rudder: str = "full_right"
    aileron: str = "full_right"
    flaps: str = "full_down"
    rtl_allowed: bool = False
    actuator_commands: Optional[Dict[str, Any]] = None


class EmergencyRecoveryManager:
    """
    Otonom Kırım Önleme, Şartname Uyumlu Fail-Safe ve Paraşütlü Acil İniş Yönetim Sistemi.
    """

    GRAVITY = 9.80665
    AIR_DENSITY = 1.225

    def __init__(
        self,
        uav_mass_kg: float = 2.60,
        params: Optional[ParachuteParams] = None,
        max_angular_rate_deg_s: float = 180.0,
        max_dive_rate_mps: float = 13.0,
        max_g_force: float = 5.2,
        vehicle_type: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        cfg = config or {}
        raw_vtype = (
            vehicle_type
            or cfg.get("failsafe", {}).get("vehicle_type")
            or cfg.get("competition", {}).get("category")
            or "fixed_wing"
        )
        self.vehicle_type = VehicleType.normalize(raw_vtype)
        # Döner kanatta RTL kesinlikle yasaktır
        self.rtl_allowed = False if self.vehicle_type == VehicleType.ROTARY_WING else False

        self.mass = uav_mass_kg
        self.params = params or ParachuteParams()
        self.max_angular_rate = max_angular_rate_deg_s
        self.max_dive_rate = max_dive_rate_mps
        self.max_g_force = max_g_force

        self.status = RecoveryStatus.ARMED
        self.trigger_reason = TriggerReason.NONE
        self.trigger_time: Optional[float] = None
        self.trigger_altitude: float = 0.0

        # Paraşütle terminal süzülme çöküş hızı (V_sink)
        denom = self.AIR_DENSITY * self.params.chute_area_m2 * self.params.drag_coefficient_cd
        self.terminal_sink_rate = math.sqrt((2.0 * self.mass * self.GRAVITY) / max(denom, 0.1))

    def get_failsafe_profile(self) -> Dict[str, Any]:
        """
        Şartname Madde 9.2'ye uygun acil durum kurtarma aktüatör profilini döndürür.
        """
        if self.vehicle_type == VehicleType.FIXED_WING:
            return {
                "vehicle_type": "fixed_wing",
                "throttle": "cut",
                "throttle_pct": 0.0,
                "pitch": "full_up",
                "elevator": "full_up",
                "rudder": "full_right",
                "aileron": "full_right",
                "flaps": "full_down",
                "rtl_allowed": False,
                "pwm_channels": {1: 2000, 2: 2000, 3: 1000, 4: 2000, 5: 2000},
                "description": "Sabit Kanat: Motor kesildi (cut throttle), irtifa tam yukarı, istikamet ve kanatçık tam sağ, flaplar tam aşağı."
            }
        else:
            return {
                "vehicle_type": "rotary_wing",
                "throttle": "half_throttle_controlled_descent",
                "throttle_pct": 50.0,
                "pitch": "neutral",
                "elevator": "neutral",
                "rudder": "neutral",
                "aileron": "neutral",
                "flaps": "none",
                "rtl_allowed": False,
                "pwm_channels": {1: 1500, 2: 1500, 3: 1500, 4: 1500, 5: 1000},
                "description": "Döner Kanat: Yarım gaz kontrollü iniş (half throttle descent), RTL KESİNLİKLE YASAK (no RTL)."
            }

    def evaluate_telemetry(
        self,
        timestamp: float,
        altitude_agl_m: float,
        vz_down_mps: float,
        roll_rate_deg_s: float,
        pitch_rate_deg_s: float,
        yaw_rate_deg_s: float,
        accel_magnitude_g: float,
        geofence_distance_outside_m: float = 0.0
    ) -> EmergencyStatusReport:
        """
        Her kontrol çevriminde uçuş dinamiklerini tarar, kırım kriteri tespit edilirse
        araç profiline uygun kurtarma sekansını icra eder.
        """
        active_terminal_states = (
            RecoveryStatus.PARACHUTE_DEPLOYED,
            RecoveryStatus.MOTOR_KILLED,
            RecoveryStatus.CONTROLLED_DESCENT
        )
        if self.status in active_terminal_states:
            return self._build_report(altitude_agl_m, 0.0)

        reason = TriggerReason.NONE

        # 1. Kontrolsüz Takla / Spin Denetimi
        max_rate = max(abs(roll_rate_deg_s), abs(pitch_rate_deg_s), abs(yaw_rate_deg_s))
        if max_rate > self.max_angular_rate:
            reason = TriggerReason.UNCONTROLLED_SPIN

        # 2. Kontrolsüz Dik Dalış (Vz Downwards > Limit)
        elif vz_down_mps > self.max_dive_rate and altitude_agl_m > 5.0:
            reason = TriggerReason.CRITICAL_DESCENT_RATE

        # 3. Yüksek G Yükü (Aşırı yapısal zorlanma / çarpma)
        elif accel_magnitude_g > self.max_g_force:
            reason = TriggerReason.EXCESSIVE_ACCELERATION

        # 4. Geofence Mutlak Sınır İhlali (> 25m dışarı kaçış)
        elif geofence_distance_outside_m > 25.0:
            reason = TriggerReason.GEOFENCE_HARD_BREACH

        # Tetikleme Şartı Gerçekleşti mi?
        if reason != TriggerReason.NONE and self.status == RecoveryStatus.ARMED:
            self._execute_trigger(reason, altitude_agl_m, timestamp)

        return self._build_report(altitude_agl_m, 0.0)

    def trigger_manual_override(self, altitude_agl_m: float, timestamp: float) -> EmergencyStatusReport:
        """Yer istasyonundan gönderilen Acil Paraşüt / FTS buton tetiklemesi."""
        self._execute_trigger(TriggerReason.MANUAL_GCS_COMMAND, altitude_agl_m, timestamp)
        return self._build_report(altitude_agl_m, 0.0)

    def trigger_failsafe_profile(self, altitude_agl_m: float, timestamp: float) -> EmergencyStatusReport:
        """Resmi Şartname Madde 9.2 Failsafe Profilini icra eder."""
        self._execute_trigger(TriggerReason.FAILSAFE_ENGAGED, altitude_agl_m, timestamp)
        return self._build_report(altitude_agl_m, 0.0)

    def _execute_trigger(self, reason: TriggerReason, altitude_m: float, timestamp: float):
        """Paraşüt açma, motor susturma veya kontrollü alçalma sıralamasını icra eder."""
        self.status = RecoveryStatus.TRIGGERED
        self.trigger_reason = reason
        self.trigger_time = timestamp
        self.trigger_altitude = altitude_m

        # Sabit kanat: motor kesilir, kontrol yüzeyleri tam sağ/yukarı/flap, paraşüt açılır
        if self.vehicle_type == VehicleType.FIXED_WING:
            self.status = RecoveryStatus.MOTOR_KILLED
            self.status = RecoveryStatus.PARACHUTE_DEPLOYED
            print(f"[RECOVERY TRIGGER] Sabit Kanat: Motor kesildi, tam yukarı/tam sağ/tam flap, paraşüt açıldı ({reason.value})")
        else:
            # Döner kanat:
            # Yapısal kırım veya spin durumunda motor susturulup paraşüt açılır;
            # geofence ihlali veya failsafe durumunda yarım gaz kontrollü inişe geçilir (RTL yasak).
            if reason in (TriggerReason.UNCONTROLLED_SPIN, TriggerReason.EXCESSIVE_ACCELERATION, TriggerReason.MANUAL_GCS_COMMAND):
                self.status = RecoveryStatus.MOTOR_KILLED
                self.status = RecoveryStatus.PARACHUTE_DEPLOYED
                print(f"[RECOVERY TRIGGER] Döner Kanat Katastrofik Acil Durum: Motor susturuldu, paraşüt devrede ({reason.value})")
            else:
                self.status = RecoveryStatus.CONTROLLED_DESCENT
                print(f"[RECOVERY TRIGGER] Döner Kanat Failsafe: Yarım gaz kontrollü iniş devrede, RTL KESİNLİKLE YASAK ({reason.value})")

    def predict_touchdown_drift(
        self,
        current_altitude_agl_m: float,
        wind_speed_mps: float,
        wind_direction_deg: float
    ) -> Tuple[float, float, float]:
        """
        Paraşüt açıldıktan sonra rüzgar sebebiyle yere değene kadar sürükleneceği
        mesafeyi ve süreyi hesaplar.
        """
        if current_altitude_agl_m <= 0.5:
            return (0.0, 0.0, wind_direction_deg)

        time_to_ground = current_altitude_agl_m / max(self.terminal_sink_rate, 1.0)
        drift_distance = wind_speed_mps * time_to_ground
        drift_dir = (wind_direction_deg + 180.0) % 360.0

        return (round(drift_distance, 2), round(time_to_ground, 2), round(drift_dir, 1))

    def _build_report(self, current_alt: float, wind_speed: float) -> EmergencyStatusReport:
        is_trig = self.status in (
            RecoveryStatus.TRIGGERED,
            RecoveryStatus.MOTOR_KILLED,
            RecoveryStatus.PARACHUTE_DEPLOYED,
            RecoveryStatus.CONTROLLED_DESCENT
        )
        drift_m = (current_alt / max(self.terminal_sink_rate, 1.0)) * wind_speed if is_trig else 0.0
        ttg = current_alt / max(self.terminal_sink_rate, 1.0) if is_trig else 0.0
        profile = self.get_failsafe_profile()

        return EmergencyStatusReport(
            is_triggered=is_trig,
            status=self.status,
            trigger_reason=self.trigger_reason,
            trigger_altitude_m=round(self.trigger_altitude, 2),
            sink_rate_mps=round(self.terminal_sink_rate, 2),
            estimated_drift_distance_m=round(drift_m, 2),
            estimated_touchdown_time_s=round(ttg, 2),
            vehicle_type=self.vehicle_type.value,
            throttle_command=profile["throttle"],
            elevator_pitch=profile["pitch"],
            rudder=profile["rudder"],
            aileron=profile["aileron"],
            flaps=profile["flaps"],
            rtl_allowed=profile["rtl_allowed"],
            actuator_commands=profile["pwm_channels"]
        )

    def reset(self):
        """Sistemi yeniden silahlandırır (ARM)."""
        self.status = RecoveryStatus.ARMED
        self.trigger_reason = TriggerReason.NONE
        self.trigger_time = None
        self.trigger_altitude = 0.0
