"""
TEKNOFEST 2026 Uluslararası İHA - Görsel Denetimli Kontrol (Visual Servoing)
---------------------------------------------------------------------------
Kameranın gördüğü hedefin merkezden sapma değerlerini (offset)
görev kontrol hız komutlarına (vx, vy, vz, yaw_rate) dönüştüren PID kontrolcü.
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional, Tuple
import time


@dataclass
class VelocityCommand:
    vx_mps: float  # İleri (+)/Geri (-)
    vy_mps: float  # Sağ (+)/Sol (-)
    vz_mps: float  # Aşağı (+)/Yukarı (-)
    yaw_rate_deg_s: float
    is_centered: bool


class PIDController:
    def __init__(self, kp: float, ki: float, kd: float, output_limit: float):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.output_limit = output_limit
        
        self.prev_error = 0.0
        self.integral = 0.0
        self.prev_time: Optional[float] = None

    def update(self, error: float, dt: Optional[float] = None) -> float:
        now = time.monotonic()
        if dt is None:
            dt = 0.05 if self.prev_time is None else max(0.001, now - self.prev_time)
        self.prev_time = now

        # Oransal
        p_term = self.kp * error

        # İntegral (Anti-windup ile)
        self.integral += error * dt
        i_term = self.ki * self.integral

        # Türev
        derivative = (error - self.prev_error) / dt
        d_term = self.kd * derivative
        self.prev_error = error

        output = p_term + i_term + d_term
        # Sınırlandırma (Clamping)
        return float(max(-self.output_limit, min(self.output_limit, output)))

    def reset(self):
        self.prev_error = 0.0
        self.integral = 0.0
        self.prev_time = None


class VisualServoController:
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        cfg = config or {}
        vs_cfg = cfg.get("visual_servoing", {})

        self.max_velocity = vs_cfg.get("max_velocity_mps", 1.8)
        self.center_tolerance = vs_cfg.get("center_tolerance_px", 30.0)

        # X (İleri/Geri - Kamera Y ekseni)
        kp_x = vs_cfg.get("kp_x", 1.8)
        ki_x = vs_cfg.get("ki_x", 0.05)
        kd_x = vs_cfg.get("kd_x", 0.3)
        self.pid_x = PIDController(kp_x, ki_x, kd_x, self.max_velocity)

        # Y (Sağ/Sol - Kamera X ekseni)
        kp_y = vs_cfg.get("kp_y", 1.8)
        ki_y = vs_cfg.get("ki_y", 0.05)
        kd_y = vs_cfg.get("kd_y", 0.3)
        self.pid_y = PIDController(kp_y, ki_y, kd_y, self.max_velocity)

        # Yaw rotasyon kontrolü
        self.pid_yaw = PIDController(kp=15.0, ki=0.0, kd=2.0, output_limit=30.0)

    def compute_control(
        self,
        target_offset_norm: Tuple[float, float],
        target_center_px: Tuple[int, int],
        screen_dims: Tuple[int, int] = (1280, 720),
        dt: Optional[float] = None
    ) -> VelocityCommand:
        """
        Görsel sapmaya göre gövde ekseninde hız komutları üretir.
        target_offset_norm: (norm_x [-1..1], norm_y [-1..1])
        """
        norm_x, norm_y = target_offset_norm
        w, h = screen_dims
        cx, cy = target_center_px
        center_dist_px = ((cx - w / 2.0)**2 + (cy - h / 2.0)**2)**0.5

        is_centered = center_dist_px <= self.center_tolerance

        # Aşağı bakan kamera oryantasyonu:
        # norm_y > 0 (hedef ekranın altında) -> İHA geri gitmeli (-vx)
        # norm_y < 0 (hedef ekranın üstünde) -> İHA ileri gitmeli (+vx)
        vx = self.pid_x.update(-norm_y, dt=dt)

        # norm_x > 0 (hedef ekranın sağında) -> İHA sağa gitmeli (+vy)
        # norm_x < 0 (hedef ekranın solunda) -> İHA sola gitmeli (-vy)
        vy = self.pid_y.update(norm_x, dt=dt)

        # Yaw rotasyonu ile hedef doğrultusuna yönel
        yaw_rate = self.pid_yaw.update(norm_x, dt=dt)

        if is_centered:
            # Merkezlendiyse hız komutlarını minimumda tut
            vx *= 0.2
            vy *= 0.2
            yaw_rate = 0.0

        return VelocityCommand(
            vx_mps=round(vx, 3),
            vy_mps=round(vy, 3),
            vz_mps=0.0,
            yaw_rate_deg_s=round(yaw_rate, 2),
            is_centered=is_centered
        )

    def reset(self):
        self.pid_x.reset()
        self.pid_y.reset()
        self.pid_yaw.reset()
