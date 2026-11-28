"""
TEKNOFEST 2026 Uluslararası İHA - Ağırlık/CG Dengesi, Muhafaza Kutusu ve Puan Optimizasyonu
===========================================================================================
TÜBİTAK TEKNOFEST 2026 V7 Şartnamesi (Madde 8.3.4, 8.3.5, 9.3.1 & Tablo 3) Uyumlu:
1. Ağırlık & Kütle Merkezi (Weight & Balance / CG Shift):
   - MTOW <= 4.0 kg doğrulaması
   - 1. yük bırakıldığında ve 2. yük bırakıldığında oluşan boylamasına/enlemesine CG kayması
   - Statik marj ve trim kararlılığı denetimi
2. Muhafaza Kutusu Hacim ve Geometri Denetçisi (Madde 8.3.4):
   - Sabit Kanat: Dairesel kesitli silindir (Vol = pi * r^2 * h; elips KESİNLİKLE YASAK)
   - Döner Kanat: Dikdörtgen/Kare prizma (Vol = a * b * c)
   - Tek kişi taşınabilirlik ve harici parça cezası (Ceza 1: 0-5 puan) hesabı
3. Kurulum Süresi ve Ek Müdahale Kronometresi (Madde 8.3.5):
   - t_eff = t_measured + sum(dt_intervention + 10.0 s)
   - 8 dakika (480s) sert diskalifiye eşiği denetimi
4. Tablo 3 Rekabetçi Puan Hassasiyet (Sensitivity) Analizi:
   - +100g faydalı yük, -10s uçuş süresi, -%10 kutu hacmi gibi mühendislik ödünleşmelerinin
     toplam PG1 ve PG2 puanına net katkısını hesaplar.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
import math


@dataclass
class MassComponent:
    """İHA üzerindeki tekil kütle bileşeni (gövde, batarya, yük vb.)."""
    name: str
    mass_kg: float
    x_m: float  # Boylamasına konum (burun +x, kuyruk -x)
    y_m: float  # Enlemesine konum (sağ +y, sol -y)
    z_m: float  # Dikey konum (yukarı +z)
    is_droppable_payload: bool = False
    payload_slot: Optional[int] = None


@dataclass
class CGState:
    """Belirli bir uçuş konfigürasyonundaki toplam kütle ve CG durumu."""
    configuration: str
    total_mass_kg: float
    cg_x_m: float
    cg_y_m: float
    cg_z_m: float
    mtow_compliant: bool
    cg_within_limits: bool
    cg_shift_from_nominal_mm: float


@dataclass
class TransportBoxAudit:
    """Şartname Madde 8.3.4 Muhafaza Kutusu doğrulama raporu."""
    category: str
    geometry: str
    volume_m3: float
    volume_liters: float
    is_compliant: bool
    external_item_penalty_pts: float
    violations: List[str] = field(default_factory=list)


@dataclass
class SetupTimingAudit:
    """Şartname Madde 8.3.5 Kurulum süresi ve ek müdahale ceza analizi."""
    measured_setup_s: float
    intervention_count: int
    total_intervention_duration_s: float
    penalty_added_s: float
    effective_setup_s: float
    within_8min_limit: bool
    remaining_margin_s: float


class CompetitionOptimizer:
    """
    Ağırlık/CG dengesi, muhafaza kutusu uyumu, kurulum süresi cezaları ve
    Tablo 3 puan hassasiyeti için entegre yarışma mühendisliği motoru.
    """

    MTOW_LIMIT_KG = 4.0
    SETUP_LIMIT_S = 480.0
    INTERVENTION_PENALTY_EACH_S = 10.0

    def __init__(
        self,
        category: str = "rotary_wing",
        cg_x_limits_m: Tuple[float, float] = (-0.04, 0.04),
        cg_y_limits_m: Tuple[float, float] = (-0.025, 0.025)
    ):
        self.category = category.lower()
        self.cg_x_limits_m = cg_x_limits_m
        self.cg_y_limits_m = cg_y_limits_m

    def _compute_cg(self, components: List[MassComponent], label: str, ref_cg: Optional[Tuple[float, float]] = None) -> CGState:
        total_m = sum(c.mass_kg for c in components)
        if total_m <= 1e-6:
            return CGState(label, 0.0, 0.0, 0.0, 0.0, True, True, 0.0)

        cg_x = sum(c.mass_kg * c.x_m for c in components) / total_m
        cg_y = sum(c.mass_kg * c.y_m for c in components) / total_m
        cg_z = sum(c.mass_kg * c.z_m for c in components) / total_m

        mtow_ok = total_m <= self.MTOW_LIMIT_KG
        cg_ok = (self.cg_x_limits_m[0] <= cg_x <= self.cg_x_limits_m[1]) and (
            self.cg_y_limits_m[0] <= cg_y <= self.cg_y_limits_m[1]
        )

        shift_mm = 0.0
        if ref_cg is not None:
            shift_mm = math.hypot(cg_x - ref_cg[0], cg_y - ref_cg[1]) * 1000.0

        return CGState(
            configuration=label,
            total_mass_kg=round(total_m, 4),
            cg_x_m=round(cg_x, 5),
            cg_y_m=round(cg_y, 5),
            cg_z_m=round(cg_z, 5),
            mtow_compliant=mtow_ok,
            cg_within_limits=cg_ok,
            cg_shift_from_nominal_mm=round(shift_mm, 2)
        )

    def analyze_weight_and_balance(self, components: List[MassComponent]) -> Dict[str, CGState]:
        """
        Tam yüklü, 1. yük bırakılmış, 2. yük bırakılmış (boş) konfigürasyonlar için
        MTOW ve CG kayması (mm) analizini üretir.
        """
        full = self._compute_cg(components, "FULL_LOAD")
        ref = (full.cg_x_m, full.cg_y_m)

        after_drop_1 = [c for c in components if not (c.is_droppable_payload and c.payload_slot == 1)]
        after_drop_2 = [c for c in components if not c.is_droppable_payload]

        s1 = self._compute_cg(after_drop_1, "AFTER_PAYLOAD_1_DROP", ref_cg=ref)
        s2 = self._compute_cg(after_drop_2, "EMPTY_AFTER_ALL_DROPS", ref_cg=ref)

        return {
            "full_load": full,
            "after_drop_1": s1,
            "empty": s2
        }

    def audit_transport_box(
        self,
        geometry: str,
        dimensions_m: Tuple[float, ...],
        single_person_portable: bool = True,
        external_items_count: int = 0
    ) -> TransportBoxAudit:
        """
        Şartname Madde 8.3.4 muhafaza kutusu denetimi:
        - Sabit Kanat: geometry == "cylindrical", dimensions_m = (diameter_m, length_m)
        - Döner Kanat: geometry == "rectangular_prism", dimensions_m = (a_m, b_m, c_m)
        """
        violations: List[str] = []
        geom = geometry.lower().strip()
        vol_m3 = 0.0

        if self.category == "fixed_wing":
            if geom != "cylindrical":
                violations.append("Sabit kanat kategorisinde dairesel kesitli silindirik kutu zorunludur (elips/prizma yasak).")
            if len(dimensions_m) == 2:
                diameter, length = dimensions_m
                if diameter <= 0 or length <= 0:
                    violations.append("Kutu boyutları pozitif olmalıdır.")
                else:
                    r = diameter / 2.0
                    vol_m3 = math.pi * (r ** 2) * length
            else:
                violations.append("Silindirik kutu için (çap_m, boy_m) şeklinde 2 boyut verilmelidir.")
        else:
            if geom not in ("rectangular_prism", "prism", "square_prism"):
                violations.append("Döner kanat kategorisinde dikdörtgen veya kare prizma kutu zorunludur.")
            if len(dimensions_m) == 3:
                a, b, c = dimensions_m
                if a <= 0 or b <= 0 or c <= 0:
                    violations.append("Prizma boyutları pozitif olmalıdır.")
                else:
                    vol_m3 = a * b * c
            else:
                violations.append("Prizma kutu için (en_m, boy_m, yükseklik_m) şeklinde 3 boyut verilmelidir.")

        if not single_person_portable:
            violations.append("Muhafaza kutusu tek (1) kişi tarafından taşınabilir olmalıdır.")

        ext_penalty = float(min(5, max(0, external_items_count * 2)))
        if external_items_count > 0:
            violations.append(f"Kutu harici {external_items_count} parça tespit edildi (Ceza 1: -{ext_penalty:.1f} puan).")

        return TransportBoxAudit(
            category=self.category,
            geometry=geom,
            volume_m3=round(vol_m3, 5),
            volume_liters=round(vol_m3 * 1000.0, 2),
            is_compliant=(len(violations) == 0),
            external_item_penalty_pts=ext_penalty,
            violations=violations
        )

    def audit_setup_timing(
        self,
        measured_setup_s: float,
        interventions_s: Optional[List[float]] = None
    ) -> SetupTimingAudit:
        """
        Şartname Madde 8.3.5:
        t_eff = t_measured + sum(dt_intervention + 10.0)
        """
        int_list = interventions_s or []
        int_count = len(int_list)
        total_int_dur = sum(max(0.0, d) for d in int_list)
        penalty_s = total_int_dur + int_count * self.INTERVENTION_PENALTY_EACH_S
        eff_s = measured_setup_s + penalty_s
        margin_s = self.SETUP_LIMIT_S - eff_s

        return SetupTimingAudit(
            measured_setup_s=round(measured_setup_s, 2),
            intervention_count=int_count,
            total_intervention_duration_s=round(total_int_dur, 2),
            penalty_added_s=round(penalty_s, 2),
            effective_setup_s=round(eff_s, 2),
            within_8min_limit=(eff_s <= self.SETUP_LIMIT_S),
            remaining_margin_s=round(margin_s, 2)
        )

    def compute_table3_score(
        self,
        c_autonomy: float = 1.0,
        vol_tk: float = 0.144,
        vol_min: float = 0.110,
        t_haz_tk: float = 180.0,
        t_haz_min: float = 120.0,
        w0_tk: float = 2.0,
        w0_min: float = 1.6,
        w_yuk_tk: float = 1.2,
        w_yuk_max: float = 1.6,
        d_target_a_tk: float = 1.0,
        d_target_a_min: float = 0.5,
        d_target_b_tk: float = 1.0,
        d_target_b_min: float = 0.5,
        t_ucus_tk: float = 150.0,
        t_ucus_min: float = 110.0,
        ay_bonus: bool = False,
        by_bonus: bool = False,
        penalty_pts: float = 0.0
    ) -> Dict[str, float]:
        """TÜBİTAK Tablo 3 PG1 ve PG2 puanlarını hesaplar."""
        r_vol = min(1.0, vol_min / max(1e-5, vol_tk))
        r_haz = min(1.0, t_haz_min / max(1.0, t_haz_tk))
        r_w0 = min(1.0, w0_min / max(0.1, w0_tk))
        r_ucus = min(1.0, t_ucus_min / max(1.0, t_ucus_tk))
        r_yuk = min(1.0, w_yuk_tk / max(0.05, w_yuk_max))
        r_da = min(1.0, d_target_a_min / max(0.05, d_target_a_tk))
        r_db = min(1.0, d_target_b_min / max(0.05, d_target_b_tk))

        pg1 = max(0.0, c_autonomy * (6.0 * r_vol + 6.0 * r_haz + 6.0 * r_w0 + 12.0 * r_ucus) - penalty_pts)

        if self.category == "fixed_wing":
            pg2 = max(
                0.0,
                c_autonomy * (
                    4.0 * r_vol + 4.0 * r_haz + 4.0 * r_w0
                    + 20.0 * r_yuk + 10.0 * r_da + 20.0 * r_db + 8.0 * r_ucus
                ) - penalty_pts
            )
        else:
            bonus = 10.0 * ((1.0 if ay_bonus else 0.0) + (1.0 if by_bonus else 0.0))
            pg2 = max(
                0.0,
                c_autonomy * (
                    4.0 * r_vol + 4.0 * r_haz + 4.0 * r_w0
                    + 20.0 * r_yuk + 8.0 * r_da + 12.0 * r_db + bonus + 8.0 * r_ucus
                ) - penalty_pts
            )

        return {
            "pg1": round(pg1, 2),
            "pg2": round(pg2, 2),
            "total_flight_score": round(pg1 + pg2, 2)
        }

    def run_sensitivity_analysis(self, baseline_kwargs: Dict[str, Any]) -> Dict[str, float]:
        """
        Mühendislik ödünleşme (trade-off) hassasiyet analizi:
        Baz tasarıma kıyasla iyileştirmelerin toplam PG1+PG2 puanına etkisini döndürür.
        """
        base = self.compute_table3_score(**baseline_kwargs)["total_flight_score"]

        def delta_with(**overrides) -> float:
            kw = dict(baseline_kwargs)
            kw.update(overrides)
            return round(self.compute_table3_score(**kw)["total_flight_score"] - base, 3)

        return {
            "baseline_total": base,
            "delta_plus_200g_payload": delta_with(w_yuk_tk=baseline_kwargs.get("w_yuk_tk", 1.2) + 0.2),
            "delta_minus_15pct_box_volume": delta_with(vol_tk=baseline_kwargs.get("vol_tk", 0.144) * 0.85),
            "delta_minus_30s_setup": delta_with(t_haz_tk=max(60.0, baseline_kwargs.get("t_haz_tk", 180.0) - 30.0)),
            "delta_minus_20s_flight": delta_with(t_ucus_tk=max(40.0, baseline_kwargs.get("t_ucus_tk", 150.0) - 20.0)),
            "delta_enable_g3_bonus": delta_with(ay_bonus=True, by_bonus=True)
        }
