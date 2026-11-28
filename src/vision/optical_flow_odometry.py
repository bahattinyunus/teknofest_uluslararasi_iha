"""
TEKNOFEST 2026 Uluslararası İHA - Optik Akış Görsel Odometri (Optical Flow VO)
==============================================================================
GPS sinyal kaybı veya RF karıştırma anında DeadReckoningNavigator'ı gerçek
kamera akışıyla beslemek için ardışık kareler arasındaki piksel ötelemesini
Faz Korelasyonu (Phase Correlation) ile <2ms gecikmede hesaplar, jiroskop açısal
hız etkisini giderir (de-rotation) ve AGL irtifasıyla metrik yer hızına dönüştürür.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Tuple

import cv2
import numpy as np


@dataclass
class OpticalFlowEstimate:
    """Ardışık iki kamera karesinden çıkarılan optik akış ve yer hızı kestirimi."""
    flow_rad_s_x: float
    flow_rad_s_y: float
    vx_mps: float
    vy_mps: float
    pixel_shift_xy: Tuple[float, float]
    quality_score: float              # 0.0 - 1.0 faz korelasyon tepesi
    valid: bool


class OpticalFlowOdometry:
    """
    Faz Korelasyonu Tabanlı Hafif Optik Akış Odometri Motoru.
    """

    def __init__(
        self,
        hfov_deg: float = 85.0,
        process_size: Tuple[int, int] = (160, 120),
        min_quality: float = 0.08,
        ema_alpha: float = 0.45,
    ):
        self.hfov_rad = math.radians(max(20.0, min(140.0, hfov_deg)))
        self.proc_w, self.proc_h = process_size
        self.min_quality = float(min_quality)
        self.ema_alpha = max(0.05, min(1.0, float(ema_alpha)))

        self._prev_gray_f32: Optional[np.ndarray] = None
        self._hann_window: np.ndarray = cv2.createHanningWindow((self.proc_w, self.proc_h), cv2.CV_32F)
        self._focal_px: float = (self.proc_w / 2.0) / math.tan(self.hfov_rad / 2.0)
        self._vx_filt: float = 0.0
        self._vy_filt: float = 0.0

    def reset(self) -> None:
        self._prev_gray_f32 = None
        self._vx_filt = 0.0
        self._vy_filt = 0.0

    def update(
        self,
        frame: np.ndarray,
        altitude_agl_m: float,
        dt_s: float = 0.05,
        gyro_roll_rate_rad_s: float = 0.0,
        gyro_pitch_rate_rad_s: float = 0.0,
    ) -> OpticalFlowEstimate:
        """Yeni kamera karesiyle optik akış (rad/s) ve yer hızını (m/s) kestirir."""
        if frame is None or frame.size == 0 or dt_s <= 1e-4:
            return OpticalFlowEstimate(0.0, 0.0, 0.0, 0.0, (0.0, 0.0), 0.0, False)

        if frame.ndim == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame

        small = cv2.resize(gray, (self.proc_w, self.proc_h), interpolation=cv2.INTER_AREA).astype(np.float32)

        if self._prev_gray_f32 is None:
            self._prev_gray_f32 = small
            return OpticalFlowEstimate(0.0, 0.0, 0.0, 0.0, (0.0, 0.0), 0.0, False)

        (shift_x, shift_y), response = cv2.phaseCorrelate(self._prev_gray_f32, small, self._hann_window)
        self._prev_gray_f32 = small

        quality = max(0.0, min(1.0, float(response)))
        if quality < self.min_quality or not (math.isfinite(shift_x) and math.isfinite(shift_y)):
            return OpticalFlowEstimate(0.0, 0.0, self._vx_filt, self._vy_filt, (0.0, 0.0), round(quality, 4), False)

        # Açısal akış (rad/s) ve jiroskop rotasyon kompanzasyonu (de-rotation)
        raw_flow_x = (shift_x / self._focal_px) / dt_s
        raw_flow_y = (shift_y / self._focal_px) / dt_s

        comp_flow_x = raw_flow_x - gyro_roll_rate_rad_s
        comp_flow_y = raw_flow_y - gyro_pitch_rate_rad_s

        # Kamera sahneyi geri kaydırdığı için araç hızı zıt işaretlidir
        alt = max(0.5, float(altitude_agl_m))
        vx_raw = -comp_flow_y * alt
        vy_raw = -comp_flow_x * alt

        self._vx_filt = self.ema_alpha * vx_raw + (1.0 - self.ema_alpha) * self._vx_filt
        self._vy_filt = self.ema_alpha * vy_raw + (1.0 - self.ema_alpha) * self._vy_filt

        return OpticalFlowEstimate(
            flow_rad_s_x=round(comp_flow_x, 5),
            flow_rad_s_y=round(comp_flow_y, 5),
            vx_mps=round(self._vx_filt, 3),
            vy_mps=round(self._vy_filt, 3),
            pixel_shift_xy=(round(float(shift_x), 3), round(float(shift_y), 3)),
            quality_score=round(quality, 4),
            valid=True,
        )
