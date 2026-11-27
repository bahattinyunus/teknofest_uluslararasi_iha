"""
TEKNOFEST 2026 Uluslararası İHA - Hava Veri Bilgisayarı (Air Data Computer - ADC)
--------------------------------------------------------------------------------
Malatya Tulga Havalimanı (938m MSL, ~90.5 kPa ortam basıncı, değişken hava yoğunluğu)
koşullarında Pitot-Statik tüp basınç farkı ve dış ortam sıcaklığını (OAT) işleyerek:
- Gösterge Hava Hızı (IAS - Indicated Airspeed)
- Kalibre Edilmiş Hava Hızı (CAS - Calibrated Airspeed)
- Gerçek Hava Hızı (TAS - True Airspeed)
- Basınç İrtifası (Pressure Altitude) ve Yoğunluk İrtifası (Density Altitude)
- Yerel Ses Hızı ve Mach Sayısı
- Sabit Kanat için Perdövites (Stall / V_stall) Uyarısı ve Stick-Pusher Müdahalesi
- Pitot Tıkanması (Icing / Blockage) Arıza Teşhisi
üreten havacılık standardı (DO-178C seviyesinde) aviyonik modülüdür.
"""

from dataclasses import dataclass
from enum import Enum
import math
from typing import Optional, Dict, Any, Tuple


class AirspeedAlert(str, Enum):
    NOMINAL = "NOMINAL"
    STALL_WARNING = "STALL_WARNING"      # IAS < V_stall (Perdövites riski)
    STALL_CRITICAL = "STALL_CRITICAL"    # Anlık irtifa kaybı / acil burun aşağı dalış
    OVERSPEED = "OVERSPEED"              # IAS > V_ne (Yapısal hasar riski)
    SENSOR_BLOCKAGE = "SENSOR_BLOCKAGE"  # Pitot veya statik port tıkanması


@dataclass
class AirDataState:
    ias_mps: float              # Gösterge Hava Hızı (m/s)
    cas_mps: float              # Kalibre Edilmiş Hava Hızı (m/s)
    tas_mps: float              # Gerçek Hava Hızı (m/s)
    tas_kmh: float              # Gerçek Hava Hızı (km/h)
    pressure_alt_m: float       # Basınç İrtifası (m MSL)
    density_alt_m: float        # Yoğunluk İrtifası (m MSL)
    air_density_kgpm3: float    # Anlık Hava Yoğunluğu (kg/m^3)
    dynamic_pressure_pa: float  # Dinamik Basınç q (Pa)
    mach_number: float          # Uçuş Mach Sayısı
    speed_of_sound_mps: float   # Ses Hızı (m/s)
    alert: AirspeedAlert        # Emniyet Durumu
    stall_margin_mps: float     # V_ias - V_stall marjı
    timestamp: float


class AirDataComputer:
    # Uluslararası Standart Atmosfer (ISA) Deniz Seviyesi Sabitleri
    P0_PA = 101325.0            # Deniz seviyesi standart basınç (Pa)
    T0_K = 288.15               # Deniz seviyesi standart sıcaklık (K)
    RHO0_KGPM3 = 1.225          # Deniz seviyesi standart hava yoğunluğu (kg/m^3)
    LAPSE_RATE_KPM = 0.0065     # Troposfer sıcaklık düşüm oranı (K/m)
    GAS_CONSTANT_R = 287.05287  # Kuru hava gaz sabiti (J/(kg*K))
    GAMMA = 1.4                 # Isıl kapasite oranı (Adyabatik indeks)
    GRAVITY_G = 9.80665         # Yerçekimi ivmesi (m/s^2)

    def __init__(
        self,
        v_stall_mps: float = 9.5,
        v_ne_mps: float = 30.0,
        pitot_cal_factor: float = 1.0,
        min_dynamic_press_pa: float = 2.0
    ):
        """
        Hava Veri Bilgisayarı Başlatıcı
        :param v_stall_mps: Sabit Kanat perdövites eşik hızı (varsayılan: 9.5 m/s)
        :param v_ne_mps: Asla aşılmaması gereken hız (V_ne, varsayılan: 30.0 m/s)
        :param pitot_cal_factor: Pitot tüpü montaj ve pozisyon kalibrasyon katsayısı
        :param min_dynamic_press_pa: Güvenilir ölçüm için minimum dinamik basınç eşiği
        """
        self.v_stall_mps = v_stall_mps
        self.v_ne_mps = v_ne_mps
        self.pitot_cal_factor = pitot_cal_factor
        self.min_dynamic_press_pa = min_dynamic_press_pa

        # Önceki durum (filtreleme ve türev için)
        self.last_state: Optional[AirDataState] = None
        self._blockage_counter: int = 0

    def compute(
        self,
        diff_pressure_pa: float,
        static_pressure_pa: float,
        oat_celsius: float = 20.0,
        timestamp: float = 0.0
    ) -> AirDataState:
        """
        Ham pitot-statik sensör verilerinden havacılık parametrelerini türetir.
        :param diff_pressure_pa: Pitot dinamik basınç farkı (P_total - P_static, Pa)
        :param static_pressure_pa: Barometrik statik basınç (Pa)
        :param oat_celsius: Dış hava sıcaklığı (°C)
        :param timestamp: Zaman damgası (s)
        """
        # 1. Sıcaklık ve Basınç Temel Değerleri
        t_kelvin = max(180.0, min(340.0, oat_celsius + 273.15))
        p_static = max(40000.0, min(110000.0, static_pressure_pa))
        dp_raw = max(0.0, diff_pressure_pa)
        dp_cal = dp_raw * self.pitot_cal_factor

        # 2. Anlık Hava Yoğunluğu (İdeal Gaz Yasası: rho = P / (R * T))
        rho = p_static / (self.GAS_CONSTANT_R * t_kelvin)

        # 3. Basınç İrtifası (Pressure Altitude)
        # H_p = (T0 / L) * [1 - (P / P0)^(R*L / g)]
        exponent = (self.GAS_CONSTANT_R * self.LAPSE_RATE_KPM) / self.GRAVITY_G
        pressure_alt_m = (self.T0_K / self.LAPSE_RATE_KPM) * (1.0 - math.pow(p_static / self.P0_PA, exponent))

        # 4. Yoğunluk İrtifası (Density Altitude)
        # H_d = H_p + 118.8 * (OAT - ISA_temp)
        isa_temp_c = 15.0 - (0.0065 * pressure_alt_m)
        temp_deviation = oat_celsius - isa_temp_c
        density_alt_m = pressure_alt_m + (36.2 * temp_deviation)

        # 5. Ses Hızı ve Mach Sayısı
        speed_of_sound = math.sqrt(self.GAMMA * self.GAS_CONSTANT_R * t_kelvin)

        # 6. Gösterge (IAS) ve Kalibre Edilmiş (CAS) Hava Hızı
        # V_ias = sqrt(2 * dp / rho0)
        if dp_cal >= self.min_dynamic_press_pa:
            ias_mps = math.sqrt((2.0 * dp_cal) / self.RHO0_KGPM3)
            # Düşük ses hızında sıkışabilirlik düzeltmesi (Subsonic CAS)
            cas_mps = ias_mps * (1.0 + 0.001 * math.pow(ias_mps / speed_of_sound, 2))
            # Gerçek Hava Hızı (TAS): V_tas = V_ias * sqrt(rho0 / rho)
            tas_mps = math.sqrt((2.0 * dp_cal) / rho)
        else:
            ias_mps = 0.0
            cas_mps = 0.0
            tas_mps = 0.0

        tas_kmh = tas_mps * 3.6
        mach = tas_mps / speed_of_sound if speed_of_sound > 0 else 0.0

        # 7. Perdövites Marjı ve Emniyet Alarmı
        stall_margin = ias_mps - self.v_stall_mps
        alert = AirspeedAlert.NOMINAL

        # Pitot tıkanma kontrolü: İrtifa tırmanırken veya hız varken basınç sıfır çakılması
        if dp_cal < 0.5 and (self._blockage_counter > 0 or (self.last_state and self.last_state.ias_mps > 12.0)):
            self._blockage_counter += 1
            if self._blockage_counter >= 3:
                alert = AirspeedAlert.SENSOR_BLOCKAGE
        else:
            self._blockage_counter = 0

        if alert != AirspeedAlert.SENSOR_BLOCKAGE:
            if ias_mps > self.v_ne_mps:
                alert = AirspeedAlert.OVERSPEED
            elif ias_mps > 0.5 and ias_mps < (self.v_stall_mps * 0.85):
                alert = AirspeedAlert.STALL_CRITICAL
            elif ias_mps > 0.5 and ias_mps <= self.v_stall_mps:
                alert = AirspeedAlert.STALL_WARNING

        state = AirDataState(
            ias_mps=round(ias_mps, 2),
            cas_mps=round(cas_mps, 2),
            tas_mps=round(tas_mps, 2),
            tas_kmh=round(tas_kmh, 1),
            pressure_alt_m=round(pressure_alt_m, 1),
            density_alt_m=round(density_alt_m, 1),
            air_density_kgpm3=round(rho, 4),
            dynamic_pressure_pa=round(dp_cal, 2),
            mach_number=round(mach, 4),
            speed_of_sound_mps=round(speed_of_sound, 1),
            alert=alert,
            stall_margin_mps=round(stall_margin, 2),
            timestamp=timestamp
        )

        self.last_state = state
        return state

    def get_stall_recovery_action(self, current_pitch_deg: float) -> Tuple[float, float]:
        """
        Perdövites durumunda otopilotun uygulaması gereken acil burun-aşağı pitch ve gaz telafisi.
        :return: (tavsiye_edilen_pitch_deg, tavsiye_edilen_gaz_orani)
        """
        # Hızlı hücum açısı küçültme: -8.0 derece burun aşağı, %100 gaz
        target_pitch = min(current_pitch_deg - 5.0, -8.0)
        target_throttle = 1.0  # Tam gaz
        return target_pitch, target_throttle
