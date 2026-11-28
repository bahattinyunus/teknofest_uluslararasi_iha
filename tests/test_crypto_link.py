"""
TEKNOFEST 2026 - 256-bit Şifreli Telemetri ve RF Güvenlik (CryptoTelemetryLink) Testleri
"""

import pytest
from src.telemetry.crypto_link import (
    CryptoTelemetryLink,
    EncryptedFrame,
    RFMetrics,
    RFAnomalyLevel,
)


def test_encrypt_decrypt_roundtrip_and_serialization():
    key = b"0123456789abcdef0123456789abcdef"
    tx = CryptoTelemetryLink(master_key=key)
    rx = CryptoTelemetryLink(master_key=key)

    payload = {"alt_agl": 34.5, "state": "SEARCHING_TARGET_A", "lat": 38.34694, "lon": 38.24444}
    frame = tx.encrypt_payload(payload)
    wire_bytes = frame.to_bytes()
    restored = EncryptedFrame.from_bytes(wire_bytes)

    decoded = rx.decrypt_frame(restored)
    assert decoded == payload
    assert tx.tx_packets == 1
    assert rx.rx_packets == 1


def test_tampered_ciphertext_rejected_by_hmac():
    key = b"abcdef0123456789abcdef0123456789"
    tx = CryptoTelemetryLink(master_key=key)
    rx = CryptoTelemetryLink(master_key=key)

    frame = tx.encrypt_payload({"cmd": "DROP_PAYLOAD_1"})
    tampered_ct = bytes([frame.ciphertext[0] ^ 0xFF]) + frame.ciphertext[1:]
    tampered = EncryptedFrame(
        version=frame.version,
        key_epoch=frame.key_epoch,
        seq_num=frame.seq_num,
        nonce=frame.nonce,
        ciphertext=tampered_ct,
        mac_tag=frame.mac_tag,
    )
    assert rx.decrypt_frame(tampered) is None
    assert rx.mac_failures == 1


def test_replay_attack_rejected():
    key = b"k" * 32
    tx = CryptoTelemetryLink(master_key=key)
    rx = CryptoTelemetryLink(master_key=key)

    frame = tx.encrypt_payload({"seq_test": 1})
    assert rx.decrypt_frame(frame) == {"seq_test": 1}
    # Aynı paketi tekrar gönder (replay)
    assert rx.decrypt_frame(frame) is None
    assert rx.replay_rejections == 1


def test_session_key_rotation_epoch_increment():
    key = b"r" * 32
    tx = CryptoTelemetryLink(master_key=key, key_rotation_interval_pkts=10)
    rx = CryptoTelemetryLink(master_key=key, key_rotation_interval_pkts=10)

    for i in range(12):
        f = tx.encrypt_payload({"i": i})
        out = rx.decrypt_frame(f)
        assert out == {"i": i}

    assert tx.key_epoch == 2


def test_rf_jamming_and_spoofing_detection():
    link = CryptoTelemetryLink(master_key=b"s" * 32)
    st_nom = link.evaluate_rf_health(RFMetrics(rssi_dbm=-55.0, noise_floor_dbm=-95.0, packet_loss_pct=0.0))
    assert st_nom.anomaly_level == RFAnomalyLevel.NOMINAL

    st_jam = link.evaluate_rf_health(RFMetrics(rssi_dbm=-68.0, noise_floor_dbm=-70.0, packet_loss_pct=45.0))
    assert st_jam.anomaly_level == RFAnomalyLevel.JAMMING_SUSPECTED

    # 3 ardışık sahte MAC hatası -> SPOOFING_ALERT
    bad_frame = EncryptedFrame(1, 1, 99, b"\x00" * 16, b"fake", b"\x00" * 32)
    for _ in range(3):
        link.decrypt_frame(bad_frame)
    assert link.latest_status.anomaly_level == RFAnomalyLevel.SPOOFING_ALERT
