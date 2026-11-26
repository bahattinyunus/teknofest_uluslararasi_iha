"""
Pinhole Camera Geo-Referencing Engine (Pixel <-> WGS84 Transformation)
======================================================================
TEKNOFEST Savaşan / Uluslararası İHA Seviye-1 / Seviye-2 uyumlu.

Geçmiş şampiyon takımların (ODTÜ Eflatun, Çelebi, Nairworks V3TOL) kod tabanlarından
elde edilen en kritik saha tecrübesi:
Hedef tespiti (bounding box / centroid) piksel uzayında yapıldıktan sonra,
yer hedefine yük bırakma veya GPS koordinatı raporlama aşamasında İHA'nın
roll/pitch/yaw açıları ve gimbal yönelimi hesaba katılmadığında onlarca metre
sapma oluşmaktadır.

Bu modül:
1. Pinhole Kamera İç Parametreleri (K matrisi / FoV / Çözünürlük)
2. Gimbal ve Gövde Yönelim Matrisi (R_NED_CAM)
3. Işın-Zemin Kesişimi (Ray-Ground Intersection via AGL / LiDAR)
4. WGS-84 Elipsoid dönüşümü ile (u, v) -> (lat, lon, alt)
5. Ters Dönüşüm (WGS-84 -> Piksel) ile HUD ve Sentetik Görüş Desteği
sağlar.
"""

import math
from typing import Tuple, Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class CameraIntrinsics:
    """Kamera iç parametreleri."""
    image_width: int = 1920
    image_height: int = 1080
    fx: float = 1440.0  # Piksel cinsinden odak uzaklığı (x ekseni)
    fy: float = 1440.0  # Piksel cinsinden odak uzaklığı (y ekseni)
    cx: float = 960.0   # Optik merkez x (genelde W/2)
    cy: float = 540.0   # Optik merkez y (genelde H/2)
    hfov_deg: Optional[float] = None  # Yatay görüş açısı (verilirse fx otomatik türetilir)
    vfov_deg: Optional[float] = None  # Dikey görüş açısı

    def __post_init__(self):
        if self.hfov_deg is not None and self.hfov_deg > 0:
            rad = math.radians(self.hfov_deg)
            self.fx = (self.image_width / 2.0) / math.tan(rad / 2.0)
        if self.vfov_deg is not None and self.vfov_deg > 0:
            rad = math.radians(self.vfov_deg)
            self.fy = (self.image_height / 2.0) / math.tan(rad / 2.0)
        elif self.hfov_deg is not None and self.vfov_deg is None:
            self.fy = self.fx  # Kare piksel varsayımı


@dataclass
class GimbalOrientation:
    """Gimbal oryantasyonu (İHA gövdesine göre veya doğrudan NED referanslı)."""
    pitch_deg: float = -90.0  # Nadir (tam aşağı) = -90, ufuk = 0
    roll_deg: float = 0.0     # Sağa yatış pozitif
    yaw_deg: float = 0.0      # Burun yönüne göre açı (veya mutlak kuzey)
    is_body_relative: bool = True  # True ise İHA oryantasyonuna eklenir


class PinholeGeoReferencer:
    """
    Kamera piksel koordinatları ile gerçek dünya WGS84 GPS koordinatları arasında
    3B rotasyon ve ışın izleme (Ray Casting) dönüşüm motoru.
    """

    # WGS-84 Sabitleri
    WGS84_A = 6378137.0         # Yarı büyük eksen (m)
    WGS84_B = 6356752.314245    # Yarı küçük eksen (m)
    WGS84_E2 = 0.00669437999014 # Birinci eksantriklik karesi

    def __init__(self, intrinsics: Optional[CameraIntrinsics] = None):
        self.intrinsics = intrinsics or CameraIntrinsics()

    @staticmethod
    def _euler_to_rotation_matrix(roll_rad: float, pitch_rad: float, yaw_rad: float) -> list:
        """
        Euler Z-Y-X (Yaw-Pitch-Roll) dönüşüm matrisini hesaplar: R_NED_to_Body.
        Döndürme sırası: Yaw (Z), sonra Pitch (Y), sonra Roll (X).
        """
        cr = math.cos(roll_rad)
        sr = math.sin(roll_rad)
        cp = math.cos(pitch_rad)
        sp = math.sin(pitch_rad)
        cy = math.cos(yaw_rad)
        sy = math.sin(yaw_rad)

        R = [
            [cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
            [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
            [-sp,     cp * sr,                cp * cr]
        ]
        return R

    @staticmethod
    def _mat_vec_mult(mat: list, vec: list) -> list:
        """3x3 matris ile 3x1 vektör çarpımı."""
        return [
            mat[0][0] * vec[0] + mat[0][1] * vec[1] + mat[0][2] * vec[2],
            mat[1][0] * vec[0] + mat[1][1] * vec[1] + mat[1][2] * vec[2],
            mat[2][0] * vec[0] + mat[2][1] * vec[1] + mat[2][2] * vec[2]
        ]

    @staticmethod
    def _mat_mult(A: list, B: list) -> list:
        """3x3 matris çarpımı C = A * B."""
        C = [[0.0]*3 for _ in range(3)]
        for i in range(3):
            for j in range(3):
                C[i][j] = A[i][0] * B[0][j] + A[i][1] * B[1][j] + A[i][2] * B[2][j]
        return C

    @staticmethod
    def _mat_transpose(A: list) -> list:
        """3x3 matris devriği."""
        return [
            [A[0][0], A[1][0], A[2][0]],
            [A[0][1], A[1][1], A[2][1]],
            [A[0][2], A[1][2], A[2][2]]
        ]

    def pixel_to_camera_ray(self, u: float, v: float) -> list:
        """
        Piksel koordinatından (u, v) Kamera Optik Çerçevesindeki birim ışın vektörünü hesaplar.
        Kamera Çerçevesi (OpenCV convention):
        +X: Sağ (Right)
        +Y: Aşağı (Down)
        +Z: Optik Eksen / İleri (Forward along lens axis)
        """
        x_c = (u - self.intrinsics.cx) / self.intrinsics.fx
        y_c = (v - self.intrinsics.cy) / self.intrinsics.fy
        z_c = 1.0

        mag = math.sqrt(x_c * x_c + y_c * y_c + z_c * z_c)
        return [x_c / mag, y_c / mag, z_c / mag]

    def camera_to_body_frame(self, ray_c: list, gimbal: Optional[GimbalOrientation] = None) -> list:
        """
        Kamera çerçevesindeki ışını İHA Gövde Çerçevesine (Body Frame: X-İleri, Y-Sağ, Z-Aşağı)
        veya gimbal montajına göre dönüştürür.
        Varsayılan montaj (Gimbal pitch=-90, roll=0, yaw=0):
        Kamera Z ekseni (optik eksen) İHA'nın Z eksenine (Aşağı),
        Kamera X ekseni İHA Y eksenine (Sağa),
        Kamera Y ekseni İHA -X eksenine (-İleri / Geriye) bakar.
        """
        if gimbal is None:
            gimbal = GimbalOrientation(pitch_deg=-90.0, roll_deg=0.0, yaw_deg=0.0)

        # Standart Nadir kamera için Kamera -> Gövde temel eşleşmesi:
        # Cam_X (sağ) -> Body_Y (sağ)
        # Cam_Y (aşağı) -> -Body_X (arka)
        # Cam_Z (ileri lens) -> Body_Z (aşağı)
        # Gimbal açılarının uygulanması:
        pitch_rad = math.radians(gimbal.pitch_deg + 90.0) # -90 iken 0 rad offset
        roll_rad = math.radians(gimbal.roll_deg)
        yaw_rad = math.radians(gimbal.yaw_deg)

        R_gimbal = self._euler_to_rotation_matrix(roll_rad, pitch_rad, yaw_rad)

        # Temel nadir dönüşüm:
        # [0, 1, 0]
        # [-1, 0, 0]
        # [0, 0, 1]
        base_body_ray = [-ray_c[1], ray_c[0], ray_c[2]]
        
        # Eğer pitch -90 (tam aşağı) değilse, gimbal rotasyonunu uygula:
        if abs(gimbal.pitch_deg - (-90.0)) > 1e-3 or abs(gimbal.roll_deg) > 1e-3 or abs(gimbal.yaw_deg) > 1e-3:
            # Optik eksenin yatayla yaptığı açı: pitch_deg (0=ufuk, -90=tam aşağı)
            # İleri bakan kamera: pitch=0 -> Cam_Z -> Body_X, Cam_X -> Body_Y, Cam_Y -> Body_Z
            p_rad = math.radians(-gimbal.pitch_deg) # pitch pozitif yukarı
            r_rad = math.radians(gimbal.roll_deg)
            y_rad = math.radians(gimbal.yaw_deg)
            # Genel kamera -> gövde matrisi
            # Ray in gimbal frame: [x_c, y_c, z_c]
            # When pitch=0: X_body = z_c, Y_body = x_c, Z_body = y_c
            # When pitch=-90: X_body = -y_c, Y_body = x_c, Z_body = z_c
            cos_p = math.cos(p_rad)
            sin_p = math.sin(p_rad)
            body_x = z_c_body = ray_c[2] * cos_p - ray_c[1] * sin_p
            body_z = ray_c[2] * sin_p + ray_c[1] * cos_p
            body_y = ray_c[0]
            return [body_x, body_y, body_z]

        return base_body_ray

    def pixel_to_gps(
        self,
        u: float,
        v: float,
        uav_lat: float,
        uav_lon: float,
        uav_alt_agl: float,
        uav_roll_deg: float = 0.0,
        uav_pitch_deg: float = 0.0,
        uav_yaw_deg: float = 0.0,
        gimbal: Optional[GimbalOrientation] = None
    ) -> Optional[Tuple[float, float, float]]:
        """
        Piksel koordinatını (u, v) İHA'nın konumu, yönelimi ve AGL (yerden yükseklik)
        bilgisini kullanarak WGS-84 yer koordinatına (lat, lon, ground_alt) dönüştürür.

        Döndürür:
            (target_lat, target_lon, target_alt) veya ışın ufuk üstüne bakıyorsa None.
        """
        if uav_alt_agl <= 0.1:
            return None

        # 1. Kamera çerçevesinde optik ışın
        ray_c = self.pixel_to_camera_ray(u, v)

        # 2. Gövde çerçevesine dönüştür
        ray_b = self.camera_to_body_frame(ray_c, gimbal)

        # 3. İHA oryantasyonu (Euler R_NED_to_Body matrisi devriği: Body -> NED)
        R_ned_b = self._euler_to_rotation_matrix(
            math.radians(uav_roll_deg),
            math.radians(uav_pitch_deg),
            math.radians(uav_yaw_deg)
        )
        # R_b_ned = R_ned_b, yani Body'den NED'e dönüştürürken bu matris vektörü çarpar
        ray_ned = self._mat_vec_mult(R_ned_b, ray_b)

        r_north, r_east, r_down = ray_ned

        # Işın aşağıya doğru (Down > 0) bakmalıdır, aksi halde yerle kesişmez (ufka veya gökyüzüne bakar)
        if r_down <= 1e-4:
            return None

        # 4. Yer düzlemiyle kesişim (Zemin mesafesi = AGL)
        # İHA'dan zemine doğru z_offset = uav_alt_agl
        scale = uav_alt_agl / r_down
        delta_north = r_north * scale
        delta_east = r_east * scale

        # 5. Metrik NED ötelemesini WGS-84 enlem/boylamına çevir
        target_lat, target_lon = self._meters_to_latlon(uav_lat, uav_lon, delta_north, delta_east)
        return (target_lat, target_lon, 0.0)

    def gps_to_pixel(
        self,
        target_lat: float,
        target_lon: float,
        target_alt_agl: float,
        uav_lat: float,
        uav_lon: float,
        uav_alt_agl: float,
        uav_roll_deg: float = 0.0,
        uav_pitch_deg: float = 0.0,
        uav_yaw_deg: float = 0.0,
        gimbal: Optional[GimbalOrientation] = None
    ) -> Optional[Tuple[float, float, bool]]:
        """
        Ters Dönüşüm (Ground -> Image Screen):
        Yer koordinatındaki bir hedefi kameranın ekran koordinatlarına (u, v) izdüşürür.
        HUD sentetik hedef kutusu veya AR (Artırılmış Gerçeklik) bindirmesi için kullanılır.

        Döndürür:
            (u, v, is_in_front_of_camera) veya hesaplanamazsa None.
        """
        # 1. WGS84 farkından metrik NED vektörü
        delta_north, delta_east = self._latlon_to_meters(uav_lat, uav_lon, target_lat, target_lon)
        delta_down = uav_alt_agl - target_alt_agl  # Hedef zeminde ise delta_down = uav_alt_agl

        pos_ned = [delta_north, delta_east, delta_down]

        # 2. NED -> Body (R_ned_b'nin tersi/devriği)
        R_ned_b = self._euler_to_rotation_matrix(
            math.radians(uav_roll_deg),
            math.radians(uav_pitch_deg),
            math.radians(uav_yaw_deg)
        )
        R_b_ned = self._mat_transpose(R_ned_b)
        pos_b = self._mat_vec_mult(R_b_ned, pos_ned)

        # 3. Body -> Camera Frame
        # Varsayılan nadir kamera montajı tersi:
        # Cam_X = Body_Y
        # Cam_Y = -Body_X (gimbal pitch=-90 iken)
        # Cam_Z = Body_Z
        if gimbal is None or abs(gimbal.pitch_deg - (-90.0)) < 1e-3:
            pos_c = [pos_b[1], -pos_b[0], pos_b[2]]
        else:
            p_rad = math.radians(-gimbal.pitch_deg)
            cos_p = math.cos(p_rad)
            sin_p = math.sin(p_rad)
            # Ters rotasyon:
            cam_x = pos_b[1]
            cam_z = pos_b[0] * cos_p + pos_b[2] * sin_p
            cam_y = -pos_b[0] * sin_p + pos_b[2] * cos_p
            pos_c = [cam_x, cam_y, cam_z]

        # Hedef kameranın önünde mi (Z_c > 0)?
        if pos_c[2] <= 0.1:
            return None

        # 4. Perspektif İzdüşüm (Kamera İç Parametreleri)
        u = self.intrinsics.fx * (pos_c[0] / pos_c[2]) + self.intrinsics.cx
        v = self.intrinsics.fy * (pos_c[1] / pos_c[2]) + self.intrinsics.cy

        is_visible = (0 <= u < self.intrinsics.image_width) and (0 <= v < self.intrinsics.image_height)
        return (round(u, 2), round(v, 2), is_visible)

    @classmethod
    def _meters_to_latlon(cls, ref_lat: float, ref_lon: float, dn: float, de: float) -> Tuple[float, float]:
        """
        Metrik North-East yer değiştirme miktarını WGS-84 enlem/boylamına ekler.
        Meridyen ve paralel eğrilik yarıçapı kullanır (Hassas jeodezik formül).
        """
        lat_rad = math.radians(ref_lat)
        sin_lat = math.sin(lat_rad)
        cos_lat = math.cos(lat_rad)

        # Meridyen eğrilik yarıçapı (Kuzey-Güney ekseni)
        denom = math.sqrt(1.0 - cls.WGS84_E2 * sin_lat * sin_lat)
        rm = cls.WGS84_A * (1.0 - cls.WGS84_E2) / (denom * denom * denom)

        # Baş dikey eğrilik yarıçapı (Doğu-Batı ekseni)
        rn = cls.WGS84_A / denom

        d_lat = dn / rm
        d_lon = de / (rn * cos_lat) if abs(cos_lat) > 1e-6 else 0.0

        target_lat = ref_lat + math.degrees(d_lat)
        target_lon = ref_lon + math.degrees(d_lon)
        return (target_lat, target_lon)

    @classmethod
    def _latlon_to_meters(cls, ref_lat: float, ref_lon: float, target_lat: float, target_lon: float) -> Tuple[float, float]:
        """
        İki WGS-84 koordinatı arasındaki metrik [North, East] farkını hesaplar.
        """
        lat_rad = math.radians(ref_lat)
        sin_lat = math.sin(lat_rad)
        cos_lat = math.cos(lat_rad)

        denom = math.sqrt(1.0 - cls.WGS84_E2 * sin_lat * sin_lat)
        rm = cls.WGS84_A * (1.0 - cls.WGS84_E2) / (denom * denom * denom)
        rn = cls.WGS84_A / denom

        d_lat = math.radians(target_lat - ref_lat)
        d_lon = math.radians(target_lon - ref_lon)

        dn = d_lat * rm
        de = d_lon * (rn * cos_lat) if abs(cos_lat) > 1e-6 else 0.0
        return (dn, de)
