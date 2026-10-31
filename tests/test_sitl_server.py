"""
Unit tests for ArduPilot SITL / MAVLink Mock Server Subsystem
"""
import socket
import time
import pytest
from src.telemetry.sitl_server import ArduPilotSITLServer


def test_sitl_server_lifecycle():
    server = ArduPilotSITLServer(host="127.0.0.1", port=14555)
    server.start()
    assert server.running is True

    # Send a dummy UDP packet to establish client addr
    client_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client_sock.sendto(b"PING", ("127.0.0.1", 14555))
    time.sleep(0.1)

    assert server.client_addr is not None
    client_sock.close()
    server.stop()
    assert server.running is False


def test_sitl_server_physics_update():
    server = ArduPilotSITLServer(host="127.0.0.1", port=14556, initial_alt=20.0)
    server.vx = 5.0
    server.start()

    time.sleep(0.15)
    # Lat should have slightly increased with positive vx
    assert server.lat >= 41.0082
    server.stop()
