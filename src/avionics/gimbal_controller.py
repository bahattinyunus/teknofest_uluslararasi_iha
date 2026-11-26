"""
Active 2-Axis / 3-Axis Gimbal Target Tracking & Horizon Stabilization Controller
=================================================================================
TEKNOFEST 2026 Uluslararası İHA & Savaşan İHA Görevleri için Aktif Gimbal Kontrolcüsü.

Havacılık Problemi & Teşhis:
Sabit aşağı bakan (nadir) kameralarda, İHA hedefe yaklaşırken veya dönüş yaparken
yüksek yatış (roll > 20°) veya hücum açısı (pitch) aldığında yerdeki hedef kameranın
görüş açısından tamamen çıkmakta ve hedef takibi kopmaktadır.

Bu modül:
1. Ufuk Stabilizasyonu: İHA'nın roll ve pitch salınımlarını ters açıyla sönümleyerek
   kameranın optik eksenini daima ufka paralel / yere dik tutar.
2. Aktif Görüş Hattı (Line-Of-Sight - LOS) Hedef Takibi:
   İHA ve yerdeki hedefin 3B konumları (NED) üzerinden gereken azimut (yaw) ve
   yükseliş (pitch) açılarını anlık hesaplar.
3. Slew-Rate Kısıtlaması (Azami açısal hız sınırlayıcı):
   Gimbal motorlarının ani sarsıntısını ve 'rolling shutter jello' etkisini önler.
4. MAVLink DO_MOUNT_CONTROL (#205) / GIMBAL_MANAGER_SET_ATTITUDE komut üretimi.
"""

import math
import struct
from typing import Tuple, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum


class GimbalMode(Enum):
    RETRACTED = "RETRACTED"          # Güvenli kilit pozisyonu (0, 0, 0)
    NADIR_STABILIZED = "NADIR"       # Yere tam dik (İHA salınımlarını sönümler)
    TARGET_LOCK_LOS = "TARGET_LOS"   # Hedef GPS/NED koordinatına kilitli LOS takibi
    VISUAL_SERVO = "VISUAL_SERVO"    # Kamera piksel merkezleme komutları ile kapalı çevrim


@dataclass
class GimbalAngles:
    """Gimbal açıları (derece cinsinden)."""
    roll_deg: float = 0.0     # Sağa yatış (+)
    pitch_deg: float = -90.0  # Ufuk: 0, Tam zemin (nadir): -90
    yaw_deg: float = 0.0      # Kuzey veya gövde referanslı azimut
    mode: GimbalMode = GimbalMode.NADIR_STABILIZED


class GimbalController:
    """
    İHA gövde hareketlerinden bağımsız, hedefi sürekli kameranın optik merkezinde
    tutan aktif 2-eksenli / 3-eksenli gimbal kontrolcüsü.
    """

    def __init__(
        self,
        max_slew_rate_deg_s: float = 120.0,
        pitch_min_deg: float = -110.0,
        pitch_max_deg: float = 15.0,
        roll_limit_deg: float = 35.0
    ):
        self.max_slew_rate = max_slew_rate_deg_s
        self.pitch_min = pitch_min_deg
        self.pitch_max = pitch_max_deg
        self.roll_limit = roll_limit_deg

        self.current_angles = GimbalAngles()
        self.target_angles = GimbalAngles()
        self.last_update_time: Optional[float] = None

    def update_nadir_stabilization(
        self,
        uav_roll_deg: float,
        uav_pitch_deg: float,
        uav_yaw_deg: float,
        timestamp: float
    ) -> GimbalAngles:
        """
        Nadir Modu: Kameranın optik eksenini doğrudan yeryüzüne dik tutar.
        İHA gövdesinin roll ve pitch salınımlarını kompanze eder.
        """
        # Gövdeye bağlı gimbal için:
        # İHA sağa yatarsa gimbal sola yatar: roll_cmd = -uav_roll_deg
        # İHA burnunu kaldırırsa: pitch_cmd = -90 - uav_pitch_deg
        desired_roll = -uav_roll_deg
        desired_pitch = -90.0 - uav_pitch_deg
        desired_yaw = 0.0  # Gövde eksenine hizalı

        return self._apply_rate_limit(
            desired_roll, desired_pitch, desired_yaw,
            GimbalMode.NADIR_STABILIZED, timestamp
        )

    def update_target_tracking(
        self,
        uav_pos_ned: Tuple[float, float, float],
        uav_attitude_rpy_deg: Tuple[float, float, float],
        target_pos_ned: Tuple[float, float, float],
        timestamp: float
    ) -> GimbalAngles:
        """
        Görüş Hattı (LOS) Modu:
        İHA ve hedefin 3B NED konum farkını kullanarak hedefi merkeze alan
        pitch ve yaw açılarını hesaplar.
        """
        un, ue, ud = uav_pos_ned
        tn, te, td = target_pos_ned
        u_roll, u_pitch, u_yaw = uav_attitude_rpy_deg

        delta_n = tn - un
        delta_e = te - ue
        delta_d = td - ud  # Hedef zeminde ise (uav_alt > 0 iken) delta_d pozitiftir

        dist_h = math.hypot(delta_n, delta_e)
        dist_3d = math.hypot(dist_h, delta_d)

        if dist_3d < 0.1:
            return self.update_nadir_stabilization(u_roll, u_pitch, u_yaw, timestamp)

        # 1. Dünya (NED) çerçevesinde mutlak LOS açıları
        # Azimut (Yaw): Kuzeyden Doğuya açı
        los_yaw_ned_deg = math.degrees(math.atan2(delta_e, delta_n))

        # Yükseliş (Elevation / Pitch):
        # Yatay düzlem = 0 deg, Tam zemin (aşağı) = -90 deg
        los_pitch_ned_deg = -math.degrees(math.atan2(delta_d, max(dist_h, 0.05)))

        # 2. Gövde referanslı açıya dönüştür
        # Gövdeye göre yaw farkı:
        yaw_body_relative = (los_yaw_ned_deg - u_yaw + 180.0) % 360.0 - 180.0
        pitch_body_relative = los_pitch_ned_deg - u_pitch
        roll_stabilized = -u_roll

        return self._apply_rate_limit(
            roll_stabilized, pitch_body_relative, yaw_body_relative,
            GimbalMode.TARGET_LOCK_LOS, timestamp
        )

    def update_visual_servo(
        self,
        norm_error_x: float,
        norm_error_y: float,
        timestamp: float,
        gain_p: float = 15.0
    ) -> GimbalAngles:
        """
        Kamera piksel hatasından (normalized -1.0 ile 1.0) kapalı çevrim P-kontrol.
        """
        pitch_cmd = self.current_angles.pitch_deg - (norm_error_y * gain_p)
        yaw_cmd = self.current_angles.yaw_deg + (norm_error_x * gain_p)
        roll_cmd = 0.0

        return self._apply_rate_limit(
            roll_cmd, pitch_cmd, yaw_cmd,
            GimbalMode.VISUAL_SERVO, timestamp
        )

    def _apply_rate_limit(
        self,
        roll: float,
        pitch: float,
        yaw: float,
        mode: GimbalMode,
        timestamp: float
    ) -> GimbalAngles:
        """Slew-rate ve mekanik sınır kısıtlamalarını uygular."""
        # Mekanik sınırlar
        clamped_roll = max(-self.roll_limit, min(self.roll_limit, roll))
        clamped_pitch = max(self.pitch_min, min(self.pitch_max, pitch))
        clamped_yaw = max(-180.0, min(180.0, yaw))

        if self.last_update_time is None:
            self.last_update_time = timestamp
            self.current_angles = GimbalAngles(
                roll_deg=round(clamped_roll, 2),
                pitch_deg=round(clamped_pitch, 2),
                yaw_deg=round(clamped_yaw, 2),
                mode=mode
            )
            return self.current_angles

        dt = max(1e-4, min(0.5, timestamp - self.last_update_time))
        self.last_update_time = timestamp

        max_delta = self.max_slew_rate * dt

        # Roll slew
        dr = clamped_roll - self.current_angles.roll_deg
        new_roll = self.current_angles.roll_deg + max(-max_delta, min(max_delta, dr))

        # Pitch slew
        dp = clamped_pitch - self.current_angles.pitch_deg
        new_pitch = self.current_angles.pitch_deg + max(-max_delta, min(max_delta, dp))

        # Yaw slew
        dy = clamped_yaw - self.current_angles.yaw_deg
        new_yaw = self.current_angles.yaw_deg + max(-max_delta, min(max_delta, dy))

        self.current_angles = GimbalAngles(
            roll_deg=round(new_roll, 2),
            pitch_deg=round(new_pitch, 2),
            yaw_deg=round(new_yaw, 2),
            mode=mode
        )
        return self.current_angles

    def generate_mavlink_mount_control(self) -> bytes:
        """
        MAVLink DO_MOUNT_CONTROL (#205) / MAV_CMD_DO_MOUNT_CONTROL komut yükü:
        param1: pitch (cdeg = deg * 100)
        param2: roll (cdeg)
        param3: yaw (cdeg)
        """
        pitch_cd = int(round(self.current_angles.pitch_deg * 100))
        roll_cd = int(round(self.current_angles.roll_deg * 100))
        yaw_cd = int(round(self.current_angles.yaw_deg * 100))
        # 3 int32 + mount_mode uint8
        return struct.pack("<iiiB", pitch_cd, roll_cd, yaw_cd, 2)  # Mode 2 = MAV_MOUNT_MODE_MAVLINK_TARGETING

    def reset(self):
        """Kontrolcüyü başlangıç nadir durumuna sıfırlar."""
        self.current_angles = GimbalAngles(roll_deg=0.0, pitch_deg=-90.0, yaw_deg=0.0)
        self.last_update_time = None
