"""
TEKNOFEST 2026 - Otonom Görev Simülasyonu ve SITL Test Koşucusu
==============================================================
1. Görev (∞ Şeklinde Otonom Uçuş) ve 2. Görev (İki Ayrı Hedefe Çift Renkli Yük Bırakma)
senaryolarını baştan sona simüle ederek tüm telemetri ve balistik doğrulamaları yapar.
"""

import sys
import os
import argparse

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.main_brain.core import ArchitectCore


def main():
    parser = argparse.ArgumentParser(description="TEKNOFEST 2026 Görev Koşucusu")
    parser.add_argument("--task", type=int, choices=[1, 2, 3], default=2, help="1: Görev 1 (∞), 2: Görev 2 (Çift Yük), 3: Hibrit")
    parser.add_argument("--duration", type=float, default=25.0, help="Simülasyon süresi")
    args = parser.parse_args()

    print("🚀 TEKNOFEST 2026 Uluslararası İHA Görev Simülasyonu Başlatılıyor...")
    core = ArchitectCore(mode="simulation", task=args.task)
    core.run_simulation(max_seconds=args.duration)


if __name__ == "__main__":
    main()
