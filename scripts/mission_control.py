"""
TEKNOFEST 2026 Uluslararası İHA - Entegre Misyon ve Komuta Merkezi (Mission Control)
=====================================================================================
Tüm alt sistemleri (SITL Sunucusu, Web GCS, Pre-flight Checklist, Canlı Simülatör,
Uçuş Analitiği, KML Harita İhracatı, Kamera Teşhisi ve Sentetik Veri Üreteci)
tek bir interaktif komuta kabuğundan yönetmeyi sağlayan ana operasyonel CLI aracı.
"""

import sys
import os
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
[11] 🧪 Tüm Otomasyonel Test Paketini Çalıştır
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


def run_tests():
    print("\n🧪 Test paketi yürütülüyor...")
    os.system("pytest -v")


def interactive_menu():
    while True:
        print(MENU_BANNER)
        choice = input("Seçiminiz [0-11]: ").strip()
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
    elif args.test:
        run_tests()
    else:
        interactive_menu()


if __name__ == "__main__":
    main()
