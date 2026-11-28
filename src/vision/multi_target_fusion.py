"""
TEKNOFEST 2026 Uluslararası İHA - Çoklu Hedef Füzyon ve Kalıcı İz Takipçisi
===========================================================================
30m x 100m tarama alanında hem Hedef A (Mavi Altıgen / 4x4m Mavi Kare) hem de
Hedef B (Kırmızı Üçgen / 2x2m Kırmızı Kare) aynı karede veya ardışık karelerde
görünebilir. Ayrıca şartname uyarınca diğer kategorinin hedefleri (decoy)
kesinlikle filtrelenmelidir:
  - Döner Kanat: Sabit kanat kare hedefleri YOK SAYILIR.
  - Sabit Kanat: Döner kanat altıgen ve üçgen hedefleri YOK SAYILIR.

Bu modül:
  - En yakın komşu veri ilişkilendirmesi (data association) ile her hedefe benzersiz
    iz numarası (track_id) atar.
  - Alfa-beta (konum + hız) filtresi ile görüntü düzleminde titreşimi sönümler ve
    kısa süreli kapanmalarda (occlusion) izi korur (coasting).
  - N-kare onay histerezisi (`confirm_hits`) ile yanlış pozitif (false positive)
    tespitleri eler.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

from src.vision.detector import TargetDetection, TargetShape, TargetType


class TrackStatus(Enum):
    TENTATIVE = "TENTATIVE"
    CONFIRMED = "CONFIRMED"
    COASTING = "COASTING"


@dataclass
class FusedTargetTrack:
    """Kalıcı çoklu hedef izi."""
    track_id: int
    target_type: TargetType
    shape: TargetShape
    center_x: float
    center_y: float
    vx_px_per_frame: float
    vy_px_per_frame: float
    normalized_offset: Tuple[float, float]
    confidence: float
    hits: int
    missed_frames: int
    status: TrackStatus
    last_detection: TargetDetection


class MultiTargetFusionTracker:
    """
    Kategori Kısıtlı Decoy Filtreli Çoklu Hedef Takip ve Füzyon Yöneticisi.
    """

    ROTARY_ALLOWED_SHAPES = {TargetShape.HEXAGON, TargetShape.TRIANGLE}
    FIXED_ALLOWED_SHAPES = {TargetShape.SQUARE}

    def __init__(
        self,
        category: str = "rotary_wing",
        max_association_dist_px: float = 140.0,
        confirm_hits: int = 3,
        max_missed_frames: int = 8,
        alpha: float = 0.65,
        beta: float = 0.20,
    ):
        self.category = category.lower()
        self.max_association_dist_px = float(max_association_dist_px)
        self.confirm_hits = max(1, int(confirm_hits))
        self.max_missed_frames = max(1, int(max_missed_frames))
        self.alpha = max(0.05, min(1.0, float(alpha)))
        self.beta = max(0.0, min(1.0, float(beta)))

        self._next_track_id: int = 1
        self._tracks: Dict[int, FusedTargetTrack] = {}
        self.rejected_decoys_count: int = 0

    def reset(self) -> None:
        self._tracks.clear()
        self._next_track_id = 1
        self.rejected_decoys_count = 0

    def is_valid_for_category(self, det: TargetDetection) -> bool:
        """Şartname Madde 8.3.2 uyarınca diğer kategorinin hedeflerini (decoy) eler."""
        if det.target_type == TargetType.UNKNOWN:
            return False
        if self.category == "rotary_wing":
            return det.shape in self.ROTARY_ALLOWED_SHAPES
        if self.category == "fixed_wing":
            return det.shape in self.FIXED_ALLOWED_SHAPES
        return True

    def update(self, detections: List[TargetDetection]) -> List[FusedTargetTrack]:
        """
        Gelen tespitleri mevcut izlerle eşleştirir, decoy hedefleri reddeder,
        onaylanmış iz listesini yüksek güvene göre sıralı döndürür.
        """
        # 1. Mevcut izleri sabit hız modeliyle bir adım ileri tahmin et
        for trk in self._tracks.values():
            trk.center_x += trk.vx_px_per_frame
            trk.center_y += trk.vy_px_per_frame
            trk.missed_frames += 1

        # 2. Kategori decoy filtresi
        valid_dets: List[TargetDetection] = []
        for det in detections:
            if self.is_valid_for_category(det):
                valid_dets.append(det)
            else:
                self.rejected_decoys_count += 1

        # 3. Açgözlü en yakın komşu (same target_type) eşleştirme
        matched_track_ids: set[int] = set()
        matched_det_indices: set[int] = set()

        candidate_pairs: List[Tuple[float, int, int]] = []
        for det_idx, det in enumerate(valid_dets):
            dx_px, dy_px = det.center_px
            for tid, trk in self._tracks.items():
                if trk.target_type != det.target_type:
                    continue
                dist = math.hypot(dx_px - trk.center_x, dy_px - trk.center_y)
                if dist <= self.max_association_dist_px:
                    candidate_pairs.append((dist, tid, det_idx))

        candidate_pairs.sort(key=lambda item: item[0])

        for _, tid, det_idx in candidate_pairs:
            if tid in matched_track_ids or det_idx in matched_det_indices:
                continue
            matched_track_ids.add(tid)
            matched_det_indices.add(det_idx)

            trk = self._tracks[tid]
            det = valid_dets[det_idx]
            meas_x, meas_y = float(det.center_px[0]), float(det.center_px[1])

            res_x = meas_x - trk.center_x
            res_y = meas_y - trk.center_y

            trk.center_x += self.alpha * res_x
            trk.center_y += self.alpha * res_y
            trk.vx_px_per_frame += self.beta * res_x
            trk.vy_px_per_frame += self.beta * res_y
            trk.normalized_offset = det.normalized_offset
            trk.confidence = 0.6 * trk.confidence + 0.4 * det.confidence
            trk.hits += 1
            trk.missed_frames = 0
            trk.last_detection = det
            trk.status = TrackStatus.CONFIRMED if trk.hits >= self.confirm_hits else TrackStatus.TENTATIVE

        # 4. Eşleşmeyen geçerli tespitler için yeni iz oluştur
        for det_idx, det in enumerate(valid_dets):
            if det_idx in matched_det_indices:
                continue
            tid = self._next_track_id
            self._next_track_id += 1
            status = TrackStatus.CONFIRMED if self.confirm_hits <= 1 else TrackStatus.TENTATIVE
            self._tracks[tid] = FusedTargetTrack(
                track_id=tid,
                target_type=det.target_type,
                shape=det.shape,
                center_x=float(det.center_px[0]),
                center_y=float(det.center_px[1]),
                vx_px_per_frame=0.0,
                vy_px_per_frame=0.0,
                normalized_offset=det.normalized_offset,
                confidence=det.confidence,
                hits=1,
                missed_frames=0,
                status=status,
                last_detection=det,
            )

        # 5. Kayıp izleri coasting durumuna geçir veya sil
        to_delete: List[int] = []
        for tid, trk in self._tracks.items():
            if trk.missed_frames > self.max_missed_frames:
                to_delete.append(tid)
            elif trk.missed_frames > 0 and trk.status == TrackStatus.CONFIRMED:
                trk.status = TrackStatus.COASTING

        for tid in to_delete:
            del self._tracks[tid]

        return sorted(self._tracks.values(), key=lambda t: (t.status != TrackStatus.CONFIRMED, -t.confidence))

    def get_confirmed_tracks(self, target_type: Optional[TargetType] = None) -> List[FusedTargetTrack]:
        """Onaylanmış (veya kısa süreli coasting) izleri döndürür."""
        out = [
            t for t in self._tracks.values()
            if t.status in (TrackStatus.CONFIRMED, TrackStatus.COASTING)
            and (target_type is None or t.target_type == target_type)
        ]
        return sorted(out, key=lambda t: -t.confidence)

    def get_best_track(self, target_type: TargetType) -> Optional[FusedTargetTrack]:
        tracks = self.get_confirmed_tracks(target_type=target_type)
        return tracks[0] if tracks else None
