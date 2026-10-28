"""
TEKNOFEST 2026 - Uçuş Öncesi Otomatik Kontrol Listesi Aracı (Pre-flight Checklist)
================================================================================
Uçuş öncesinde otopilot, GPS, LiPo batarya, 120m kısıtı, kamera, yapay zeka
ve çift servo mekanizmasını 8 dakikalık kısıt içerisinde saniyeler içinde denetler.
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
from src.avionics.preflight import PreflightChecker


def main():
    parser = argparse.ArgumentParser(description="TEKNOFEST 2026 Pre-Flight Checklist")
    parser.add_argument("--mode", default="simulation", choices=["simulation", "sitl", "live"])
    args = parser.parse_args()

    core = ArchitectCore(mode=args.mode)
    checker = PreflightChecker(core_instance=core)

    report = checker.run_all_checks()
    checker.print_terminal_report(report)

    if report.overall_status != "GO_FOR_TAKEOFF":
        sys.exit(1)


if __name__ == "__main__":
    main()
