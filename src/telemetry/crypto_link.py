"""
TEKNOFEST 2026 Uluslararası İHA - Uçtan Uca Şifreli Telemetri ve RF Güvenlik Modülü
====================================================================================
Şartname Referansı:
  - Madde 9.4: Telemetri ve kumanda linkinin RF karışma ve sabotaja karşı
    uçtan uca şifrelenmesi (256-bit oturum anahtarı + HMAC-SHA256 bütünlük doğrulama).
  - Madde 9.3.2: Kasıtlı frekans karıştırma (RF Jamming) ve sahte paket enjeksiyonu
    (Replay / Spoofing) tespiti ve anlık alarm üretimi.

Tasarım:
  - Sıfır harici bağımlılık (yalnızca Python standart kütüphanesi: hashlib, hmac, secrets).
  - Encrypt-then-MAC (SHA-256 CTR anahtar akışı + HMAC-SHA256 doğrulama etiketi).
  - Monotonik sıra numarası (sequence counter) ile tekrar oynatma (replay) koruması.
  - Periyodik oturum anahtarı döndürme (epoch key rotation).
  - RSSI, SNR, gürültü tabanı ve paket kaybı üzerinden RF Jamming/Spoofing kestirimi.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import struct
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional, Tuple


class RFAnomalyLevel(Enum):
    NOMINAL = "NOMINAL"
    DEGRADED = "DEGRADED"
    JAMMING_SUSPECTED = "JAMMING_SUSPECTED"
    SPOOFING_ALERT = "SPOOFING_ALERT"


@dataclass
class EncryptedFrame:
    """Şifrelenmiş ve imzalanmış telemetri paketi."""
    version: int
    key_epoch: int
    seq_num: int
    nonce: bytes          # 16 byte
    ciphertext: bytes
    mac_tag: bytes        # 32 byte HMAC-SHA256

    def to_bytes(self) -> bytes:
        header = struct.pack(">BHI", self.version, self.key_epoch, self.seq_num)
        ct_len = struct.pack(">I", len(self.ciphertext))
        return header + self.nonce + ct_len + self.ciphertext + self.mac_tag

    @classmethod
    def from_bytes(cls, raw: bytes) -> "EncryptedFrame":
        min_len = 7 + 16 + 4 + 32
        if len(raw) < min_len:
            raise ValueError(f"Geçersiz paket uzunluğu: {len(raw)} < {min_len}")
        version, key_epoch, seq_num = struct.unpack(">BHI", raw[:7])
        nonce = raw[7:23]
        (ct_len,) = struct.unpack(">I", raw[23:27])
        if len(raw) != 27 + ct_len + 32:
            raise ValueError("Paket gövde uzunluğu başlıkla uyuşmuyor")
        ciphertext = raw[27:27 + ct_len]
        mac_tag = raw[27 + ct_len:]
        return cls(
            version=version,
            key_epoch=key_epoch,
            seq_num=seq_num,
            nonce=nonce,
            ciphertext=ciphertext,
            mac_tag=mac_tag,
        )


@dataclass
class RFMetrics:
    """Anlık RF link kalite ölçümü."""
    rssi_dbm: float = -58.0
    noise_floor_dbm: float = -95.0
    packet_loss_pct: float = 0.0
    timestamp: float = field(default_factory=time.time)

    @property
    def snr_db(self) -> float:
        return self.rssi_dbm - self.noise_floor_dbm


@dataclass
class LinkSecurityStatus:
    """Telemetri linki şifreleme ve RF güvenlik özet durumu."""
    anomaly_level: RFAnomalyLevel
    key_epoch: int
    tx_packets: int
    rx_packets: int
    replay_rejections: int
    mac_failures: int
    snr_db: float
    packet_loss_pct: float
    encryption_active: bool
    diagnostic_message: str


class CryptoTelemetryLink:
    """
    256-bit Anahtar Türetmeli Encrypt-then-MAC Telemetri Güvenlik Katmanı
    ve RF Jamming / Spoofing İzleyici.
    """

    PROTOCOL_VERSION = 1

    def __init__(
        self,
        master_key: Optional[bytes] = None,
        key_rotation_interval_pkts: int = 500,
        replay_window_size: int = 64,
    ):
        self._master_key: bytes = master_key if master_key is not None else secrets.token_bytes(32)
        if len(self._master_key) < 16:
            raise ValueError("Ana anahtar en az 16 bayt (128-bit) olmalıdır.")

        self.key_rotation_interval_pkts = max(10, int(key_rotation_interval_pkts))
        self.replay_window_size = max(8, int(replay_window_size))

        self.key_epoch: int = 1
        self._tx_seq: int = 0
        self._rx_highest_seq: int = 0
        self._rx_seen_window: set[int] = set()

        self.tx_packets: int = 0
        self.rx_packets: int = 0
        self.replay_rejections: int = 0
        self.mac_failures: int = 0
        self._consecutive_auth_failures: int = 0

        self.latest_rf: RFMetrics = RFMetrics()
        self.latest_status: LinkSecurityStatus = LinkSecurityStatus(
            anomaly_level=RFAnomalyLevel.NOMINAL,
            key_epoch=self.key_epoch,
            tx_packets=0,
            rx_packets=0,
            replay_rejections=0,
            mac_failures=0,
            snr_db=self.latest_rf.snr_db,
            packet_loss_pct=0.0,
            encryption_active=True,
            diagnostic_message="Şifreli telemetri hattı hazır (256-bit EtM).",
        )

    def _derive_epoch_keys(self, epoch: int) -> Tuple[bytes, bytes]:
        """Master anahtardan ilgili epoch için şifreleme ve MAC alt anahtarlarını türetir."""
        enc_key = hmac.new(
            self._master_key,
            b"TEKNOFEST2026-ENC-EPOCH-" + struct.pack(">H", epoch),
            hashlib.sha256,
        ).digest()
        mac_key = hmac.new(
            self._master_key,
            b"TEKNOFEST2026-MAC-EPOCH-" + struct.pack(">H", epoch),
            hashlib.sha256,
        ).digest()
        return enc_key, mac_key

    @staticmethod
    def _keystream(enc_key: bytes, nonce: bytes, length: int) -> bytes:
        """SHA-256 CTR modu ile deterministik anahtar akışı üretir."""
        out = bytearray()
        counter = 0
        while len(out) < length:
            block = hashlib.sha256(enc_key + nonce + struct.pack(">I", counter)).digest()
            out.extend(block)
            counter += 1
        return bytes(out[:length])

    @staticmethod
    def _xor_bytes(data: bytes, mask: bytes) -> bytes:
        return bytes(a ^ b for a, b in zip(data, mask))

    def _compute_mac(self, mac_key: bytes, version: int, epoch: int, seq: int, nonce: bytes, ciphertext: bytes) -> bytes:
        header = struct.pack(">BHI", version, epoch, seq)
        return hmac.new(mac_key, header + nonce + ciphertext, hashlib.sha256).digest()

    def rotate_session_key(self) -> int:
        """Oturum anahtarını bir sonraki epoch'a döndürür."""
        self.key_epoch = (self.key_epoch % 65535) + 1
        return self.key_epoch

    def encrypt_payload(self, payload: Dict[str, Any]) -> EncryptedFrame:
        """Sözlük tabanlı telemetri verisini şifreler ve HMAC-SHA256 ile imzalar."""
        if self.tx_packets > 0 and (self.tx_packets % self.key_rotation_interval_pkts == 0):
            self.rotate_session_key()

        self._tx_seq += 1
        plaintext = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        nonce = secrets.token_bytes(16)

        enc_key, mac_key = self._derive_epoch_keys(self.key_epoch)
        stream = self._keystream(enc_key, nonce, len(plaintext))
        ciphertext = self._xor_bytes(plaintext, stream)
        mac_tag = self._compute_mac(mac_key, self.PROTOCOL_VERSION, self.key_epoch, self._tx_seq, nonce, ciphertext)

        self.tx_packets += 1
        return EncryptedFrame(
            version=self.PROTOCOL_VERSION,
            key_epoch=self.key_epoch,
            seq_num=self._tx_seq,
            nonce=nonce,
            ciphertext=ciphertext,
            mac_tag=mac_tag,
        )

    def decrypt_frame(self, frame: EncryptedFrame) -> Optional[Dict[str, Any]]:
        """
        Şifreli paketi doğrular (HMAC + Replay Window) ve çözer.
        Bütünlük veya tekrar oynatma ihlalinde None döner ve güvenlik sayaçlarını günceller.
        """
        enc_key, mac_key = self._derive_epoch_keys(frame.key_epoch)
        expected_mac = self._compute_mac(
            mac_key, frame.version, frame.key_epoch, frame.seq_num, frame.nonce, frame.ciphertext
        )
        if not hmac.compare_digest(expected_mac, frame.mac_tag):
            self.mac_failures += 1
            self._consecutive_auth_failures += 1
            self.evaluate_rf_health(self.latest_rf)
            return None

        # Replay koruması (sliding window)
        if frame.seq_num <= 0:
            self.replay_rejections += 1
            self._consecutive_auth_failures += 1
            self.evaluate_rf_health(self.latest_rf)
            return None

        min_valid_seq = max(1, self._rx_highest_seq - self.replay_window_size + 1)
        if frame.seq_num < min_valid_seq or frame.seq_num in self._rx_seen_window:
            self.replay_rejections += 1
            self._consecutive_auth_failures += 1
            self.evaluate_rf_health(self.latest_rf)
            return None

        # Geçerli paket -> pencereyi güncelle
        if frame.seq_num > self._rx_highest_seq:
            self._rx_highest_seq = frame.seq_num
            cutoff = max(1, self._rx_highest_seq - self.replay_window_size + 1)
            self._rx_seen_window = {s for s in self._rx_seen_window if s >= cutoff}
        self._rx_seen_window.add(frame.seq_num)

        stream = self._keystream(enc_key, frame.nonce, len(frame.ciphertext))
        plaintext = self._xor_bytes(frame.ciphertext, stream)
        self.rx_packets += 1
        self._consecutive_auth_failures = 0

        try:
            return json.loads(plaintext.decode("utf-8"))
        except Exception:
            self.mac_failures += 1
            return None

    def evaluate_rf_health(self, rf: RFMetrics) -> LinkSecurityStatus:
        """
        RF sinyal metrikleri ve kriptografik hata sayaçlarına göre
        Jamming / Spoofing durumunu sınıflandırır (Şartname §9.3.2 & §9.4).
        """
        self.latest_rf = rf
        snr = rf.snr_db

        if self._consecutive_auth_failures >= 3 or (self.mac_failures + self.replay_rejections) >= 5:
            level = RFAnomalyLevel.SPOOFING_ALERT
            msg = (
                f"KRİTİK: Sahte paket/Replay saldırısı şüphesi! "
                f"(MAC hatası: {self.mac_failures}, Replay reddi: {self.replay_rejections})"
            )
        elif rf.noise_floor_dbm > -75.0 or (snr < 8.0 and rf.packet_loss_pct > 25.0):
            level = RFAnomalyLevel.JAMMING_SUSPECTED
            msg = (
                f"UYARI: RF karıştırma (Jamming) tespit edildi! "
                f"(Gürültü tabanı: {rf.noise_floor_dbm:.1f} dBm, SNR: {snr:.1f} dB, Kayıp: %{rf.packet_loss_pct:.1f})"
            )
        elif snr < 15.0 or rf.packet_loss_pct > 10.0:
            level = RFAnomalyLevel.DEGRADED
            msg = f"RF link kalitesi zayıfladı (SNR: {snr:.1f} dB, Kayıp: %{rf.packet_loss_pct:.1f})."
        else:
            level = RFAnomalyLevel.NOMINAL
            msg = f"Şifreli telemetri linki nominal (Epoch #{self.key_epoch}, SNR: {snr:.1f} dB)."

        self.latest_status = LinkSecurityStatus(
            anomaly_level=level,
            key_epoch=self.key_epoch,
            tx_packets=self.tx_packets,
            rx_packets=self.rx_packets,
            replay_rejections=self.replay_rejections,
            mac_failures=self.mac_failures,
            snr_db=round(snr, 2),
            packet_loss_pct=round(rf.packet_loss_pct, 2),
            encryption_active=True,
            diagnostic_message=msg,
        )
        return self.latest_status
