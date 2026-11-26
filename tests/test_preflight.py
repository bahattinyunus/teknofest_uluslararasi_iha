"""
Unit tests for TEKNOFEST 2026 UAV V7 Preflight Diagnostics & Checklist Subsystem
=================================================================================
Verifies compliance with TÜBİTAK TEKNOFEST 2026 V7 rules:
- 8-minute setup time limit and extra intervention penalties
- 8-minute flight prep time limit and crew rules (max 3 UAV crew + 1 GCS, no advisors)
- SHGM UAV registration, QR code, and pilot licensing
- Emergency power cut switch (<= 2s integrated switch)
- Baret (helmet) and safety gear requirements
- Transport box shape and 1-person portability rules (Sabit: silindirik, Döner: prizma)
- MTOW 4.0 kg limit and 25 km/h wind threshold
"""
import pytest
from src.avionics.preflight import (
    PreflightChecker,
    PreflightReport,
    CheckItem,
    TransportBoxSpec,
    SHGMRegistration,
    PowerCutSwitch,
    TimingConstraints,
    SafetyEquipment
)


def test_preflight_checker_standalone():
    checker = PreflightChecker(core_instance=None)
    report = checker.run_all_checks()

    assert report.total_count == 17
    assert report.passed_count == 17
    assert report.critical_failures == 0
    assert report.overall_status == "GO_FOR_TAKEOFF"
    assert report.duration_s < 2.0


def test_preflight_checker_items_content():
    checker = PreflightChecker(core_instance=None)
    report = checker.run_all_checks()

    item_names = [item.name for item in report.items]
    expected_items = [
        "MAVLINK_HEARTBEAT",
        "GPS_NAVIGATION",
        "BATTERY_POWER",
        "MTOW_WEIGHT_LIMIT",
        "120M_GEOFENCE_CEILING",
        "WEATHER_WIND_LIMIT",
        "SETUP_TIME_LIMIT",
        "PREP_TIME_LIMIT",
        "SHGM_REGISTRATION",
        "EMERGENCY_POWER_CUT_SWITCH",
        "SAFETY_BARET_REQUIREMENT",
        "TRANSPORT_BOX_SPEC",
        "CAMERA_STREAM_FPS",
        "VISION_DETECTION_ENGINE",
        "PAYLOAD_ACTUATORS",
        "STORAGE_TELEMETRY_LOG",
        "GUIDANCE_BALLISTICS_EKF"
    ]
    for exp in expected_items:
        assert exp in item_names, f"Expected {exp} in preflight checklist"


def test_setup_time_limits_and_penalties():
    checker = PreflightChecker(core_instance=None)

    # 1. Within 8 minutes (e.g. 300s) -> Pass
    checker.set_setup_timing(setup_time_s=300.0, extra_interventions=0, penalty_s=0.0)
    report = checker.run_all_checks()
    setup_item = next(it for it in report.items if it.name == "SETUP_TIME_LIMIT")
    assert setup_item.passed is True
    assert report.overall_status == "GO_FOR_TAKEOFF"

    # 2. Exceeding 8 minutes (e.g. 485s) -> Fail (NO_GO_ABORT)
    checker.set_setup_timing(setup_time_s=485.0, extra_interventions=0, penalty_s=0.0)
    report = checker.run_all_checks()
    setup_item = next(it for it in report.items if it.name == "SETUP_TIME_LIMIT")
    assert setup_item.passed is False
    assert report.overall_status == "NO_GO_ABORT"

    # 3. Base time under 480s, but extra interventions push it over 480s -> Fail
    checker.set_setup_timing(setup_time_s=450.0, extra_interventions=2, penalty_s=40.0)
    report = checker.run_all_checks()
    setup_item = next(it for it in report.items if it.name == "SETUP_TIME_LIMIT")
    assert setup_item.passed is False
    assert report.overall_status == "NO_GO_ABORT"


def test_prep_time_limits_and_crew_rules():
    checker = PreflightChecker(core_instance=None)

    # 1. Normal prep time (240s) with 3 members, no advisor -> Pass
    checker.set_prep_timing(prep_time_s=240.0, team_count=3, gcs_count=1, advisor_active=False)
    report = checker.run_all_checks()
    prep_item = next(it for it in report.items if it.name == "PREP_TIME_LIMIT")
    assert prep_item.passed is True

    # 2. Prep time exceeding 8 min (500s) -> Fail
    checker.set_prep_timing(prep_time_s=500.0, team_count=3, gcs_count=1, advisor_active=False)
    report = checker.run_all_checks()
    prep_item = next(it for it in report.items if it.name == "PREP_TIME_LIMIT")
    assert prep_item.passed is False
    assert report.overall_status == "NO_GO_ABORT"

    # 3. Too many members on flight line (e.g. 4 > 3) -> Fail
    checker.set_prep_timing(prep_time_s=200.0, team_count=4, gcs_count=1, advisor_active=False)
    report = checker.run_all_checks()
    prep_item = next(it for it in report.items if it.name == "PREP_TIME_LIMIT")
    assert prep_item.passed is False

    # 4. Advisor interference -> Fail
    checker.set_prep_timing(prep_time_s=200.0, team_count=3, gcs_count=1, advisor_active=True)
    report = checker.run_all_checks()
    prep_item = next(it for it in report.items if it.name == "PREP_TIME_LIMIT")
    assert prep_item.passed is False


def test_shgm_registration_checks():
    checker = PreflightChecker(core_instance=None)

    # 1. Fully registered -> Pass
    checker.set_shgm_registration(
        registered=True,
        qr_code="TR-UAV-2026-TULGA-042",
        plate="IHA0-TR-MALATYA-2026-042",
        pilot_license="SHGM-PILOT-IHA1-TR-98214",
        verified=True
    )
    report = checker.run_all_checks()
    shgm_item = next(it for it in report.items if it.name == "SHGM_REGISTRATION")
    assert shgm_item.passed is True

    # 2. Missing registration -> Fail
    checker.set_shgm_registration(registered=False)
    report = checker.run_all_checks()
    shgm_item = next(it for it in report.items if it.name == "SHGM_REGISTRATION")
    assert shgm_item.passed is False
    assert report.overall_status == "NO_GO_ABORT"

    # 3. Missing QR code -> Fail
    checker.set_shgm_registration(registered=True, qr_code="", plate="IHA0-TR-MALATYA", pilot_license="LIC-123")
    report = checker.run_all_checks()
    shgm_item = next(it for it in report.items if it.name == "SHGM_REGISTRATION")
    assert shgm_item.passed is False


def test_power_cut_switch_2s_rule():
    checker = PreflightChecker(core_instance=None)

    # 1. 0.8s integrated switch -> Pass
    checker.set_power_cut_switch(cut_time_s=0.8, integrated=True, accessible=True, verified=True)
    report = checker.run_all_checks()
    switch_item = next(it for it in report.items if it.name == "EMERGENCY_POWER_CUT_SWITCH")
    assert switch_item.passed is True

    # 2. Cut time > 2.0s (e.g. 2.4s) -> Fail
    checker.set_power_cut_switch(cut_time_s=2.4, integrated=True, accessible=True, verified=True)
    report = checker.run_all_checks()
    switch_item = next(it for it in report.items if it.name == "EMERGENCY_POWER_CUT_SWITCH")
    assert switch_item.passed is False
    assert report.overall_status == "NO_GO_ABORT"

    # 3. External breaker pull (integrated=False) -> Fail
    checker.set_power_cut_switch(cut_time_s=1.0, integrated=False, accessible=True, verified=True)
    report = checker.run_all_checks()
    switch_item = next(it for it in report.items if it.name == "EMERGENCY_POWER_CUT_SWITCH")
    assert switch_item.passed is False


def test_baret_and_ppe_requirement():
    checker = PreflightChecker(core_instance=None)

    # 1. Helmets worn -> Pass
    checker.set_safety_equipment(baret_worn=True)
    report = checker.run_all_checks()
    baret_item = next(it for it in report.items if it.name == "SAFETY_BARET_REQUIREMENT")
    assert baret_item.passed is True

    # 2. Helmets NOT worn -> Fail (NO_GO_ABORT)
    checker.set_safety_equipment(baret_worn=False)
    report = checker.run_all_checks()
    baret_item = next(it for it in report.items if it.name == "SAFETY_BARET_REQUIREMENT")
    assert baret_item.passed is False
    assert report.overall_status == "NO_GO_ABORT"


def test_transport_box_specs():
    # 1. Rotary Wing requires rectangular or square prism
    checker_rw = PreflightChecker(core_instance=None, category="rotary_wing")
    report_rw = checker_rw.run_all_checks()
    box_item = next(it for it in report_rw.items if it.name == "TRANSPORT_BOX_SPEC")
    assert box_item.passed is True

    # Rotary Wing with cylindrical box -> Fail
    checker_rw.set_transport_box(box_type="cylindrical")
    report_rw2 = checker_rw.run_all_checks()
    box_item2 = next(it for it in report_rw2.items if it.name == "TRANSPORT_BOX_SPEC")
    assert box_item2.passed is False

    # 2. Fixed Wing requires cylindrical box
    checker_fw = PreflightChecker(core_instance=None, category="fixed_wing")
    report_fw = checker_fw.run_all_checks()
    box_item_fw = next(it for it in report_fw.items if it.name == "TRANSPORT_BOX_SPEC")
    assert box_item_fw.passed is True

    # Fixed Wing with rectangular prism -> Fail
    checker_fw.set_transport_box(box_type="rectangular_prism")
    report_fw2 = checker_fw.run_all_checks()
    box_item_fw2 = next(it for it in report_fw2.items if it.name == "TRANSPORT_BOX_SPEC")
    assert box_item_fw2.passed is False

    # 3. Not single-person portable -> Fail
    checker_rw.set_transport_box(box_type="rectangular_prism", single_person_portable=False)
    report_rw3 = checker_rw.run_all_checks()
    box_item3 = next(it for it in report_rw3.items if it.name == "TRANSPORT_BOX_SPEC")
    assert box_item3.passed is False


def test_mtow_weight_limit():
    checker = PreflightChecker(core_instance=None)

    # 1. 3.85 kg <= 4.0 kg -> Pass
    checker.set_takeoff_weight(3.85)
    report = checker.run_all_checks()
    weight_item = next(it for it in report.items if it.name == "MTOW_WEIGHT_LIMIT")
    assert weight_item.passed is True

    # 2. 4.2 kg > 4.0 kg -> Fail
    checker.set_takeoff_weight(4.2)
    report = checker.run_all_checks()
    weight_item = next(it for it in report.items if it.name == "MTOW_WEIGHT_LIMIT")
    assert weight_item.passed is False
    assert report.overall_status == "NO_GO_ABORT"
