"""
TEKNOFEST 2026 - Uçuş Sonrası Veri ve Puanlama Analiz Aracı
===========================================================
Uçuş tamamlandıktan sonra kara kutu (CSV) telemetri kayıtlarını inceler,
isabet puanlarını hesaplar ve şartname uyumluluk raporu basar.
"""

import sys
import os
import glob
import argparse

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.telemetry.analytics import FlightAnalyticsEngine


def run_analytics(log_path=None, category="rotary_wing", export_md=True):
    engine = FlightAnalyticsEngine(category=category)

    if not log_path:
        # En son oluşturulan log dosyasını bul
        csv_files = glob.glob(os.path.join("logs", "*.csv"))
        if not csv_files:
            print("[ANALYTICS] 'logs/' dizininde analiz edilecek CSV dosyası bulunamadı.")
            return
        log_path = max(csv_files, key=os.path.getctime)

    print(f"📊 Uçuş Günlüğü Analiz Ediliyor: {log_path}")
    summary = engine.analyze_csv_log(log_path)
    if not summary:
        print("[ANALYTICS] Günlük verisi boş veya ayrıştırılamadı.")
        return

    md_report = engine.generate_markdown_report(summary)
    print("\n" + md_report)

    if export_md:
        out_path = os.path.splitext(log_path)[0] + "_report.md"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(md_report)
        print(f"📄 Markdown Raporu Kaydedildi: {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Uçuş Sonrası Puanlama ve Analiz")
    parser.add_argument("--log", help="CSV log dosyası yolu (varsayılan: en son log)")
    parser.add_argument("--category", choices=["rotary_wing", "fixed_wing"], default="rotary_wing")
    args = parser.parse_args()

    run_analytics(log_path=args.log, category=args.category)
