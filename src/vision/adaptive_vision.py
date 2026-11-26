"""
Adaptive Lighting & Shadow-Invariant Vision Pipeline
====================================================
TEKNOFEST Uluslararası İHA / Savaşan İHA Görevleri için Gelişmiş Görüntü Ön İşleme.

Saha Şartları ve Problem Analizi (Geçmiş Şampiyon Takımlar Tecrübesi):
- Yunuseli / Samsun / Adana yarışma meydanlarında öğle güneşi (aşırı parlama)
  veya bulut gölgeleri sabit HSV eşiklerini bozar (doğruluk %40'ın altına düşer).
- Teknofest hedefleri: Kırmızı Altıgen (Target A) ve Mavi Üçgen (Target B).

Bu modülün sağladığı yetenekler:
1. Dinamik Işık ve Parlaklık Tahmini (Mean Luminescence & Glare Index)
2. Normalleştirilmiş Kromatiklik (Normalized Chromaticity Coordinates - NCC):
   r = R / (R+G+B), g = G / (R+G+B), b = B / (R+G+B)
   Işık şiddetinden (gölge ve bulut) bağımsız saf renk dağılımı.
3. CLAHE (Contrast Limited Adaptive Histogram Equalization) Desteği
4. Hedef Bazlı Dinamik Eşikleme (Kırmızı Altıgen & Mavi Üçgen için otomatik adaptasyon)
"""

import math
from typing import Tuple, Dict, Any, Optional, List
from dataclasses import dataclass

try:
    import cv2
    import numpy as np
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False


@dataclass
class LightingMetrics:
    """Işık ve aydınlatma istatistikleri."""
    mean_brightness: float       # Ortalama parlaklık (0 - 255)
    std_brightness: float        # Parlaklık standart sapması
    glare_ratio: float           # Aşırı parlak (parlayan) piksel oranı (0.0 - 1.0)
    shadow_ratio: float          # Derin gölge altındaki piksel oranı (0.0 - 1.0)
    condition: str               # "OPTIMAL", "HARSH_SUNLIGHT", "OVERCAST_SHADOW", "LOW_LIGHT"


class AdaptiveLightingNormalizer:
    """
    Kamera karelerindeki ışık değişimlerini, gölgeleri ve güneş parlamalarını
    gerçek zamanlı normalize eden ve hedef tespit doğruluğunu koruyan ön işlemci.
    """

    def __init__(self, clip_limit: float = 2.5, tile_grid_size: Tuple[int, int] = (8, 8)):
        self.clip_limit = clip_limit
        self.tile_grid_size = tile_grid_size
        self._clahe = None
        if HAS_CV2:
            try:
                self._clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)
            except Exception:
                self._clahe = None

    def analyze_lighting(self, frame_or_brightness: Any) -> LightingMetrics:
        """
        Kareden aydınlatma durumunu çıkarır.
        Numpy array (BGR/Gri) veya ortalama parlaklık değeri alabilir.
        """
        if HAS_CV2 and isinstance(frame_or_brightness, np.ndarray):
            if len(frame_or_brightness.shape) == 3:
                gray = cv2.cvtColor(frame_or_brightness, cv2.COLOR_BGR2GRAY)
            else:
                gray = frame_or_brightness
            mean_b = float(np.mean(gray))
            std_b = float(np.std(gray))
            total_pixels = float(gray.size)
            glare_pixels = float(np.count_nonzero(gray >= 240))
            shadow_pixels = float(np.count_nonzero(gray <= 40))
            glare_ratio = glare_pixels / max(total_pixels, 1.0)
            shadow_ratio = shadow_pixels / max(total_pixels, 1.0)
        elif isinstance(frame_or_brightness, (int, float)):
            mean_b = float(frame_or_brightness)
            std_b = 30.0
            glare_ratio = 0.2 if mean_b > 210 else 0.05
            shadow_ratio = 0.25 if mean_b < 50 else 0.05
        else:
            mean_b = 128.0
            std_b = 35.0
            glare_ratio = 0.05
            shadow_ratio = 0.05

        if mean_b > 190 or glare_ratio > 0.15:
            cond = "HARSH_SUNLIGHT"
        elif mean_b < 65 or shadow_ratio > 0.35:
            cond = "OVERCAST_SHADOW"
        elif mean_b < 40:
            cond = "LOW_LIGHT"
        else:
            cond = "OPTIMAL"

        return LightingMetrics(
            mean_brightness=round(mean_b, 2),
            std_brightness=round(std_b, 2),
            glare_ratio=round(glare_ratio, 4),
            shadow_ratio=round(shadow_ratio, 4),
            condition=cond
        )

    def apply_clahe(self, frame: Any) -> Any:
        """
        Kareye Lab renk uzayında L (Luminance) kanalı üzerinden CLAHE uygular.
        Renk tonlarını bozmadan gölgelerdeki detayları öne çıkarır.
        """
        if not HAS_CV2 or not isinstance(frame, np.ndarray) or self._clahe is None:
            return frame

        if len(frame.shape) == 2:
            return self._clahe.apply(frame)

        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        l_clahe = self._clahe.apply(l)
        merged = cv2.merge((l_clahe, a, b))
        return cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)

    def extract_normalized_chromaticity(self, frame: Any) -> Any:
        """
        Normalized Chromaticity Coordinates (NCC) dönüşümü:
        Işık parlaklığını elimine eder, sadece saf renk oranlarını bırakır.
        r = R / (R+G+B), g = G / (R+G+B), b = B / (R+G+B)
        """
        if not HAS_CV2 or not isinstance(frame, np.ndarray):
            return frame

        b, g, r = cv2.split(frame.astype(np.float32))
        total = b + g + r + 1e-5
        norm_r = (r / total) * 255.0
        norm_g = (g / total) * 255.0
        norm_b = (b / total) * 255.0

        return cv2.merge([norm_b.astype(np.uint8), norm_g.astype(np.uint8), norm_r.astype(np.uint8)])

    def get_adaptive_hsv_ranges(self, target_type: str, metrics: LightingMetrics) -> List[Tuple[Tuple[int, int, int], Tuple[int, int, int]]]:
        """
        Anlık ışık koşullarına göre Kırmızı Altıgen veya Mavi Üçgen için
        dinamik HSV alt ve üst sınırlarını adapte eder.

        Döndürür:
            [(lower_hsv, upper_hsv), ...] (Kırmızı için 2 aralık, mavi için 1 aralık)
        """
        target = target_type.upper()

        # Temel eşikler
        if target in ("A", "TARGET_A") or "HEXAGON" in target or "RED" in target:
            # Standart kırmızı 2 aralıklıdır (0-10 ve 170-180)
            if metrics.condition == "HARSH_SUNLIGHT":
                # Güneş parlamasında satürasyon düşer, parlaklık tavandır
                s_min = 70
                v_min = 120
            elif metrics.condition == "OVERCAST_SHADOW":
                # Gölgeli alanda satürasyon korunabilir ama V (Value) düşer
                s_min = 90
                v_min = 40
            else:
                s_min = 100
                v_min = 70

            return [
                ((0, s_min, v_min), (10, 255, 255)),
                ((170, s_min, v_min), (180, 255, 255))
            ]

        elif target in ("B", "TARGET_B") or "TRIANGLE" in target or "BLUE" in target:
            # Mavi hedef: H ~ 100-130
            if metrics.condition == "HARSH_SUNLIGHT":
                s_min = 60
                v_min = 110
            elif metrics.condition == "OVERCAST_SHADOW":
                s_min = 80
                v_min = 40
            else:
                s_min = 90
                v_min = 60

            return [
                ((100, s_min, v_min), (135, 255, 255))
            ]

        # Varsayılan genel renk
        return [((0, 50, 50), (180, 255, 255))]

    def preprocess_for_target(self, frame: Any, target_type: str) -> Dict[str, Any]:
        """
        Giriş karesini analiz eder, aydınlatmayı tespit eder, CLAHE uygular
        ve hedefe özel optimize edilmiş ikili maske (mask) üretir.
        """
        metrics = self.analyze_lighting(frame)

        if not HAS_CV2 or not isinstance(frame, np.ndarray):
            return {
                "lighting": metrics,
                "processed_frame": frame,
                "mask": None,
                "hsv_ranges": self.get_adaptive_hsv_ranges(target_type, metrics)
            }

        # 1. CLAHE ile kontrast dengeleme
        enhanced = self.apply_clahe(frame)

        # 2. Gaussian Blur ile yüksek frekanslı kamera parazitini temizle
        blurred = cv2.GaussianBlur(enhanced, (5, 5), 0)

        # 3. HSV dönüşümü
        hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)

        # 4. Dinamik HSV aralıklarını uygula
        ranges = self.get_adaptive_hsv_ranges(target_type, metrics)
        mask = None
        for (lower, upper) in ranges:
            low_np = np.array(lower, dtype=np.uint8)
            up_np = np.array(upper, dtype=np.uint8)
            m = cv2.inRange(hsv, low_np, up_np)
            mask = m if mask is None else cv2.bitwise_or(mask, m)

        # 5. Morfolojik Açma ve Kapama (Gürültü silme ve delik doldurma)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)

        return {
            "lighting": metrics,
            "processed_frame": enhanced,
            "mask": mask,
            "hsv_ranges": ranges
        }
