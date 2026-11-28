"""
TEKNOFEST 2026 Uluslararası İHA - Entegre Misyon ve Komuta Merkezi (Mission Control)
=====================================================================================
Tüm alt sistemleri (SITL Sunucusu, Web GCS, Pre-flight Checklist, Canlı Simülatör,
Uçuş Analitiği, KML Harita İhracatı, Kamera Teşhisi ve Sentetik Veri Üreteci)
tek bir interaktif komuta kabuğundan yönetmeyi sağlayan ana operasyonel CLI aracı.
"""

import sys
import os
import math
import argparse
import time

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.main_brain.core import ArchitectCore
from src.avionics.preflight import PreflightChecker
from src.telemetry.analytics import FlightAnalyticsEngine
from src.telemetry.geo_export import FlightTrajectoryExporter
from src.vision.dataset_generator import SyntheticDatasetGenerator
from src.telemetry.sitl_server import ArduPilotSITLServer
from src.web_gcs.server import WebGCSServer
from src.navigation.trajectory_optimizer import TrajectoryOptimizer
from src.avionics.sensor_fusion_validator import SensorFusionValidator
from src.navigation.mission_playbook import MissionPlaybook
from src.telemetry.debrief_engine import MissionDebriefEngine
from src.navigation.georeference import PinholeGeoReferencer, CameraIntrinsics, GimbalOrientation
from src.navigation.rolling_ballistics import RestingBallisticsOptimizer
from src.telemetry.mission_uploader import MAVLinkMissionUploader, MissionItem
from src.avionics.gimbal_controller import GimbalController
from src.simulation.flight_dynamics import FlightDynamics6DOF, ControlInputs
from src.avionics.emergency_recovery import EmergencyRecoveryManager
from src.avionics.air_data_computer import AirDataComputer
from src.avionics.payload_grabber import PayloadGrabberController
from src.navigation.payload_transfer_planner import PayloadTransferPlanner
from src.navigation.gust_alleviation import GustAlleviationController
from src.telemetry.referee_report_generator import RefereeReportGenerator
from src.telemetry.link_security import TelemetryLinkSecurity
from src.navigation.pylon_navigator import PylonNavigator
from src.simulation.monte_carlo import MonteCarloDropSimulator, MonteCarloConfig
from src.avionics.competition_optimizer import CompetitionOptimizer, MassComponent
from src.telemetry.crypto_link import CryptoTelemetryLink, RFMetrics
from src.avionics.storage_box_optimizer import (
    StorageBoxOptimizer,
    StorageBoxSpec,
    BoxGeometry,
    CompetitionTeamProfile
)
from src.navigation.pylon_gate_monitor import PylonGateMonitor
from src.simulation.mission_benchmark import MissionReadinessBenchmark, BenchmarkConfig
from src.avionics.propulsion_health import PropulsionHealthMonitor, PropulsionSnapshot
from src.telemetry.attempt_manager import CompetitionAttemptManager, FieldCrewRoster
from src.navigation.dubins_planner import DubinsPathPlanner, DubinsPose
from src.telemetry.flight_replayer import FlightTelemetryReplayer
import glob


MENU_BANNER = """
===========================================================================
🛸 UAV-ARCHITECT-GLOBAL | TEKNOFEST 2026 ENTEGRE KOMUTA MERKEZİ
===========================================================================
[1] 📋 Uçuş Öncesi Otomatik Kontrol (Pre-flight Checklist - 8 Dk Kısıtı)
[2] 🚀 Otonom Görev Simülasyonunu Başlat (SITL / Simülatör)
[3] 🌐 Web Tabanlı Canlı Yer Kontrol İstasyonunu Başlat (Web GCS)
[4] 🤖 ArduPilot MAVLink Mock SITL Sunucusunu Başlat (UDP:14550)
[5] 📊 Uçuş Sonrası Hakem Puanlama ve Uyumluluk Analizi
[6] 🗺️ 3B Uçuş Yolunu KML (Google Earth) ve GeoJSON Olarak Dışa Aktar
[7] 🎯 Kamera Netlik, Renk Eşikleme ve Hedef Tespit Teşhisi
[8] 🖼️ YOLOv10/v8 Uyumlu Sentetik Veri Seti Üret (Mavi Altıgen / Kırmızı Üçgen)
[9] 📈 3B Minimum-Jerk Yörünge Optimizasyonu Profili (Task 1 & 2)
[10] 🛡️ Sensör Çapraz Sağlık & FDIR Güvenlik Doğrulaması
[11] 📜 Görev Playbook & Fırsatçı Dinamik Hedef Yeniden Planlama
[12] 📑 Kara Kutu (Blackbox) Uçuş Brifingi & CEP İstatistik Raporu
[13] 🎯 Pinhole Ray Casting & WGS84 Georeferencing Doğrulaması
[14] 🛞 Şartname 5.3 Zemin Yuvarlanma & Durma Noktası Balistik Testi
[15] 🛰️ MAVLink Native Otopilot Görev Protokolü (Mission Upload)
[16] 🎥 Aktif 2/3 Eksen Gimbal Ufuk Stabilizasyonu & LOS Hedef Takibi
[17] ✈️ 6-DOF Aerodinamik Uçuş Dinamikleri Fiziği Simülatörü
[18] 🪂 Bağımsız Uçuş Kırım Önleme (FTS) & Balistik Paraşüt Sistemi
[19] 🌬️ Hava Veri Bilgisayarı (ADC) & Perdövites (Stall) Koruması
[20] 🦾 Döner Kanat Görev 3 Bonus Yük Alma (Grabber) & Transfer
[21] 🌪️ NASA F-Faktörü Rüzgar Kesmesi (Wind Shear) & Darbe Sönümleyici
[22] 📑 TÜBİTAK TEKNOFEST 2026 Resmi Hakem Denetim Raporu
[23] 🔐 Uçtan Uca Şifreli Telemetri & Jamming/Spoofing Koruması (Madde 9.4)
[24] 🏁 150m Direk Dış Dönüş Güdümü & Ceza 2 Önleme Kalkanı
[25] 🎲 Monte Carlo Balistik Dağılım (CEP50 / R95) Simülasyonu
[26] ⚖️ Ağırlık/CG Kayması, Muhafaza Kutusu & Tablo 3 Puan Optimizasyonu
[27] 🧪 Tüm Otomasyonel Test Paketini Çalıştır
[0] 🚪 Çıkış
===========================================================================
"""


def run_preflight():
    print("\n🔍 Uçuş öncesi kontroller icra ediliyor...")
    core = ArchitectCore(mode="simulation")
    checker = PreflightChecker(core_instance=core)
    report = checker.run_all_checks()
    checker.print_terminal_report(report)


def run_simulation(duration=35.0, task=2):
    print(f"\n🚀 Görev {task} simülasyonu başlatılıyor ({duration} saniye)...")
    core = ArchitectCore(mode="simulation", task=task)
    core.run_simulation(max_seconds=duration)


def run_web_gcs(port=8080):
    print(f"\n🌐 Web GCS başlatılıyor -> http://localhost:{port}")
    core = ArchitectCore(mode="simulation", task=2)
    core.start_mission()
    server = WebGCSServer(host="127.0.0.1", port=port, core_instance=core)
    server.start_background()
    print("[INFO] Çıkmak için Enter'a basın...")
    try:
        input()
    finally:
        server.stop()
        core.stop_mission()


def run_sitl_server(port=14550):
    print(f"\n🤖 MAVLink SITL sunucusu başlatılıyor -> udp://127.0.0.1:{port}")
    server = ArduPilotSITLServer(host="127.0.0.1", port=port)
    server.start()
    print("[INFO] ArduPilot SITL dinliyor. Durdurmak için Enter'a basın...")
    try:
        input()
    finally:
        server.stop()


def run_analytics():
    print("\n📊 En son uçuş günlüğü analiz ediliyor...")
    import glob
    csv_files = glob.glob(os.path.join("logs", "*.csv"))
    if not csv_files:
        print("[ANALYTICS] Henüz kaydedilmiş telemetri logu bulunamadı. Önce bir simülasyon çalıştırın.")
        return
    latest = max(csv_files, key=os.path.getctime)
    engine = FlightAnalyticsEngine(category="rotary_wing")
    summary = engine.analyze_csv_log(latest)
    if summary:
        print(engine.generate_markdown_report(summary))


def run_export():
    print("\n🗺️ 3B Uçuş haritası çıkarılıyor...")
    import glob
    csv_files = glob.glob(os.path.join("logs", "*.csv"))
    if not csv_files:
        print("[ERROR] CSV logu bulunamadı.")
        return
    latest = max(csv_files, key=os.path.getctime)
    exp = FlightTrajectoryExporter()
    kml = os.path.splitext(latest)[0] + ".kml"
    geojson = os.path.splitext(latest)[0] + ".geojson"
    exp.export_kml(latest, kml)
    exp.export_geojson(latest, geojson)
    print(f"✅ KML: {kml}")
    print(f"✅ GeoJSON: {geojson}")


def run_camera():
    from scripts.camera_check import run_camera_check
    run_camera_check(source="synthetic", width=1280, height=720, headless=True, max_frames=30)


def run_dataset_gen(count=20):
    print(f"\n🖼️ {count} adet sentetik eğitim karesi üretiliyor...")
    gen = SyntheticDatasetGenerator(output_dir="dataset_synthetic", width=1280, height=720)
    out = gen.generate_batch(count=count)
    print(f"✅ Veri seti dizini: {out}")


def run_trajectory():
    print("\n📈 3B Yörünge Optimizasyonu hesaplanıyor (Görev 1 Sonsuz ∞ Manevrası)...")
    opt = TrajectoryOptimizer(max_velocity=16.0, max_acceleration=4.0)
    pts, metrics = opt.optimize_figure_eight(center=(0.0, 0.0, 30.0), radius=35.0, num_waypoints=16)
    print(f"✅ Optimize Edilen Nokta Sayısı: {metrics.num_samples}")
    print(f"⏱️ Toplam Tahmini Uçuş Süresi: {metrics.total_duration_s} sn")
    print(f"📏 Toplam Rota Uzunluğu: {metrics.total_distance_m} m")
    print(f"⚡ Azami Hız: {metrics.max_speed_mps} m/s | Ortalama: {metrics.average_speed_mps} m/s")
    print(f"🔋 Tahmini Tüketim: {metrics.estimated_energy_wh} Wh")
    print("🎯 İlk 3 ve Son 3 Yörünge Noktası:")
    for p in pts[:3]:
        print(f"   T+{p.time_s:5.2f}s | Konum: ({p.x:6.2f}, {p.y:6.2f}, {p.z:5.1f})m | Hız: {p.speed:4.1f}m/s | Eğrilik: {p.curvature:.4f}")
    print("   ...")
    for p in pts[-3:]:
        print(f"   T+{p.time_s:5.2f}s | Konum: ({p.x:6.2f}, {p.y:6.2f}, {p.z:5.1f})m | Hız: {p.speed:4.1f}m/s | Eğrilik: {p.curvature:.4f}")


def run_fdir():
    print("\n🛡️ Çoklu Sensör FDIR (Hata Tespiti ve İzolasyonu) Testi...")
    validator = SensorFusionValidator()
    # Nominal case
    rep1 = validator.validate_sensors(timestamp=10.0, baro_alt=30.0, lidar_alt=29.8, gps_alt=30.2, gps_vx=12.0, gps_vy=0.5, flow_vx=11.9, flow_vy=0.4)
    print(f"1. Nominal Sensör Durumu: Sağlık = {rep1.health_level.value} | Eylem = {rep1.recommended_action.value}")
    # Glitch case
    rep2 = validator.validate_sensors(timestamp=11.0, baro_alt=30.0, lidar_alt=29.9, gps_alt=85.0, gps_vx=12.0, gps_vy=0.5)
    print(f"2. GPS Glitch Enjeksiyonu: Sağlık = {rep2.health_level.value} | İzolasyon = {rep2.isolated_sensors} | Tanılar = {rep2.diagnostic_messages}")


def run_playbook():
    print("\n📜 Görev Playbook & Dinamik Hedef Yeniden Sıralama Simülasyonu...")
    playbook = MissionPlaybook()
    st = playbook.update((0.0, 0.0, 0.0))
    print(f"Başlangıç Aşaması: {st.current_phase.value} (Aşama {st.phase_index + 1}/{st.total_phases})")
    # Simulate advance to search
    playbook.current_phase_idx = 3
    playbook._build_phase_waypoints()
    print(f"Arama Moduna Geçildi: Hedef Arama Alanı Waypoint Sayısı = {len(playbook.active_waypoints)}")
    # Opportunity replan trigger: Target B spotted while en route to Target A
    playbook.current_phase_idx = 4
    playbook._build_phase_waypoints()
    replan_ok = playbook.evaluate_opportunity_replan(
        current_uav_pos=(10.0, 5.0),
        detected_target_type="TARGET_B",
        target_pos=(25.0, 5.0),
        headwind_mps=2.5
    )
    st_replan = playbook.update((10.0, 5.0, 30.0))
    print(f"Fırsatçı Yeniden Sıralama Tetiklendi: {replan_ok}")
    print(f"Yeni Öncelikli Aşama: {st_replan.current_phase.value} | Atanan Yük Haznesi: Slot {st_replan.payload_slot_assigned}")


def run_debrief():
    print("\n📑 Kara Kutu (Blackbox) Uçuş Brifingi...")
    logs = sorted(glob.glob("logs/flight_telemetry_*.csv"), reverse=True)
    if not logs:
        print("⚠️ Henüz kayıtlı uçuş günlüğü (.csv) bulunamadı.")
        return
    engine = MissionDebriefEngine()
    target_log = None
    metrics = None
    for log_path in logs:
        m = engine.analyze_log_file(log_path)
        if m is not None:
            target_log = log_path
            metrics = m
            break
    if not metrics or not target_log:
        print("⚠️ Çözümlenebilecek uçuş verisi içeren telemetri günlüğü bulunamadı.")
        return
    report_md = engine.generate_markdown_report(metrics, target_log)
    print(report_md)


def run_georef():
    print("\n🎯 Pinhole Ray Casting & WGS84 Georeferencing Doğrulaması...")
    geo = PinholeGeoReferencer(CameraIntrinsics(image_width=1920, image_height=1080, hfov_deg=85.0))
    uav_lat, uav_lon, uav_alt = 40.123456, 29.654321, 30.0
    u_px, v_px = 960.0, 540.0
    target_gps = geo.pixel_to_gps(u_px, v_px, uav_lat, uav_lon, uav_alt, uav_pitch_deg=-5.0, uav_yaw_deg=45.0)
    print(f"İHA Konumu  : Lat={uav_lat:.6f}, Lon={uav_lon:.6f}, İrtifa={uav_alt:.1f}m")
    print(f"Hedef Piksel: ({u_px}, {v_px}) [Merkez Optik Eksen]")
    if target_gps:
        t_lat, t_lon, _ = target_gps
        print(f"Hesaplanan Hedef GPS: Lat={t_lat:.6f}, Lon={t_lon:.6f}")
        # Ters dönüşüm testi
        rev = geo.gps_to_pixel(t_lat, t_lon, 0.0, uav_lat, uav_lon, uav_alt, uav_pitch_deg=-5.0, uav_yaw_deg=45.0)
        print(f"Ters İzdüşüm (WGS84 -> Piksel) Doğrulama: {rev}")


def run_resting_ballistics():
    print("\n🛞 Şartname Madde 5.3 Zemin Yuvarlanma & Durma Noktası Balistik Testi...")
    optimizer = RestingBallisticsOptimizer()
    pred = optimizer.simulate_flight_and_roll(
        release_altitude_agl_m=30.0,
        uav_ground_speed_ms=18.0,
        wind_along_track_ms=2.0
    )
    print(f"Bırakma İrtifası      : 30.0 m | İHA Hızı: 18.0 m/s | Rüzgar: +2.0 m/s")
    print(f"Havadaki Uçuş Süresi  : {pred.time_of_flight_s:.2f} s")
    print(f"İlk Vuruş Mesafesi    : {pred.impact_distance_forward_m:.2f} m (Yatay Vuruş Hızı: {pred.impact_velocity_horizontal_ms:.1f} m/s)")
    print(f"Çim Yuvarlanma Mesafesi: {pred.roll_distance_m:.2f} m")
    print(f"Toplam Durma Mesafesi : {pred.total_lead_distance_m:.2f} m [100 Puan Bırakma Referansı]")


def run_mission_upload():
    print("\n🛰️ MAVLink Native Otopilot Görev Protokolü (Mission Upload) Simülasyonu...")
    uploader = MAVLinkMissionUploader(sys_id=255, comp_id=1, target_sys=1, target_comp=1)
    items = [
        MissionItem(seq=0, lat=40.231, lon=29.008, alt_m=30.0),
        MissionItem(seq=1, lat=40.233, lon=29.010, alt_m=30.0),
        MissionItem(seq=2, lat=40.235, lon=29.012, alt_m=25.0)
    ]
    res = uploader.simulate_mock_handshake(items)
    print(f"Görev Noktası Sayısı : {res['items_uploaded']}")
    print(f"Paket İletişim Durumu: {res['state']}")
    print(f"El Sıkışma Başarısı   : {'✅ BAŞARILI' if res['success'] else '❌ HATA'}")


def run_gimbal():
    print("\n🎥 Aktif Gimbal Ufuk Stabilizasyonu & LOS Hedef Takibi Doğrulaması...")
    gimbal = GimbalController(max_slew_rate_deg_s=120.0)
    # İHA dönüşte (roll = 25 deg, pitch = 5 deg)
    stab = gimbal.update_nadir_stabilization(uav_roll_deg=25.0, uav_pitch_deg=5.0, uav_yaw_deg=40.0, timestamp=1.0)
    print(f"Ufuk Stabilize Gimbal Komutu (Nadir): Roll={stab.roll_deg:.1f}°, Pitch={stab.pitch_deg:.1f}°")
    # Hedefe kilitlenme: İHA (0, 0, -30), Hedef (50, 20, 0)
    los = gimbal.update_target_tracking(
        uav_pos_ned=(0.0, 0.0, -30.0),
        uav_attitude_rpy_deg=(25.0, 5.0, 40.0),
        target_pos_ned=(50.0, 20.0, 0.0),
        timestamp=1.1
    )
    print(f"Hedef LOS Kilit Açıları: Pitch={los.pitch_deg:.1f}°, Yaw={los.yaw_deg:.1f}°, Mod={los.mode.value}")


def run_6dof_sim():
    print("\n✈️ 6-DOF Aerodinamik Uçuş Dinamikleri Simülasyonu (Newton-Euler RK4)...")
    sim = FlightDynamics6DOF()
    ctrl = ControlInputs(throttle=0.60, elevator_rad=-0.05, aileron_rad=0.02, rudder_rad=0.0)
    print("Simülasyon 1.0 saniye ilerletiliyor (dt=0.02s, 50 Hz)...")
    for _ in range(50):
        st = sim.step(ctrl, wind_ned=(2.0, -1.0, 0.0), dt=0.02)
    alt = -st.pos_d
    speed = math.sqrt(st.u**2 + st.v**2 + st.w**2)
    print(f"1 sn Sonrası Durum: Hız={speed:.2f} m/s | İrtifa={alt:.1f} m | Pitch={math.degrees(st.theta):.1f}° | Roll={math.degrees(st.phi):.1f}°")


def run_emergency_fts():
    print("\n🪂 Bağımsız Uçuş Kırım Önleme (FTS) & Paraşüt Kurtarma Testi...")
    rec = EmergencyRecoveryManager(uav_mass_kg=2.60)
    # Normal uçuş
    r_norm = rec.evaluate_telemetry(timestamp=1.0, altitude_agl_m=35.0, vz_down_mps=0.2, roll_rate_deg_s=10.0, pitch_rate_deg_s=5.0, yaw_rate_deg_s=5.0, accel_magnitude_g=1.1)
    print(f"Nominal Durum: {r_norm.status.value} (Tetiklendi mi: {r_norm.is_triggered})")
    # Vril / Spin Anomali Simülasyonu: Roll rate = 220 deg/s
    r_spin = rec.evaluate_telemetry(timestamp=1.05, altitude_agl_m=34.0, vz_down_mps=6.0, roll_rate_deg_s=220.0, pitch_rate_deg_s=15.0, yaw_rate_deg_s=10.0, accel_magnitude_g=2.5)
    print(f"Vril Tespiti: Neden={r_spin.trigger_reason.value} | Durum={r_spin.status.value}")
    drift_m, ttg_s, d_dir = rec.predict_touchdown_drift(current_altitude_agl_m=34.0, wind_speed_mps=4.0, wind_direction_deg=270.0)
    print(f"Paraşüt İniş Süresi: {ttg_s:.1f}s | Rüzgar Sürüklenme Mesafesi: {drift_m:.1f}m (Yön: {d_dir:.0f}°)")


def run_adc():
    print("\n🌬️ Hava Veri Bilgisayarı (ADC) & Perdövites Koruması Test Ediliyor...")
    adc = AirDataComputer(v_stall_mps=9.5, v_ne_mps=30.0)
    # Test 1: Normal Seyrüsefer Uçuşu (Malatya Tulga 938m MSL)
    p_static = 90500.0  # Pa
    dp_cruise = 0.5 * 1.15 * (14.0 ** 2)  # ~112.7 Pa
    st = adc.compute(diff_pressure_pa=dp_cruise, static_pressure_pa=p_static, oat_celsius=24.0, timestamp=1.0)
    print(f"[*] Seyrüsefer: IAS={st.ias_mps} m/s | TAS={st.tas_mps} m/s ({st.tas_kmh} km/h) | Yoğunluk İrtifası={st.density_alt_m}m | Alarm={st.alert.value}")

    # Test 2: Düşük Hız ve Perdövites Uyarısı (IAS < 9.5 m/s)
    dp_low = 0.5 * 1.15 * (8.5 ** 2)
    st_stall = adc.compute(diff_pressure_pa=dp_low, static_pressure_pa=p_static, oat_celsius=24.0, timestamp=2.0)
    rec_pitch, rec_throt = adc.get_stall_recovery_action(current_pitch_deg=6.0)
    print(f"[*] Perdövites Durumu: IAS={st_stall.ias_mps} m/s | Alarm={st_stall.alert.value} | İyileştirme: Pitch={rec_pitch}° | Gaz=%{rec_throt*100:.0f}")


def run_payload_grabber():
    print("\n🦾 Döner Kanat Görev 3 Bonus Yük Alma (Grabber) & Transfer Simülasyonu...")
    grabber = PayloadGrabberController()
    planner = PayloadTransferPlanner(target_a_xy=(-20.0, 45.0), target_b_xy=(25.0, 45.0), grabber_controller=grabber)
    planner.start_transfer_mission()
    print(f"[*] Görev 3 Başlatıldı -> Faz: {planner.phase.value}")

    # Hedef A'ya yaklaşma ve alçalma
    s1 = planner.update(uav_xy=(-20.0, 45.0), uav_alt_m=0.35, contact_switch=True, motor_current_ma=920.0, timestamp=1.0)
    s2 = planner.update(uav_xy=(-20.0, 45.0), uav_alt_m=0.35, contact_switch=True, motor_current_ma=920.0, timestamp=2.5)
    print(f"[*] Hedef A Alçalış & Kavrama: Faz={s2.phase.value} | AY Bonusu={s2.ay_bonus_awarded} (+10 Puan) | Toplam Bonus={s2.total_bonus_points} Puan")

    # Hedef B'ye transit ve bırakma
    s3 = planner.update(uav_xy=(25.0, 45.0), uav_alt_m=1.20, contact_switch=False, timestamp=5.0)
    s4 = planner.update(uav_xy=(25.0, 45.0), uav_alt_m=1.20, contact_switch=False, timestamp=6.0)
    print(f"[*] Hedef B Bırakma: Faz={s4.phase.value} | BY Bonusu={s4.by_bonus_awarded} (+10 Puan) | Toplam Bonus={s4.total_bonus_points} / 20 Puan")


def run_gust_alleviation():
    print("\n🌪️ NASA F-Faktörü Rüzgar Kesmesi (Wind Shear) & Darbe Sönümleyici Test Ediliyor...")
    gla = GustAlleviationController(f_factor_threshold=0.13, wind_speed_limit_mps=6.94)
    # T=0 İlk Başlangıç
    gla.update(wind_vx=3.0, wind_vy=1.0, wind_vz=0.0, airspeed_mps=14.0, timestamp=0.0)
    # T=0.1 Ani Rüzgar Darbesi ve Çöküş (Microburst)
    res = gla.update(wind_vx=7.5, wind_vy=-4.0, wind_vz=-1.8, airspeed_mps=14.0, in_release_run=True, timestamp=0.1)
    print(f"[*] Rüzgar Kesmesi: F-Faktörü={res.f_factor} | Tehlike Seviyesi={res.hazard_level.value}")
    print(f"[*] Düzeltme Komutları: Roll Düzeltmesi={res.delta_roll_cmd}° | Pitch Düzeltmesi={res.delta_pitch_cmd}° | Gaz Artışı=+%{res.delta_throttle*100:.1f}")
    print(f"[*] Pas Geçme Tavsiyesi: {res.go_around_recommended}")


def run_referee_audit():
    print("\n📑 TÜBİTAK TEKNOFEST 2026 Resmi Hakem Denetim ve Telemetri Raporu Üretiliyor...")
    gen = RefereeReportGenerator(team_name="UAV-ARCHITECT-GLOBAL")
    mock_telemetry = [
        {"timestamp": 0.0, "alt_agl_m": 0.0, "ground_speed_mps": 0.0, "wind_speed_mps": 2.5, "pos_x": 0.0, "pos_y": 0.0},
        {"timestamp": 60.0, "alt_agl_m": 35.0, "ground_speed_mps": 14.5, "wind_speed_mps": 4.2, "pos_x": -75.0, "pos_y": 0.0},
        {"timestamp": 120.0, "alt_agl_m": 34.0, "ground_speed_mps": 15.0, "wind_speed_mps": 3.8, "pos_x": 75.0, "pos_y": 0.0},
        {"timestamp": 180.0, "alt_agl_m": 22.0, "ground_speed_mps": 10.0, "wind_speed_mps": 3.0, "pos_x": 0.0, "pos_y": 45.0}
    ]
    audit = gen.generate_audit(
        category="rotary_wing",
        task_number=2,
        c_autonomy=1.0,
        flight_telemetry_points=mock_telemetry,
        setup_duration_s=210.0,
        extra_interventions=0,
        target_a_miss_m=0.45,
        target_b_miss_m=0.80,
        ay_bonus=True,
        by_bonus=True
    )
    print(f"[*] Hakem Brifingi: Takım={audit.team_name} | Konum={audit.venue}")
    print(f"[*] Tavan İhlali: {audit.ceiling_breached} (Max İrtifa: {audit.max_altitude_agl_m}m / 120m AGL)")
    print(f"[*] Saha Güvenliği: Geofence İhlali={audit.geofence_breached} | 2. Direk Dış Dönüşü={audit.pole_2_outer_turn_valid}")
    print(f"[*] Tablo 3 Görev 2 Puanı: {audit.calculated_score} / {audit.max_possible_score} (c={audit.c_autonomy})")
    print(f"[*] Telemetri SHA-256 İmzası: {audit.telemetry_hash}")


def run_link_security():
    print("\n🔐 Uçtan Uca Şifreli Telemetri & Jamming/Spoofing Koruması (Madde 9.4) Test Ediliyor...")
    key = b"TEKNOFEST-2026-MALATYA-TULGA-AES"
    tx = TelemetryLinkSecurity(master_key=key)
    rx = TelemetryLinkSecurity(master_key=key)
    pkt = tx.encrypt_packet({"state": "LOCKING_TARGET_A", "alt_m": 24.5, "slot": 1})
    ok, decoded, reason = rx.decrypt_packet(pkt)
    replay_ok, _, replay_reason = rx.decrypt_packet(pkt)
    health = rx.evaluate_link_health(rssi_dbm=-56.0, packet_loss_pct=0.8, time_since_last_packet_s=0.1)
    print(f"[*] Şifreleme Paketi : {len(pkt)} byte | Doğrulama: {ok} ({reason}) | Veri: {decoded}")
    print(f"[*] Anti-Replay Testi: Tekrar Paket Reddedildi={not replay_ok} ({replay_reason})")
    print(f"[*] Link Sağlık Durumu: {health.health_state.value} | Jamming Skoru: {health.jamming_score}")


def run_pylon_nav():
    print("\n🏁 150m Direk (Pylon) Dış Dönüş Güdümü & Ceza 2 Önleme Kalkanı Test Ediliyor...")
    nav = PylonNavigator(pole_distance_m=150.0, max_bank_angle_deg=35.0)
    turn_r = nav.compute_dynamic_turn_radius(airspeed_mps=16.0, wind_speed_mps=4.0)
    wps = nav.generate_outer_turn_figure_eight(altitude_m=30.0, airspeed_mps=16.0, wind_speed_mps=4.0, laps=2)
    print(f"[*] Rüzgar Kompanzasyonlu Dönüş Yarıçapı: {turn_r} m")
    print(f"[*] 2 Tur ∞ Dış Dönüş Waypoint Sayısı   : {len(wps)} nokta (Max X={max(w[0] for w in wps)}m, Min X={min(w[0] for w in wps)}m)")


def run_monte_carlo():
    print("\n🎲 Monte Carlo Balistik Dağılım (CEP50 / R95) Simülasyonu Çalıştırılıyor...")
    sim = MonteCarloDropSimulator(MonteCarloConfig(num_trials=200, category="rotary_wing", release_altitude_m=20.0))
    res = sim.run()
    print(f"[*] Deneme Sayısı: {res.num_trials} | Kategori: {res.category} (Çember <= {res.scoring_radius_m}m)")
    print(f"[*] CEP50: {res.cep50_m} m | R95: {res.r95_m} m | Ortalama Hata: {res.mean_error_m} m")
    print(f"[*] Puanlama İsabet Olasılığı: %{res.hit_probability_pct} | 2m Tam İsabet: %{res.bullseye_2m_probability_pct}")


def run_competition_optimizer():
    print("\n⚖️ Ağırlık/CG Kayması, Muhafaza Kutusu & Tablo 3 Puan Optimizasyonu Çalıştırılıyor...")
    opt = CompetitionOptimizer(category="rotary_wing")
    wb = opt.analyze_weight_and_balance([
        MassComponent("Gövde+Aviyonik", 1.50, 0.0, 0.0, 0.0),
        MassComponent("Batarya 4S", 0.55, 0.01, 0.0, -0.02),
        MassComponent("Yük 1 (Kırmızı)", 0.45, 0.02, 0.03, -0.05, True, 1),
        MassComponent("Yük 2 (Mavi)", 0.45, -0.02, -0.03, -0.05, True, 2),
    ])
    box = opt.audit_transport_box("rectangular_prism", (0.55, 0.55, 0.35))
    timing = opt.audit_setup_timing(measured_setup_s=195.0, interventions_s=[])
    print(f"[*] MTOW: {wb['full_load'].total_mass_kg} kg (Uygun={wb['full_load'].mtow_compliant}) | 1. Bırakma CG Kayması: {wb['after_drop_1'].cg_shift_from_nominal_mm} mm")
    print(f"[*] Muhafaza Kutusu: {box.volume_liters} L (Uygun={box.is_compliant}) | Kurulum: {timing.effective_setup_s}s / 480s")


def run_crypto_security():
    print("\n🔐 256-bit Şifreli Telemetri & RF Güvenlik Doğrulaması (Şartname §9.4)...")
    link = CryptoTelemetryLink()
    sample = {"alt_agl": 32.5, "lat": 38.34694, "lon": 38.24444, "state": "SEARCHING_TARGET_A"}
    frame = link.encrypt_payload(sample)
    decoded = link.decrypt_frame(frame)
    replay_blocked = link.decrypt_frame(frame) is None
    st = link.evaluate_rf_health(RFMetrics(rssi_dbm=-56.0, noise_floor_dbm=-95.0, packet_loss_pct=0.2))
    print(f"[*] Şifreli Paket Boyutu : {len(frame.to_bytes())} bayt (Epoch #{frame.key_epoch}, Seq #{frame.seq_num})")
    print(f"[*] Bütünlük & Çözme     : {'BAŞARILI' if decoded == sample else 'HATA'}")
    print(f"[*] Replay Saldırı Engeli: {'AKTİF (REDDEDİLDİ)' if replay_blocked else 'ZAYIF'}")
    print(f"[*] RF Güvenlik Seviyesi : {st.anomaly_level.value} | SNR: {st.snr_db} dB")


def run_box_optimizer():
    print("\n📦 Muhafaza Kutusu Doğrulama & Tablo 3 Puan Optimizasyonu (§8.3.4 & §11.1)...")
    opt = StorageBoxOptimizer()
    spec = StorageBoxSpec(
        category="rotary_wing",
        geometry=BoxGeometry.RECTANGULAR_PRISM,
        dim_a_m=0.60, dim_b_m=0.60, dim_c_m=0.40
    )
    box_res = opt.validate_storage_box(spec)
    profile = CompetitionTeamProfile(
        category="rotary_wing",
        empty_mass_w0_kg=1.85,
        single_payload_mass_kg=0.60,
        box_volume_m3=box_res.volume_m3,
        setup_time_s=195.0,
        bonus_ay_pickup=True,
        bonus_by_delivery=True
    )
    res = opt.optimize_team_strategy(profile)
    print(f"[*] Kutu Uyumluluğu : {'UYGUN' if box_res.is_compliant else 'İHLAL'} | Hacim: {box_res.volume_m3:.4f} m³")
    print(f"[*] MTOW            : {res.mtow_kg:.2f} kg / 4.00 kg ({'UYGUN' if res.mtow_compliant else 'AŞILDI'})")
    print(f"[*] Tahmini Puan    : PG1={res.predicted_pg1:.2f} | PG2={res.predicted_pg2:.2f} | Toplam={res.predicted_total_flight_score:.2f}")
    print(f"[*] En Verimli Kaldıraç: {res.top_engineering_lever}")
    print(f"[*] Yük Deneme Stratejisi: {res.payload_recommendation.rationale}")


def run_pylon_gate():
    print("\n🚩 150m Referans Direkleri Dış Dönüş & ∞ Kapı İzleyici Testi (§8.3.1)...")
    mon = PylonGateMonitor()
    # 2. direk (-75, 0) etrafında dıştan dönüş simülasyonu
    for deg in range(0, 210, 30):
        rad = math.radians(deg)
        x = -75.0 - 20.0 * math.sin(rad)
        y = 20.0 * math.cos(rad)
        st = mon.update(x, y)
    st_scan = mon.update(0.0, 0.0)
    print(f"[*] Uyumluluk Durumu       : {st_scan.compliance_state.value}")
    print(f"[*] 2. Direk Dış Dönüşü    : {'DOĞRULANDI' if st_scan.pole_2_outer_turn_verified else 'BEKLENİYOR'}")
    print(f"[*] Tarama Alanı Yetkisi   : {'AÇIK' if st_scan.vision_scan_authorized else 'KİLİTLİ'}")
    print(f"[*] Tahmini Ceza Puanı 2   : {st_scan.estimated_penalty_2_pts:.1f} puan")


def run_mission_benchmark():
    print("\n🎲 Malatya Tulga Monte Carlo Yarışma Hazırlık Kıyaslaması (50 Sorti)...")
    bench = MissionReadinessBenchmark(BenchmarkConfig(num_runs=50, category="rotary_wing"))
    rep = bench.run()
    print(f"[*] Tulga Hava Yoğunluğu : {rep.tulga_air_density_kgpm3:.4f} kg/m³ (938m MSL)")
    print(f"[*] Durma Noktası CEP50  : {rep.cep50_m:.2f}m | CEP90: {rep.cep90_m:.2f}m (Limit: {rep.scoring_radius_m:.0f}m)")
    print(f"[*] Yarıçap İçi Başarı   : %{rep.in_radius_success_rate_pct:.1f} | Rüzgar İptal Riski: %{rep.wind_abort_rate_pct:.1f}")
    print(f"[*] Ortalama Tablo 3     : PG1={rep.mean_pg1:.2f} | PG2={rep.mean_pg2:.2f} | Toplam={rep.mean_total_flight_score:.2f}")
    print(f"[*] Hazırlık İndeksi CRI : {rep.readiness_index_0_100:.1f}/100 ({rep.readiness_grade})")


def run_propulsion_health():
    print("\n🔥 İtki, ESC Termal & Titreşim Sağlık Analizi (Malatya Tulga 938m MSL)...")
    mon = PropulsionHealthMonitor()
    rep = mon.evaluate(PropulsionSnapshot(
        motor_rpms=[7200.0, 7240.0, 7180.0, 7210.0],
        esc_temps_c=[62.0, 64.5, 61.0, 63.2],
        throttle_pct=56.0,
        air_density_kgpm3=1.06,
        vibration_rms_mps2=3.1
    ))
    print(f"[*] Sağlık Seviyesi     : {rep.alert_level.value}")
    print(f"[*] Yoğunluk İtki Oranı : {rep.density_thrust_ratio:.3f} | Hover Marjı: %{rep.hover_throttle_margin_pct:.1f}")
    print(f"[*] Max ESC Sıcaklığı   : {rep.max_esc_temp_c:.1f}°C (Derating: {rep.thermal_derating_factor:.2f})")
    print(f"[*] RPM Asimetrisi      : %{rep.rpm_asymmetry_pct:.2f} | Titreşim RMS: {rep.vibration_rms_mps2:.2f} m/s²")


def run_attempt_manager():
    print("\n🏆 4 Uçuş Hakkı, Kronometre & Saha Ekibi Uyumluluk Simülasyonu...")
    mgr = CompetitionAttemptManager(team_name="UAV-ARCHITECT-GLOBAL", video_score=9.5)
    mgr.set_crew_roster(FieldCrewRoster(
        member_names=["Pilot", "YKİ Operatörü", "Teknisyen-1", "Teknisyen-2"],
        advisor_on_field=False,
        all_helmets_worn=True,
        shgm_qr_verified=True
    ))
    mgr.record_attempt(1, setup_duration_s=185.0, prep_duration_s=120.0, flight_duration_s=94.0, raw_score=27.8)
    mgr.record_attempt(2, setup_duration_s=195.0, prep_duration_s=130.0, flight_duration_s=162.0, raw_score=69.4)
    sm = mgr.get_summary()
    print(f"[*] Kullanılan / Kalan Hak : {sm.attempts_used} / {sm.attempts_remaining}")
    print(f"[*] G1 Onayı: {'EVET' if sm.task1_qualified else 'HAYIR'} | En İyi G1={sm.best_task1_score} | En İyi G2={sm.best_task2_score}")
    print(f"[*] Toplam Yarışma Puanı   : {sm.combined_total_score:.2f} | Saha Ekibi: {'UYGUN' if sm.crew_compliant else 'İHLAL'}")
    print(f"[*] Taktik Öneri           : {sm.tactical_recommendation}")


def run_dubins_planner():
    print("\n✈️ 3B Dubins Kinodinamik Rota Planlayıcı (150m Pylon Dönüşü)...")
    planner = DubinsPathPlanner(max_climb_angle_deg=18.0)
    r_min = planner.compute_min_turn_radius(airspeed_mps=16.0, max_bank_deg=35.0)
    path = planner.plan(
        start=DubinsPose(-75.0, -25.0, 30.0, 0.0),
        goal=DubinsPose(75.0, 25.0, 35.0, math.pi),
        turn_radius_m=r_min,
        step_size_m=10.0
    )
    print(f"[*] Min Dönüş Yarıçapı : {r_min:.2f}m (V=16m/s, Bank=35°)")
    print(f"[*] En Kısa Dubins Tipi: {path.path_type} | 2B={path.total_length_2d_m:.1f}m | 3B={path.total_length_3d_m:.1f}m")
    print(f"[*] Tırmanma Açısı     : {path.climb_angle_deg:.2f}° ({'UYGUN' if path.glide_slope_feasible else 'AŞILDI'}) | Nokta Sayısı: {len(path.samples)}")


def run_flight_replayer():
    print("\n⏪ Kara Kutu Tekrar Oynatma ve Regresyon Denetimi...")
    replayer = FlightTelemetryReplayer()
    sample_rows = [
        {"timestamp": 0.0, "altitude_agl": 0.0, "ground_speed": 0.0, "vz": 0.0, "battery_v": 16.4, "payloads_left": 2},
        {"timestamp": 10.0, "altitude_agl": 32.0, "ground_speed": 14.5, "vz": 0.0, "battery_v": 15.9, "payloads_left": 2},
        {"timestamp": 25.0, "altitude_agl": 20.0, "ground_speed": 12.0, "vz": 0.5, "battery_v": 15.6, "payloads_left": 1},
        {"timestamp": 45.0, "altitude_agl": 20.0, "ground_speed": 12.5, "vz": 0.2, "battery_v": 15.3, "payloads_left": 0},
        {"timestamp": 60.0, "altitude_agl": 0.0, "ground_speed": 0.0, "vz": 1.2, "battery_v": 15.1, "payloads_left": 0},
    ]
    res = replayer.replay_rows(sample_rows, source_name="tulga_regression_sample")
    print(f"[*] Regresyon Durumu : {'GEÇTİ' if res.passed_regression else 'BAŞARISIZ'} (Kritik={res.critical_count}, Uyarı={res.warning_count})")
    print(f"[*] Max İrtifa: {res.max_altitude_agl_m}m | Min Batarya: {res.min_battery_v}V | Bırakılan Yük: {res.payloads_released}")


def run_tests():
    print("\n🧪 Test paketi yürütülüyor...")
    os.system("pytest -v")


def interactive_menu():
    while True:
        print(MENU_BANNER)
        choice = input("Seçiminiz [0-27]: ").strip()
        if choice == "1":
            run_preflight()
        elif choice == "2":
            run_simulation()
        elif choice == "3":
            run_web_gcs()
        elif choice == "4":
            run_sitl_server()
        elif choice == "5":
            run_analytics()
        elif choice == "6":
            run_export()
        elif choice == "7":
            run_camera()
        elif choice == "8":
            run_dataset_gen()
        elif choice == "9":
            run_trajectory()
        elif choice == "10":
            run_fdir()
        elif choice == "11":
            run_playbook()
        elif choice == "12":
            run_debrief()
        elif choice == "13":
            run_georef()
        elif choice == "14":
            run_resting_ballistics()
        elif choice == "15":
            run_mission_upload()
        elif choice == "16":
            run_gimbal()
        elif choice == "17":
            run_6dof_sim()
        elif choice == "18":
            run_emergency_fts()
        elif choice == "19":
            run_adc()
        elif choice == "20":
            run_payload_grabber()
        elif choice == "21":
            run_gust_alleviation()
        elif choice == "22":
            run_referee_audit()
        elif choice == "23":
            run_link_security()
        elif choice == "24":
            run_pylon_nav()
        elif choice == "25":
            run_monte_carlo()
        elif choice == "26":
            run_competition_optimizer()
        elif choice == "27":
            run_tests()
        elif choice == "0":
            print("\n👋 Güvenli uçuşlar dileriz!")
            break
        else:
            print("\n❌ Geçersiz seçenek!")
        time.sleep(1)


def main():
    parser = argparse.ArgumentParser(description="TEKNOFEST 2026 Entegre Komuta Merkezi")
    parser.add_argument("--preflight", action="store_true", help="Uçuş öncesi checklist çalıştır")
    parser.add_argument("--simulate", action="store_true", help="Otonom simülasyonu başlat")
    parser.add_argument("--web-gcs", action="store_true", help="Web GCS'i başlat")
    parser.add_argument("--sitl", action="store_true", help="ArduPilot SITL sunucusunu başlat")
    parser.add_argument("--analytics", action="store_true", help="Uçuş sonrası analiz yap")
    parser.add_argument("--export", action="store_true", help="Uçuş haritalarını dışa aktar")
    parser.add_argument("--camera-check", action="store_true", help="Kamera teşhisini çalıştır")
    parser.add_argument("--generate-dataset", action="store_true", help="YOLO sentetik veri seti üret")
    parser.add_argument("--trajectory", action="store_true", help="3B Yörünge optimizasyonunu çalıştır")
    parser.add_argument("--fdir", action="store_true", help="Sensör FDIR teşhisini çalıştır")
    parser.add_argument("--playbook", action="store_true", help="Görev playbook dinamik planlamasını çalıştır")
    parser.add_argument("--debrief", action="store_true", help="Kara kutu debriefing raporu oluştur")
    parser.add_argument("--georef", action="store_true", help="Pinhole georeferencing testini çalıştır")
    parser.add_argument("--resting-ballistics", action="store_true", help="Durma noktası ve yuvarlanma balistik testini çalıştır")
    parser.add_argument("--mission-upload", action="store_true", help="MAVLink görev yükleme el sıkışmasını test et")
    parser.add_argument("--gimbal", action="store_true", help="Aktif gimbal hedef takibi ve stabilizasyonunu test et")
    parser.add_argument("--flight-dynamics", action="store_true", help="6-DOF uçuş dinamikleri aerodinamik simülatörünü çalıştır")
    parser.add_argument("--emergency-fts", action="store_true", help="Acil durum paraşüt ve kırım önleme sistemini test et")
    parser.add_argument("--adc", action="store_true", help="Hava veri bilgisayarı (ADC) ve stall testini çalıştır")
    parser.add_argument("--grabber", action="store_true", help="Döner kanat yük alma (grabber) ve transfer simülasyonunu çalıştır")
    parser.add_argument("--gust", action="store_true", help="Rüzgar darbe ve kesme sönümleyicisini test et")
    parser.add_argument("--referee-audit", action="store_true", help="Resmi hakem heyeti uçuş denetim raporu üret")
    parser.add_argument("--link-security", action="store_true", help="Şifreli telemetri ve jamming koruma testi")
    parser.add_argument("--pylon-nav", action="store_true", help="150m direk dış dönüş güdüm testi")
    parser.add_argument("--monte-carlo", action="store_true", help="Monte Carlo balistik dağılım simülasyonu")
    parser.add_argument("--competition-opt", action="store_true", help="Ağırlık/CG, kutu ve Tablo 3 puan optimizasyonu")
    parser.add_argument("--crypto", action="store_true", help="256-bit EtM şifreli telemetri ve RF güvenlik testi")
    parser.add_argument("--box-opt", action="store_true", help="Muhafaza kutusu doğrulama ve Tablo 3 duyarlılık optimizasyonu")
    parser.add_argument("--pylon-gate", action="store_true", help="150m direk dış dönüş kapı ve ∞ tur izleyici testi")
    parser.add_argument("--benchmark", action="store_true", help="Malatya Tulga Monte Carlo Yarışma Hazırlık Kıyaslaması (CRI)")
    parser.add_argument("--propulsion", action="store_true", help="İtki, ESC termal ve titreşim sağlık analizi")
    parser.add_argument("--attempts", action="store_true", help="4 uçuş hakkı ve saha operasyon yöneticisi testi")
    parser.add_argument("--dubins", action="store_true", help="3B Dubins kinodinamik rota planlayıcı testi")
    parser.add_argument("--replay", action="store_true", help="Kara kutu tekrar oynatma ve regresyon denetimi")
    parser.add_argument("--test", action="store_true", help="Pytest testlerini çalıştır")

    args = parser.parse_args()

    if args.preflight:
        run_preflight()
    elif args.simulate:
        run_simulation()
    elif args.web_gcs:
        run_web_gcs()
    elif args.sitl:
        run_sitl_server()
    elif args.analytics:
        run_analytics()
    elif args.export:
        run_export()
    elif args.camera_check:
        run_camera()
    elif args.generate_dataset:
        run_dataset_gen()
    elif args.trajectory:
        run_trajectory()
    elif args.fdir:
        run_fdir()
    elif args.playbook:
        run_playbook()
    elif args.debrief:
        run_debrief()
    elif args.georef:
        run_georef()
    elif args.resting_ballistics:
        run_resting_ballistics()
    elif args.mission_upload:
        run_mission_upload()
    elif args.gimbal:
        run_gimbal()
    elif args.flight_dynamics:
        run_6dof_sim()
    elif args.emergency_fts:
        run_emergency_fts()
    elif args.adc:
        run_adc()
    elif args.grabber:
        run_payload_grabber()
    elif args.gust:
        run_gust_alleviation()
    elif args.referee_audit:
        run_referee_audit()
    elif args.link_security:
        run_link_security()
    elif args.pylon_nav:
        run_pylon_nav()
    elif args.monte_carlo:
        run_monte_carlo()
    elif args.competition_opt:
        run_competition_optimizer()
    elif args.crypto:
        run_crypto_security()
    elif args.box_opt:
        run_box_optimizer()
    elif args.pylon_gate:
        run_pylon_gate()
    elif args.benchmark:
        run_mission_benchmark()
    elif args.propulsion:
        run_propulsion_health()
    elif args.attempts:
        run_attempt_manager()
    elif args.dubins:
        run_dubins_planner()
    elif args.replay:
        run_flight_replayer()
    elif args.test:
        run_tests()
    else:
        interactive_menu()


if __name__ == "__main__":
    main()
