"""
TEKNOFEST 2026 - Web Tabanlı Yer Kontrol İstasyonu (Web Ground Station)
======================================================================
Tarayıcı üzerinden canlı telemetri, radar haritası, suni ufuk ve görev
kontrol butonları sunan tam donanımlı yer kontrol istasyonunu başlatır.
"""

import sys
import os
import time
import argparse
import webbrowser

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.main_brain.core import ArchitectCore
from src.web_gcs.server import WebGCSServer


def main():
    parser = argparse.ArgumentParser(description="Web Tabanlı Yer Kontrol İstasyonu")
    parser.add_argument("--port", type=int, default=8080, help="Web sunucu portu")
    parser.add_argument("--host", default="127.0.0.1", help="Web sunucu adresi")
    parser.add_argument("--mode", default="simulation", choices=["simulation", "sitl", "live"])
    parser.add_argument("--task", type=int, default=2)
    parser.add_argument("--no-browser", action="store_true", help="Tarayıcıyı otomatik açma")

    args = parser.parse_args()

    print("=" * 65)
    print("🛸 TEKNOFEST 2026 - WEB YER KONTROL İSTASYONU (WEB GCS)")
    print(f"[*] Adres : http://{args.host}:{args.port}")
    print(f"[*] Mod   : {args.mode.upper()}")
    print("=" * 65)

    core = ArchitectCore(mode=args.mode, task=args.task)
    core.start_mission()

    server = WebGCSServer(host=args.host, port=args.port, core_instance=core)
    server.start_background()

    url = f"http://{args.host}:{args.port}"
    if not args.no_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    print(f"[INFO] GCS arayüzü tarayıcıda açıldı: {url}")
    print("[INFO] Çıkış yapmak için Ctrl+C tuşlayın...")

    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\n[INFO] Web GCS durduruluyor...")
    finally:
        server.stop()
        core.stop_mission()
        print("[INFO] Web GCS başarıyla kapatıldı.")


if __name__ == "__main__":
    main()
