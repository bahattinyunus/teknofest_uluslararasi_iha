"""
TEKNOFEST 2026 Uluslararası İHA - Güç ve Batarya Enerji Yöneticisi (Power Manager)
---------------------------------------------------------------------------------
4S LiPo/Li-ion bataryaların deşarj eğrisini, Peukert kapasite kaybını,
uçuş fazına bağlı dinamik güç tüketimini (Hover/Cruise/Climb Watt) ve
kalkış noktasına güvenli dönüş için "Dönüşü Olmayan Nokta" (Point of No Return - PNR)
enerji rezervini hesaplar.
"""

from dataclasses import dataclass
from typing import Tuple, Dict, Any, Optional
import math
import time


@dataclass
class PowerStatus:
    voltage_v: float
    current_a: float
    cell_voltage_v: float
    state_of_charge_pct: float       # Kalan şarj yüzdesi (0-100%)
    consumed_energy_wh: float        # Tüketilen toplam enerji (Wh)
    remaining_energy_wh: float       # Kalan kullanılabilir enerji (Wh)
    instantaneous_power_w: float     # Anlık güç tüketimi (W)
    remaining_flight_time_min: float # Kalan tahmini havada kalış süresi (dakika)
    rtl_energy_required_wh: float    # Eve dönüş için gereken minimum enerji (Wh)
    is_pnr_reached: bool             # Point of No Return eşiğine ulaşıldı mı?
    throttle_limit_factor: float     # Termal/Düşük voltaj gaz sınırı katsayısı (0.5 - 1.0)


class BatteryPowerManager:
    def __init__(
        self,
        nominal_capacity_mah: float = 5000.0,
        cell_count: int = 4,
        peukert_exponent: float = 1.15,
        nominal_voltage_v: float = 14.8,
        min_cell_voltage_v: float = 3.30,
        max_cell_voltage_v: float = 4.20,
        rtl_safety_reserve_pct: float = 25.0
    ):
        self.capacity_mah = nominal_capacity_mah
        self.cells = cell_count
        self.peukert_k = peukert_exponent
        self.nominal_v = nominal_voltage_v
        self.min_cell_v = min_cell_voltage_v
        self.max_cell_v = max_cell_voltage_v
        self.safety_reserve_ratio = rtl_safety_reserve_pct / 100.0

        # Nominal toplam enerji (Wh) = Ah * V
        self.total_energy_wh = (self.capacity_mah / 1000.0) * self.nominal_v
        self.consumed_mah = 0.0
        self.consumed_wh = 0.0
        self.is_initialized = False
        self.last_update_time: Optional[float] = None

    def estimate_soc_from_voltage(self, cell_v: float) -> float:
        """
        4S LiPo açık devre dinlenme voltajından SoC tahmini (Sigmoid/Polinom yaklaşımı).
        3.3V: 0%, 3.7V: ~20%, 3.8V: ~50%, 4.0V: ~85%, 4.2V: 100%
        """
        if cell_v <= self.min_cell_v:
            return 0.0
        if cell_v >= self.max_cell_v:
            return 100.0

        # Doğrusal olmayan LiPo eğrisi
        if cell_v < 3.70:
            soc = (cell_v - 3.30) / (3.70 - 3.30) * 20.0
        elif cell_v < 3.85:
            soc = 20.0 + (cell_v - 3.70) / (3.85 - 3.70) * 40.0
        else:
            soc = 60.0 + (cell_v - 3.85) / (4.20 - 3.85) * 40.0

        return float(max(0.0, min(100.0, soc)))

    def calculate_rtl_energy(
        self,
        distance_to_home_m: float,
        cruise_speed_mps: float = 8.0,
        headwind_mps: float = 0.0,
        cruise_power_w: float = 220.0
    ) -> float:
        """
        Kalkış noktasına dönüş için gerekli enerji (Wh).
        Mesafe, rüzgar hızı ve güvenlik payı hesaba katılır.
        """
        effective_ground_speed = max(1.5, cruise_speed_mps - headwind_mps)
        time_to_home_s = distance_to_home_m / effective_ground_speed
        time_to_home_h = time_to_home_s / 3600.0

        # Enerji (Wh) = Güç (W) * Süre (h) * (1 + Güvenlik Payı)
        required_wh = cruise_power_w * time_to_home_h * (1.0 + self.safety_reserve_ratio)
        # Ekstra iniş rezervi (30 saniye hover ~ 2.5 Wh)
        landing_wh = 2.5
        return float(required_wh + landing_wh)

    def update(
        self,
        voltage_v: float,
        current_a: float,
        distance_to_home_m: float = 0.0,
        headwind_mps: float = 0.0,
        dt: Optional[float] = None
    ) -> PowerStatus:
        now = time.monotonic()
        if dt is None:
            dt = 0.05 if self.last_update_time is None else max(0.001, now - self.last_update_time)
        self.last_update_time = now

        cell_v = voltage_v / float(self.cells)
        power_w = max(0.0, voltage_v * current_a)

        # İlk çalıştırmada başlangıç voltajından SoC ve tüketim belirle
        if not self.is_initialized:
            init_soc = self.estimate_soc_from_voltage(cell_v)
            self.consumed_mah = max(0.0, (1.0 - init_soc / 100.0) * self.capacity_mah)
            self.consumed_wh = max(0.0, (1.0 - init_soc / 100.0) * self.total_energy_wh)
            self.is_initialized = True

        # Peukert akım düzeltmesi
        nominal_current = self.capacity_mah / 1000.0  # 1C akımı
        i_ratio = max(0.1, current_a / max(0.1, nominal_current))
        eff_current = current_a * (i_ratio ** (self.peukert_k - 1.0))

        # Enerji ve kapasite entegrasyonu
        delta_mah = (eff_current * (dt / 3600.0)) * 1000.0
        self.consumed_mah += delta_mah

        delta_wh = (power_w * (dt / 3600.0))
        self.consumed_wh += delta_wh

        # Coulomb sayımı ve voltaj füzyonu ile SoC
        soc_coulomb = max(0.0, 100.0 - (self.consumed_mah / self.capacity_mah * 100.0))
        soc_voltage = self.estimate_soc_from_voltage(cell_v)
        # Ağır yük altında voltaj çökmesini sönümlemek için %80 Coulomb, %20 Voltaj
        soc_final = 0.80 * soc_coulomb + 0.20 * soc_voltage

        rem_energy_wh = max(0.0, (soc_final / 100.0) * self.total_energy_wh)

        # Kalan süre (dakika)
        avg_power = max(50.0, power_w)
        rem_time_min = (rem_energy_wh / avg_power) * 60.0

        # RTL gereksinimi ve PNR kontrolü
        rtl_req_wh = self.calculate_rtl_energy(
            distance_to_home_m=distance_to_home_m,
            headwind_mps=headwind_mps
        )
        is_pnr = rem_energy_wh <= rtl_req_wh

        # Gaz kısıtlama katsayısı (Hücre voltajı 3.5V altına inerse pili korumak için gazı sınırla)
        throttle_factor = 1.0
        if cell_v < 3.50:
            throttle_factor = max(0.60, (cell_v - self.min_cell_v) / (3.50 - self.min_cell_v))

        return PowerStatus(
            voltage_v=round(voltage_v, 2),
            current_a=round(current_a, 2),
            cell_voltage_v=round(cell_v, 2),
            state_of_charge_pct=round(soc_final, 1),
            consumed_energy_wh=round(self.consumed_wh, 2),
            remaining_energy_wh=round(rem_energy_wh, 2),
            instantaneous_power_w=round(power_w, 1),
            remaining_flight_time_min=round(rem_time_min, 1),
            rtl_energy_required_wh=round(rtl_req_wh, 2),
            is_pnr_reached=is_pnr,
            throttle_limit_factor=round(throttle_factor, 2)
        )

    def reset(self):
        self.consumed_mah = 0.0
        self.consumed_wh = 0.0
        self.is_initialized = False
        self.last_update_time = None
