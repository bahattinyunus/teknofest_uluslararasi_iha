"""
Unit tests for Integrated Mission Control CLI Subsystem
"""
import pytest
import subprocess
import sys


def test_mission_control_cli_help():
    res = subprocess.run(
        [sys.executable, "scripts/mission_control.py", "--help"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace"
    )
    assert res.returncode == 0
    assert "TEKNOFEST 2026 Entegre Komuta Merkezi" in res.stdout
    assert "--preflight" in res.stdout
    assert "--web-gcs" in res.stdout
    assert "--sitl" in res.stdout


def test_mission_control_cli_preflight():
    res = subprocess.run(
        [sys.executable, "scripts/mission_control.py", "--preflight"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace"
    )
    assert res.returncode == 0
    assert "UÇUŞ ÖNCESİ OTOMATİK CHECKLIST" in res.stdout
    assert "KALKIŞA UYGUN" in res.stdout


def test_mission_control_cli_trajectory():
    res = subprocess.run(
        [sys.executable, "scripts/mission_control.py", "--trajectory"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace"
    )
    assert res.returncode == 0
    assert "3B Yörünge Optimizasyonu" in res.stdout
    assert "Optimize Edilen Nokta Sayısı" in res.stdout


def test_mission_control_cli_fdir():
    res = subprocess.run(
        [sys.executable, "scripts/mission_control.py", "--fdir"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace"
    )
    assert res.returncode == 0
    assert "Çoklu Sensör FDIR" in res.stdout
    assert "Nominal Sensör Durumu" in res.stdout


def test_mission_control_cli_playbook():
    res = subprocess.run(
        [sys.executable, "scripts/mission_control.py", "--playbook"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace"
    )
    assert res.returncode == 0
    assert "Görev Playbook" in res.stdout
    assert "Fırsatçı Yeniden Sıralama" in res.stdout


def test_mission_control_cli_debrief():
    res = subprocess.run(
        [sys.executable, "scripts/mission_control.py", "--debrief"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace"
    )
    assert res.returncode == 0
    assert "Kara Kutu" in res.stdout
