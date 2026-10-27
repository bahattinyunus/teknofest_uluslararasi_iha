"""
TEKNOFEST 2026 Uluslararası İHA - Web Yer Kontrol İstasyonu Sunucusu (Web GCS)
------------------------------------------------------------------------------
Python dahili HTTP sunucusu ile sıfır harici bağımlılıkla çalışan,
web tarayıcısından İHA telemetrisini (Suni Ufuk, Radar, Batarya, İrtifa,
Hedef Durumu) canlı görselleştiren ve görev komutları gönderen web arayüzü.
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import threading
import time
from typing import Dict, Any, Optional

HTML_DASHBOARD = """<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🛸 UAV-ARCHITECT-GLOBAL | Canlı Yer Kontrol İstasyonu (GCS)</title>
    <style>
        :root {
            --bg-dark: #0a0e17;
            --panel-bg: rgba(18, 26, 43, 0.85);
            --border-glow: #00f2ff;
            --accent-cyan: #00f2ff;
            --accent-red: #ff3366;
            --accent-green: #00ff88;
            --accent-gold: #ffd700;
            --text-main: #e2e8f0;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', monospace, sans-serif; }
        body { background: var(--bg-dark); color: var(--text-main); min-height: 100vh; padding: 15px; }
        header { display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid var(--border-glow); padding-bottom: 12px; margin-bottom: 20px; }
        .logo { font-size: 22px; font-weight: 900; letter-spacing: 2px; color: var(--accent-cyan); text-shadow: 0 0 10px rgba(0,242,255,0.5); }
        .badge { background: rgba(0,255,136,0.2); color: var(--accent-green); padding: 5px 12px; border-radius: 4px; border: 1px solid var(--accent-green); font-size: 13px; font-weight: bold; }
        .grid { display: grid; grid-template-columns: 320px 1fr 340px; gap: 20px; }
        .panel { background: var(--panel-bg); border: 1px solid rgba(0,242,255,0.2); border-radius: 8px; padding: 18px; box-shadow: 0 4px 20px rgba(0,0,0,0.5); backdrop-filter: blur(10px); }
        .panel h2 { font-size: 15px; text-transform: uppercase; letter-spacing: 1.5px; color: var(--accent-cyan); margin-bottom: 15px; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 6px; }
        .metric-row { display: flex; justify-content: space-between; margin-bottom: 10px; font-size: 14px; }
        .metric-val { font-weight: bold; color: #fff; }
        .tape-container { display: flex; justify-content: space-around; margin: 15px 0; }
        .tape-box { text-align: center; background: rgba(0,0,0,0.4); padding: 10px 18px; border-radius: 6px; border-left: 3px solid var(--accent-cyan); }
        .tape-num { font-size: 28px; font-weight: bold; color: var(--accent-cyan); }
        .tape-label { font-size: 11px; text-transform: uppercase; color: #94a3b8; }
        #radarCanvas { width: 100%; height: 380px; background: #050811; border-radius: 6px; border: 1px solid #1e293b; display: block; }
        .horizon-box { text-align: center; margin: 15px 0; background: #000; border-radius: 6px; border: 1px solid #334155; position: relative; height: 160px; overflow: hidden; display: flex; align-items: center; justify-content: center; }
        .horizon-ladder { position: absolute; width: 140px; height: 2px; background: var(--accent-green); box-shadow: 0 0 8px var(--accent-green); transition: transform 0.1s linear; }
        .horizon-center { width: 12px; height: 12px; border: 2px solid #ffd700; border-radius: 50%; z-index: 2; }
        .btn-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 15px; }
        button { background: rgba(0,242,255,0.1); border: 1px solid var(--accent-cyan); color: #fff; padding: 10px; border-radius: 6px; cursor: pointer; font-weight: bold; transition: all 0.2s; font-size: 12px; }
        button:hover { background: var(--accent-cyan); color: #000; box-shadow: 0 0 15px rgba(0,242,255,0.6); }
        button.btn-danger { border-color: var(--accent-red); background: rgba(255,51,102,0.1); color: var(--accent-red); }
        button.btn-danger:hover { background: var(--accent-red); color: #fff; }
    </style>
</head>
<body>
    <header>
        <div class="logo">🛸 UAV-ARCHITECT-GLOBAL</div>
        <div style="display:flex; gap:15px; align-items:center;">
            <span id="stateBadge" class="badge">BAĞLANTI BEKLENİYOR</span>
            <span style="font-size:13px; color:#94a3b8;" id="clock">00:00:00</span>
        </div>
    </header>

    <div class="grid">
        <!-- SOL PANEL: Uçuş Telemetrisi -->
        <div class="panel">
            <h2>UÇUŞ ENSTRÜMANLARI</h2>
            <div class="tape-container">
                <div class="tape-box">
                    <div class="tape-num" id="altVal">0.0</div>
                    <div class="tape-label">İRTİFA (AGL m)</div>
                </div>
                <div class="tape-box">
                    <div class="tape-num" id="spdVal">0.0</div>
                    <div class="tape-label">YER HIZI (m/s)</div>
                </div>
            </div>

            <div class="horizon-box">
                <div class="horizon-ladder" id="horizonBar"></div>
                <div class="horizon-center"></div>
            </div>
            <div class="metric-row">
                <span>Roll / Pitch:</span>
                <span class="metric-val" id="attVal">0.0° / 0.0°</span>
            </div>
            <div class="metric-row">
                <span>Baş Açısı (Heading):</span>
                <span class="metric-val" id="hdgVal">0.0°</span>
            </div>
            <div class="metric-row">
                <span>Rüzgar Vektörü:</span>
                <span class="metric-val" id="windVal">0.0 m/s @ 0°</span>
            </div>
            <div class="metric-row">
                <span>Batarya (4S LiPo):</span>
                <span class="metric-val" id="batVal" style="color:var(--accent-green)">16.20 V</span>
            </div>
            <div class="metric-row">
                <span>Aviyonik Failsafe:</span>
                <span class="metric-val" id="fsVal">NOMİNAL</span>
            </div>
        </div>

        <!-- ORTA PANEL: Taktik Radar & Hedef Takibi -->
        <div class="panel">
            <h2>TAKTIK UÇUŞ RADARI & HEDEF SAHASI</h2>
            <canvas id="radarCanvas" width="600" height="380"></canvas>
            <div style="display:flex; justify-content:space-between; margin-top:12px; font-size:13px;">
                <span>🟦 Hedef A (Mavi Altıgen): <b id="targetAStatus">ARANIYOR</b></span>
                <span>🟥 Hedef B (Kırmızı Üçgen): <b id="targetBStatus">ARANIYOR</b></span>
                <span>Kilit: <b id="lockStatus" style="color:var(--accent-gold)">YOK</b></span>
            </div>
        </div>

        <!-- SAĞ PANEL: Görev & Yük Kontrolü -->
        <div class="panel">
            <h2>2026 GÖREV VE YÜK KONTROLÜ</h2>
            <div class="metric-row">
                <span>Kalan Yük Sayısı:</span>
                <span class="metric-val" id="payloadVal" style="font-size:20px; color:var(--accent-gold)">2</span>
            </div>
            <div class="metric-row">
                <span>Hedef A Yükü (Kırmızı):</span>
                <span class="metric-val" id="slot1Val">HAZIRDA (ARMED)</span>
            </div>
            <div class="metric-row">
                <span>Hedef B Yükü (Mavi):</span>
                <span class="metric-val" id="slot2Val">HAZIRDA (ARMED)</span>
            </div>
            <div class="metric-row">
                <span>Hedefe Kalan Sapma:</span>
                <span class="metric-val" id="missVal">--- m</span>
            </div>

            <div class="btn-grid">
                <button onclick="sendCommand('START_MISSION_2')">▶ GÖREV 2 BAŞLAT</button>
                <button onclick="sendCommand('START_MISSION_1')">∞ GÖREV 1 BAŞLAT</button>
                <button onclick="sendCommand('DROP_PAYLOAD_1')">🔴 1. YÜK BIRAK</button>
                <button onclick="sendCommand('DROP_PAYLOAD_2')">🔵 2. YÜK BIRAK</button>
                <button class="btn-danger" onclick="sendCommand('RTL')">🏠 OTONOM RTL</button>
                <button class="btn-danger" onclick="sendCommand('LAND')">⬇ ACİL İNİŞ</button>
            </div>
        </div>
    </div>

    <script>
        const canvas = document.getElementById('radarCanvas');
        const ctx = canvas.getContext('2d');

        function updateClock() {
            document.getElementById('clock').innerText = new Date().toLocaleTimeString();
        }
        setInterval(updateClock, 1000);

        async function fetchTelemetry() {
            try {
                const res = await fetch('/api/telemetry');
                if (!res.ok) return;
                const data = await res.json();

                // Metrikleri güncelle
                document.getElementById('stateBadge').innerText = data.state || 'IDLE';
                document.getElementById('altVal').innerText = (data.altitude_agl || 0).toFixed(1);
                document.getElementById('spdVal').innerText = (data.ground_speed || 0).toFixed(1);
                document.getElementById('attVal').innerText = (data.roll_deg || 0).toFixed(1) + '° / ' + (data.pitch_deg || 0).toFixed(1) + '°';
                document.getElementById('hdgVal').innerText = (data.heading_deg || 0).toFixed(1) + '°';
                document.getElementById('windVal').innerText = (data.wind_speed || 0).toFixed(1) + ' m/s @ ' + (data.wind_dir || 0).toFixed(0) + '°';
                document.getElementById('batVal').innerText = (data.battery_v || 0).toFixed(2) + ' V';
                document.getElementById('fsVal').innerText = data.failsafe_status || 'NOMİNAL';
                document.getElementById('payloadVal').innerText = data.payloads_remaining ?? 2;
                document.getElementById('lockStatus').innerText = data.locked_target || 'YOK';
                document.getElementById('missVal').innerText = data.miss_distance && data.miss_distance < 100 ? data.miss_distance.toFixed(2) + ' m' : '---';

                // Suni ufuk animasyonu
                const roll = data.roll_deg || 0;
                const pitch = data.pitch_deg || 0;
                const bar = document.getElementById('horizonBar');
                bar.style.transform = `rotate(${-roll}deg) translateY(${pitch * 2}px)`;

                // Radarı çiz
                drawRadar(data);
            } catch (e) {
                console.error(e);
            }
        }

        function drawRadar(data) {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            const cx = canvas.width / 2;
            const cy = canvas.height / 2;

            // Radar halkaları
            ctx.strokeStyle = '#1e293b';
            ctx.lineWidth = 1;
            for (let r = 50; r <= 180; r += 45) {
                ctx.beginPath();
                ctx.arc(cx, cy, r, 0, Math.PI * 2);
                ctx.stroke();
            }

            // Radar eksen çizgileri
            ctx.beginPath();
            ctx.moveTo(cx, 10); ctx.lineTo(cx, canvas.height - 10);
            ctx.moveTo(10, cy); ctx.lineTo(canvas.width - 10, cy);
            ctx.stroke();

            // Hedef A (Mavi Altıgen) - Sanal Konum
            const hexX = cx + 80;
            const hexY = cy - 40;
            ctx.strokeStyle = '#00f2ff';
            ctx.fillStyle = 'rgba(0,242,255,0.3)';
            ctx.beginPath();
            for (let i = 0; i < 6; i++) {
                const a = i * Math.PI / 3;
                const px = hexX + 18 * Math.cos(a);
                const py = hexY + 18 * Math.sin(a);
                if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
            }
            ctx.closePath();
            ctx.stroke(); ctx.fill();
            ctx.fillStyle = '#00f2ff';
            ctx.font = '11px sans-serif';
            ctx.fillText("HEDEF A (Mavi)", hexX - 35, hexY - 24);

            // Hedef B (Kırmızı Üçgen) - Sanal Konum
            const triX = cx - 90;
            const triY = cy + 50;
            ctx.strokeStyle = '#ff3366';
            ctx.fillStyle = 'rgba(255,51,102,0.3)';
            ctx.beginPath();
            ctx.moveTo(triX, triY - 18);
            ctx.lineTo(triX - 16, triY + 14);
            ctx.lineTo(triX + 16, triY + 14);
            ctx.closePath();
            ctx.stroke(); ctx.fill();
            ctx.fillStyle = '#ff3366';
            ctx.fillText("HEDEF B (Kırmızı)", triX - 38, triY + 28);

            // İHA Konumu ve Yönü (Merkez)
            ctx.save();
            ctx.translate(cx, cy);
            ctx.rotate((data.heading_deg || 0) * Math.PI / 180);
            ctx.fillStyle = '#ffd700';
            ctx.beginPath();
            ctx.moveTo(0, -14); ctx.lineTo(10, 10); ctx.lineTo(0, 5); ctx.lineTo(-10, 10);
            ctx.closePath();
            ctx.fill();
            ctx.restore();
        }

        async function sendCommand(cmd) {
            try {
                await fetch('/api/command', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ command: cmd })
                });
                console.log("Komut iletildi:", cmd);
            } catch (e) {
                alert("Komut iletilemedi: " + e);
            }
        }

        setInterval(fetchTelemetry, 150);
    </script>
</body>
</html>
"""


class WebGCSRequestHandler(BaseHTTPRequestHandler):
    core_instance = None

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_DASHBOARD.encode("utf-8"))
        elif self.path == "/api/telemetry":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            telemetry_data = {}
            if self.core_instance is not None:
                telemetry_data = self.core_instance.step()

            self.wfile.write(json.dumps(telemetry_data).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/api/command":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            cmd_data = json.loads(body) if body else {}

            cmd = cmd_data.get("command")
            print(f"[WEB GCS] Operatör Komutu Alındı: {cmd}")

            if self.core_instance is not None:
                if cmd == "RTL":
                    self.core_instance.comms.trigger_rtl()
                elif cmd == "DROP_PAYLOAD_1":
                    self.core_instance.actuator.release_payload_for_target("TARGET_A")
                elif cmd == "DROP_PAYLOAD_2":
                    self.core_instance.actuator.release_payload_for_target("TARGET_B")
                elif cmd == "START_MISSION_2":
                    self.core_instance.start_mission()

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "SUCCESS", "command": cmd}).encode("utf-8"))

    def log_message(self, format, *args):
        # HTTP log çıktısını sustur
        pass


class WebGCSServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 8080, core_instance=None):
        self.host = host
        self.port = port
        self.core = core_instance
        WebGCSRequestHandler.core_instance = core_instance
        self.server = HTTPServer((host, port), WebGCSRequestHandler)
        self.thread: Optional[threading.Thread] = None

    def start_background(self):
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        print(f"[WEB GCS] Canlı Yer Kontrol İstasyonu Başlatıldı -> http://{self.host}:{self.port}")

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
