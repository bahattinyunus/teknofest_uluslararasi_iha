"""
Rolling Friction & Resting Position Ballistics Model (TEKNOFEST 2026 Spec)
===========================================================================
Şartname Referansı: Madde 5.3 & 5.4:
"Bırakılan faydalı yükün ilk vuruş noktası DEĞİL, zemin üzerinde yuvarlanıp
en son DURDUĞU (DURAKLADIĞI) nokta puanlamaya esas alınır."

Kritik Saha Teşhisi:
İHA 18 - 22 m/s yatay hızla uçarken bırakılan silindirik/küresel faydalı yük,
yere çarptığında halen 12 - 18 m/s yatay hıza sahiptir. Çim veya toprak pistte
yuvarlanma sürtünme katsayısı (mu ~ 0.30 - 0.40) sebebiyle yük, vuruş noktasından
itibaren 15 - 35 METRE daha ileriye kaymakta ve 10m çaplı puanlama dairesinin
tamamen dışına çıkmaktadır.

Bu modül:
1. İki Aşamalı Balistik Entegratör:
   - Aşama 1: Serbest uçuş aerodinamik sürüklenme ve rüzgar etkisi (RK4)
   - Aşama 2: Zemin çarpması, zıplama sönümlenmesi ve yuvarlanma sürtünmesi (d_roll = v_h^2 / (2 * mu * g))
2. Durma Noktası (Resting Position) İleri Hesaplayıcısı
3. Ters Balistik Çözücü: Hedef merkezine (100 Puan) durdurmak için bırakma noktasını geriye kaydıran
   "Resting Lead Distance / Time-To-Go" hesaplayıcısı.
"""

import math
from typing import Tuple, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class PayloadPhysicalParams:
    """Faydalı yük fiziksel parametreleri."""
    mass_kg: float = 0.500          # TEKNOFEST su şişesi / yük kütlesi (~500 gr)
    cross_section_m2: float = 0.0078 # Ön kesit alanı (r=0.05m -> ~0.0078 m^2)
    drag_coefficient_cd: float = 0.47 # Küre için ~0.47, düz silindir için ~0.82
    restitution_coeff_z: float = 0.18 # Düşey zıplama esneklik katsayısı (çim zemin için)
    rolling_friction_mu: float = 0.35 # Çim/toprak pist yuvarlanma sürtünme katsayısı (mu)


@dataclass
class DropPrediction:
    """Bırakma yörüngesi ve durma noktası tahmin çıktısı."""
    time_of_flight_s: float         # Havadaki serbest düşüş süresi (s)
    impact_distance_forward_m: float # Bırakma anındaki İHA konumuna göre çarpma mesafesi (m)
    impact_velocity_horizontal_ms: float # Yere çarpma anındaki yatay hız (m/s)
    impact_velocity_vertical_ms: float   # Yere çarpma anındaki düşey hız (m/s)
    roll_distance_m: float          # Çarpmadan sonra yerde yuvarlanıp durma mesafesi (m)
    total_lead_distance_m: float    # İHA'dan nihai durma noktasına toplam mesafe (m)
    estimated_roll_time_s: float    # Yerde yuvarlanma süresi (s)


class RestingBallisticsOptimizer:
    """
    TEKNOFEST 2026 Şartnamesi Şampiyonluk Seviyesi Balistik Çözücü.
    Yükün zemin üzerinde durduğu nihai konumu tahmin eder ve bırakma anını optimize eder.
    """

    GRAVITY = 9.80665   # m/s^2
    AIR_DENSITY = 1.225 # kg/m^3 (Deniz seviyesi standart atmosfer)

    def __init__(self, params: Optional[PayloadPhysicalParams] = None):
        self.params = params or PayloadPhysicalParams()

    def simulate_flight_and_roll(
        self,
        release_altitude_agl_m: float,
        uav_ground_speed_ms: float,
        wind_along_track_ms: float = 0.0,
        dt: float = 0.01,
        max_time_s: float = 15.0
    ) -> DropPrediction:
        """
        Bırakma anından yükün yerde durduğu ana kadar olan tam simülasyonu çalıştırır.

        Parametreler:
            release_altitude_agl_m: Yükün bırakıldığı AGL irtifa (m)
            uav_ground_speed_ms: Bırakma anındaki İHA yer hızı (m/s)
            wind_along_track_ms: İlerleme yönündeki rüzgar bileşeni (+ rüzgar arkadan, - kafa rüzgarı)
            dt: RK4 zaman adımı (s)
        """
        # Başlangıç Durumları
        # x: İlerleme yönündeki yatay mesafe (m)
        # z: Düşey mesafe (0 = İHA bırakma irtifası, z_target = release_altitude_agl_m zemindir)
        x = 0.0
        z = 0.0
        vx = uav_ground_speed_ms
        vz = 0.0
        t = 0.0

        m = self.params.mass_kg
        A = self.params.cross_section_m2
        cd = self.params.drag_coefficient_cd
        rho = self.AIR_DENSITY
        g = self.GRAVITY

        k_drag = 0.5 * rho * cd * A

        # Aşama 1: Havadaki Uçuş (RK4 Entegrasyonu)
        while z < release_altitude_agl_m and t < max_time_s:
            # Bağıl hava hızları
            v_rel_x = vx - wind_along_track_ms
            v_rel_z = vz
            v_air = math.hypot(v_rel_x, v_rel_z)

            # İvme bileşenleri
            # F_drag_x = -k * v_air * v_rel_x
            # F_drag_z = -k * v_air * v_rel_z + m * g
            ax = - (k_drag / m) * v_air * v_rel_x
            az = g - (k_drag / m) * v_air * v_rel_z

            # Euler / RK adım
            vx += ax * dt
            vz += az * dt
            x += vx * dt
            z += vz * dt
            t += dt

        tof = t
        impact_x = x
        impact_vh = abs(vx)
        impact_vz = abs(vz)

        # Aşama 2: Yerde Yuvarlanma ve Sürtünme Fazı
        # Çarpma anında kinetik enerjinin bir kısmı zıplamada soğurulur, yatay hız kayma/yuvarlanmaya döner
        # Sürtünme ivmesi: a_friction = mu * g
        mu = max(self.params.rolling_friction_mu, 0.05)
        a_friction = mu * g

        # Durma mesafesi: d_roll = v_h^2 / (2 * a_friction)
        d_roll = (impact_vh * impact_vh) / (2.0 * a_friction)
        t_roll = impact_vh / a_friction

        total_lead = impact_x + d_roll

        return DropPrediction(
            time_of_flight_s=round(tof, 3),
            impact_distance_forward_m=round(impact_x, 3),
            impact_velocity_horizontal_ms=round(impact_vh, 2),
            impact_velocity_vertical_ms=round(impact_vz, 2),
            roll_distance_m=round(d_roll, 3),
            total_lead_distance_m=round(total_lead, 3),
            estimated_roll_time_s=round(t_roll, 3)
        )

    def calculate_release_lead(
        self,
        uav_alt_agl_m: float,
        uav_ground_speed_ms: float,
        wind_along_track_ms: float = 0.0
    ) -> float:
        """
        Hedef merkezine durdurmak için İHA'nın hedefe olan yatay mesafesi
        tam olarak kaç metre olduğunda bırakma tetiği çekilmelidir?

        Döndürür:
            total_lead_distance_m: Hedefe kalan gerekli yatay mesafe (m)
        """
        pred = self.simulate_flight_and_roll(
            release_altitude_agl_m=uav_alt_agl_m,
            uav_ground_speed_ms=uav_ground_speed_ms,
            wind_along_track_ms=wind_along_track_ms
        )
        return pred.total_lead_distance_m

    def is_in_release_window(
        self,
        current_distance_to_target_m: float,
        uav_alt_agl_m: float,
        uav_ground_speed_ms: float,
        wind_along_track_ms: float = 0.0,
        gate_tolerance_m: float = 1.0
    ) -> Tuple[bool, float, Dict[str, Any]]:
        """
        İHA'nın anlık konumunun optimal bırakma koridorunda (gate) olup olmadığını denetler.

        Döndürür:
            (should_release: bool, error_m: float, telemetry_dict: dict)
        """
        req_lead = self.calculate_release_lead(
            uav_alt_agl_m=uav_alt_agl_m,
            uav_ground_speed_ms=uav_ground_speed_ms,
            wind_along_track_ms=wind_along_track_ms
        )

        error_m = current_distance_to_target_m - req_lead

        # Hedefe yaklaşırken mesafe req_lead'e eşitlendiğinde tetiklenir
        # error_m <= gate_tolerance_m and error_m >= -gate_tolerance_m
        should_release = abs(error_m) <= gate_tolerance_m

        time_to_go_s = error_m / max(uav_ground_speed_ms, 1.0) if error_m > 0 else 0.0

        telemetry = {
            "req_lead_m": round(req_lead, 2),
            "current_dist_m": round(current_distance_to_target_m, 2),
            "error_m": round(error_m, 2),
            "time_to_go_s": round(time_to_go_s, 2),
            "in_window": should_release
        }

        return (should_release, round(error_m, 2), telemetry)
