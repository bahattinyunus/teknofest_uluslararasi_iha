"""
TEKNOFEST 2026 Uluslararası İHA - Hedef Takip ve Filtreleme Modülü
-----------------------------------------------------------------
Hedef koordinatlarını zamansal olarak filtreler (EMA / Kalman benzeri yaklaşım),
gürültüyü ve ani kamera titreşimlerini sönümleyerek visual servoing
ve balistik bırakma için kararlı hedef koordinatları üretir.
"""

from typing import Optional, Tuple
import numpy as np
from src.vision.detector import TargetDetection, TargetType


class TargetTracker:
    def __init__(self, alpha: float = 0.65, max_missing_frames: int = 15):
        """
        :param alpha: Exponential Moving Average ağırlığı (0.0: eski değer, 1.0: anlık değer)
        :param max_missing_frames: Hedef kaybolduğunda kilidin korunacağı maksimum kare sayısı
        """
        self.alpha = alpha
        self.max_missing_frames = max_missing_frames
        
        self.tracked_target: Optional[TargetDetection] = None
        self.smoothed_center: Optional[Tuple[float, float]] = None
        self.smoothed_offset: Optional[Tuple[float, float]] = None
        self.missing_count = 0
        self.locked = False

    def update(self, detections: list[TargetDetection], desired_target_type: Optional[TargetType] = None) -> Optional[TargetDetection]:
        """
        Yeni gelen tespit listesi ile takibi günceller.
        """
        matched_detection: Optional[TargetDetection] = None

        # 1. Filtreleme: Aranan hedef tipine uygun adayları seç
        candidates = detections
        if desired_target_type:
            candidates = [d for d in detections if d.target_type == desired_target_type]

        if candidates:
            if self.smoothed_center is not None and self.locked:
                # Önceki konuma en yakın adayı seç (Euclidean distance)
                candidates.sort(
                    key=lambda d: np.hypot(d.center_px[0] - self.smoothed_center[0],
                                           d.center_px[1] - self.smoothed_center[1])
                )
                matched_detection = candidates[0]
            else:
                # En yüksek güven skoruna sahip olanı seç
                candidates.sort(key=lambda d: d.confidence, reverse=True)
                matched_detection = candidates[0]

        if matched_detection is not None:
            # Hedef bulundu
            self.missing_count = 0
            self.locked = True

            if self.smoothed_center is None:
                self.smoothed_center = (float(matched_detection.center_px[0]), float(matched_detection.center_px[1]))
                self.smoothed_offset = matched_detection.normalized_offset
            else:
                # Exponential smoothing
                scx = self.alpha * matched_detection.center_px[0] + (1 - self.alpha) * self.smoothed_center[0]
                scy = self.alpha * matched_detection.center_px[1] + (1 - self.alpha) * self.smoothed_center[1]
                self.smoothed_center = (scx, scy)

                sox = self.alpha * matched_detection.normalized_offset[0] + (1 - self.alpha) * self.smoothed_offset[0]
                soy = self.alpha * matched_detection.normalized_offset[1] + (1 - self.alpha) * self.smoothed_offset[1]
                self.smoothed_offset = (sox, soy)

            # Güncellenmiş sanal tespit nesnesi
            self.tracked_target = TargetDetection(
                target_type=matched_detection.target_type,
                shape=matched_detection.shape,
                color=matched_detection.color,
                confidence=matched_detection.confidence,
                bbox=matched_detection.bbox,
                center_px=(int(self.smoothed_center[0]), int(self.smoothed_center[1])),
                normalized_offset=self.smoothed_offset,
                area=matched_detection.area,
                contour=matched_detection.contour
            )
            return self.tracked_target
        else:
            # Hedef tespit edilemedi
            self.missing_count += 1
            if self.missing_count > self.max_missing_frames:
                self.reset()
                return None
            return self.tracked_target

    def reset(self):
        """Hedef kilidini sıfırlar."""
        self.tracked_target = None
        self.smoothed_center = None
        self.smoothed_offset = None
        self.missing_count = 0
        self.locked = False
