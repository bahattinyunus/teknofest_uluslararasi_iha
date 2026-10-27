"""
TEKNOFEST 2026 Uluslararası İHA - Genişletilmiş Kalman Filtresi (Target EKF)
----------------------------------------------------------------------------
Kamera piksel koordinatları, İHA'nın anlık 3 eksenli oryantasyonu (Roll, Pitch, Yaw)
ve AGL irtifasını kullanarak hedefin yerdeki mutlak koordinatlarını (X, Y)
santimetre hassasiyetinde ve gürültüsüz kestiren EKF takip filtresi.
"""

from dataclasses import dataclass
from typing import Tuple, Optional
import numpy as np


@dataclass
class TargetState:
    pos_x_m: float      # Hedefin kalkış noktasına göre X konumu (metre)
    pos_y_m: float      # Hedefin kalkış noktasına göre Y konumu (metre)
    vel_x_mps: float    # Hedef hareket hızı X (statik hedeflerde ~0)
    vel_y_mps: float    # Hedef hareket hızı Y (statik hedeflerde ~0)
    uncertainty_m: float # 1-sigma konum belirsizliği (metre)
    is_converged: bool  # Filtre yakınsadı mı?


class TargetEKF:
    def __init__(self, process_noise_q: float = 0.05, measurement_noise_r: float = 0.8):
        """
        Durum vektörü: x = [pos_x, pos_y, vel_x, vel_y]^T
        """
        self.q_val = process_noise_q
        self.r_val = measurement_noise_r

        # Durum vektörü ve kovaryans matrisi
        self.x = np.zeros((4, 1), dtype=np.float64)
        self.P = np.eye(4, dtype=np.float64) * 100.0  # Başlangıçta yüksek belirsizlik

        self.initialized = False
        self.last_update_time: Optional[float] = None
        self.update_count = 0

    def predict(self, dt: float):
        """Durum kestirimi adımı (Time update / prediction)."""
        if not self.initialized:
            return

        dt = max(0.001, min(0.5, dt))

        # Durum geçiş matrisi F
        F = np.array([
            [1.0, 0.0,  dt, 0.0],
            [0.0, 1.0, 0.0,  dt],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0]
        ], dtype=np.float64)

        # Süreç gürültüsü kovaryansı Q (Sürekli beyaz gürültü modeli)
        q = self.q_val
        q_pos = (dt**3) / 3.0 * q
        q_cross = (dt**2) / 2.0 * q
        q_vel = dt * q
        Q = np.array([
            [q_pos,   0.0, q_cross,     0.0],
            [  0.0, q_pos,     0.0, q_cross],
            [q_cross, 0.0,   q_vel,     0.0],
            [  0.0, q_cross,   0.0,   q_vel]
        ], dtype=np.float64)

        self.x = F @ self.x
        self.P = F @ self.P @ F.T + Q

    def project_pixel_to_ground(
        self,
        norm_offset_xy: Tuple[float, float],
        uav_pos_xy: Tuple[float, float],
        altitude_agl: float,
        roll_deg: float = 0.0,
        pitch_deg: float = 0.0,
        yaw_deg: float = 0.0,
        fov_deg: float = 85.0
    ) -> Tuple[float, float]:
        """
        Pinhole kamera modeli ve Euler açıları ile piksel sapmasını
        yer düzlemindeki 2D koordinata (X_ground, Y_ground) projekte eder.
        """
        norm_x, norm_y = norm_offset_xy
        h = max(1.0, altitude_agl)

        # Görüş açısına göre optik sapma açısı
        fov_rad = np.radians(fov_deg)
        half_fov = fov_rad / 2.0

        # İHA gövdesine göre kamera ışın açısı
        ang_x = norm_x * half_fov  # Sağa/Sola
        ang_y = norm_y * half_fov  # İleri/Geri

        # Oryantasyon düzeltmesi (Roll ve Pitch kompanzasyonu)
        roll_rad = np.radians(roll_deg)
        pitch_rad = np.radians(pitch_deg)
        yaw_rad = np.radians(yaw_deg)

        total_ang_x = ang_x + roll_rad
        total_ang_y = -ang_y + pitch_rad  # İleri yön (+ pitch)

        # Yere düşüş mesafeleri (İHA gövde ekseninde)
        body_dx = h * np.tan(total_ang_y)
        body_dy = h * np.tan(total_ang_x)

        # Dünya (NED) koordinatlarına rotasyon (Yaw dönüşümü)
        cos_yaw = np.cos(yaw_rad)
        sin_yaw = np.sin(yaw_rad)

        world_dx = body_dx * cos_yaw - body_dy * sin_yaw
        world_dy = body_dx * sin_yaw + body_dy * cos_yaw

        ground_x = uav_pos_xy[0] + world_dx
        ground_y = uav_pos_xy[1] + world_dy

        return float(ground_x), float(ground_y)

    def update(
        self,
        norm_offset_xy: Tuple[float, float],
        uav_pos_xy: Tuple[float, float],
        altitude_agl: float,
        roll_deg: float = 0.0,
        pitch_deg: float = 0.0,
        yaw_deg: float = 0.0,
        dt: float = 0.05
    ) -> TargetState:
        """
        Yeni bir kamera tespit ölçümü ile EKF filtresini günceller.
        """
        # Ham yer ölçümünü hesapla
        meas_x, meas_y = self.project_pixel_to_ground(
            norm_offset_xy=norm_offset_xy,
            uav_pos_xy=uav_pos_xy,
            altitude_agl=altitude_agl,
            roll_deg=roll_deg,
            pitch_deg=pitch_deg,
            yaw_deg=yaw_deg
        )

        z = np.array([[meas_x], [meas_y]], dtype=np.float64)

        if not self.initialized:
            self.x[0, 0] = meas_x
            self.x[1, 0] = meas_y
            self.x[2, 0] = 0.0
            self.x[3, 0] = 0.0
            self.P = np.eye(4, dtype=np.float64) * 5.0
            self.initialized = True
            self.update_count = 1
            return self.get_state()

        # Önce tahmin adımı
        self.predict(dt)

        # Ölçüm matrisi H (Yalnızca pos_x ve pos_y ölçülür)
        H = np.array([
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0]
        ], dtype=np.float64)

        # İrtifa arttıkça ölçüm gürültüsü artar
        r = self.r_val * (1.0 + (altitude_agl / 40.0)**2)
        R = np.eye(2, dtype=np.float64) * r

        # İnovasyon (Artık vektör)
        y = z - (H @ self.x)
        S = H @ self.P @ H.T + R
        K = self.P @ H.T @ np.linalg.inv(S)

        # Durum ve Kovaryans güncellemesi
        self.x = self.x + K @ y
        I = np.eye(4, dtype=np.float64)
        # Joseph formülasyonu (Sayısal kararlılık için)
        self.P = (I - K @ H) @ self.P @ (I - K @ H).T + K @ R @ K.T

        self.update_count += 1
        return self.get_state()

    def get_state(self) -> TargetState:
        pos_x = float(self.x[0, 0])
        pos_y = float(self.x[1, 0])
        vel_x = float(self.x[2, 0])
        vel_y = float(self.x[3, 0])

        pos_var = float(self.P[0, 0] + self.P[1, 1]) / 2.0
        uncertainty = float(np.sqrt(max(0.0, pos_var)))
        converged = bool(self.update_count >= 10 and uncertainty < 1.5)

        return TargetState(
            pos_x_m=round(pos_x, 3),
            pos_y_m=round(pos_y, 3),
            vel_x_mps=round(vel_x, 3),
            vel_y_mps=round(vel_y, 3),
            uncertainty_m=round(uncertainty, 3),
            is_converged=converged
        )

    def reset(self):
        self.x = np.zeros((4, 1), dtype=np.float64)
        self.P = np.eye(4, dtype=np.float64) * 100.0
        self.initialized = False
        self.update_count = 0
