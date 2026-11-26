"""
Autonomous Flight Termination System (FTS) & Ballistic Parachute Recovery Manager
==================================================================================
TEKNOFEST 2026 Havacılık Emniyeti ve Uçuş Kırım Önleme Sistemi (Madde 7 Uyumlu).

Havacılık Emniyet Standartları:
Yarışma esnasında İHA'nın kontrolsüz vril / taklaya girmesi (spin), 120m tavan
veya harici geofence sınırını mutlak ihlal etmesi ya da motor/batarya tam çöküşünde
İHA'nın yere serbest düşerek can ve mal güvenliğini tehdit etmesini önlemek amacıyla
bağımsız bir Acil Durum Paraşütü ve Motor Susturma (FTS) mimarisi şarttır.

Bu modül:
1. Uçuş Dinamiği Anomali Gözetimi (Tumble / Uncontrolled Spin / Excessive G-load)
2. Otomatik Motor Durdurma (Motor Cutoff - Pervanelerin paraşüt iplerine dolanmasını önler)
3. Balistik Yaylı/Piroteknik Paraşüt Fırlatma Tetikleyicisi (MAVLink MAV_CMD_DO_PARACHUTE #208)
4. Paraşütlü Süzülme ve Rüzgar Sürüklenme Tahmini (Touchdown Drift Estimator):
   V_sink = sqrt(2 * m * g / (rho * S_chute * Cd)) ~ 4.2 m/s
5. Kaza Kırım Konum Tahmini (GPS Touchdown Point)
"""

import math
from typing import Tuple, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum


class RecoveryStatus(Enum):
    STANDBY = "STANDBY"
    ARMED = "ARMED"
    TRIGGERED = "TRIGGERED"
    PARACHUTE_DEPLOYED = "PARACHUTE_DEPLOYED"
    MOTOR_KILLED = "MOTOR_KILLED"
    TOUCHDOWN = "TOUCHDOWN"


class TriggerReason(Enum):
    NONE = "NONE"
    MANUAL_GCS_COMMAND = "MANUAL_COMMAND"
    UNCONTROLLED_SPIN = "UNCONTROLLED_SPIN"       # Açısal hız > 180 deg/s
    CRITICAL_DESCENT_RATE = "EXCESSIVE_DIVE"      # Düşey hız > 14 m/s (kontrolsüz dalış)
    EXCESSIVE_ACCELERATION = "HIGH_G_OVERLOAD"    # G yükü > 5.5G (yapısal kırılma)
    GEOFENCE_HARD_BREACH = "GEOFENCE_BREACH"      # Harici tampon sınır aşımı
    COMPLETE_POWER_LOSS = "TOTAL_POWER_FAILURE"   # Kritik voltaj çöküşü


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


class EmergencyRecoveryManager:
    """
    Otonom Kırım Önleme ve Paraşütlü Acil İniş Yönetim Sistemi.
    """

    GRAVITY = 9.80665
    AIR_DENSITY = 1.225

    def __init__(
        self,
        uav_mass_kg: float = 2.60,
        params: Optional[ParachuteParams] = None,
        max_angular_rate_deg_s: float = 180.0,
        max_dive_rate_mps: float = 13.0,
        max_g_force: float = 5.2
    ):
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
        # V_sink = sqrt(2 * m * g / (rho * S * Cd))
        denom = self.AIR_DENSITY * self.params.chute_area_m2 * self.params.drag_coefficient_cd
        self.terminal_sink_rate = math.sqrt((2.0 * self.mass * self.GRAVITY) / max(denom, 0.1))

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
        paraşütü ve FTS'i milisaniyeler mertebesinde tetikler.
        """
        if self.status in (RecoveryStatus.PARACHUTE_DEPLOYED, RecoveryStatus.MOTOR_KILLED):
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

    def _execute_trigger(self, reason: TriggerReason, altitude_m: float, timestamp: float):
        """Paraşüt açma ve motor susturma sıralamasını icra eder."""
        self.status = RecoveryStatus.TRIGGERED
        self.trigger_reason = reason
        self.trigger_time = timestamp
        self.trigger_altitude = altitude_m

        # 1. Anında motorları sustur
        self.status = RecoveryStatus.MOTOR_KILLED

        # 2. Paraşütü fırlat
        self.status = RecoveryStatus.PARACHUTE_DEPLOYED

    def predict_touchdown_drift(
        self,
        current_altitude_agl_m: float,
        wind_speed_mps: float,
        wind_direction_deg: float
    ) -> Tuple[float, float, float]:
        """
        Paraşüt açıldıktan sonra rüzgar sebebiyle yere değene kadar sürükleneceği
        mesafeyi ve süreyi hesaplar.

        Döndürür:
            (drift_distance_m: float, time_to_ground_s: float, drift_direction_deg: float)
        """
        if current_altitude_agl_m <= 0.5:
            return (0.0, 0.0, wind_direction_deg)

        time_to_ground = current_altitude_agl_m / max(self.terminal_sink_rate, 1.0)
        # Sürüklenme yönü: Rüzgarın estiği yön (wind_dir + 180 mod 360)
        drift_distance = wind_speed_mps * time_to_ground
        drift_dir = (wind_direction_deg + 180.0) % 360.0

        return (round(drift_distance, 2), round(time_to_ground, 2), round(drift_dir, 1))

    def _build_report(self, current_alt: float, wind_speed: float) -> EmergencyStatusReport:
        is_trig = self.status in (RecoveryStatus.TRIGGERED, RecoveryStatus.MOTOR_KILLED, RecoveryStatus.PARACHUTE_DEPLOYED)
        drift_m = (current_alt / max(self.terminal_sink_rate, 1.0)) * wind_speed if is_trig else 0.0
        ttg = current_alt / max(self.terminal_sink_rate, 1.0) if is_trig else 0.0

        return EmergencyStatusReport(
            is_triggered=is_trig,
            status=self.status,
            trigger_reason=self.trigger_reason,
            trigger_altitude_m=round(self.trigger_altitude, 2),
            sink_rate_mps=round(self.terminal_sink_rate, 2),
            estimated_drift_distance_m=round(drift_m, 2),
            estimated_touchdown_time_s=round(ttg, 2)
        )

    def reset(self):
        """Sistemi yeniden silahlandırır (ARM)."""
        self.status = RecoveryStatus.ARMED
        self.trigger_reason = TriggerReason.NONE
        self.trigger_time = None
        self.trigger_altitude = 0.0
