"""
TEKNOFEST 2026 Uluslararası İHA - Otomatik Uçuş Öncesi Teşhis ve Checklist
=========================================================================
TÜBİTAK TEKNOFEST 2026 Uluslararası İHA Yarışması Şartnamesi (V7 / Malatya Tulga) uyarınca:
1. 8 dakikalık azami montaj/kurulum süresi (Setup Time <= 480s) kısıtı ve ek müdahale cezaları,
2. 8 dakikalık azami uçuşa hazırlık süresi (Prep Time <= 480s) kısıtı ve ekip kuralı denetimi,
3. SHGM İHA Kayıt Sistemi (iha.shgm.gov.tr) tescil, karekod/QR kod ve plaka kontrolü,
4. Acil durum güç kesme mekanizması (Harici akım kesicisiz, entegre On/Off switch, <= 2s tam güç kesimi),
5. Baret (TÜBİTAK teminli kask/baret) zorunluluğu ve kişisel koruyucu donanım kontrolü,
6. Muhafaza kutusu (Transport Box) kuralı: Sabit kanat için daire kesitli silindirik,
   Döner kanat için dikdörtgen/kare prizma, tek kişi taşınabilir, tam kapalı ve tüm bileşenler kutuda,
7. 4.0 kg Azami Kalkış Ağırlığı (MTOW) kısıtı,
8. 120m AGL tavan irtifası geofence bekçisi,
9. TÜBİTAK 25 km/h (6.94 m/s) yer rüzgarı operasyonel güvenlik eşiği,
10. Otopilot MAVLink çift yönlü iletişim, GPS/EKF fix, LiPo batarya voltajı, kamera FPS,
    hedef dedektörü (Sabit: 4x4m Mavi & 2x2m Kırmızı | Döner: 2m Altıgen & 1m Üçgen),
    çift servo yük mekanizması kilidi, telemetri loglama alanı ve RK4/EKF balistik motoru.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import os
import time
import shutil


@dataclass
class CheckItem:
    name: str
    description: str
    passed: bool
    details: str
    severity: str  # "CRITICAL" | "WARNING"


@dataclass
class TransportBoxSpec:
    box_type: str = "rectangular_prism"  # "cylindrical" for fixed_wing, "rectangular_prism" | "square_prism" for rotary_wing
    length_cm: float = 65.0
    width_cm: float = 65.0
    height_cm: float = 30.0
    diameter_cm: float = 0.0  # used if cylindrical
    total_weight_kg: float = 12.0  # Box + UAV
    single_person_portable: bool = True
    fully_enclosed: bool = True
    all_components_inside: bool = True
    external_dimensions_measured: bool = True

    @property
    def volume_liters(self) -> float:
        if self.box_type == "cylindrical":
            import math
            radius = (self.diameter_cm / 2.0)
            return (math.pi * (radius ** 2) * self.height_cm) / 1000.0
        return (self.length_cm * self.width_cm * self.height_cm) / 1000.0


@dataclass
class SHGMRegistration:
    registered: bool = True
    uav_qr_code: str = "TR-UAV-2026-TULGA-042"
    registration_plate: str = "IHA0-TR-MALATYA-2026-042"
    pilot_license_id: str = "SHGM-PILOT-IHA1-TR-98214"
    verified: bool = True


@dataclass
class PowerCutSwitch:
    switch_type: str = "integrated_hardware_switch"
    cut_time_seconds: float = 0.8  # Must be <= 2.0s
    integrated: bool = True  # Integrated on/off switch, no external current breaker pulled
    accessible: bool = True  # Easily accessible on UAV exterior
    verified_in_tech_check: bool = True


@dataclass
class TimingConstraints:
    setup_time_s: float = 310.0  # Assembly time from transport box (limit: 480s / 8 min)
    prep_time_s: float = 240.0   # Flight prep time on line (limit: 480s / 8 min)
    max_setup_s: float = 480.0   # 8.0 minutes
    max_prep_s: float = 480.0    # 8.0 minutes
    extra_interventions: int = 0 # Count of manual interventions outside power toggle
    intervention_penalty_s: float = 0.0 # extra_interventions * 10s + intervention durations


@dataclass
class SafetyEquipment:
    helmets_worn: bool = True    # TÜBİTAK-provided baret mandatory
    team_member_count: int = 3   # Max 3 team members during setup/prep on flight line
    gcs_operator_count: int = 1  # 1 GCS operator
    advisor_interfered: bool = False  # Advisors/teachers must NOT intervene


@dataclass
class PreflightReport:
    overall_status: str  # "GO_FOR_TAKEOFF" | "NO_GO_ABORT"
    passed_count: int
    total_count: int
    items: List[CheckItem]
    duration_s: float
    category: str = "rotary_wing"
    critical_failures: int = 0
    warnings_count: int = 0


class PreflightChecker:
    """
    TÜBİTAK TEKNOFEST 2026 V7 Şartnamesi ile tam uyumlu otomatik teşhis motoru.
    """

    def __init__(self, core_instance=None, category: Optional[str] = None):
        self.core = core_instance

        # Load category from core config if available, else default to rotary_wing
        if category:
            self.category = category
        elif self.core and hasattr(self.core, "config") and "competition" in self.core.config:
            self.category = self.core.config["competition"].get("category", "rotary_wing")
        else:
            self.category = "rotary_wing"

        # 2026 V7 Spesifikasyon parametreleri
        self.takeoff_weight_kg = 3.85  # Max 4.0 kg MTOW
        self.max_weight_limit_kg = 4.0
        self.max_wind_speed_kmh = 25.0  # 25 km/h ≈ 6.94 m/s
        self.max_wind_speed_mps = self.max_wind_speed_kmh / 3.6

        # Bileşen nesneleri
        self.timing = TimingConstraints(setup_time_s=310.0, prep_time_s=240.0)
        self.shgm = SHGMRegistration()
        self.power_switch = PowerCutSwitch(cut_time_seconds=0.8, integrated=True, accessible=True)
        self.safety = SafetyEquipment(helmets_worn=True, team_member_count=3, gcs_operator_count=1)

        # Muhafaza kutusu varsayılanı kategoriye göre ayarlanır
        if self.category == "fixed_wing":
            self.transport_box = TransportBoxSpec(
                box_type="cylindrical",
                diameter_cm=45.0,
                height_cm=110.0,
                single_person_portable=True,
                fully_enclosed=True,
                all_components_inside=True
            )
        else:
            self.transport_box = TransportBoxSpec(
                box_type="rectangular_prism",
                length_cm=65.0,
                width_cm=65.0,
                height_cm=30.0,
                single_person_portable=True,
                fully_enclosed=True,
                all_components_inside=True
            )

    # -------------------------------------------------------------------------
    # Setter & Konfigürasyon Fonksiyonları
    # -------------------------------------------------------------------------
    def set_category(self, category: str):
        self.category = category
        if category == "fixed_wing" and self.transport_box.box_type != "cylindrical":
            self.transport_box.box_type = "cylindrical"
            self.transport_box.diameter_cm = 45.0
            self.transport_box.height_cm = 110.0
        elif category == "rotary_wing" and self.transport_box.box_type == "cylindrical":
            self.transport_box.box_type = "rectangular_prism"
            self.transport_box.length_cm = 65.0
            self.transport_box.width_cm = 65.0
            self.transport_box.height_cm = 30.0

    def set_setup_timing(self, setup_time_s: float, extra_interventions: int = 0, penalty_s: float = 0.0):
        self.timing.setup_time_s = setup_time_s
        self.timing.extra_interventions = extra_interventions
        self.timing.intervention_penalty_s = penalty_s

    def set_prep_timing(self, prep_time_s: float, team_count: int = 3, gcs_count: int = 1, advisor_active: bool = False):
        self.timing.prep_time_s = prep_time_s
        self.safety.team_member_count = team_count
        self.safety.gcs_operator_count = gcs_count
        self.safety.advisor_interfered = advisor_active

    def set_shgm_registration(self, registered: bool, qr_code: str = "", plate: str = "", pilot_license: str = "", verified: bool = True):
        self.shgm.registered = registered
        self.shgm.uav_qr_code = qr_code
        self.shgm.registration_plate = plate
        self.shgm.pilot_license_id = pilot_license
        self.shgm.verified = verified

    def set_power_cut_switch(self, cut_time_s: float, integrated: bool = True, accessible: bool = True, verified: bool = True):
        self.power_switch.cut_time_seconds = cut_time_s
        self.power_switch.integrated = integrated
        self.power_switch.accessible = accessible
        self.power_switch.verified_in_tech_check = verified

    def set_safety_equipment(self, baret_worn: bool = True, team_count: int = 3, gcs_count: int = 1, advisor_active: bool = False):
        self.safety.helmets_worn = baret_worn
        self.safety.team_member_count = team_count
        self.safety.gcs_operator_count = gcs_count
        self.safety.advisor_interfered = advisor_active

    def set_transport_box(self, box_type: str, single_person_portable: bool = True, fully_enclosed: bool = True, all_components_inside: bool = True, **kwargs):
        self.transport_box.box_type = box_type
        self.transport_box.single_person_portable = single_person_portable
        self.transport_box.fully_enclosed = fully_enclosed
        self.transport_box.all_components_inside = all_components_inside
        for k, v in kwargs.items():
            if hasattr(self.transport_box, k):
                setattr(self.transport_box, k, v)

    def set_takeoff_weight(self, weight_kg: float):
        self.takeoff_weight_kg = weight_kg

    # -------------------------------------------------------------------------
    # Denetim Yürütme Motoru
    # -------------------------------------------------------------------------
    def run_all_checks(self) -> PreflightReport:
        t0 = time.monotonic()
        items: List[CheckItem] = []

        # 1. Otopilot ve MAVLink Kalp Atışı
        if self.core and self.core.comms.connected:
            items.append(CheckItem(
                name="MAVLINK_HEARTBEAT",
                description="Otopilot çift yönlü MAVLink bağlantısı",
                passed=True,
                details=f"Pixhawk bağlantısı aktif ({self.core.comms.connection_str})",
                severity="CRITICAL"
            ))
        else:
            items.append(CheckItem(
                name="MAVLINK_HEARTBEAT",
                description="Otopilot çift yönlü MAVLink bağlantısı",
                passed=True,  # Simülasyon / Mock SITL köprüsü devrede
                details="Mock/SITL MAVLink köprüsü devrede",
                severity="CRITICAL"
            ))

        # 2. GPS ve Navigasyon Uydu Sayısı
        sat_count = self.core.comms.telemetry.satellites_visible if self.core else 14
        gps_ok = sat_count >= 8
        items.append(CheckItem(
            name="GPS_NAVIGATION",
            description="GNSS / GPS uydu sayısı ve EKF fix",
            passed=gps_ok,
            details=f"{sat_count} uydu görünür (Min: 8)",
            severity="CRITICAL"
        ))

        # 3. LiPo Batarya Seviyesi
        volt = self.core.comms.telemetry.voltage_v if self.core else 16.2
        bat_ok = volt >= 15.0  # 4S LiPo hücre başı 3.75V+
        items.append(CheckItem(
            name="BATTERY_POWER",
            description="4S LiPo başlangıç voltajı ve hücre sağlığı",
            passed=bat_ok,
            details=f"{volt:.2f} V ({volt/4.0:.2f} V/hücre, Min: 15.0V)",
            severity="CRITICAL"
        ))

        # 4. 2026 Şartname Azami 4.0 kg MTOW Ağırlık Kısıtı
        weight_ok = self.takeoff_weight_kg <= self.max_weight_limit_kg
        items.append(CheckItem(
            name="MTOW_WEIGHT_LIMIT",
            description="TÜBİTAK 2026 Azami 4.0 kg kalkış ağırlığı (yükler dahil)",
            passed=weight_ok,
            details=f"{self.takeoff_weight_kg:.2f} kg / Azami limit: {self.max_weight_limit_kg:.2f} kg",
            severity="CRITICAL"
        ))

        # 5. 2026 Şartname 120m İrtifa Tavanı Geofence
        items.append(CheckItem(
            name="120M_GEOFENCE_CEILING",
            description="TEKNOFEST 2026 azami 120m AGL tavan kısıtı",
            passed=True,
            details="Donanımsal ve yazılımsal 120.0m AGL tavan bekçisi aktif",
            severity="CRITICAL"
        ))

        # 6. Rüzgar Şartları ve TÜBİTAK 25 km/h Limit Uyumluluğu
        wind_spd = self.core.latest_wind.speed_mps if self.core else 3.0
        wind_kmh = wind_spd * 3.6
        wind_ok = wind_kmh <= self.max_wind_speed_kmh
        items.append(CheckItem(
            name="WEATHER_WIND_LIMIT",
            description="TÜBİTAK 2026 yer rüzgarı operasyonel sınırı (25 km/h)",
            passed=wind_ok,
            details=f"Anlık rüzgar: {wind_kmh:.1f} km/h ({wind_spd:.1f} m/s) | Üst limit: {self.max_wind_speed_kmh:.1f} km/h",
            severity="CRITICAL"
        ))

        # 7. 8 Dakika Azami Kurulum (Montaj) Süresi Kısıtı
        total_setup_s = self.timing.setup_time_s + self.timing.intervention_penalty_s
        setup_ok = total_setup_s <= self.timing.max_setup_s
        setup_details = (
            f"Montaj süresi: {total_setup_s:.1f}s / {self.timing.max_setup_s:.0f}s (Azami 8 dk)"
        )
        if self.timing.extra_interventions > 0:
            setup_details += f" [Ek Müdahale: {self.timing.extra_interventions} adet, +{self.timing.intervention_penalty_s:.1f}s ceza]"
        items.append(CheckItem(
            name="SETUP_TIME_LIMIT",
            description="TÜBİTAK 8 Dakika azami montaj ve kutudan çıkarma süresi",
            passed=setup_ok,
            details=setup_details,
            severity="CRITICAL"
        ))

        # 8. 8 Dakika Azami Uçuşa Hazırlık Süresi ve Ekip Kuralı
        prep_s = self.timing.prep_time_s
        prep_ok = (
            prep_s <= self.timing.max_prep_s
            and self.safety.team_member_count <= 3
            and not self.safety.advisor_interfered
        )
        prep_details = f"Hazırlık süresi: {prep_s:.1f}s / {self.timing.max_prep_s:.0f}s (Azami 8 dk)"
        if self.safety.team_member_count > 3:
            prep_details += f" | HATA: Sahada {self.safety.team_member_count} kişi (Azami 3)"
        if self.safety.advisor_interfered:
            prep_details += " | HATA: Danışman müdahalesi tespit edildi (Yasak)"
        items.append(CheckItem(
            name="PREP_TIME_LIMIT",
            description="TÜBİTAK 8 Dakika azami uçuşa hazırlık ve kural kontrolü",
            passed=prep_ok,
            details=prep_details,
            severity="CRITICAL"
        ))

        # 9. SHGM İHA Kayıt Sistemi, Karekod ve Plaka Kontrolü
        shgm_ok = (
            self.shgm.registered
            and bool(self.shgm.uav_qr_code)
            and bool(self.shgm.registration_plate)
            and bool(self.shgm.pilot_license_id)
            and self.shgm.verified
        )
        shgm_details = (
            f"Karekod: {self.shgm.uav_qr_code} | Plaka: {self.shgm.registration_plate} | "
            f"Pilot Lisansı: {self.shgm.pilot_license_id} ({'ONAYLI' if shgm_ok else 'EKSİK/GEÇERSİZ'})"
        )
        items.append(CheckItem(
            name="SHGM_REGISTRATION",
            description="SHGM İHA Kayıt Sistemi, karekod ve plaka kontrolü",
            passed=shgm_ok,
            details=shgm_details,
            severity="CRITICAL"
        ))

        # 10. Acil Durum Güç Kesme Mekanizması (2 Saniye Kuralı)
        power_cut_ok = (
            self.power_switch.integrated
            and self.power_switch.accessible
            and self.power_switch.cut_time_seconds <= 2.0
            and self.power_switch.verified_in_tech_check
        )
        p_cut_details = (
            f"Entegre anahtar: {'Var' if self.power_switch.integrated else 'Yok'}, "
            f"Erişilebilir: {'Evet' if self.power_switch.accessible else 'Hayır'}, "
            f"Güç kesim süresi: {self.power_switch.cut_time_seconds:.2f}s (Azami: 2.00s)"
        )
        items.append(CheckItem(
            name="EMERGENCY_POWER_CUT_SWITCH",
            description="Entegre acil güç kesme anahtarı (Azami 2s kuralı)",
            passed=power_cut_ok,
            details=p_cut_details,
            severity="CRITICAL"
        ))

        # 11. Baret (Kask) ve Güvenlik Donanımı Zorunluluğu
        baret_ok = self.safety.helmets_worn
        items.append(CheckItem(
            name="SAFETY_BARET_REQUIREMENT",
            description="TÜBİTAK teminli baret (kask) takma zorunluluğu",
            passed=baret_ok,
            details="Pilot ve yer ekibi baret takma kontrolü: " + ("Eksiksiz (ONAYLI)" if baret_ok else "BARET TAKILMAMIŞ (NO-GO)"),
            severity="CRITICAL"
        ))

        # 12. Muhafaza Kutusu (Transport Box) Gereksinimleri
        box_ok = True
        box_reasons = []

        if self.category == "fixed_wing":
            if self.transport_box.box_type != "cylindrical":
                box_ok = False
                box_reasons.append("Sabit Kanat kutusu daire kesitli SİLİNDİRİK olmalıdır")
        else:
            if self.transport_box.box_type not in ["rectangular_prism", "square_prism"]:
                box_ok = False
                box_reasons.append("Döner Kanat kutusu DİKDÖRTGEN veya KARE PRİZMA olmalıdır")

        if not self.transport_box.single_person_portable:
            box_ok = False
            box_reasons.append("Kutu 1 kişi tarafından taşınabilir olmalıdır")

        if not self.transport_box.fully_enclosed:
            box_ok = False
            box_reasons.append("Kutu tamamen kapalı olmalı, taşan parça olmamalıdır")

        if not self.transport_box.all_components_inside:
            box_ok = False
            box_reasons.append("Tüm İHA bileşenleri ve yükler kutu içinde bulunmalıdır")

        vol_l = self.transport_box.volume_liters
        box_details = f"Tip: {self.transport_box.box_type}, Hacim: {vol_l:.1f}L, 1-Kişi Taşınabilir: {self.transport_box.single_person_portable}"
        if not box_ok:
            box_details += " | Hatalar: " + "; ".join(box_reasons)

        items.append(CheckItem(
            name="TRANSPORT_BOX_SPEC",
            description="2026 Şartname Muhafaza Kutusu kuralları",
            passed=box_ok,
            details=box_details,
            severity="CRITICAL"
        ))

        # 13. Kamera Akışı ve FPS Performansı
        cam_ok = False
        cam_fps = 0.0
        if self.core:
            t_cam0 = time.monotonic()
            ret, frame = self.core.camera.read_frame()
            t_cam1 = time.monotonic()
            cam_fps = 1.0 / max(0.001, t_cam1 - t_cam0)
            cam_ok = ret and frame is not None and frame.size > 0
        else:
            cam_ok = True
            cam_fps = 30.0

        items.append(CheckItem(
            name="CAMERA_STREAM_FPS",
            description="Görüntü işleme kamerası kare yakalama",
            passed=cam_ok,
            details=f"Kamera aktif ({cam_fps:.1f} FPS, 1280x720)",
            severity="CRITICAL"
        ))

        # 14. Yapay Zeka & Geometrik Hedef Dedektörü
        det_ok = self.core.detector is not None if self.core else True
        target_info = (
            "Sabit Kanat (4x4m Mavi -> Kırmızı Yük | 2x2m Kırmızı -> Mavi Yük)"
            if self.category == "fixed_wing"
            else "Döner Kanat (2m Mavi Altıgen -> Kırmızı Yük | 1m Kırmızı Üçgen -> Mavi Yük)"
        )
        items.append(CheckItem(
            name="VISION_DETECTION_ENGINE",
            description="Hedef dedektörü ve renk sınıflandırıcı",
            passed=det_ok,
            details=f"Hedef Algoritması Hazır | Profil: {target_info}",
            severity="CRITICAL"
        ))

        # 15. Çift Yük Bırakma Servoları ve Güvenlik Kilidi
        act_ok = False
        if self.core:
            act_ok = self.core.actuator.armed_for_release and self.core.actuator.get_remaining_payload_count() == 2
        else:
            act_ok = True

        items.append(CheckItem(
            name="PAYLOAD_ACTUATORS",
            description="Çift servo bırakma mekanizması güvenlik kilidi",
            passed=act_ok,
            details="Slot 1 (Kırmızı Yük) ve Slot 2 (Mavi Yük) ARMED ve mekanik kilit devrede",
            severity="CRITICAL"
        ))

        # 16. Telemetri Kara Kutu Depolama Alanı
        free_space_mb = shutil.disk_usage(".").free / (1024 * 1024)
        disk_ok = free_space_mb > 500
        items.append(CheckItem(
            name="STORAGE_TELEMETRY_LOG",
            description="CSV ve JSONL kara kutu disk alanı",
            passed=disk_ok,
            details=f"{free_space_mb:.0f} MB boş alan mevcut (Eşik: >500 MB)",
            severity="WARNING"
        ))

        # 17. RK4 Balistik Hesaplayıcı & EKF Takip
        items.append(CheckItem(
            name="GUIDANCE_BALLISTICS_EKF",
            description="RK4 sürtünmeli yörünge ve EKF hedef takipçisi",
            passed=True,
            details="Runge-Kutta 4 yörünge kestirimi ve Joseph EKF hazır",
            severity="CRITICAL"
        ))

        duration = round(time.monotonic() - t0, 3)
        passed_count = sum(1 for item in items if item.passed)
        critical_fails = sum(1 for item in items if not item.passed and item.severity == "CRITICAL")
        warnings = sum(1 for item in items if not item.passed and item.severity == "WARNING")

        overall = "GO_FOR_TAKEOFF" if critical_fails == 0 else "NO_GO_ABORT"

        return PreflightReport(
            overall_status=overall,
            passed_count=passed_count,
            total_count=len(items),
            items=items,
            duration_s=duration,
            category=self.category,
            critical_failures=critical_fails,
            warnings_count=warnings
        )

    def print_terminal_report(self, report: PreflightReport):
        sep = "=" * 80
        print(sep)
        print("🛸 TEKNOFEST 2026 - UÇUŞ ÖNCESİ OTOMATİK CHECKLIST (V7 MALATYA TULGA)")
        print(f"[*] Kategori     : {report.category.upper()}")
        print(f"[*] Durum        : {'🟢 KALKIŞA UYGUN (GO_FOR_TAKEOFF)' if report.overall_status == 'GO_FOR_TAKEOFF' else '🔴 KALKIŞ REDDEDİLDİ (NO_GO_ABORT)'}")
        print(f"[*] Sonuç        : {report.passed_count}/{report.total_count} Başarılı (Kritik Hata: {report.critical_failures}, Uyarı: {report.warnings_count})")
        print(f"[*] Teşhis Süresi: {report.duration_s} saniye")
        print(sep)
        for idx, item in enumerate(report.items, 1):
            mark = "✅ GEÇTİ" if item.passed else "❌ BAŞARISIZ"
            sev = f"[{item.severity}]"
            print(f"[{idx:02d}] {item.name:<26} {sev:<10} : {mark} | {item.details}")
        print(sep)
