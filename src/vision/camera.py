"""
TEKNOFEST 2026 Uluslararası İHA - Kamera Arayüzü & Sentetik Simülatör
--------------------------------------------------------------------
USB, CSI GStreamer (Jetson), RTSP ve Yazılımsal Sentetik Kamera
akışlarını yöneten modüler kamera sürücüsü.
"""

from typing import Optional, Tuple
import cv2
import numpy as np


class CameraInterface:
    def __init__(
        self,
        source: str = "synthetic",
        width: int = 1280,
        height: int = 720,
        fps: int = 30
    ):
        self.source = source
        self.width = width
        self.height = height
        self.fps = fps
        self.cap: Optional[cv2.VideoCapture] = None
        self._sim_tick = 0
        self._sim_target_x = width // 2 + 100
        self._sim_target_y = height // 2 + 60

        self._initialize_camera()

    def _gstreamer_pipeline(self) -> str:
        """NVIDIA Jetson Orin Nano CSI kamera için donanım hızlandırmalı pipeline."""
        return (
            f"nvarguscamerasrc ! "
            f"video/x-raw(memory:NVMM), width=(int){self.width}, height=(int){self.height}, format=(string)NV12, framerate=(fraction){self.fps}/1 ! "
            f"nvvidconv flip-method=0 ! "
            f"video/x-raw, width=(int){self.width}, height=(int){self.height}, format=(string)BGRx ! "
            f"videoconvert ! "
            f"video/x-raw, format=(string)BGR ! appsink"
        )

    def _initialize_camera(self):
        if self.source == "synthetic":
            print("[CAMERA] Sentetik/Simülasyon kamera kaynağı devrede.")
            return

        if self.source == "csi":
            pipeline = self._gstreamer_pipeline()
            self.cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
        elif str(self.source).isdigit():
            self.cap = cv2.VideoCapture(int(self.source), cv2.CAP_DSHOW if cv2.__file__ else cv2.CAP_ANY)
        else:
            self.cap = cv2.VideoCapture(self.source)

        if self.cap and self.cap.isOpened():
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            self.cap.set(cv2.CAP_PROP_FPS, self.fps)
            print(f"[CAMERA] Kamera başarıyla açıldı ({self.source}, {self.width}x{self.height} @ {self.fps}FPS)")
        else:
            print(f"[CAMERA] UYARI: Donanım kamerası ({self.source}) açılamadı, sentetik moda geçiliyor.")
            self.source = "synthetic"

    def read_frame(self) -> Tuple[bool, np.ndarray]:
        """Kameradan yeni kare okur."""
        if self.source == "synthetic":
            return True, self._generate_synthetic_frame()

        if self.cap is not None and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret and frame is not None:
                return True, frame

        # Başarısız olursa sentetik kare döndür
        return True, self._generate_synthetic_frame()

    def _generate_synthetic_frame(self) -> np.ndarray:
        """
        TEKNOFEST 2026 kurallarına uygun Mavi Altıgen ve Kırmızı Üçgen
        içeren sentetik test karesi oluşturur.
        """
        self._sim_tick += 1
        # Arka plan: Çim dokusu (Yeşilimsi gri)
        frame = np.full((self.height, self.width, 3), (70, 110, 60), dtype=np.uint8)

        # Hafif rastgele gürültü ekle
        noise = np.random.randint(-10, 10, (self.height, self.width, 3), dtype=np.int16)
        frame = np.clip(frame.astype(np.int16) + noise, 0, 255).astype(np.uint8)

        # 1. HEDEF A: Mavi Altıgen (Target A - Rotary Wing)
        # Salınımlı hareket simülasyonu
        drift_x = int(30 * np.sin(self._sim_tick * 0.05))
        drift_y = int(20 * np.cos(self._sim_tick * 0.05))
        hex_center = (self._sim_target_x + drift_x, self._sim_target_y + drift_y)
        hex_radius = 65

        angles = np.linspace(0, 2 * np.pi, 7)[:-1]
        hex_pts = np.array([
            [int(hex_center[0] + hex_radius * np.cos(a)),
             int(hex_center[1] + hex_radius * np.sin(a))]
            for a in angles
        ], dtype=np.int32)

        # Mavi dolgu: BGR (220, 100, 20)
        cv2.fillPoly(frame, [hex_pts], (220, 100, 20))
        cv2.polylines(frame, [hex_pts], isClosed=True, color=(255, 255, 255), thickness=3)

        # 2. HEDEF B: Kırmızı Üçgen (Target B - Rotary Wing)
        tri_center = (self.width // 4 + drift_x // 2, self.height // 2 - drift_y // 2)
        tri_side = 80
        h_tri = int(tri_side * np.sqrt(3) / 2)
        tri_pts = np.array([
            [tri_center[0], tri_center[1] - (2 * h_tri // 3)],
            [tri_center[0] - tri_side // 2, tri_center[1] + h_tri // 3],
            [tri_center[0] + tri_side // 2, tri_center[1] + h_tri // 3]
        ], dtype=np.int32)

        # Kırmızı dolgu: BGR (30, 30, 220)
        cv2.fillPoly(frame, [tri_pts], (30, 30, 220))
        cv2.polylines(frame, [tri_pts], isClosed=True, color=(255, 255, 255), thickness=3)

        return frame

    def release(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None
