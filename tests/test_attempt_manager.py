"""
TEKNOFEST 2026 - 4 Uçuş Hakkı, Kronometre & Saha Ekibi Yöneticisi Testleri
"""

import pytest
from src.telemetry.attempt_manager import (
    CompetitionAttemptManager,
    FieldCrewRoster,
    AttemptStatus,
)


def test_task2_blocked_until_task1_qualified():
    mgr = CompetitionAttemptManager()
    with pytest.raises(PermissionError):
        mgr.record_attempt(2, setup_duration_s=180.0, prep_duration_s=100.0, flight_duration_s=150.0, raw_score=70.0)


def test_best_of_four_scoring_and_time_limit_enforcement():
    mgr = CompetitionAttemptManager(video_score=9.5)
    # 1. hak: Görev 1 başarılı
    r1 = mgr.record_attempt(1, setup_duration_s=200.0, prep_duration_s=120.0, flight_duration_s=95.0, raw_score=26.5)
    assert r1.status == AttemptStatus.SUCCESS

    # 2. hak: Görev 2 güvenli yük ile başarılı
    r2 = mgr.record_attempt(2, setup_duration_s=190.0, prep_duration_s=110.0, flight_duration_s=170.0, raw_score=64.0)
    assert r2.status == AttemptStatus.SUCCESS

    # 3. hak: Görev 2 süre aşımı (>600s) -> geçersiz (0 puan)
    r3 = mgr.record_attempt(2, setup_duration_s=190.0, prep_duration_s=110.0, flight_duration_s=615.0, raw_score=75.0)
    assert r3.status == AttemptStatus.FAILED_TIME_LIMIT
    assert r3.valid_score == 0.0

    # 4. hak: Görev 2 agresif yük ile daha yüksek skor
    r4 = mgr.record_attempt(2, setup_duration_s=180.0, prep_duration_s=100.0, flight_duration_s=160.0, raw_score=74.5)
    assert r4.status == AttemptStatus.SUCCESS

    # 5. hak yasak
    with pytest.raises(ValueError):
        mgr.record_attempt(2, setup_duration_s=150.0, prep_duration_s=90.0, flight_duration_s=140.0, raw_score=79.0)

    sm = mgr.get_summary()
    assert sm.attempts_used == 4
    assert sm.attempts_remaining == 0
    assert sm.best_task1_score == 26.5
    assert sm.best_task2_score == 74.5
    assert sm.combined_total_score == pytest.approx(9.5 + 26.5 + 74.5)


def test_extra_intervention_breaks_setup_limit():
    mgr = CompetitionAttemptManager()
    # 440s + (25+10) + (15+10) = 500s > 480s -> FAILED_SETUP_LIMIT
    rec = mgr.record_attempt(
        1,
        setup_duration_s=440.0,
        prep_duration_s=100.0,
        flight_duration_s=90.0,
        raw_score=28.0,
        extra_interventions_s=[25.0, 15.0],
    )
    assert rec.status == AttemptStatus.FAILED_SETUP_LIMIT
    assert rec.valid_score == 0.0


def test_field_crew_quota_and_advisor_ban():
    mgr = CompetitionAttemptManager()
    bad_roster = FieldCrewRoster(
        member_names=["A", "B", "C", "D", "E"],
        advisor_on_field=True,
        all_helmets_worn=False,
    )
    violations = mgr.set_crew_roster(bad_roster)
    assert len(violations) >= 3
    assert mgr.get_summary().crew_compliant is False
