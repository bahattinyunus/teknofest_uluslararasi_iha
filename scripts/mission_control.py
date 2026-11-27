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
[23] 🧪 Tüm Otomasyonel Test Paketini Çalıştır
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


def run_tests():
    print("\n🧪 Test paketi yürütülüyor...")
    os.system("pytest -v")


def interactive_menu():
    while True:
        print(MENU_BANNER)
        choice = input("Seçiminiz [0-23]: ").strip()
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
    elif args.test:
        run_tests()
    else:
        interactive_menu()


if __name__ == "__main__":
    main()
