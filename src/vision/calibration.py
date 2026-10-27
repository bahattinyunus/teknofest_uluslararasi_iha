"""
TEKNOFEST 2026 Uluslararası İHA - Kamera Kalibrasyon ve Distorsiyon Giderme
-------------------------------------------------------------------------
Geniş açılı İHA kameralarında (Sony IMX477, Raspberry Pi HQ vb.) oluşan
fıçı (barrel) ve teğetsel (tangential) distorsiyonları düzeltir.
İçsel kamera matrisi (K) ve distorsiyon katsayılarını (D) hesaplayarak
hedef tespiti ve balistik açı kestiriminde optik hatayı sıfıra indirir.
"""

from typing import Tuple, Optional, List, Dict, Any
import os
import json
import cv2
import numpy as np


class CameraCalibrator:
    def __init__(
        self,
        camera_matrix: Optional[np.ndarray] = None,
        dist_coeffs: Optional[np.ndarray] = None,
        image_size: Tuple[int, int] = (1280, 720)
    ):
        self.image_size = image_size
        w, h = image_size

        if camera_matrix is None:
            # Tipik 85 derece FOV için varsayılan içsel matris
            focal_length = w / (2.0 * np.tan(np.radians(85.0) / 2.0))
            self.camera_matrix = np.array([
                [focal_length, 0.0, w / 2.0],
                [0.0, focal_length, h / 2.0],
                [0.0, 0.0, 1.0]
            ], dtype=np.float64)
            self.dist_coeffs = np.zeros((5, 1), dtype=np.float64)
            self.is_calibrated = False
        else:
            self.camera_matrix = np.array(camera_matrix, dtype=np.float64)
            self.dist_coeffs = np.array(dist_coeffs if dist_coeffs is not None else np.zeros((5, 1)), dtype=np.float64)
            self.is_calibrated = True

        self._map1 = None
        self._map2 = None
        self._init_undistort_maps()

    def _init_undistort_maps(self):
        w, h = self.image_size
        new_cam_matrix, _ = cv2.getOptimalNewCameraMatrix(
            self.camera_matrix, self.dist_coeffs, (w, h), 1, (w, h)
        )
        self._map1, self._map2 = cv2.initUndistortRectifyMap(
            self.camera_matrix, self.dist_coeffs, None, new_cam_matrix, (w, h), cv2.CV_16SC2
        )

    def undistort(self, frame: np.ndarray) -> np.ndarray:
        """Kamera karesindeki optik distorsiyonu giderir."""
        if frame is None or not self.is_calibrated:
            return frame

        if self._map1 is not None and self._map2 is not None:
            return cv2.remap(frame, self._map1, self._map2, interpolation=cv2.INTER_LINEAR)
        return cv2.undistort(frame, self.camera_matrix, self.dist_coeffs)

    def get_fov(self) -> Tuple[float, float]:
        """Yatay ve dikey görüş açısını (FOV - Derece) hesaplar."""
        fx = self.camera_matrix[0, 0]
        fy = self.camera_matrix[1, 1]
        w, h = self.image_size
        fov_x = 2.0 * np.degrees(np.arctan2(w, 2.0 * fx))
        fov_y = 2.0 * np.degrees(np.arctan2(h, 2.0 * fy))
        return float(fov_x), float(fov_y)

    def save_calibration(self, file_path: str):
        """Kalibrasyon matrislerini JSON dosyasına kaydeder."""
        data = {
            "image_size": list(self.image_size),
            "camera_matrix": self.camera_matrix.tolist(),
            "dist_coeffs": self.dist_coeffs.tolist(),
            "fov_deg": list(self.get_fov())
        }
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"[CALIB] Kamera kalibrasyonu kaydedildi: {file_path}")

    @classmethod
    def load_calibration(cls, file_path: str) -> "CameraCalibrator":
        """JSON dosyasından kalibrasyon matrislerini yükler."""
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(
            camera_matrix=np.array(data["camera_matrix"]),
            dist_coeffs=np.array(data["dist_coeffs"]),
            image_size=tuple(data["image_size"])
        )
