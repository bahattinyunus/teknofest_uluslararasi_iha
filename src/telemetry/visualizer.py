"""
TEKNOFEST 2026 Uluslararası İHA - Telemetri Görselleştirici ve Canlı HUD
-----------------------------------------------------------------------
İHA'nın anlık irtifa, hız, suni ufuk (Roll/Pitch), pusula, rüzgar vektörü,
hedef kilit durumu ve aviyonik sağlık durumunu gösteren komuta terminali HUD'ı.
"""

from typing import Dict, Any, Optional
import math
import time


class TelemetryVisualizer:
    def __init__(self):
        self.last_render_time = time.monotonic()

    def generate_ascii_horizon(self, pitch_deg: float, roll_deg: float) -> str:
        """Suni ufuk göstergesi (Pitch & Roll ASCII art)."""
        clamped_pitch = max(-20.0, min(20.0, pitch_deg))
        clamped_roll = max(-45.0, min(45.0, roll_deg))

        # Roll eğimi gösterimi
        roll_char = "—"
        if clamped_roll > 10:
            roll_char = "\\"
        elif clamped_roll < -10:
            roll_char = "/"

        pitch_offset = int(clamped_pitch / 5.0)
        lines = [
            "    +10° [     ]    ",
            f"     0°  [=={roll_char}==]    ",
            "    -10° [     ]    "
        ]
        return "\n".join(lines)

    def render_hud_text(
        self,
        state: str,
        altitude_m: float,
        ground_speed_mps: float,
        heading_deg: float,
        pitch_deg: float,
        roll_deg: float,
        battery_v: float,
        wind_speed_mps: float,
        wind_dir_deg: float,
        target_locked: bool,
        target_name: str,
        miss_dist_m: float,
        payloads_left: int,
        failsafe_status: str
    ) -> str:
        """Tam konsol telemetri paneli metni üretir."""
        horizon = self.generate_ascii_horizon(pitch_deg, roll_deg)
        target_str = f"KİLİTLİ ({target_name})" if target_locked else "ARANIYOR"
        fs_str = f"NOMİNAL" if failsafe_status == "NOMINAL" else f"UYARI: {failsafe_status}"

        hud = f"""
┌────────────────────────────────────────────────────────────────────────┐
│ 🛸 UAV-ARCHITECT-GLOBAL: ELİT TELEMETRİ GÖSTERGE PANELİ (GCS HUD)       │
├───────────────────────────────────┬────────────────────────────────────┤
│ GÖREV FAZI     : {state:<16} │ BATARYA         : {battery_v:5.2f} V ({battery_v/4.0:4.2f}V/c) │
│ İRTİFA (AGL)   : {altitude_m:5.1f} m (Lim: 120m)│ AVİYONİK SAĞLIK : {fs_str:<18} │
│ YER HIZI       : {ground_speed_mps:5.1f} m/s          │ HEDEF DURUMU    : {target_str:<18} │
│ BAŞ AÇISI      : {heading_deg:5.1f}°            │ HEDEF SAPMA     : {miss_dist_m:5.2f} m          │
│ RÜZGAR VEKTÖRÜ : {wind_speed_mps:4.1f}m/s @ {wind_dir_deg:3.0f}°    │ KALAN YÜK       : {payloads_left} Adet             │
├───────────────────────────────────┴────────────────────────────────────┤
│ SUNİ UFUK & ORYANTASYON (Roll: {roll_deg:+5.1f}°, Pitch: {pitch_deg:+5.1f}°):                 │
{horizon}
└────────────────────────────────────────────────────────────────────────┘
"""
        return hud
