"""
TEKNOFEST 2026 - Yer Kontrol İstasyonu ve Canlı Telemetri HUD (GCS Dashboard)
=============================================================================
Yer istasyonunda operatörün İHA'nın anlık irtifa, hız, suni ufuk, rüzgar vektörü,
hedef kilit ve yük durumunu canlı olarak izlemesini sağlayan gösterge paneli.
"""

import sys
import os
import time
import argparse

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.main_brain.core import ArchitectCore


def run_gcs_dashboard(duration=30.0, mode="simulation", task=2):
    print("🚀 GCS Komuta Paneli Başlatılıyor...")
    core = ArchitectCore(mode=mode, task=task)
    core.start_mission()
    start_time = time.monotonic()

    try:
        while core.running and (time.monotonic() - start_time) < duration:
            info = core.step()
            hud_text = core.visualizer.render_hud_text(
                state=info["state"],
                altitude_m=info["altitude_agl"],
                ground_speed_mps=info["ground_speed"],
                heading_deg=info["heading_deg"],
                pitch_deg=info["pitch_deg"],
                roll_deg=info["roll_deg"],
                battery_v=info["battery_v"],
                wind_speed_mps=info["wind_speed"],
                wind_dir_deg=info["wind_dir"],
                target_locked=info["locked_target"] is not None,
                target_name=info["locked_target"] or "YOK",
                miss_dist_m=info["miss_distance"],
                payloads_left=info["payloads_remaining"],
                failsafe_status=info["failsafe_status"]
            )

            # Ekranı temizle (Windows / Linux)
            os.system("cls" if os.name == "nt" else "clear")
            print(hud_text)

            time.sleep(0.15)
    except KeyboardInterrupt:
        print("\n[GCS] Operatör tarafından durduruldu.")
    finally:
        core.stop_mission()
        print("[GCS] Panel kapatıldı.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Canlı Telemetri GCS HUD")
    parser.add_argument("--mode", default="simulation", choices=["simulation", "sitl", "live"])
    parser.add_argument("--task", type=int, default=2)
    parser.add_argument("--duration", type=float, default=25.0)
    args = parser.parse_args()

    run_gcs_dashboard(duration=args.duration, mode=args.mode, task=args.task)
