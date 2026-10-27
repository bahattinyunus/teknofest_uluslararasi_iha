"""
TEKNOFEST 2026 Uluslararası İHA - Gerçek Zamanlı Rüzgar Vektörü Kestiricisi
-------------------------------------------------------------------------
İHA'nın GPS tabanlı yer hızı (Ground Speed) vektörü ile hava hızı (Airspeed)
ve baş açısı (Heading) arasındaki farkı süzerek anlık yatay rüzgar
hızını ve yönünü (Wind Vector) gerçek zamanlı kestirir.

Balistik yük bırakma hesaplayıcısına anlık rüzgar düzeltmesi besler.
"""

from dataclasses import dataclass
from typing import Tuple, Optional
import math
import time


@dataclass
class WindEstimate:
    wind_x_mps: float       # Doğu yönlü rüzgar bileşeni (+ Doğuya doğru)
    wind_y_mps: float       # Kuzey yönlü rüzgar bileşeni (+ Kuzeye doğru)
    speed_mps: float        # Toplam rüzgar şiddeti (m/s)
    direction_deg: float    # Rüzgarın estiği yön (0-360 derece, pusula referansı)
    crosswind_mps: float    # İHA gövdesine dik yan rüzgar
    headwind_mps: float     # İHA gövdesine karşı rüzgar (+ Karşı, - Arka)
    confidence: float       # Kestirim güven katsayısı (0.0 - 1.0)


class WindEstimator:
    def __init__(self, filter_alpha: float = 0.15, min_airspeed_mps: float = 3.0):
        """
        :param filter_alpha: Düşük geçiren filtre (LPF) yumuşatma katsayısı (0.05 - 0.3)
        :param min_airspeed_mps: Rüzgar kestirimi için gerekli minimum hava hızı
        """
        self.alpha = filter_alpha
        self.min_airspeed = min_airspeed_mps

        # Kestirilen rüzgar durumu (Kuzey, Doğu)
        self.est_wind_n = 0.0
        self.est_wind_e = 0.0
        self.initialized = False
        self.last_update_time = time.monotonic()
        self.sample_count = 0

    def update(
        self,
        ground_speed_n: float,
        ground_speed_e: float,
        heading_deg: float,
        true_airspeed_mps: Optional[float] = None
    ) -> WindEstimate:
        """
        Yeni telemetri paketi ile rüzgar kestirimini günceller.
        V_ground = V_air + V_wind  =>  V_wind = V_ground - V_air
        """
        now = time.monotonic()
        dt = max(0.01, now - self.last_update_time)
        self.last_update_time = now

        # Eğer pitot tüpünden hava hızı gelmiyorsa yer hızını nominal varsay
        heading_rad = math.radians(heading_deg)
        if true_airspeed_mps is None or true_airspeed_mps < 0.5:
            # Tahmini hava hızı (yer hızı normundan türetilir)
            g_speed = math.hypot(ground_speed_n, ground_speed_e)
            v_air = max(self.min_airspeed, g_speed)
        else:
            v_air = true_airspeed_mps

        # İHA'nın aerodinamik hava hız vektörü
        v_air_n = v_air * math.cos(heading_rad)
        v_air_e = v_air * math.sin(heading_rad)

        # Anlık rüzgar farkı
        raw_wind_n = ground_speed_n - v_air_n
        raw_wind_e = ground_speed_e - v_air_e

        # Sınırlandırma (Uçuş güvenliği için aşırı rüzgar anomalilerini kırp)
        max_realistic_wind = 25.0  # m/s (~90 km/s)
        raw_wind_n = max(-max_realistic_wind, min(max_realistic_wind, raw_wind_n))
        raw_wind_e = max(-max_realistic_wind, min(max_realistic_wind, raw_wind_e))

        if not self.initialized:
            self.est_wind_n = raw_wind_n
            self.est_wind_e = raw_wind_e
            self.initialized = True
        else:
            # Düşük geçiren filtre
            self.est_wind_n = (1.0 - self.alpha) * self.est_wind_n + self.alpha * raw_wind_n
            self.est_wind_e = (1.0 - self.alpha) * self.est_wind_e + self.alpha * raw_wind_e

        self.sample_count += 1
        speed = math.hypot(self.est_wind_n, self.est_wind_e)

        # Rüzgarın estiği yön (Compass direction)
        direction_rad = math.atan2(self.est_wind_e, self.est_wind_n)
        direction_deg = (math.degrees(direction_rad) + 360.0) % 360.0

        # İHA gövdesine göre yan rüzgar (crosswind) ve karşı rüzgar (headwind) bileşenleri
        # Bağıl açı: rüzgar yönü ile İHA baş açısı farkı
        rel_angle = math.radians(direction_deg - heading_deg)
        headwind = speed * math.cos(rel_angle)
        crosswind = speed * math.sin(rel_angle)

        confidence = min(1.0, self.sample_count / 30.0)

        return WindEstimate(
            wind_x_mps=round(self.est_wind_e, 2),
            wind_y_mps=round(self.est_wind_n, 2),
            speed_mps=round(speed, 2),
            direction_deg=round(direction_deg, 1),
            crosswind_mps=round(crosswind, 2),
            headwind_mps=round(headwind, 2),
            confidence=round(confidence, 2)
        )

    def get_current_wind(self) -> Tuple[float, float]:
        """(wind_x, wind_y) formatında döndürür."""
        return (self.est_wind_e, self.est_wind_n)

    def reset(self):
        self.est_wind_n = 0.0
        self.est_wind_e = 0.0
        self.initialized = False
        self.sample_count = 0
