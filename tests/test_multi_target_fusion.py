"""
TEKNOFEST 2026 - Çoklu Hedef Füzyon ve Kategori Decoy Filtresi Testleri
"""

from src.vision.detector import TargetDetection, TargetType, TargetShape, TargetColor
from src.vision.multi_target_fusion import MultiTargetFusionTracker, TrackStatus


def _make_det(t_type: TargetType, shape: TargetShape, cx: int, cy: int, conf: float = 0.9) -> TargetDetection:
    color = TargetColor.BLUE if t_type == TargetType.TARGET_A else TargetColor.RED
    return TargetDetection(
        target_type=t_type,
        shape=shape,
        color=color,
        center_px=(cx, cy),
        bbox=(cx - 25, cy - 25, 50, 50),
        area=2500.0,
        confidence=conf,
        normalized_offset=(0.0, 0.0),
    )


def test_rotary_wing_tracks_both_targets_and_rejects_square_decoy():
    tracker = MultiTargetFusionTracker(category="rotary_wing", confirm_hits=3, max_missed_frames=4)

    for step in range(3):
        dets = [
            _make_det(TargetType.TARGET_A, TargetShape.HEXAGON, 400 + step * 5, 300),
            _make_det(TargetType.TARGET_B, TargetShape.TRIANGLE, 900 + step * 4, 360),
            _make_det(TargetType.TARGET_A, TargetShape.SQUARE, 640, 200),  # Sabit kanat decoy!
        ]
        tracker.update(dets)

    assert tracker.rejected_decoys_count == 3
    confirmed = tracker.get_confirmed_tracks()
    assert len(confirmed) == 2
    types = {t.target_type for t in confirmed}
    assert types == {TargetType.TARGET_A, TargetType.TARGET_B}


def test_fixed_wing_rejects_hexagon_and_triangle_decoys():
    tracker = MultiTargetFusionTracker(category="fixed_wing", confirm_hits=2)

    for _ in range(2):
        tracker.update([
            _make_det(TargetType.TARGET_A, TargetShape.SQUARE, 500, 350),
            _make_det(TargetType.TARGET_A, TargetShape.HEXAGON, 200, 200),
            _make_det(TargetType.TARGET_B, TargetShape.TRIANGLE, 800, 400),
        ])

    assert tracker.rejected_decoys_count == 4
    confirmed = tracker.get_confirmed_tracks()
    assert len(confirmed) == 1
    assert confirmed[0].shape == TargetShape.SQUARE


def test_track_coasting_during_brief_occlusion_and_expiry():
    tracker = MultiTargetFusionTracker(category="rotary_wing", confirm_hits=2, max_missed_frames=3)
    for _ in range(2):
        tracker.update([_make_det(TargetType.TARGET_A, TargetShape.HEXAGON, 500, 300)])

    assert tracker.get_best_track(TargetType.TARGET_A).status == TrackStatus.CONFIRMED

    # 2 kare kapanma -> COASTING durumunda korunmalı
    tracker.update([])
    tracker.update([])
    trk = tracker.get_best_track(TargetType.TARGET_A)
    assert trk is not None
    assert trk.status == TrackStatus.COASTING

    # 2 kare daha yok -> max_missed_frames=3 aşılır, iz silinir
    tracker.update([])
    tracker.update([])
    assert tracker.get_best_track(TargetType.TARGET_A) is None
