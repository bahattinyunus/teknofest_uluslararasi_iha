"""
TEKNOFEST 2026 Uluslararası İHA - Rüzgar Darbesi ve Rüzgar Kesmesi Sönümleyici (GLA)
-----------------------------------------------------------------------------------
Malatya Tulga sahasındaki dağlık termal rüzgar türbülansı ve 25 km/h limitindeki ani
rüzgar darbelerine (Gust) karşı:
- NASA F-Faktörü Rüzgar Kesmesi (Wind Shear Criterion) Tespiti
- İleri Beslemeli (Feedforward) Kanatçık ve İrtifa Dümeni Rüzgar Darbe Sönümlemesi
- Görev 2 Hassas Bırakma Hattında Ani Sapma Engelleme ve Otomatik Pas Geçme (Go-Around)
yapan yüksek hızlı aviyonik stabilizasyon kontrolcüsüdür.
"""

from dataclasses import dataclass
from enum import Enum
import math
import time
from typing import Tuple, Optional, Dict, Any


class ShearHazardLevel(str, Enum):
    NOMINAL = "NOMINAL"          # Normal rüzgar koşulları (F < 0.08)
    CAUTION = "CAUTION"          # Orta şiddetli türbülans (0.08 <= F < 0.13)
    WARNING_SHEAR = "WARNING"    # Rüzgar kesmesi tehlikesi (F >= 0.13, Pas Geçme Tavsiyesi)
    EMERGENCY_GUST = "EMERGENCY" # 25 km/h şartname sınırı aşımı / aşırı rüzgar


@dataclass
class GustCompensationOutput:
    delta_roll_cmd: float        # Düzeltici Roll açısı / aileron emri (deg)
    delta_pitch_cmd: float       # Düzeltici Pitch açısı / elevator emri (deg)
    delta_throttle: float        # Rüzgar kesmesi dikey çöküş telafi gazı
    f_factor: float              # NASA Wind Shear Tehlike İndeksi
    gust_rate_mps2: float        # Rüzgar ivmelenme şiddeti (m/s^2)
    hazard_level: ShearHazardLevel
    go_around_recommended: bool # Bırakma hattında pas geçme tavsiyesi
    timestamp: float


class GustAlleviationController:
    GRAVITY = 9.80665

    def __init__(
        self,
        k_roll_gust: float = 1.25,     # Yan rüzgar darbesi roll kazancı
        k_pitch_gust: float = 0.95,    # Baş rüzgarı pitch kazancı
        f_factor_threshold: float = 0.13, # NASA F-factor tehlike sınırı
        wind_speed_limit_mps: float = 6.94 # 25 km/h şartname eşiği
    ):
        self.k_roll_gust = k_roll_gust
        self.k_pitch_gust = k_pitch_gust
        self.f_factor_threshold = f_factor_threshold
        self.wind_speed_limit_mps = wind_speed_limit_mps

        self.last_wind_vec: Optional[Tuple[float, float, float]] = None
        self.last_time: Optional[float] = None

    def update(
        self,
        wind_vx: float,
        wind_vy: float,
        wind_vz: float = 0.0,
        airspeed_mps: float = 14.0,
        in_release_run: bool = False,
        timestamp: Optional[float] = None
    ) -> GustCompensationOutput:
        """
        Anlık rüzgar vektöründen darbe türevini ve F-faktörünü hesaplayarak sönümleme üretir.
        :param wind_vx: Gövde/Kuzey ekseni rüzgar hızı (m/s)
        :param wind_vy: Gövde/Doğu ekseni rüzgar hızı (m/s)
        :param wind_vz: Dikey rüzgar hızı (m/s, pozitif yukarı)
        :param airspeed_mps: İHA gerçek hava hızı (TAS)
        :param in_release_run: Yük bırakma koridorunda olup olmadığı
        :param timestamp: Zaman damgası
        """
        t = timestamp or time.time()
        airspeed = max(3.0, airspeed_mps)
        wind_mag = math.hypot(wind_vx, wind_vy)

        if self.last_wind_vec is None or self.last_time is None:
            self.last_wind_vec = (wind_vx, wind_vy, wind_vz)
            self.last_time = t
            return GustCompensationOutput(
                delta_roll_cmd=0.0,
                delta_pitch_cmd=0.0,
                delta_throttle=0.0,
                f_factor=0.0,
                gust_rate_mps2=0.0,
                hazard_level=ShearHazardLevel.NOMINAL,
                go_around_recommended=False,
                timestamp=t
            )

        dt = max(0.005, min(0.5, t - self.last_time))
        prev_vx, prev_vy, prev_vz = self.last_wind_vec

        # Rüzgar ivmesi (Gust Acceleration Vector)
        acc_x = (wind_vx - prev_vx) / dt
        acc_y = (wind_vy - prev_vy) / dt
        acc_z = (wind_vz - prev_vz) / dt
        gust_rate = math.sqrt(acc_x**2 + acc_y**2 + acc_z**2)

        # NASA Wind Shear F-Faktörü: F = (d/dt W_x) / g - (W_z / V)
        # F > 0.13 uçuş emniyetini tehdit eden şiddetli rüzgar kesmesidir.
        f_factor = (acc_x / self.GRAVITY) - (wind_vz / airspeed)

        # Tehlike seviyesi değerlendirmesi
        hazard = ShearHazardLevel.NOMINAL
        if wind_mag > self.wind_speed_limit_mps:
            hazard = ShearHazardLevel.EMERGENCY_GUST
        elif abs(f_factor) >= self.f_factor_threshold:
            hazard = ShearHazardLevel.WARNING_SHEAR
        elif abs(f_factor) >= 0.08 or gust_rate > 3.5:
            hazard = ShearHazardLevel.CAUTION

        # Düzeltici Komutlar (İleri Besleme)
        # Yan rüzgar darbesi için ters roll
        delta_roll = -self.k_roll_gust * acc_y
        delta_roll = max(-15.0, min(15.0, delta_roll))

        # Baş rüzgarı darbesinde burun yukarı/aşağı telafisi
        delta_pitch = -self.k_pitch_gust * acc_x
        delta_pitch = max(-10.0, min(10.0, delta_pitch))

        # Çöküş rüzgarında gaz artışı
        delta_throttle = 0.0
        if wind_vz < -0.8:
            delta_throttle = min(0.35, abs(wind_vz) * 0.12)

        # Bırakma koridorunda rüzgar kesmesi varsa pas geçme tavsiyesi
        go_around = in_release_run and (hazard in (ShearHazardLevel.WARNING_SHEAR, ShearHazardLevel.EMERGENCY_GUST))

        self.last_wind_vec = (wind_vx, wind_vy, wind_vz)
        self.last_time = t

        return GustCompensationOutput(
            delta_roll_cmd=round(delta_roll, 2),
            delta_pitch_cmd=round(delta_pitch, 2),
            delta_throttle=round(delta_throttle, 3),
            f_factor=round(f_factor, 4),
            gust_rate_mps2=round(gust_rate, 2),
            hazard_level=hazard,
            go_around_recommended=go_around,
            timestamp=t
        )

    def reset(self):
        self.last_wind_vec = None
        self.last_time = None
