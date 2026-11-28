"""
Unit tests for TelemetryLinkSecurity (TEKNOFEST 2026 Madde 9.3.2 & 9.4)
"""
import pytest
from src.telemetry.link_security import TelemetryLinkSecurity, LinkHealthState


def test_encrypt_decrypt_roundtrip():
    key = b"TEKNOFEST-2026-MALATYA-TULGA-KEY!"
    tx = TelemetryLinkSecurity(master_key=key)
    rx = TelemetryLinkSecurity(master_key=key)

    payload = {"state": "LOCKING_TARGET_A", "alt_m": 25.4, "lat": 38.34694, "lon": 38.24444}
    frame = tx.encrypt_packet(payload)

    ok, decoded, reason = rx.decrypt_packet(frame)
    assert ok is True
    assert reason == "OK"
    assert decoded == payload
    assert tx.packets_sent == 1
    assert rx.packets_verified == 1


def test_tampered_ciphertext_rejected_by_mac():
    key = b"SECRET-KEY-32-BYTES-MINIMUM-TEST"
    tx = TelemetryLinkSecurity(master_key=key)
    rx = TelemetryLinkSecurity(master_key=key)

    frame = bytearray(tx.encrypt_packet({"cmd": "DROP_PAYLOAD", "slot": 1}))
    # Flip a bit in the payload ciphertext
    frame[TelemetryLinkSecurity.HEADER_SIZE] ^= 0xFF

    ok, decoded, reason = rx.decrypt_packet(bytes(frame))
    assert ok is False
    assert decoded is None
    assert reason == "MAC_VERIFICATION_FAILED"
    assert rx.packets_rejected_mac == 1


def test_replay_attack_detected_and_blocked():
    key = b"REPLAY-PROTECTION-KEY-2026-V7!!!"
    tx = TelemetryLinkSecurity(master_key=key)
    rx = TelemetryLinkSecurity(master_key=key)

    frame = tx.encrypt_packet({"cmd": "ARM"})
    ok1, _, _ = rx.decrypt_packet(frame)
    ok2, _, reason2 = rx.decrypt_packet(frame)

    assert ok1 is True
    assert ok2 is False
    assert reason2 == "REPLAY_ATTACK_DETECTED"
    assert rx.packets_rejected_replay == 1


def test_session_key_rotation_seamless_decryption():
    key = b"KEY-ROTATION-MASTER-KEY-2026-UAV"
    tx = TelemetryLinkSecurity(master_key=key)
    rx = TelemetryLinkSecurity(master_key=key)

    f1 = tx.encrypt_packet({"seq": 1})
    new_key_id = tx.rotate_session_key()
    assert new_key_id == 2
    f2 = tx.encrypt_packet({"seq": 2})

    ok1, p1, _ = rx.decrypt_packet(f1)
    ok2, p2, _ = rx.decrypt_packet(f2)
    assert ok1 is True and p1["seq"] == 1
    assert ok2 is True and p2["seq"] == 2


def test_jamming_and_spoofing_health_detection():
    sec = TelemetryLinkSecurity(master_key=b"JAMMING-CHECK-MASTER-KEY-2026!!!")

    st_ok = sec.evaluate_link_health(rssi_dbm=-55.0, packet_loss_pct=1.0, time_since_last_packet_s=0.1)
    assert st_ok.health_state == LinkHealthState.SECURE

    st_jam = sec.evaluate_link_health(rssi_dbm=-95.0, packet_loss_pct=45.0, time_since_last_packet_s=0.2)
    assert st_jam.health_state == LinkHealthState.JAMMING_SUSPECTED
    assert st_jam.jamming_score > 0.5

    st_lost = sec.evaluate_link_health(rssi_dbm=-105.0, packet_loss_pct=100.0, time_since_last_packet_s=6.5)
    assert st_lost.health_state == LinkHealthState.LINK_LOST

    # Inject 3 MAC failures to trigger SPOOFING_ALERT
    for _ in range(3):
        sec.decrypt_packet(b"BADFRAME")
    st_spoof = sec.evaluate_link_health(rssi_dbm=-60.0, packet_loss_pct=2.0, time_since_last_packet_s=0.1)
    assert st_spoof.health_state == LinkHealthState.SPOOFING_ALERT
    assert st_spoof.spoofing_detected is True


def test_short_master_key_raises():
    with pytest.raises(ValueError):
        TelemetryLinkSecurity(master_key=b"short")
