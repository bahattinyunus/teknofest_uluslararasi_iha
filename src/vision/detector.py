"""
TEKNOFEST 2026 Uluslararası İHA - Gelişmiş Hedef Tespit Modülü
-------------------------------------------------------------
Bu modül, 2026 şartnamesinde yer alan geometrik hedefleri (Mavi Altıgen,
Kırmızı Üçgen, Mavi Dikdörtgen, Kırmızı Kare) OpenCV geometrik analizi
ve opsiyonel YOLOv10/YOLOv8 derin öğrenme modelleri ile yüksek
kesinlikle tespit eder.
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple, Dict, Any
import cv2
import numpy as np


class TargetType(str, Enum):
    TARGET_A = "TARGET_A"  # Mavi Altıgen / Mavi Dikdörtgen -> Kırmızı Yük
    TARGET_B = "TARGET_B"  # Kırmızı Üçgen / Kırmızı Kare -> Mavi Yük
    UNKNOWN = "UNKNOWN"


class TargetShape(str, Enum):
    HEXAGON = "hexagon"
    TRIANGLE = "triangle"
    RECTANGLE = "rectangle"
    UNKNOWN = "unknown"


class TargetColor(str, Enum):
    BLUE = "blue"
    RED = "red"
    UNKNOWN = "unknown"


@dataclass
class TargetDetection:
    target_type: TargetType
    shape: TargetShape
    color: TargetColor
    confidence: float
    bbox: Tuple[int, int, int, int]  # (x, y, w, h)
    center_px: Tuple[int, int]       # (cx, cy)
    normalized_offset: Tuple[float, float]  # (-1.0 to 1.0) merkezden sapma
    area: float
    contour: Optional[np.ndarray] = None


class VisionDetector:
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Görüntü İşleme Motoru
        """
        self.config = config or {}
        vision_cfg = self.config.get("vision", {})
        
        self.confidence_threshold = vision_cfg.get("confidence_threshold", 0.65)
        self.min_contour_area = vision_cfg.get("min_contour_area", 350.0)
        self.yolo_model_path = vision_cfg.get("yolo_model_path", None)
        self.yolo_model = None

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

        # 1. Üçgen Tespiti: 3 köşe
        if num_vertices == 3 and is_convex:
            # Eşkenar üçgen kontrolü
            pts = approx.reshape(3, 2)
            d01 = np.linalg.norm(pts[0] - pts[1])
            d12 = np.linalg.norm(pts[1] - pts[2])
            d20 = np.linalg.norm(pts[2] - pts[0])
            sides = np.array([d01, d12, d20])
            std_ratio = np.std(sides) / (np.mean(sides) + 1e-6)
            confidence = max(0.5, min(0.98, 1.0 - std_ratio))
            return TargetShape.TRIANGLE, float(confidence)

        # 2. Dörtgen / Kare Tespiti: 4 köşe
        if num_vertices == 4 and is_convex:
            _, _, w, h = cv2.boundingRect(contour)
            aspect_ratio = float(w) / h if h > 0 else 0
            if 0.65 <= aspect_ratio <= 1.45:
                confidence = 0.90 if 0.85 <= aspect_ratio <= 1.15 else 0.80
                return TargetShape.RECTANGLE, confidence

        # 3. Altıgen Tespiti: 5-8 köşe ve yüksek dairesellik (düzgün altıgende circularity ~ 0.907)
        if 5 <= num_vertices <= 8:
            # Düzgün altıgende circularity yaklaşık 0.9069
            # Dairesellik 0.70 ile 0.96 arasında olmalı
            if 0.70 <= circularity <= 0.96 and is_convex:
                confidence = min(0.98, 0.75 + (0.23 * (1.0 - abs(circularity - 0.907))))
                return TargetShape.HEXAGON, float(confidence)

        # Dairesellik kontrolü ile gevşetilmiş altıgen doğrulaması
        if 0.78 <= circularity <= 0.93 and area > self.min_contour_area * 1.5:
            return TargetShape.HEXAGON, 0.75

        return TargetShape.UNKNOWN, 0.0

    def detect(self, frame: np.ndarray) -> List[TargetDetection]:
        """
        Kamera karesinde 2026 şartnamesine uygun hedefleri tespit eder.
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
                return detections

        # Geometrik + HSV Algılama
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        blue_mask, red_mask = self.detect_color_masks(hsv)

        # Mavi Konturları Tara
        blue_contours, _ = cv2.findContours(blue_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in blue_contours:
            area = cv2.contourArea(cnt)
            if area < self.min_contour_area:
                continue

            shape, conf = self.classify_shape(cnt)
            if shape in (TargetShape.HEXAGON, TargetShape.RECTANGLE) and conf >= self.confidence_threshold:
                # 2026 Kuralı: Mavi Altıgen / Dikdörtgen -> TARGET_A (Bırakılacak yük: Kırmızı)
                det = self._create_detection(
                    target_type=TargetType.TARGET_A,
                    shape=shape,
                    color=TargetColor.BLUE,
                    confidence=conf,
                    contour=cnt,
                    center_screen=center_screen,
                    frame_dims=(w, h)
                )
                detections.append(det)

        # Kırmızı Konturları Tara
        red_contours, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in red_contours:
            area = cv2.contourArea(cnt)
            if area < self.min_contour_area:
                continue

            shape, conf = self.classify_shape(cnt)
            if shape in (TargetShape.TRIANGLE, TargetShape.RECTANGLE) and conf >= self.confidence_threshold:
                # 2026 Kuralı: Kırmızı Üçgen / Kare -> TARGET_B (Bırakılacak yük: Mavi)
                det = self._create_detection(
                    target_type=TargetType.TARGET_B,
                    shape=shape,
                    color=TargetColor.RED,
                    confidence=conf,
                    contour=cnt,
                    center_screen=center_screen,
                    frame_dims=(w, h)
                )
                detections.append(det)

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
        frame_dims: Tuple[int, int]
    ) -> TargetDetection:
        M = cv2.moments(contour)
        if M["m00"] != 0:
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
        else:
            x, y, bw, bh = cv2.boundingRect(contour)
            cx, cy = x + bw // 2, y + bh // 2

        w_frame, h_frame = frame_dims
        # Normalized offset: [-1.0, 1.0] (merkez 0.0, 0.0)
        norm_x = (cx - center_screen[0]) / (w_frame / 2.0)
        norm_y = (cy - center_screen[1]) / (h_frame / 2.0)

        bx, by, bw, bh = cv2.boundingRect(contour)
        area = float(cv2.contourArea(contour))

        return TargetDetection(
            target_type=target_type,
            shape=shape,
            color=color,
            confidence=confidence,
            bbox=(bx, by, bw, bh),
            center_px=(cx, cy),
            normalized_offset=(norm_x, norm_y),
            area=area,
            contour=contour
        )

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

                    if "blue" in cls_name or "target_a" in cls_name or "hex" in cls_name:
                        target_type = TargetType.TARGET_A
                        color = TargetColor.BLUE
                        shape = TargetShape.HEXAGON
                    elif "red" in cls_name or "target_b" in cls_name or "triangle" in cls_name:
                        target_type = TargetType.TARGET_B
                        color = TargetColor.RED
                        shape = TargetShape.TRIANGLE

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
                        contour=None
                    ))
        except Exception as e:
            print(f"[VISION] YOLO çıkarım hatası: {e}")
        return detections

    def draw_hud(self, frame: np.ndarray, detections: List[TargetDetection], locked_target: Optional[TargetDetection] = None) -> np.ndarray:
        """
        Kamera görüntüsü üzerine telemetri, hedef kilitlenme göstergesi ve HUD çizimi yapar.
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

            # Bilgi etiketi
            label = f"{det.target_type.value} | {det.shape.value} ({det.confidence*100:.1f}%)"
            cv2.putText(hud, label, (x, max(20, y - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color_bgr, 2)

            # Hedefe çizgi çek
            cv2.line(hud, (cx_scr, cy_scr), det.center_px, color_bgr, 1, cv2.LINE_AA)

        # Üst Bilgi Barı
        status_text = f"HEDEFLER: {len(detections)} | KILIT: {'AKTIF' if locked_target else 'ARANIYOR'}"
        cv2.putText(hud, status_text, (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2)
        return hud
