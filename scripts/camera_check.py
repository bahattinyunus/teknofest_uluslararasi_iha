"""
TEKNOFEST 2026 - Kamera ve Görüntü İşleme Doğrulama Aracı (Camera Check)
========================================================================
Uçuş öncesi sahada kameranın netlik ayarlarını, renk eşiklerini (HSV),
FPS performansını ve TEKNOFEST 2026 geometrik hedeflerini doğrulamak
için kullanılan teşhis aracıdır.
"""

import sys
import os
import time
import argparse
import cv2
import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Ana dizini PYTHONPATH'e ekle
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.vision.camera import CameraInterface
from src.vision.detector import VisionDetector, TargetColor, TargetShape
from src.vision.tracker import TargetTracker


def run_camera_check(source="synthetic", width=1280, height=720, headless=False, max_frames=100):
    print("=" * 65)
    print("🎯 TEKNOFEST 2026 - KAMERA VE HEDEF TESPİT DOĞRULAMA ARACI")
    print(f"[*] Kaynak : {source}")
    print(f"[*] Çözünürlük: {width}x{height}")
    print(f"[*] Mod     : {'Headless (Konsol)' if headless else 'Görsel HUD Penceresi'}")
    print("=" * 65)

    cam = CameraInterface(source=source, width=width, height=height, fps=30)
    detector = VisionDetector()
    tracker = TargetTracker()

    frame_count = 0
    start_time = time.monotonic()
    total_detections = 0

    try:
        while frame_count < max_frames:
            ret, frame = cam.read_frame()
            if not ret or frame is None:
                print("[ERROR] Kare okunamadı!")
                break

            t0 = time.monotonic()
            detections = detector.detect(frame)
            inf_time = (time.monotonic() - t0) * 1000.0

            locked = tracker.update(detections)
            total_detections += len(detections)
            frame_count += 1

            fps = frame_count / max(0.001, (time.monotonic() - start_time))

            # Tespit bilgisi formatla
            det_summary = ", ".join([f"{d.target_type.value}({d.shape.value})" for d in detections]) or "YOK"
            print(f"\r[Kare {frame_count:03d}] FPS: {fps:4.1f} | Çıkarım: {inf_time:4.1f}ms | Hedefler: {det_summary:<30} | Kilit: {locked.shape.value if locked else 'YOK':<10}", end="")

            if not headless:
                hud = detector.draw_hud(frame, detections, locked_target=locked)
                cv2.imshow("TEKNOFEST 2026 - Kamera Kontrol Paneli", hud)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    print("\n[INFO] Kullanıcı tarafından sonlandırıldı.")
                    break

        print("\n" + "=" * 65)
        print("✅ Kamera Teşhis Testi Başarıyla Tamamlandı.")
        print(f"[*] Toplam Kare  : {frame_count}")
        print(f"[*] Ortalama FPS : {fps:.1f}")
        print(f"[*] Toplam Tespit: {total_detections}")
        print("=" * 65)

    finally:
        cam.release()
        if not headless:
            cv2.destroyAllWindows()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Kamera ve Hedef Tespit Doğrulama")
    parser.add_argument("--source", default="synthetic", help="Kamera kaynağı (0, 1, 'csi', 'synthetic')")
    parser.add_argument("--width", type=int, default=1280, help="Genişlik")
    parser.add_argument("--height", type=int, default=720, help="Yükseklik")
    parser.add_argument("--headless", action="store_true", help="Görsel pencere açmadan çalıştır")
    parser.add_argument("--frames", type=int, default=80, help="Test karesi sayısı")

    args = parser.parse_args()
    run_camera_check(source=args.source, width=args.width, height=args.height, headless=args.headless, max_frames=args.frames)
