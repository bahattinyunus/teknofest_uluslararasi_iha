"""
TEKNOFEST 2026 Uluslararası İHA - Çokgen No-Fly Zone (NFZ) & Geofence Sakınma Motoru
----------------------------------------------------------------------------------
Yarışma sahasındaki hakem çadırları, seyirci alanları, anten direkleri gibi
uçuşa yasak bölgeleri (No-Fly Zones - NFZ) çokgen olarak tanımlar.
İHA sınırlara yaklaştığında Işın Gönderme (Ray Casting) ve İtici Vektör Alanı
(Repulsive Potential Field) algoritmalarıyla otonom sakınma hız komutları üretir.
"""

from dataclasses import dataclass
from typing import List, Tuple, Dict, Any, Optional
import math
import numpy as np


@dataclass
class GeofenceStatus:
    is_inside_flight_boundary: bool  # Dış uçuş sınırları içinde mi?
    is_inside_nfz: bool              # Herhangi bir NFZ içine girdi mi? (İHLAL)
    distance_to_nearest_nfz_m: float # En yakın yasak bölgeye mesafe
    distance_to_boundary_m: float    # Dış sınıra kalan mesafe
    altitude_agl_m: float
    is_altitude_violation: bool      # 120m AGL tavanı aşıldı mı?
    avoidance_velocity_ned: Tuple[float, float, float] # (vx, vy, vz) itici hız
    requires_avoidance: bool         # Sakınma manevrası gerekiyor mu?


class GeofenceManager:
    def __init__(
        self,
        outer_radius_m: float = 500.0,
        max_altitude_m: float = 120.0,
        min_altitude_m: float = 2.0,
        buffer_distance_m: float = 15.0,
        max_avoidance_speed_mps: float = 3.5
    ):
        self.outer_radius = outer_radius_m
        self.max_alt = max_altitude_m
        self.min_alt = min_altitude_m
        self.buffer_dist = buffer_distance_m
        self.max_avoid_spd = max_avoidance_speed_mps

        # Çokgen No-Fly Zone (NFZ) listesi: List of polygon vertices [(x1,y1), (x2,y2), ...]
        self.no_fly_zones: List[List[Tuple[float, float]]] = []

        # Varsayılan TEKNOFEST yarışma hakem & seyirci NFZ bölgesi ekle (örnek: merkezden 80m güneyde 30x30m alan)
        self.add_no_fly_zone([
            (70.0, -90.0),
            (110.0, -90.0),
            (110.0, -60.0),
            (70.0, -60.0)
        ])

    def add_no_fly_zone(self, polygon_vertices: List[Tuple[float, float]]):
        """Yeni bir çokgen uçuşa yasak bölge (NFZ) ekler."""
        if len(polygon_vertices) >= 3:
            self.no_fly_zones.append(polygon_vertices)

    @staticmethod
    def is_point_in_polygon(point: Tuple[float, float], polygon: List[Tuple[float, float]]) -> bool:
        """Işın Gönderme (Ray Casting) algoritması ile noktanın çokgen içinde olup olmadığını saptar."""
        x, y = point
        inside = False
        n = len(polygon)
        p1x, p1y = polygon[0]
        for i in range(n + 1):
            p2x, p2y = polygon[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
        return inside

    @staticmethod
    def distance_point_to_segment(p: Tuple[float, float], a: Tuple[float, float], b: Tuple[float, float]) -> Tuple[float, Tuple[float, float]]:
        """Noktadan doğru parçasına olan en kısa mesafeyi ve en yakın noktayı hesaplar."""
        px, py = p
        ax, ay = a
        bx, by = b
        dx = bx - ax
        dy = by - ay
        if dx == 0 and dy == 0:
            return math.hypot(px - ax, py - ay), a

        t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
        nearest_x = ax + t * dx
        nearest_y = ay + t * dy
        dist = math.hypot(px - nearest_x, py - nearest_y)
        return dist, (nearest_x, nearest_y)

    def evaluate_geofence(
        self,
        uav_pos_xy: Tuple[float, float],
        altitude_agl_m: float
    ) -> GeofenceStatus:
        """
        İHA'nın anlık konumunu tüm geofence sınırlarına ve NFZ bölgelerine göre denetler.
        İtici sakınma hız vektörü üretir.
        """
        x, y = uav_pos_xy
        dist_from_origin = math.hypot(x, y)
        dist_to_boundary = max(0.0, self.outer_radius - dist_from_origin)
        is_inside_boundary = dist_from_origin <= self.outer_radius

        is_alt_violation = altitude_agl_m > self.max_alt or altitude_agl_m < self.min_alt

        is_inside_any_nfz = False
        min_nfz_dist = 9999.0
        repulsive_x = 0.0
        repulsive_y = 0.0

        for nfz in self.no_fly_zones:
            in_nfz = self.is_point_in_polygon((x, y), nfz)
            if in_nfz:
                is_inside_any_nfz = True

            # Her doğru parçasına mesafeyi hesapla
            for i in range(len(nfz)):
                p1 = nfz[i]
                p2 = nfz[(i + 1) % len(nfz)]
                d, nearest = self.distance_point_to_segment((x, y), p1, p2)
                if d < min_nfz_dist:
                    min_nfz_dist = d
                    # İtici yön (En yakın noktadan İHA'ya doğru)
                    diff_x = x - nearest[0]
                    diff_y = y - nearest[1]
                    norm = math.hypot(diff_x, diff_y)
                    if norm > 0.001:
                        # Potansiyel alan itme kuvveti: F = (1/d - 1/d_buffer)
                        if in_nfz:
                            repulsive_x = (diff_x / norm) * self.max_avoid_spd
                            repulsive_y = (diff_y / norm) * self.max_avoid_spd
                        elif d < self.buffer_dist:
                            force_mag = self.max_avoid_spd * ((self.buffer_dist - d) / self.buffer_dist)
                            repulsive_x += (diff_x / norm) * force_mag
                            repulsive_y += (diff_y / norm) * force_mag

        # Dış sınır sakınması: Sınıra çok yaklaşıldıysa merkeze doğru itme
        if dist_to_boundary < self.buffer_dist and dist_from_origin > 0.1:
            boundary_force = self.max_avoid_spd * ((self.buffer_dist - dist_to_boundary) / self.buffer_dist)
            repulsive_x -= (x / dist_from_origin) * boundary_force
            repulsive_y -= (y / dist_from_origin) * boundary_force

        # İrtifa tavanı sakınması: 120m'ye yaklaşırsa aşağı yönlü hız (vz > 0 in NED)
        repulsive_z = 0.0
        approaching_alt_limit = False
        if altitude_agl_m > (self.max_alt - 5.0):
            repulsive_z = 1.8  # NED sisteminde +Z aşağı yöndür (alçalma)
            approaching_alt_limit = True
        elif altitude_agl_m < (self.min_alt + 1.0):
            repulsive_z = -1.2 # Yükselme
            approaching_alt_limit = True

        # Hız vektörünü sınırla
        h_norm = math.hypot(repulsive_x, repulsive_y)
        if h_norm > self.max_avoid_spd:
            repulsive_x = (repulsive_x / h_norm) * self.max_avoid_spd
            repulsive_y = (repulsive_y / h_norm) * self.max_avoid_spd

        requires_avoidance = (
            is_inside_any_nfz or
            min_nfz_dist < self.buffer_dist or
            dist_to_boundary < self.buffer_dist or
            is_alt_violation or
            approaching_alt_limit
        )

        return GeofenceStatus(
            is_inside_flight_boundary=is_inside_boundary,
            is_inside_nfz=is_inside_any_nfz,
            distance_to_nearest_nfz_m=round(min_nfz_dist, 2),
            distance_to_boundary_m=round(dist_to_boundary, 2),
            altitude_agl_m=round(altitude_agl_m, 2),
            is_altitude_violation=is_alt_violation,
            avoidance_velocity_ned=(round(repulsive_x, 2), round(repulsive_y, 2), round(repulsive_z, 2)),
            requires_avoidance=requires_avoidance
        )
