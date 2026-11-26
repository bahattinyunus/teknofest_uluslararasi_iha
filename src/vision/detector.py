"""
TEKNOFEST 2026 Uluslararası İHA - Gelişmiş Hedef Tespit Modülü (V7 Uyumlu)
-------------------------------------------------------------------------
Bu modül, TÜBİTAK TEKNOFEST 2026 Uluslararası İHA V7 Şartnamesinde yer alan
geometrik hedefleri OpenCV bilgisayarlı görü ve opsiyonel YOLO derin öğrenme
modelleri ile yüksek kesinlikle tespit eder.

2026 V7 Şartname Hedef Tanımları:
1. Sabit Kanat (Fixed Wing):
   - Hedef A: 4m x 4m Mavi Kare / Dikdörtgen -> Bırakılacak Yük: KIRMIZI
   - Hedef B: 2m x 2m Kırmızı Kare / Dikdörtgen -> Bırakılacak Yük: MAVİ
   - Puanlama Çapı: Merkezden itibaren 20 metre (Madde 10.1 & Tablo 3)
   - Alan Oranı (A/B): Yaklaşık 4.0 (16 m² / 4 m²)

2. Döner Kanat (Rotary Wing):
   - Hedef A: 2m Kenar Mavi Düzgün Altıgen -> Bırakılacak Yük: KIRMIZI
   - Hedef B: 1m Kenar Kırmızı Eşkenar Üçgen -> Bırakılacak Yük: MAVİ
   - Puanlama Çapı: Merkezden itibaren 10 metre (Madde 10.2 & Tablo 3)
   - Çevrel Çap / Yükseklik: Altıgen dış çapı 4.0m, Üçgen yüksekliği ~0.866m
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple, Dict, Any
import math
import cv2
import numpy as np


class TargetCategory(str, Enum):
    ROTARY_WING = "rotary_wing"
    FIXED_WING = "fixed_wing"
    ALL = "all"


class TargetType(str, Enum):
    TARGET_A = "TARGET_A"  # Sabit: 4x4m Mavi Kare | Döner: 2m Mavi Altıgen -> Kırmızı Yük
    TARGET_B = "TARGET_B"  # Sabit: 2x2m Kırmızı Kare | Döner: 1m Kırmızı Üçgen -> Mavi Yük
    UNKNOWN = "UNKNOWN"


class TargetShape(str, Enum):
    HEXAGON = "hexagon"
    TRIANGLE = "triangle"
    RECTANGLE = "rectangle"
    SQUARE = "square"
    UNKNOWN = "unknown"


class TargetColor(str, Enum):
    BLUE = "blue"
    RED = "red"
    UNKNOWN = "unknown"


class PayloadColor(str, Enum):
    RED = "red"    # Hedef A için zorunlu bırakılacak yük rengi
    BLUE = "blue"  # Hedef B için zorunlu bırakılacak yük rengi
    NONE = "none"


# TÜBİTAK TEKNOFEST 2026 V7 Resmi Şartname Hedef Özellikleri
OFFICIAL_TARGET_SPECS_V7: Dict[str, Any] = {
    "fixed_wing": {
        "description": "Sabit Kanat Hedefleri: 4x4m Mavi Kare ve 2x2m Kırmızı Kare",
        "scoring_radius_m": 20.0,
        "target_a": {
            "name": "Sabit Kanat Hedef A (4x4m Mavi Kare)",
            "geometry": "square",
            "dimensions_m": (4.0, 4.0),
            "area_m2": 16.0,
            "color": "blue",
            "payload_color": "red",
            "scoring_radius_m": 20.0
        },
        "target_b": {
            "name": "Sabit Kanat Hedef B (2x2m Kırmızı Kare)",
            "geometry": "square",
            "dimensions_m": (2.0, 2.0),
            "area_m2": 4.0,
            "color": "red",
            "payload_color": "blue",
            "scoring_radius_m": 20.0
        },
        "area_ratio_a_to_b": 4.0,
        "linear_ratio_a_to_b": 2.0
    },
    "rotary_wing": {
        "description": "Döner Kanat Hedefleri: 2m Kenar Mavi Altıgen ve 1m Kenar Kırmızı Üçgen",
        "scoring_radius_m": 10.0,
        "target_a": {
            "name": "Döner Kanat Hedef A (2m Mavi Altıgen)",
            "geometry": "regular_hexagon",
            "side_length_m": 2.0,
            "outer_diameter_m": 4.0,
            "area_m2": 10.392,  # 6 * (sqrt(3)/4) * 2^2
            "color": "blue",
            "payload_color": "red",
            "scoring_radius_m": 10.0
        },
        "target_b": {
            "name": "Döner Kanat Hedef B (1m Kırmızı Üçgen)",
            "geometry": "equilateral_triangle",
            "side_length_m": 1.0,
            "height_m": 0.866,
            "area_m2": 0.433,   # (sqrt(3)/4) * 1^2
            "color": "red",
            "payload_color": "blue",
            "scoring_radius_m": 10.0
        }
    }
}


@dataclass
class TargetDetection:
    target_type: TargetType
    shape: TargetShape
    color: TargetColor
    confidence: float
    bbox: Tuple[int, int, int, int]  # (x, y, w, h)
    center_px: Tuple[int, int]       # (cx, cy)
    normalized_offset: Tuple[float, float]  # (-1.0 to 1.0) merkezden sapma
    area: float                      # Piksel alanı
    contour: Optional[np.ndarray] = None

    # TEKNOFEST 2026 V7 Şartname Alanları (Geriye Dönük Uyumlu)
    category: str = "rotary_wing"    # "fixed_wing" | "rotary_wing"
    target_name: str = ""            # Örn: "Sabit Kanat Hedef A (4x4m Mavi)"
    payload_color: str = "red"       # "red" | "blue"
    estimated_size_m: Optional[Tuple[float, float]] = None # (width_m, height_m)
    estimated_area_m2: Optional[float] = None              # Fiziksel alan (m²)
    scoring_radius_m: float = 10.0   # Sabit: 20m, Döner: 10m
    circularity: float = 0.0         # 4*pi*area / peri^2
    aspect_ratio: float = 1.0        # w / h
    cross_validated: bool = False    # Göreceli boyut ve oran tutarlılık doğrulaması


class VisionDetector:
    def __init__(self, config: Optional[Dict[str, Any]] = None, category: Optional[str] = None):
        """
        Görüntü İşleme Motoru (TÜBİTAK TEKNOFEST 2026 V7 Uyumlu)
        Sabit Kanat (4x4m Mavi Kare, 2x2m Kırmızı Kare) ve
        Döner Kanat (2m Mavi Altıgen, 1m Kırmızı Üçgen) hedeflerini destekler.
        """
        self.config = config or {}
        vision_cfg = self.config.get("vision", {})
        comp_cfg = self.config.get("competition", {})

        # Kategori: "rotary_wing", "fixed_wing", veya "all"
        raw_cat = category or vision_cfg.get("category") or comp_cfg.get("category", "all")
        self.category = raw_cat.lower() if raw_cat else "all"

        self.confidence_threshold = vision_cfg.get("confidence_threshold", 0.65)
        self.min_contour_area = vision_cfg.get("min_contour_area", 350.0)
        self.yolo_model_path = vision_cfg.get("yolo_model_path", None)
        self.yolo_model = None

        # Kamera Görüş Açısı (FOV) - Fiziksel boyut tahmini için
        self.fov_h_deg = vision_cfg.get("fov_h_deg", 78.0)
        self.fov_v_deg = vision_cfg.get("fov_v_deg", 52.0)

        # HSV Renk Eşik Değerleri
        color_ranges = vision_cfg.get("color_ranges", {})
        self.blue_lower = np.array(color_ranges.get("blue", {}).get("lower", [100, 100, 50]), dtype=np.uint8)
        self.blue_upper = np.array(color_ranges.get("blue", {}).get("upper", [140, 255, 255]), dtype=np.uint8)

        self.red_lower1 = np.array(color_ranges.get("red_lower_range", {}).get("lower", [0, 100, 50]), dtype=np.uint8)
        self.red_upper1 = np.array(color_ranges.get("red_lower_range", {}).get("upper", [10, 255, 255]), dtype=np.uint8)
        self.red_lower2 = np.array(color_ranges.get("red_upper_range", {}).get("lower", [170, 100, 50]), dtype=np.uint8)
        self.red_upper2 = np.array(color_ranges.get("red_upper_range", {}).get("upper", [180, 255, 255]), dtype=np.uint8)

        # YOLO yüklemeyi dene
        if self.yolo_model_path:
            self._load_yolo(self.yolo_model_path)

    def set_category(self, category: str):
        """Çalışma anında yarışma kategorisini değiştirir (rotary_wing / fixed_wing / all)."""
        self.category = category.lower()

    def get_target_specs(self, category: Optional[str] = None) -> Dict[str, Any]:
        """TÜBİTAK TEKNOFEST 2026 V7 şartname hedef parametrelerini döndürür."""
        cat = (category or self.category).lower()
        if cat in OFFICIAL_TARGET_SPECS_V7:
            return OFFICIAL_TARGET_SPECS_V7[cat]
        return OFFICIAL_TARGET_SPECS_V7

    def get_expected_payload(self, target_type: TargetType) -> PayloadColor:
        """Hedef tipine göre bırakılması zorunlu yük rengini döndürür (Hedef A -> Kırmızı, Hedef B -> Mavi)."""
        if target_type == TargetType.TARGET_A:
            return PayloadColor.RED
        elif target_type == TargetType.TARGET_B:
            return PayloadColor.BLUE
        return PayloadColor.NONE

    def get_scoring_radius(self, target_type: TargetType, category: Optional[str] = None) -> float:
        """Şartname puanlama yarıçapını döndürür: Sabit Kanat için 20m, Döner Kanat için 10m."""
        cat = (category or self.category).lower()
        if cat == "fixed_wing":
            return 20.0
        return 10.0

    def _load_yolo(self, model_path: str):
        try:
            from ultralytics import YOLO
            self.yolo_model = YOLO(model_path)
            print(f"[VISION] YOLO Modeli başarıyla yüklendi: {model_path}")
        except Exception as e:
            print(f"[VISION] YOLO yüklenemedi, geometrik tabanlı yedek moda geçiliyor: {e}")
            self.yolo_model = None

    def detect_color_masks(self, hsv_frame: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Mavi ve Kırmızı HSV renk maskelerini oluşturur ve morfolojik filtreler uygular.
        """
        # Mavi Maskesi
        blue_mask = cv2.inRange(hsv_frame, self.blue_lower, self.blue_upper)

        # Kırmızı Maskesi (0-10 ve 170-180 derece çift aralık)
        red_mask1 = cv2.inRange(hsv_frame, self.red_lower1, self.red_upper1)
        red_mask2 = cv2.inRange(hsv_frame, self.red_lower2, self.red_upper2)
        red_mask = cv2.bitwise_or(red_mask1, red_mask2)

        # Gürültü giderme: Opening (erozyon+genleşme) & Closing
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        blue_clean = cv2.morphologyEx(blue_mask, cv2.MORPH_OPEN, kernel, iterations=1)
        blue_clean = cv2.morphologyEx(blue_clean, cv2.MORPH_CLOSE, kernel, iterations=2)

        red_clean = cv2.morphologyEx(red_mask, cv2.MORPH_OPEN, kernel, iterations=1)
        red_clean = cv2.morphologyEx(red_clean, cv2.MORPH_CLOSE, kernel, iterations=2)

        return blue_clean, red_clean

    def classify_shape(self, contour: np.ndarray) -> Tuple[TargetShape, float]:
        """
        Kontur geometrisini analiz ederek şekli ve güven skorunu sınıflandırır.
        Desteklenen şekiller:
        - TRIANGLE (Döner Kanat Hedef B: 1m Kırmızı Üçgen)
        - SQUARE / RECTANGLE (Sabit Kanat Hedef A: 4x4m Mavi Kare, Hedef B: 2x2m Kırmızı Kare)
        - HEXAGON (Döner Kanat Hedef A: 2m Mavi Altıgen)
        """
        peri = cv2.arcLength(contour, True)
        if peri == 0:
            return TargetShape.UNKNOWN, 0.0

        area = cv2.contourArea(contour)
        if area < self.min_contour_area:
            return TargetShape.UNKNOWN, 0.0

        # Çokgen Yaklaşımı
        approx = cv2.approxPolyDP(contour, 0.035 * peri, True)
        num_vertices = len(approx)

        # Dış bükeylik kontrolü
        is_convex = cv2.isContourConvex(approx)

        # Çevre / Alan tabanlı dairesellik skoru (4 * pi * alan / peri^2)
        circularity = 4 * np.pi * area / (peri * peri)

        # 1. Üçgen Tespiti: 3 köşe (Döner Kanat Hedef B)
        if num_vertices == 3 and is_convex:
            pts = approx.reshape(3, 2)
            d01 = np.linalg.norm(pts[0] - pts[1])
            d12 = np.linalg.norm(pts[1] - pts[2])
            d20 = np.linalg.norm(pts[2] - pts[0])
            sides = np.array([d01, d12, d20])
            std_ratio = np.std(sides) / (np.mean(sides) + 1e-6)
            confidence = max(0.5, min(0.98, 1.0 - std_ratio))
            return TargetShape.TRIANGLE, float(confidence)

        # 2. Dörtgen / Kare Tespiti: 4 köşe (Sabit Kanat 4x4m / 2x2m Kare)
        if num_vertices == 4 and is_convex:
            _, _, w, h = cv2.boundingRect(contour)
            aspect_ratio = float(w) / h if h > 0 else 0
            if 0.60 <= aspect_ratio <= 1.65:
                # Köşelerin diklik kontrolü (Orthogonality check)
                pts = approx.reshape(4, 2)
                ortho_scores = []
                for i in range(4):
                    p_prev = pts[(i - 1) % 4]
                    p_curr = pts[i]
                    p_next = pts[(i + 1) % 4]
                    v1 = p_prev - p_curr
                    v2 = p_next - p_curr
                    len1 = np.linalg.norm(v1)
                    len2 = np.linalg.norm(v2)
                    if len1 > 0 and len2 > 0:
                        cos_theta = abs(np.dot(v1, v2) / (len1 * len2))
                        ortho_scores.append(1.0 - cos_theta)
                mean_ortho = float(np.mean(ortho_scores)) if ortho_scores else 0.85

                if 0.80 <= aspect_ratio <= 1.25:
                    confidence = min(0.98, max(0.70, 0.5 * (1.0 - abs(aspect_ratio - 1.0)) + 0.5 * mean_ortho))
                    return TargetShape.SQUARE, float(confidence)
                else:
                    confidence = min(0.92, max(0.60, mean_ortho * 0.90))
                    return TargetShape.RECTANGLE, float(confidence)

        # 3. Altıgen Tespiti: 5-8 köşe ve yüksek dairesellik (Döner Kanat Hedef A)
        # Düzgün altıgende teorik dairesellik: pi * sqrt(3) / 6 ~= 0.9069
        if 5 <= num_vertices <= 8:
            if 0.70 <= circularity <= 0.96 and is_convex:
                confidence = min(0.98, 0.75 + (0.23 * (1.0 - abs(circularity - 0.907))))
                return TargetShape.HEXAGON, float(confidence)

        # Dairesellik kontrolü ile gevşetilmiş altıgen doğrulaması
        if 0.76 <= circularity <= 0.94 and area > self.min_contour_area * 1.5:
            return TargetShape.HEXAGON, 0.75

        return TargetShape.UNKNOWN, 0.0

    def estimate_physical_dimensions(
        self,
        bbox: Tuple[int, int, int, int],
        contour_area: float,
        frame_dims: Tuple[int, int],
        altitude_agl_m: float
    ) -> Dict[str, Any]:
        """
        UAV irtifası ve kamera FOV değerine göre hedefin fiziksel boyutlarını (metre) tahmin eder.
        GSD (Ground Sample Distance) = 2 * alt * tan(FOV/2) / frame_width
        """
        w_px, h_px = bbox[2], bbox[3]
        fw, fh = frame_dims
        fov_h_rad = math.radians(self.fov_h_deg)
        gsd = (2.0 * max(1.0, altitude_agl_m) * math.tan(fov_h_rad / 2.0)) / float(fw)

        width_m = w_px * gsd
        height_m = h_px * gsd
        area_m2 = contour_area * (gsd ** 2)

        return {
            "gsd_m_px": round(gsd, 4),
            "width_m": round(width_m, 2),
            "height_m": round(height_m, 2),
            "area_m2": round(area_m2, 2)
        }

    def detect(self, frame: np.ndarray, altitude_agl: Optional[float] = None) -> List[TargetDetection]:
        """
        Kamera karesinde TÜBİTAK TEKNOFEST 2026 V7 şartnamesine uygun hedefleri tespit eder.
        Sabit Kanat (4x4m Mavi Kare, 2x2m Kırmızı Kare) ve
        Döner Kanat (2m Mavi Altıgen, 1m Kırmızı Üçgen) hedeflerini sınıflandırır.
        """
        detections: List[TargetDetection] = []
        if frame is None or frame.size == 0:
            return detections

        h, w = frame.shape[:2]
        center_screen = (w // 2, h // 2)

        # YOLO modeli varsa önce onu çalıştır
        if self.yolo_model is not None:
            detections = self._detect_with_yolo(frame, center_screen)
            if len(detections) > 0:
                self._apply_cross_validation(detections, altitude_agl, (w, h))
                return detections

        # Geometrik + HSV Algılama
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        blue_mask, red_mask = self.detect_color_masks(hsv)

        # Mavi Konturları Tara (Target A adayları)
        blue_contours, _ = cv2.findContours(blue_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in blue_contours:
            area = cv2.contourArea(cnt)
            if area < self.min_contour_area:
                continue

            shape, conf = self.classify_shape(cnt)
            if conf < self.confidence_threshold:
                continue

            # Döner Kanat: Mavi Altıgen
            if shape == TargetShape.HEXAGON and self.category in ("rotary_wing", "all", "auto", "both"):
                det = self._create_detection(
                    target_type=TargetType.TARGET_A,
                    shape=shape,
                    color=TargetColor.BLUE,
                    confidence=conf,
                    contour=cnt,
                    center_screen=center_screen,
                    frame_dims=(w, h),
                    category="rotary_wing",
                    target_name="Döner Kanat Hedef A (2m Mavi Altıgen)",
                    payload_color="red",
                    scoring_radius_m=10.0,
                    altitude_agl=altitude_agl
                )
                detections.append(det)

            # Sabit Kanat: 4x4m Mavi Kare / Dikdörtgen
            elif shape in (TargetShape.SQUARE, TargetShape.RECTANGLE) and self.category in ("fixed_wing", "all", "auto", "both"):
                det = self._create_detection(
                    target_type=TargetType.TARGET_A,
                    shape=shape,
                    color=TargetColor.BLUE,
                    confidence=conf,
                    contour=cnt,
                    center_screen=center_screen,
                    frame_dims=(w, h),
                    category="fixed_wing",
                    target_name="Sabit Kanat Hedef A (4x4m Mavi Kare)",
                    payload_color="red",
                    scoring_radius_m=20.0,
                    altitude_agl=altitude_agl
                )
                detections.append(det)

        # Kırmızı Konturları Tara (Target B adayları)
        red_contours, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in red_contours:
            area = cv2.contourArea(cnt)
            if area < self.min_contour_area:
                continue

            shape, conf = self.classify_shape(cnt)
            if conf < self.confidence_threshold:
                continue

            # Döner Kanat: Kırmızı Üçgen
            if shape == TargetShape.TRIANGLE and self.category in ("rotary_wing", "all", "auto", "both"):
                det = self._create_detection(
                    target_type=TargetType.TARGET_B,
                    shape=shape,
                    color=TargetColor.RED,
                    confidence=conf,
                    contour=cnt,
                    center_screen=center_screen,
                    frame_dims=(w, h),
                    category="rotary_wing",
                    target_name="Döner Kanat Hedef B (1m Kırmızı Üçgen)",
                    payload_color="blue",
                    scoring_radius_m=10.0,
                    altitude_agl=altitude_agl
                )
                detections.append(det)

            # Sabit Kanat: 2x2m Kırmızı Kare / Dikdörtgen
            elif shape in (TargetShape.SQUARE, TargetShape.RECTANGLE) and self.category in ("fixed_wing", "all", "auto", "both"):
                det = self._create_detection(
                    target_type=TargetType.TARGET_B,
                    shape=shape,
                    color=TargetColor.RED,
                    confidence=conf,
                    contour=cnt,
                    center_screen=center_screen,
                    frame_dims=(w, h),
                    category="fixed_wing",
                    target_name="Sabit Kanat Hedef B (2x2m Kırmızı Kare)",
                    payload_color="blue",
                    scoring_radius_m=20.0,
                    altitude_agl=altitude_agl
                )
                detections.append(det)

        # Hedefler arası tutarlılık ve ölçek doğrulaması
        self._apply_cross_validation(detections, altitude_agl, (w, h))

        # Güven skoruna göre sırala
        detections.sort(key=lambda d: d.confidence, reverse=True)
        return detections

    def _create_detection(
        self,
        target_type: TargetType,
        shape: TargetShape,
        color: TargetColor,
        confidence: float,
        contour: np.ndarray,
        center_screen: Tuple[int, int],
        frame_dims: Tuple[int, int],
        category: str = "rotary_wing",
        target_name: str = "",
        payload_color: str = "red",
        scoring_radius_m: float = 10.0,
        altitude_agl: Optional[float] = None
    ) -> TargetDetection:
        M = cv2.moments(contour)
        if M["m00"] != 0:
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
        else:
            x, y, bw, bh = cv2.boundingRect(contour)
            cx, cy = x + bw // 2, y + bh // 2

        w_frame, h_frame = frame_dims
        norm_x = (cx - center_screen[0]) / (w_frame / 2.0)
        norm_y = (cy - center_screen[1]) / (h_frame / 2.0)

        bx, by, bw, bh = cv2.boundingRect(contour)
        area = float(cv2.contourArea(contour))
        peri = cv2.arcLength(contour, True)
        circ = (4.0 * math.pi * area) / (peri * peri) if peri > 0 else 0.0
        aspect = float(bw) / bh if bh > 0 else 1.0

        est_size = None
        est_area = None
        if altitude_agl is not None and altitude_agl > 0:
            phys = self.estimate_physical_dimensions((bx, by, bw, bh), area, frame_dims, altitude_agl)
            est_size = (phys["width_m"], phys["height_m"])
            est_area = phys["area_m2"]

        return TargetDetection(
            target_type=target_type,
            shape=shape,
            color=color,
            confidence=confidence,
            bbox=(bx, by, bw, bh),
            center_px=(cx, cy),
            normalized_offset=(norm_x, norm_y),
            area=area,
            contour=contour,
            category=category,
            target_name=target_name,
            payload_color=payload_color,
            estimated_size_m=est_size,
            estimated_area_m2=est_area,
            scoring_radius_m=scoring_radius_m,
            circularity=circ,
            aspect_ratio=aspect,
            cross_validated=False
        )

    def _apply_cross_validation(
        self,
        detections: List[TargetDetection],
        altitude_agl: Optional[float],
        frame_dims: Tuple[int, int]
    ):
        """
        Şartname kurallarına göre tespitler arası göreceli alan ve fiziksel boyut tutarlılığını doğrular.
        - Sabit Kanat: Hedef A (4x4m = 16m²) ile Hedef B (2x2m = 4m²) alan oranı ~4.0 olmalıdır.
        - Döner Kanat: Hedef A (10.39m²) Hedef B'den (~0.43m²) belirgin şekilde büyük olmalıdır.
        """
        fixed_a = [d for d in detections if d.category == "fixed_wing" and d.target_type == TargetType.TARGET_A]
        fixed_b = [d for d in detections if d.category == "fixed_wing" and d.target_type == TargetType.TARGET_B]

        if fixed_a and fixed_b:
            fa = fixed_a[0]
            fb = fixed_b[0]
            if fb.area > 0:
                area_ratio = fa.area / fb.area
                # Teorik alan oranı: 16 m2 / 4 m2 = 4.0
                if 2.0 <= area_ratio <= 7.0:
                    fa.cross_validated = True
                    fb.cross_validated = True
                    fa.confidence = min(0.99, fa.confidence + 0.05)
                    fb.confidence = min(0.99, fb.confidence + 0.05)

        # Fiziksel boyut doğrulaması (İrtifa biliniyorsa)
        if altitude_agl is not None and altitude_agl > 0:
            for d in detections:
                if d.estimated_size_m is not None:
                    ew, eh = d.estimated_size_m
                    max_dim = max(ew, eh)
                    if d.category == "fixed_wing":
                        if d.target_type == TargetType.TARGET_A:
                            # 4.0m hedef: tolerans [2.6m, 5.5m]
                            if 2.6 <= max_dim <= 5.5:
                                d.confidence = min(0.99, d.confidence + 0.04)
                                d.cross_validated = True
                        elif d.target_type == TargetType.TARGET_B:
                            # 2.0m hedef: tolerans [1.2m, 2.9m]
                            if 1.2 <= max_dim <= 2.9:
                                d.confidence = min(0.99, d.confidence + 0.04)
                                d.cross_validated = True
                    elif d.category == "rotary_wing":
                        if d.target_type == TargetType.TARGET_A:
                            # 2.0m kenar altıgen (dış çap ~4.0m): tolerans [2.5m, 5.5m]
                            if 2.5 <= max_dim <= 5.5:
                                d.confidence = min(0.99, d.confidence + 0.04)
                                d.cross_validated = True
                        elif d.target_type == TargetType.TARGET_B:
                            # 1.0m kenar üçgen: tolerans [0.6m, 1.6m]
                            if 0.6 <= max_dim <= 1.6:
                                d.confidence = min(0.99, d.confidence + 0.04)
                                d.cross_validated = True

    def _detect_with_yolo(self, frame: np.ndarray, center_screen: Tuple[int, int]) -> List[TargetDetection]:
        detections: List[TargetDetection] = []
        try:
            results = self.yolo_model(frame, verbose=False)
            h, w = frame.shape[:2]
            for r in results:
                boxes = r.boxes
                for box in boxes:
                    cls_id = int(box.cls[0].item())
                    conf = float(box.conf[0].item())
                    if conf < self.confidence_threshold:
                        continue
                    cls_name = r.names.get(cls_id, "").lower()

                    target_type = TargetType.UNKNOWN
                    shape = TargetShape.UNKNOWN
                    color = TargetColor.UNKNOWN
                    category = "rotary_wing"
                    payload_color = "red"
                    scoring_radius = 10.0
                    target_name = ""

                    # Sabit Kanat Sınıfları
                    if any(k in cls_name for k in ("fixed_blue", "sabit_mavi", "blue_square", "target_a_fixed")):
                        target_type = TargetType.TARGET_A
                        color = TargetColor.BLUE
                        shape = TargetShape.SQUARE
                        category = "fixed_wing"
                        payload_color = "red"
                        scoring_radius = 20.0
                        target_name = "Sabit Kanat Hedef A (4x4m Mavi Kare)"
                    elif any(k in cls_name for k in ("fixed_red", "sabit_kirmizi", "red_square", "target_b_fixed")):
                        target_type = TargetType.TARGET_B
                        color = TargetColor.RED
                        shape = TargetShape.SQUARE
                        category = "fixed_wing"
                        payload_color = "blue"
                        scoring_radius = 20.0
                        target_name = "Sabit Kanat Hedef B (2x2m Kırmızı Kare)"

                    # Döner Kanat Sınıfları
                    elif any(k in cls_name for k in ("blue", "target_a", "hex", "altigen")):
                        target_type = TargetType.TARGET_A
                        color = TargetColor.BLUE
                        shape = TargetShape.HEXAGON
                        category = "rotary_wing"
                        payload_color = "red"
                        scoring_radius = 10.0
                        target_name = "Döner Kanat Hedef A (2m Mavi Altıgen)"
                    elif any(k in cls_name for k in ("red", "target_b", "triangle", "ucgen")):
                        target_type = TargetType.TARGET_B
                        color = TargetColor.RED
                        shape = TargetShape.TRIANGLE
                        category = "rotary_wing"
                        payload_color = "blue"
                        scoring_radius = 10.0
                        target_name = "Döner Kanat Hedef B (1m Kırmızı Üçgen)"

                    # Kategori filtresi
                    if self.category not in ("all", "auto", "both") and category != self.category:
                        continue

                    xyxy = box.xyxy[0].cpu().numpy().astype(int)
                    bx, by, bx2, by2 = xyxy
                    bw, bh = bx2 - bx, by2 - by
                    cx = bx + bw // 2
                    cy = by + bh // 2
                    norm_x = (cx - center_screen[0]) / (w / 2.0)
                    norm_y = (cy - center_screen[1]) / (h / 2.0)

                    detections.append(TargetDetection(
                        target_type=target_type,
                        shape=shape,
                        color=color,
                        confidence=conf,
                        bbox=(bx, by, bw, bh),
                        center_px=(cx, cy),
                        normalized_offset=(norm_x, norm_y),
                        area=float(bw * bh),
                        contour=None,
                        category=category,
                        target_name=target_name,
                        payload_color=payload_color,
                        scoring_radius_m=scoring_radius,
                        aspect_ratio=float(bw) / bh if bh > 0 else 1.0
                    ))
        except Exception as e:
            print(f"[VISION] YOLO çıkarım hatası: {e}")
        return detections

    def draw_hud(
        self,
        frame: np.ndarray,
        detections: List[TargetDetection],
        locked_target: Optional[TargetDetection] = None
    ) -> np.ndarray:
        """
        Kamera görüntüsü üzerine telemetri, hedef kilitlenme göstergesi,
        TÜBİTAK 2026 V7 hedef bilgileri ve HUD çizimi yapar.
        """
        hud = frame.copy()
        h, w = hud.shape[:2]
        cx_scr, cy_scr = w // 2, h // 2

        # Reticle (Merkez Nişangah)
        cv2.line(hud, (cx_scr - 30, cy_scr), (cx_scr + 30, cy_scr), (0, 255, 0), 1)
        cv2.line(hud, (cx_scr, cy_scr - 30), (cx_scr, cy_scr + 30), (0, 255, 0), 1)
        cv2.circle(hud, (cx_scr, cy_scr), 20, (0, 255, 0), 1)

        for det in detections:
            is_locked = locked_target and (locked_target.center_px == det.center_px)
            color_bgr = (0, 255, 0) if is_locked else ((255, 120, 0) if det.color == TargetColor.BLUE else (0, 0, 255))

            x, y, bw, bh = det.bbox
            cv2.rectangle(hud, (x, y), (x + bw, y + bh), color_bgr, 2 if not is_locked else 3)

            # Merkez noktası
            cv2.circle(hud, det.center_px, 4, color_bgr, -1)

            # Bilgi etiketi 1: Kategori | Hedef Tipi | Şekil (Güven)
            cat_tag = "SABIT" if det.category == "fixed_wing" else "DONER"
            verified_tag = " [OK]" if det.cross_validated else ""
            label = f"[{cat_tag}] {det.target_type.value} | {det.shape.value} ({det.confidence*100:.1f}%){verified_tag}"
            cv2.putText(hud, label, (x, max(20, y - 22)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color_bgr, 2)

            # Bilgi etiketi 2: Gerekli Yük Rengi ve Puanlama Yarıçapı
            payload_txt = f"YUK: {det.payload_color.upper()} | R_puan: {det.scoring_radius_m:.0f}m"
            if det.estimated_size_m:
                payload_txt += f" | {det.estimated_size_m[0]:.1f}x{det.estimated_size_m[1]:.1f}m"
            cv2.putText(hud, payload_txt, (x, max(36, y - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (255, 255, 255), 1)

            # Hedefe çizgi çek
            cv2.line(hud, (cx_scr, cy_scr), det.center_px, color_bgr, 1, cv2.LINE_AA)

        # Üst Bilgi Barı
        cat_title = "SABİT KANAT" if self.category == "fixed_wing" else ("DÖNER KANAT" if self.category == "rotary_wing" else "TÜM KATEGORİLER")
        status_text = f"MOD: {cat_title} | HEDEFLER: {len(detections)} | KILIT: {'AKTIF' if locked_target else 'ARANIYOR'}"
        cv2.putText(hud, status_text, (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.60, (0, 255, 255), 2)
        return hud

    @classmethod
    def generate_synthetic_frame(
        cls,
        category: str = "rotary_wing",
        width: int = 1280,
        height: int = 720,
        add_noise: bool = True
    ) -> np.ndarray:
        """
        TÜBİTAK TEKNOFEST 2026 V7 Şartnamesine uygun sentetik hedef karesi üretir:
        - "fixed_wing": 4x4m Mavi Kare (Hedef A) ve 2x2m Kırmızı Kare (Hedef B)
        - "rotary_wing": 2m Kenar Mavi Altıgen (Hedef A) ve 1m Kenar Kırmızı Üçgen (Hedef B)
        - "all": Her iki kategorinin hedeflerini de içerir
        """
        frame = np.full((height, width, 3), (70, 110, 60), dtype=np.uint8)

        if add_noise:
            noise = np.random.randint(-10, 10, (height, width, 3), dtype=np.int16)
            frame = np.clip(frame.astype(np.int16) + noise, 0, 255).astype(np.uint8)

        # 1. Döner Kanat Hedefleri
        if category in ("rotary_wing", "all"):
            # Mavi Altıgen (Target A - Rotary)
            hex_center = (width // 3, height // 2)
            hex_radius = 65
            angles = np.linspace(0, 2 * np.pi, 7)[:-1]
            hex_pts = np.array([
                [int(hex_center[0] + hex_radius * np.cos(a)),
                 int(hex_center[1] + hex_radius * np.sin(a))]
                for a in angles
            ], dtype=np.int32)
            cv2.fillPoly(frame, [hex_pts], (220, 100, 20))
            cv2.polylines(frame, [hex_pts], isClosed=True, color=(255, 255, 255), thickness=2)

            # Kırmızı Üçgen (Target B - Rotary)
            tri_center = (2 * width // 3, height // 2)
            tri_side = 75
            h_tri = int(tri_side * np.sqrt(3) / 2)
            tri_pts = np.array([
                [tri_center[0], tri_center[1] - (2 * h_tri // 3)],
                [tri_center[0] - tri_side // 2, tri_center[1] + h_tri // 3],
                [tri_center[0] + tri_side // 2, tri_center[1] + h_tri // 3]
            ], dtype=np.int32)
            cv2.fillPoly(frame, [tri_pts], (30, 30, 220))
            cv2.polylines(frame, [tri_pts], isClosed=True, color=(255, 255, 255), thickness=2)

        # 2. Sabit Kanat Hedefleri
        if category in ("fixed_wing", "all"):
            # Sabit Kanat Hedef A: 4x4m Mavi Kare (Görselde daha büyük)
            offset_y = 120 if category == "all" else 0
            sq_a_center = (width // 3, height // 2 - offset_y)
            sq_a_size = 110  # 4x4m temsil eden büyük kare
            x1_a = sq_a_center[0] - sq_a_size // 2
            y1_a = sq_a_center[1] - sq_a_size // 2
            cv2.rectangle(frame, (x1_a, y1_a), (x1_a + sq_a_size, y1_a + sq_a_size), (220, 100, 20), -1)
            cv2.rectangle(frame, (x1_a, y1_a), (x1_a + sq_a_size, y1_a + sq_a_size), (255, 255, 255), 2)

            # Sabit Kanat Hedef B: 2x2m Kırmızı Kare (Görselde daha küçük, ~1/2 kenar boyutu)
            sq_b_center = (2 * width // 3, height // 2 - offset_y)
            sq_b_size = 55   # 2x2m temsil eden küçük kare (kenar oranı 1/2, alan oranı ~1/4)
            x1_b = sq_b_center[0] - sq_b_size // 2
            y1_b = sq_b_center[1] - sq_b_size // 2
            cv2.rectangle(frame, (x1_b, y1_b), (x1_b + sq_b_size, y1_b + sq_b_size), (30, 30, 220), -1)
            cv2.rectangle(frame, (x1_b, y1_b), (x1_b + sq_b_size, y1_b + sq_b_size), (255, 255, 255), 2)

        return frame
