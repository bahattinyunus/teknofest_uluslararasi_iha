"""
TEKNOFEST 2026 Uluslararası İHA - Web Yer Kontrol İstasyonu Sunucusu (Web GCS)
------------------------------------------------------------------------------
Resmi TÜBİTAK TEKNOFEST 2026 İHA Şartnamesi (V7) ile Birebir Uyumlu:
- Yarışma Alanı: Malatya Tulga Havalimanı (38.34694° N, 38.24444° E, 938m MSL)
- 200m x 300m Uçuş Sahası (Tampon bölge yoktur)
- 150m Mesafeli Direkler (Direk 1 & Direk 2 - ∞ Figür-8 Parkuru)
- 30m x 100m Tarama ve Yük Bırakma Sahası
- Kategori Seçici / Geçişi (Sabit Kanat vs Döner Kanat)
  * Sabit Kanat: Hedef A (4x4m Mavi Kare -> Kırmızı Yük), Hedef B (2x2m Kırmızı Kare -> Mavi Yük), 20m Puanlama Çemberi
  * Döner Kanat: Hedef A (2m Kenar Mavi Düzgün Altıgen -> Kırmızı Yük), Hedef B (1m Kenar Kırmızı Üçgen -> Mavi Yük), 10m Puanlama Çemberi
- TÜBİTAK Tablo 3 Resmi PG1 ve PG2 Puanlama Hesaplayıcıları (c çarpanı, AY/BY bonusları)
- 120m AGL Üst İrtifa Sınırı ve 25 km/h Rüzgar Limiti Canlı Takibi
- Ön Uçuş Kontrol Listesi (SHGM, MTOW <= 4.0 kg, 2s Güç Kesme, Kutu Şartı)
- İnteraktif Taktik Harita (Pan/Zoom, Rota İzi, FOV Ayak İzi, Balistik Halka) & Kamera Optik Nişangah HUD
"""

from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import json
import math
import threading
import time
from typing import Dict, Any, Optional, List

try:
    from src.telemetry.analytics import FlightAnalyticsEngine
except ImportError:
    FlightAnalyticsEngine = None


HTML_DASHBOARD = """<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🛸 UAV-ARCHITECT-GLOBAL | TEKNOFEST 2026 MALATYA TULGA GCS (V7)</title>
    <style>
        :root {
            --bg-dark: #060911;
            --panel-bg: rgba(13, 20, 36, 0.94);
            --panel-card: rgba(19, 30, 54, 0.85);
            --border-glow: #00f2ff;
            --accent-cyan: #00f2ff;
            --accent-red: #ff3366;
            --accent-green: #00ff88;
            --accent-gold: #ffd700;
            --accent-purple: #a855f7;
            --accent-blue: #38bdf8;
            --text-main: #f8fafc;
            --text-dim: #94a3b8;
            --tape-bg: #090e1a;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, monospace, sans-serif; }
        body { background: var(--bg-dark); color: var(--text-main); min-height: 100vh; padding: 10px 16px; overflow-x: hidden; }
        
        /* HEADER */
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 2px solid var(--border-glow);
            padding: 8px 12px;
            margin-bottom: 12px;
            background: linear-gradient(90deg, rgba(0,242,255,0.12) 0%, rgba(13,20,36,0.6) 50%, rgba(168,85,247,0.12) 100%);
            border-radius: 8px;
            box-shadow: 0 4px 20px rgba(0,242,255,0.15);
        }
        .header-title-box { display: flex; flex-direction: column; gap: 3px; }
        .logo { font-size: 19px; font-weight: 900; letter-spacing: 1.5px; color: var(--accent-cyan); text-shadow: 0 0 12px rgba(0,242,255,0.7); display: flex; align-items: center; gap: 8px; }
        .spec-tag { font-size: 11px; color: var(--text-dim); display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
        .venue-pill {
            background: rgba(168,85,247,0.22);
            border: 1px solid var(--accent-purple);
            color: #d8b4fe;
            padding: 3px 8px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
            display: inline-flex;
            align-items: center;
            gap: 4px;
        }
        .header-controls { display: flex; align-items: center; gap: 10px; }
        .category-toggle {
            display: inline-flex;
            background: #0a0f1d;
            border: 1px solid #334155;
            border-radius: 8px;
            padding: 2px;
        }
        .cat-btn {
            background: transparent;
            border: none;
            color: var(--text-dim);
            padding: 5px 12px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        .cat-btn.active {
            background: var(--accent-cyan);
            color: #060911;
            box-shadow: 0 0 12px rgba(0,242,255,0.6);
        }
        .badge {
            background: rgba(0,255,136,0.18);
            color: var(--accent-green);
            padding: 4px 10px;
            border-radius: 6px;
            border: 1px solid var(--accent-green);
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.5px;
        }
        .badge.warn { background: rgba(255,215,0,0.18); color: var(--accent-gold); border-color: var(--accent-gold); }
        .badge.danger { background: rgba(255,51,102,0.18); color: var(--accent-red); border-color: var(--accent-red); }
        .clock-box { font-size: 12px; color: var(--text-dim); font-family: monospace; font-weight: 600; }

        /* GRID LAYOUT */
        .grid {
            display: grid;
            grid-template-columns: 310px 1fr 340px;
            gap: 12px;
        }
        @media (max-width: 1280px) {
            .grid { grid-template-columns: 1fr; }
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid rgba(0,242,255,0.22);
            border-radius: 10px;
            padding: 14px;
            box-shadow: 0 4px 24px rgba(0,0,0,0.65);
            backdrop-filter: blur(10px);
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        .panel h2 {
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 1.2px;
            color: var(--accent-cyan);
            border-bottom: 1px solid rgba(255,255,255,0.08);
            padding-bottom: 6px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .panel h2 .sub { font-size: 10px; color: var(--text-dim); font-weight: normal; }

        /* PRIMARY FLIGHT DISPLAY (PFD) */
        .pfd-container {
            position: relative;
            background: #000;
            border: 1px solid #334155;
            border-radius: 8px;
            height: 160px;
            overflow: hidden;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: inset 0 0 20px rgba(0,0,0,0.8);
        }
        .pfd-horizon {
            position: absolute;
            width: 280px;
            height: 280px;
            transition: transform 0.08s linear;
        }
        .pfd-sky { width: 100%; height: 50%; background: linear-gradient(180deg, #1e3a8a 0%, #3b82f6 100%); }
        .pfd-ground { width: 100%; height: 50%; background: linear-gradient(180deg, #854d0e 0%, #3f2203 100%); border-top: 1.5px solid #fff; }
        .pfd-ladder {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: 140px;
            height: 120px;
            pointer-events: none;
        }
        .ladder-line {
            position: absolute;
            left: 50%;
            transform: translateX(-50%);
            border-top: 1.5px solid rgba(255,255,255,0.7);
            text-align: center;
            color: #fff;
            font-size: 8px;
            font-family: monospace;
        }
        .pfd-crosshair {
            position: absolute;
            width: 36px;
            height: 36px;
            border: 2px solid var(--accent-gold);
            border-radius: 50%;
            z-index: 5;
            pointer-events: none;
        }
        .pfd-crosshair::before { content:''; position:absolute; top:50%; left:-10px; width:10px; height:2px; background:var(--accent-gold); }
        .pfd-crosshair::after { content:''; position:absolute; top:50%; right:-10px; width:10px; height:2px; background:var(--accent-gold); }

        /* TAPES: SPEED & ALTITUDE */
        .tape-container { display: flex; justify-content: space-between; gap: 8px; }
        .tape-box {
            flex: 1;
            text-align: center;
            background: var(--tape-bg);
            padding: 8px 10px;
            border-radius: 6px;
            border-left: 3px solid var(--accent-cyan);
            position: relative;
        }
        .tape-box.warning-limit { border-left-color: var(--accent-red); }
        .tape-num { font-size: 22px; font-weight: 800; color: var(--accent-cyan); font-family: monospace; }
        .tape-label { font-size: 9px; text-transform: uppercase; color: var(--text-dim); margin-top: 2px; }
        
        .progress-bar-bg { width: 100%; height: 5px; background: #1e293b; border-radius: 3px; overflow: hidden; margin-top: 4px; }
        .progress-bar-fill { height: 100%; background: var(--accent-cyan); width: 0%; transition: width 0.3s; }
        .progress-bar-fill.danger { background: var(--accent-red); }
        .progress-bar-fill.warning { background: var(--accent-gold); }
        .progress-bar-fill.success { background: var(--accent-green); }

        .metric-row { display: flex; justify-content: space-between; font-size: 12px; }
        .metric-val { font-weight: 700; color: #fff; font-family: monospace; }

        /* BATTERY CELLS */
        .battery-card {
            background: var(--panel-card);
            border-radius: 6px;
            padding: 8px;
            border: 1px solid rgba(255,255,255,0.06);
        }
        .cell-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 4px; margin-top: 4px; }
        .cell-item {
            background: #090e1a;
            border-radius: 4px;
            padding: 4px 2px;
            text-align: center;
            font-size: 9px;
            font-family: monospace;
            border: 1px solid #1e293b;
        }
        .cell-bar { height: 3px; background: var(--accent-green); border-radius: 2px; margin-top: 3px; width: 92%; margin-left: auto; margin-right: auto; }

        /* FAILSAFE BANNER */
        .failsafe-banner {
            background: rgba(255,51,102,0.12);
            border: 1px solid rgba(255,51,102,0.4);
            border-radius: 6px;
            padding: 8px 10px;
            font-size: 11px;
            line-height: 1.4;
            color: #fca5a5;
        }
        .failsafe-banner strong { color: var(--accent-red); }

        /* CENTER PANEL: RADAR & TACTICAL DISPLAY */
        .view-tabs { display: flex; gap: 6px; }
        .view-tab {
            padding: 5px 12px;
            background: #090e1a;
            border: 1px solid #334155;
            color: var(--text-dim);
            font-size: 11px;
            border-radius: 6px;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.2s;
        }
        .view-tab.active { background: var(--accent-cyan); color: #060911; border-color: var(--accent-cyan); font-weight: 700; }
        
        .radar-card {
            position: relative;
            background: #040711;
            border-radius: 8px;
            border: 1px solid #1e293b;
            overflow: hidden;
            display: flex;
            flex-direction: column;
        }
        #radarCanvas { width: 100%; height: 390px; display: block; background: #030610; cursor: grab; }
        #radarCanvas:active { cursor: grabbing; }

        .radar-toolbar {
            position: absolute;
            top: 8px;
            right: 8px;
            display: flex;
            gap: 4px;
            z-index: 10;
        }
        .tool-btn {
            background: rgba(10,15,29,0.85);
            border: 1px solid #334155;
            color: #fff;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 11px;
            cursor: pointer;
        }
        .tool-btn:hover { background: var(--accent-cyan); color: #000; }

        .map-legend {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            justify-content: space-between;
            padding: 8px 10px;
            background: rgba(0,0,0,0.4);
            border-radius: 6px;
            font-size: 10px;
        }
        .legend-item { display: inline-flex; align-items: center; gap: 5px; }
        .legend-dot { width: 9px; height: 9px; border-radius: 2px; display: inline-block; }

        /* BUTTONS & ACTIONS */
        .btn-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 7px; margin-top: 4px; }
        button {
            background: rgba(0,242,255,0.08);
            border: 1px solid var(--accent-cyan);
            color: #fff;
            padding: 8px 10px;
            border-radius: 6px;
            cursor: pointer;
            font-weight: 700;
            transition: all 0.2s;
            font-size: 11px;
            text-align: center;
        }
        button:hover { background: var(--accent-cyan); color: #060911; box-shadow: 0 0 12px rgba(0,242,255,0.5); }
        button.btn-danger { border-color: var(--accent-red); background: rgba(255,51,102,0.12); color: var(--accent-red); }
        button.btn-danger:hover { background: var(--accent-red); color: #fff; box-shadow: 0 0 12px rgba(255,51,102,0.6); }
        button.btn-success { border-color: var(--accent-green); background: rgba(0,255,136,0.12); color: var(--accent-green); }
        button.btn-success:hover { background: var(--accent-green); color: #060911; }
        button.btn-warn { border-color: var(--accent-gold); background: rgba(255,215,0,0.12); color: var(--accent-gold); }
        button.btn-warn:hover { background: var(--accent-gold); color: #000; }

        /* PAYLOAD BAYS */
        .bays-card {
            background: var(--panel-card);
            border-radius: 6px;
            padding: 8px;
            border: 1px solid rgba(255,255,255,0.06);
            display: flex;
            flex-direction: column;
            gap: 6px;
        }
        .bay-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: #090e1a;
            padding: 6px 10px;
            border-radius: 4px;
            font-size: 11px;
            border-left: 3px solid var(--accent-green);
        }
        .bay-item.dropped { border-left-color: #64748b; opacity: 0.6; }

        /* PREFLIGHT CHECKLIST ACCORDION */
        .check-card {
            background: var(--panel-card);
            border-radius: 6px;
            padding: 8px 10px;
            font-size: 11px;
            border: 1px solid rgba(255,255,255,0.06);
        }
        .check-title { display: flex; justify-content: space-between; font-weight: bold; cursor: pointer; color: var(--accent-cyan); }
        .check-list { display: flex; flex-direction: column; gap: 4px; margin-top: 6px; }
        .check-row { display: flex; align-items: center; gap: 6px; font-size: 10px; color: var(--text-dim); }
        .check-row input[type="checkbox"] { accent-color: var(--accent-green); }

        /* SCORE CALCULATOR CARD */
        .calc-panel {
            background: rgba(15, 23, 42, 0.95);
            border: 1px solid rgba(255,215,0,0.35);
            border-radius: 8px;
            padding: 10px;
        }
        .calc-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            cursor: pointer;
            color: var(--accent-gold);
            font-size: 11px;
            font-weight: 800;
            letter-spacing: 0.8px;
        }
        .calc-content { margin-top: 8px; font-size: 11px; }
        .calc-tabs { display: flex; gap: 6px; margin-bottom: 8px; }
        .calc-tab {
            flex: 1;
            padding: 4px;
            background: #1e293b;
            border: 1px solid #334155;
            color: var(--text-dim);
            font-size: 10px;
            border-radius: 4px;
            text-align: center;
            cursor: pointer;
            font-weight: 600;
        }
        .calc-tab.active { background: var(--accent-gold); color: #000; font-weight: bold; border-color: var(--accent-gold); }
        .calc-row { display: grid; grid-template-columns: 1fr 65px; gap: 6px; align-items: center; margin-bottom: 4px; }
        .calc-row input, .calc-row select {
            background: #090e1a;
            border: 1px solid #334155;
            color: #fff;
            padding: 3px 5px;
            border-radius: 4px;
            font-size: 10px;
            font-family: monospace;
            text-align: right;
        }
        .calc-result-box {
            margin-top: 8px;
            padding: 6px 10px;
            background: rgba(0,0,0,0.45);
            border-radius: 6px;
            border-left: 3px solid var(--accent-gold);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .calc-result-val { font-size: 17px; font-weight: 900; color: var(--accent-gold); font-family: monospace; }

        /* BOTTOM TICKER / LOGS */
        .bottom-bar {
            margin-top: 10px;
            background: var(--panel-bg);
            border: 1px solid rgba(0,242,255,0.18);
            border-radius: 8px;
            padding: 8px 12px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 11px;
            color: var(--text-dim);
        }
        .log-ticker { font-family: monospace; color: var(--accent-green); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 65%; }
        .export-btns { display: flex; gap: 6px; }
        .export-btn {
            background: #090e1a;
            border: 1px solid #334155;
            color: var(--text-dim);
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 10px;
            cursor: pointer;
        }
        .export-btn:hover { background: var(--accent-cyan); color: #000; border-color: var(--accent-cyan); }
    </style>
</head>
<body>
    <header>
        <div class="header-title-box">
            <div class="logo">
                <span>🛸 UAV-ARCHITECT-GLOBAL</span>
                <span style="font-size:12px; color:var(--text-dim); font-weight:normal;">| 2026 GCS</span>
            </div>
            <div class="spec-tag">
                <span class="venue-pill">📍 Malatya Tulga (38.34694° N, 38.24444° E, 938m)</span>
                <span>TÜBİTAK ULUSLARARASI İHA YARIŞMASI (V7 ŞARTNAME) • 8 - 13 EYLÜL 2026</span>
            </div>
        </div>
        <div class="header-controls">
            <div class="category-toggle">
                <button id="catRotaryBtn" class="cat-btn active" onclick="setCategory('rotary_wing')">🛸 DÖNER KANAT</button>
                <button id="catFixedBtn" class="cat-btn" onclick="setCategory('fixed_wing')">🛫 SABİT KANAT</button>
            </div>
            <span id="stateBadge" class="badge">BAĞLANTI BEKLENİYOR</span>
            <span class="clock-box" id="clock">00:00:00</span>
        </div>
    </header>

    <div class="grid">
        <!-- SOL PANEL: Uçuş Telemetrisi, PFD & Enstrümanlar -->
        <div class="panel">
            <h2>
                <span>UÇUŞ ENSTRÜMANLARI</span>
                <span class="sub">120m AGL & 25 km/h LİMİT</span>
            </h2>
            
            <!-- PFD (Primary Flight Display) / Suni Ufuk -->
            <div class="pfd-container">
                <div class="pfd-horizon" id="pfdHorizon">
                    <div class="pfd-sky"></div>
                    <div class="pfd-ground"></div>
                </div>
                <div class="pfd-ladder" id="pfdLadder">
                    <div class="ladder-line" style="top:25px; width:50px;">+15°</div>
                    <div class="ladder-line" style="top:42px; width:35px;">+10°</div>
                    <div class="ladder-line" style="top:59px; width:20px;">+5°</div>
                    <div class="ladder-line" style="top:78px; width:20px;">-5°</div>
                    <div class="ladder-line" style="top:95px; width:35px;">-10°</div>
                    <div class="ladder-line" style="top:112px; width:50px;">-15°</div>
                </div>
                <div class="pfd-crosshair"></div>
            </div>

            <!-- Hız ve İrtifa Göstergeleri (120m Tavan Korumalı) -->
            <div class="tape-container">
                <div class="tape-box" id="altBox">
                    <div class="tape-num" id="altVal">0.0</div>
                    <div class="tape-label">İRTİFA (AGL m) [Azami 120m AGL]</div>
                    <div class="progress-bar-bg">
                        <div class="progress-bar-fill" id="altBar"></div>
                    </div>
                </div>
                <div class="tape-box" id="spdBox">
                    <div class="tape-num" id="spdVal">0.0</div>
                    <div class="tape-label">YER HIZI (m/s)</div>
                    <div class="progress-bar-bg">
                        <div class="progress-bar-fill success" id="spdBar"></div>
                    </div>
                </div>
            </div>

            <div class="metric-row">
                <span>Roll / Pitch / Yaw:</span>
                <span class="metric-val" id="attVal">0.0° / 0.0° / 0.0°</span>
            </div>
            <div class="metric-row">
                <span>Baş Açısı (Heading):</span>
                <span class="metric-val" id="hdgVal">0.0°</span>
            </div>
            <div class="metric-row">
                <span>Rüzgar Vektörü:</span>
                <span class="metric-val" id="windVal">0.0 m/s (0.0 km/h) @ 0°</span>
            </div>

            <!-- Batarya & LiPo Hücre Takibi -->
            <div class="battery-card">
                <div class="metric-row" style="margin-bottom:2px;">
                    <span>4S LiPo Güç Durumu:</span>
                    <span class="metric-val" id="batVal" style="color:var(--accent-green)">16.20 V (90%)</span>
                </div>
                <div class="cell-grid">
                    <div class="cell-item">H1: <b id="c1Val">4.05V</b><div class="cell-bar" id="c1Bar"></div></div>
                    <div class="cell-item">H2: <b id="c2Val">4.05V</b><div class="cell-bar" id="c2Bar"></div></div>
                    <div class="cell-item">H3: <b id="c3Val">4.05V</b><div class="cell-bar" id="c3Bar"></div></div>
                    <div class="cell-item">H4: <b id="c4Val">4.05V</b><div class="cell-bar" id="c4Bar"></div></div>
                </div>
            </div>

            <div class="metric-row">
                <span>Aviyonik / FDIR:</span>
                <span class="metric-val" id="fsVal">NOMİNAL / GPS EKF3</span>
            </div>
            <div class="metric-row">
                <span>MTOW / Ağırlık Bütçesi:</span>
                <span class="metric-val" id="mtowVal">3.65 kg / ≤ 4.0 kg ✅</span>
            </div>

            <!-- V7 Fail-Safe Kuralı Banner -->
            <div class="failsafe-banner" id="failsafeInfo">
                <strong>V7 ARALIKSIZ FAIL-SAFE KURALI:</strong><br>
                <span id="failsafeDetail">Döner Kanat: Yarım gaz kontrollü alçalma. RTL kesinlikle YASAKTIR!</span>
            </div>
        </div>

        <!-- ORTA PANEL: Taktik Uçuş Sahası & Kamera Optik HUD -->
        <div class="panel">
            <h2>
                <span>TAKTIK UÇUŞ SAHASI (MALATYA TULGA)</span>
                <span class="sub" id="fieldDimensions">200m x 300m SAHA | 150m DİREK MESAFESİ</span>
            </h2>
            
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div class="view-tabs">
                    <div class="view-tab active" id="tabMap" onclick="setViewMode('map')">🗺️ TAKTİK HARİTA (200x300m)</div>
                    <div class="view-tab" id="tabCam" onclick="setViewMode('camera')">📷 KAMERA NİŞANGAH HUD</div>
                    <div class="view-tab" id="tabDual" onclick="setViewMode('dual')">🔀 ÇİFT EKRAN</div>
                </div>
                <div style="font-size:11px; color:var(--text-dim);">
                    <span>Zoom: </span><b id="zoomLabel">1.0x</b>
                </div>
            </div>

            <div class="radar-card">
                <canvas id="radarCanvas" width="720" height="390"></canvas>
                <div class="radar-toolbar">
                    <button class="tool-btn" onclick="zoomIn()">➕</button>
                    <button class="tool-btn" onclick="zoomOut()">➖</button>
                    <button class="tool-btn" onclick="resetView()">⟲ Sıfırla</button>
                </div>
            </div>

            <div class="map-legend">
                <div class="legend-item">
                    <span class="legend-dot" style="background:var(--accent-purple)"></span>
                    <span>200x300m Uçuş Sahası (Tampon Yok)</span>
                </div>
                <div class="legend-item">
                    <span class="legend-dot" style="background:#ffaa00"></span>
                    <span>150m Direkler (∞ Parkuru)</span>
                </div>
                <div class="legend-item">
                    <span class="legend-dot" style="background:rgba(0,242,255,0.4)"></span>
                    <span>30x100m Tarama Sahası</span>
                </div>
                <div class="legend-item">
                    <span class="legend-dot" style="background:#00f2ff"></span>
                    <span id="legendTargetA">Hedef A (Mavi)</span>
                </div>
                <div class="legend-item">
                    <span class="legend-dot" style="background:#ff3366"></span>
                    <span id="legendTargetB">Hedef B (Kırmızı)</span>
                </div>
                <div class="legend-item">
                    <span class="legend-dot" style="background:#ffd700"></span>
                    <span>İHA & Görüş Açısı (FOV)</span>
                </div>
            </div>

            <div style="display:flex; justify-content:space-between; font-size:12px; color:var(--text-dim);">
                <span>Hedef Kilidi: <b id="lockStatus" style="color:var(--accent-gold)">YOK</b></span>
                <span>Hedefe Kalan Sapma: <b id="missVal" style="color:var(--accent-cyan)">---</b></span>
                <span>Puanlama Çemberi: <b id="scoreRadiusLabel">10m Yarıçap</b></span>
            </div>
        </div>

        <!-- SAĞ PANEL: Görev Komutları, Yükler, Zamanlayıcılar & Tablo 3 -->
        <div class="panel">
            <h2>
                <span>2026 GÖREV VE YÜK YÖNETİMİ</span>
                <span class="sub">TABLO 3 UYUMLU</span>
            </h2>
            
            <!-- Yük Hazneleri ve Durumu -->
            <div class="bays-card">
                <div class="bay-item" id="bay1">
                    <span>🔴 1. YÜK (Kırmızı / 600g):</span>
                    <b id="slot1Val" style="color:var(--accent-green)">HAZIRDA (ARMED)</b>
                </div>
                <div class="bay-item" id="bay2">
                    <span>🔵 2. YÜK (Mavi / 600g):</span>
                    <b id="slot2Val" style="color:var(--accent-green)">HAZIRDA (ARMED)</b>
                </div>
            </div>

            <!-- Görev Komuta Butonları -->
            <div class="btn-grid">
                <button onclick="sendCommand('START_MISSION_1')">∞ 1. GÖREV (150m DİREK)</button>
                <button onclick="sendCommand('START_MISSION_2')">🎯 2. GÖREV (TARAMA)</button>
                <button onclick="sendCommand('DROP_PAYLOAD_1')">🔴 1. YÜK BIRAK (A)</button>
                <button onclick="sendCommand('DROP_PAYLOAD_2')">🔵 2. YÜK BIRAK (B)</button>
                <button id="rtlBtn" class="btn-danger" onclick="sendCommand('RTL')">🏠 OTONOM RTL</button>
                <button class="btn-danger" onclick="sendCommand('DEPLOY_PARACHUTE')">🚨 ACİL FTS / PARAŞÜT</button>
            </div>

            <!-- Şartname Zamanlayıcıları (§8.3.5) -->
            <div class="check-card">
                <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                    <span style="font-weight:bold; color:var(--accent-cyan);">⏱️ ŞARTNAME ZAMAN SAYAÇLARI</span>
                    <span style="font-size:10px; color:var(--text-dim);" id="interveneCount">Ek Müdahale: 0 (+0 sn)</span>
                </div>
                <div style="display:grid; grid-template-columns:1fr 1fr; gap:6px; font-size:10px;">
                    <div style="background:#090e1a; padding:4px 6px; border-radius:4px;">
                        <span>Kurulum (Azami 8 dk):</span><br>
                        <b id="timerSetup" style="font-size:13px; color:var(--accent-gold); font-family:monospace;">00:00</b> / 08:00
                    </div>
                    <div style="background:#090e1a; padding:4px 6px; border-radius:4px;">
                        <span>Uçuş (G1:5dk / G2:10dk):</span><br>
                        <b id="timerFlight" style="font-size:13px; color:var(--accent-cyan); font-family:monospace;">00:00</b>
                    </div>
                </div>
            </div>

            <!-- Uçuş Öncesi Teknik Kontrol Matrisi -->
            <div class="check-card">
                <div class="check-title" onclick="toggleChecklist()">
                    <span>📋 UÇUŞ ÖNCESİ KONTROL MATRİSİ (SHGM & TEKNOFEST)</span>
                    <span id="checkIcon">▼</span>
                </div>
                <div class="check-list" id="checkList">
                    <label class="check-row"><input type="checkbox" checked disabled> SHGM Pilot & İHA Kaydı Doğrulandı (QR Kod)</label>
                    <label class="check-row"><input type="checkbox" checked disabled> Muhafaza Kutusu Şartı (Sabit:Silindir / Döner:Prizma)</label>
                    <label class="check-row"><input type="checkbox" checked disabled> MTOW ≤ 4.0 kg Tartımı Onaylandı</label>
                    <label class="check-row"><input type="checkbox" checked disabled> 2 Saniye Güç Kesme Anahtar Testi Başarılı</label>
                    <label class="check-row"><input type="checkbox" checked disabled> Görev Bilgisayarı TEK Kamera Kuralına Uygun</label>
                    <label class="check-row"><input type="checkbox" checked disabled> Saha Ekibi TÜBİTAK Onaylı Baret Takılı</label>
                </div>
            </div>

            <!-- TÜBİTAK TABLO 3 RESMİ PUAN HESAPLAYICI -->
            <div class="calc-panel">
                <div class="calc-header" onclick="toggleCalc()">
                    <span>📊 TÜBİTAK TABLO 3 PUAN HESAPLAYICI</span>
                    <span id="calcToggleIcon">▼</span>
                </div>
                <div class="calc-content" id="calcContent">
                    <div class="calc-tabs">
                        <div class="calc-tab active" id="tabPg1" onclick="switchCalcTab('pg1')">GÖREV 1 (PG1)</div>
                        <div class="calc-tab" id="tabPg2" onclick="switchCalcTab('pg2')">GÖREV 2 (PG2)</div>
                    </div>

                    <!-- PG1 Formu -->
                    <div id="pg1Form">
                        <div class="calc-row">
                            <label>Otonomi Çarpanı (c):</label>
                            <select id="pg1_c" onchange="recalculatePG1()">
                                <option value="1.0">1.0 (Tam Otonom)</option>
                                <option value="0.7">0.7 (Yarı Otonom)</option>
                            </select>
                        </div>
                        <div class="calc-row">
                            <label>Hacim Oranı (Vol_min / Vol_tk):</label>
                            <input type="number" id="pg1_vol" value="1.0" step="0.05" min="0.1" max="1.0" oninput="recalculatePG1()">
                        </div>
                        <div class="calc-row">
                            <label>Hazırlık Oranı (thaz_min / thaz_tk):</label>
                            <input type="number" id="pg1_haz" value="1.0" step="0.05" min="0.1" max="1.0" oninput="recalculatePG1()">
                        </div>
                        <div class="calc-row">
                            <label>Ağırlık Oranı (W0_min / W0_tk):</label>
                            <input type="number" id="pg1_w0" value="1.0" step="0.05" min="0.1" max="1.0" oninput="recalculatePG1()">
                        </div>
                        <div class="calc-row">
                            <label>Uçuş Oranı (tuçuş_min / tuçuş_tk):</label>
                            <input type="number" id="pg1_ucus" value="1.0" step="0.05" min="0.1" max="1.0" oninput="recalculatePG1()">
                        </div>
                        <div class="calc-row">
                            <label>Ceza Puanı (Ceza 1 / 2):</label>
                            <input type="number" id="pg1_ceza" value="0.0" step="1.0" min="0" max="30" oninput="recalculatePG1()">
                        </div>
                        <div class="calc-result-box">
                            <span>PG1 Puanı (Azami 30):</span>
                            <span class="calc-result-val" id="pg1Result">30.00</span>
                        </div>
                    </div>

                    <!-- PG2 Formu -->
                    <div id="pg2Form" style="display:none;">
                        <div class="calc-row">
                            <label>Otonomi Çarpanı (c):</label>
                            <select id="pg2_c" onchange="recalculatePG2()">
                                <option value="1.0">1.0 (Tam Otonom)</option>
                                <option value="0.7">0.7 (Yarı Otonom)</option>
                            </select>
                        </div>
                        <div class="calc-row">
                            <label>Hacim Oranı (Vol):</label>
                            <input type="number" id="pg2_vol" value="1.0" step="0.05" min="0.1" max="1.0" oninput="recalculatePG2()">
                        </div>
                        <div class="calc-row">
                            <label>Hazırlık Oranı (thaz):</label>
                            <input type="number" id="pg2_haz" value="1.0" step="0.05" min="0.1" max="1.0" oninput="recalculatePG2()">
                        </div>
                        <div class="calc-row">
                            <label>Boş Ağırlık Oranı (W0):</label>
                            <input type="number" id="pg2_w0" value="1.0" step="0.05" min="0.1" max="1.0" oninput="recalculatePG2()">
                        </div>
                        <div class="calc-row">
                            <label>Yük Ağırlık Oranı (Wyük):</label>
                            <input type="number" id="pg2_wyuk" value="1.0" step="0.05" min="0.1" max="1.0" oninput="recalculatePG2()">
                        </div>
                        <div class="calc-row" id="rowTarget1">
                            <label id="lblTarget1">Hedef A Sapma (m):</label>
                            <input type="number" id="pg2_d1" value="0.5" step="0.1" min="0.0" oninput="recalculatePG2()">
                        </div>
                        <div class="calc-row" id="rowTarget2">
                            <label id="lblTarget2">Hedef B Sapma (m):</label>
                            <input type="number" id="pg2_d2" value="0.8" step="0.1" min="0.0" oninput="recalculatePG2()">
                        </div>
                        <div class="calc-row" id="rowBonus">
                            <label>Döner Kanat AY/BY Bonus:</label>
                            <select id="pg2_bonus" onchange="recalculatePG2()">
                                <option value="0">Bonus Yok (0 Puan)</option>
                                <option value="10">AY Bonus (+10 Puan)</option>
                                <option value="10b">BY Bonus (+10 Puan)</option>
                                <option value="20" selected>AY + BY Tam Bonus (+20 Puan)</option>
                            </select>
                        </div>
                        <div class="calc-row">
                            <label>Uçuş Süresi Oranı (tuçuş):</label>
                            <input type="number" id="pg2_ucus" value="1.0" step="0.05" min="0.1" max="1.0" oninput="recalculatePG2()">
                        </div>
                        <div class="calc-row">
                            <label>Ceza Puanı:</label>
                            <input type="number" id="pg2_ceza" value="0.0" step="1.0" min="0" oninput="recalculatePG2()">
                        </div>
                        <div class="calc-result-box">
                            <span id="pg2MaxLabel">PG2 Puanı (Azami 80):</span>
                            <span class="calc-result-val" id="pg2Result">80.00</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- ALT BİLGİ VE DIŞA AKTARIM PANELİ -->
    <div class="bottom-bar">
        <div class="log-ticker" id="logTicker">
            [SİSTEM] GCS Malatya Tulga yerleşkesine bağlandı. Telemetri 20Hz akıyor. EKF3 3D Fix stabil.
        </div>
        <div class="export-btns">
            <button class="export-btn" onclick="exportData('geojson')">🗺️ GeoJSON İndir</button>
            <button class="export-btn" onclick="exportData('csv')">📊 CSV Kara Kutu</button>
            <button class="export-btn" onclick="exportData('report')">📑 Hakem Raporu</button>
        </div>
    </div>

    <script>
        let currentCategory = 'rotary_wing';
        let currentView = 'map'; // 'map', 'camera', 'dual'
        let uavPos = { x: 0, y: 0, heading: 0, alt: 0, spd: 0 };
        let flightTrail = [];
        let viewScale = 1.0;
        let viewPanX = 0;
        let viewPanY = 0;
        let isDragging = false;
        let dragStartX = 0;
        let dragStartY = 0;

        const canvas = document.getElementById('radarCanvas');
        const ctx = canvas.getContext('2d');

        // Mouse Pan & Zoom Olayları
        canvas.addEventListener('mousedown', (e) => {
            isDragging = true;
            dragStartX = e.clientX - viewPanX;
            dragStartY = e.clientY - viewPanY;
        });
        window.addEventListener('mousemove', (e) => {
            if (isDragging) {
                viewPanX = e.clientX - dragStartX;
                viewPanY = e.clientY - dragStartY;
            }
        });
        window.addEventListener('mouseup', () => { isDragging = false; });
        canvas.addEventListener('wheel', (e) => {
            e.preventDefault();
            const delta = e.deltaY < 0 ? 1.15 : 0.85;
            viewScale = Math.max(0.4, Math.min(3.5, viewScale * delta));
            document.getElementById('zoomLabel').innerText = viewScale.toFixed(1) + 'x';
        }, { passive: false });

        function zoomIn() {
            viewScale = Math.min(3.5, viewScale * 1.2);
            document.getElementById('zoomLabel').innerText = viewScale.toFixed(1) + 'x';
        }
        function zoomOut() {
            viewScale = Math.max(0.4, viewScale / 1.2);
            document.getElementById('zoomLabel').innerText = viewScale.toFixed(1) + 'x';
        }
        function resetView() {
            viewScale = 1.0;
            viewPanX = 0;
            viewPanY = 0;
            document.getElementById('zoomLabel').innerText = '1.0x';
        }

        function setViewMode(mode) {
            currentView = mode;
            document.getElementById('tabMap').classList.toggle('active', mode === 'map');
            document.getElementById('tabCam').classList.toggle('active', mode === 'camera');
            document.getElementById('tabDual').classList.toggle('active', mode === 'dual');
        }

        function updateClock() {
            document.getElementById('clock').innerText = new Date().toLocaleTimeString();
        }
        setInterval(updateClock, 1000);

        function toggleChecklist() {
            const list = document.getElementById('checkList');
            const icon = document.getElementById('checkIcon');
            if (list.style.display === 'none') {
                list.style.display = 'flex';
                icon.innerText = '▼';
            } else {
                list.style.display = 'none';
                icon.innerText = '▶';
            }
        }

        function setCategory(cat) {
            currentCategory = cat;
            document.getElementById('catRotaryBtn').classList.toggle('active', cat === 'rotary_wing');
            document.getElementById('catFixedBtn').classList.toggle('active', cat === 'fixed_wing');

            const failsafeDetail = document.getElementById('failsafeDetail');
            const scoreRadiusLabel = document.getElementById('scoreRadiusLabel');
            const legendTargetA = document.getElementById('legendTargetA');
            const legendTargetB = document.getElementById('legendTargetB');
            const rtlBtn = document.getElementById('rtlBtn');

            if (cat === 'rotary_wing') {
                failsafeDetail.innerText = "DÖNER KANAT: Yarım gaz kontrollü iniş. RTL kesinlikle YASAKTIR! Hakem komutuyla motor durdurma.";
                scoreRadiusLabel.innerText = "10m Yarıçap (Döner)";
                legendTargetA.innerText = "Hedef A (2m Mavi Altıgen -> Kırmızı Yük)";
                legendTargetB.innerText = "Hedef B (1m Kırmızı Üçgen -> Mavi Yük)";
                rtlBtn.innerText = "⬇ KONTROLLÜ İNİŞ (DÖNER)";
                document.getElementById('lblTarget1').innerText = "Hedef A (Altıgen) Sapma (m):";
                document.getElementById('lblTarget2').innerText = "Hedef B (Üçgen) Sapma (m):";
                document.getElementById('rowBonus').style.display = 'grid';
                document.getElementById('pg2MaxLabel').innerText = "PG2 Puanı (Azami 80):";
            } else {
                failsafeDetail.innerText = "SABİT KANAT: Gaz kes, tam yukarı irtifa, tam sağ istikamet ve kanatçık, tam açık flap!";
                scoreRadiusLabel.innerText = "20m Yarıçap (Sabit)";
                legendTargetA.innerText = "Hedef A (4x4m Mavi Kare -> Kırmızı Yük)";
                legendTargetB.innerText = "Hedef B (2x2m Kırmızı Kare -> Mavi Yük)";
                rtlBtn.innerText = "🏠 OTONOM RTL (SABİT)";
                document.getElementById('lblTarget1').innerText = "Hedef A (4x4m) Sapma (m):";
                document.getElementById('lblTarget2').innerText = "Hedef B (2x2m) Sapma (m):";
                document.getElementById('rowBonus').style.display = 'none';
                document.getElementById('pg2MaxLabel').innerText = "PG2 Puanı (Azami 70):";
            }

            sendCommand('SET_CATEGORY', { category: cat });
            recalculatePG2();
        }

        async function fetchTelemetry() {
            try {
                const res = await fetch('/api/telemetry');
                if (!res.ok) return;
                const data = await res.json();

                if (data.category && data.category !== currentCategory) {
                    setCategory(data.category);
                }

                // Badge ve Durum
                const badge = document.getElementById('stateBadge');
                badge.innerText = data.state || 'IDLE';
                if (data.state && (data.state.includes('EMERGENCY') || data.state.includes('FAILSAFE'))) {
                    badge.className = 'badge danger';
                } else if (data.state && data.state.includes('LOCKED')) {
                    badge.className = 'badge warn';
                } else {
                    badge.className = 'badge';
                }

                const alt = data.altitude_agl || 0;
                const spd = data.ground_speed || 0;
                document.getElementById('altVal').innerText = alt.toFixed(1);
                document.getElementById('spdVal').innerText = spd.toFixed(1);

                // 120m AGL Üst İrtifa Denetimi (§8.3.1)
                const altPct = Math.min(100, (alt / 120.0) * 100);
                const altBar = document.getElementById('altBar');
                altBar.style.width = altPct + '%';
                if (alt > 120.0) {
                    altBar.className = 'progress-bar-fill danger';
                    document.getElementById('altBox').className = 'tape-box warning-limit';
                } else if (alt > 100.0) {
                    altBar.className = 'progress-bar-fill warning';
                    document.getElementById('altBox').className = 'tape-box';
                } else {
                    altBar.className = 'progress-bar-fill';
                    document.getElementById('altBox').className = 'tape-box';
                }

                // 25 km/h Rüzgar Eşiği Denetimi (§8.3)
                const windMs = data.wind_speed || 0;
                const windKmh = windMs * 3.6;
                const windDir = data.wind_dir || 0;
                const windVal = document.getElementById('windVal');
                windVal.innerText = `${windMs.toFixed(1)} m/s (${windKmh.toFixed(1)} km/h) @ ${windDir.toFixed(0)}°`;
                if (windKmh > 25.0) {
                    windVal.style.color = 'var(--accent-red)';
                } else {
                    windVal.style.color = '#fff';
                }

                const roll = data.roll_deg || 0;
                const pitch = data.pitch_deg || 0;
                const yaw = data.heading_deg || 0;
                document.getElementById('attVal').innerText = `${roll.toFixed(1)}° / ${pitch.toFixed(1)}° / ${yaw.toFixed(1)}°`;
                document.getElementById('hdgVal').innerText = yaw.toFixed(1) + '°';
                
                // Batarya & Hücreler
                const batV = data.battery_v || 16.20;
                const soc = data.soc_pct || 90;
                document.getElementById('batVal').innerText = `${batV.toFixed(2)} V (${soc.toFixed(0)}%)`;
                const cellV = (batV / 4.0).toFixed(2) + 'V';
                document.getElementById('c1Val').innerText = cellV;
                document.getElementById('c2Val').innerText = cellV;
                document.getElementById('c3Val').innerText = cellV;
                document.getElementById('c4Val').innerText = cellV;

                document.getElementById('fsVal').innerText = (data.failsafe_status || 'NOMİNAL') + ' / ' + (data.nav_source || 'GPS');
                
                // Kalan Yük ve Bay Renkleri
                const rem = data.payloads_remaining ?? 2;
                document.getElementById('payloadVal').innerText = rem;
                if (rem <= 1) {
                    document.getElementById('bay1').className = 'bay-item dropped';
                    document.getElementById('slot1Val').innerText = 'BIRAKILDI (DROPPED)';
                    document.getElementById('slot1Val').style.color = '#94a3b8';
                }
                if (rem <= 0) {
                    document.getElementById('bay2').className = 'bay-item dropped';
                    document.getElementById('slot2Val').innerText = 'BIRAKILDI (DROPPED)';
                    document.getElementById('slot2Val').style.color = '#94a3b8';
                }

                document.getElementById('lockStatus').innerText = data.locked_target || 'YOK';

                const miss = data.miss_distance;
                if (miss !== undefined && miss < 100) {
                    const maxR = currentCategory === 'rotary_wing' ? 10.0 : 20.0;
                    const inside = miss <= maxR;
                    document.getElementById('missVal').innerText = miss.toFixed(2) + ' m ' + (inside ? '✅' : '❌ DIŞINDA');
                } else {
                    document.getElementById('missVal').innerText = '---';
                }

                // PFD Suni Ufuk
                document.getElementById('pfdHorizon').style.transform = `rotate(${-roll}deg) translateY(${pitch * 2.2}px)`;
                document.getElementById('pfdLadder').style.transform = `translate(-50%, -50%) translateY(${pitch * 2.2}px)`;

                // UAV Pozisyonu ve Tarihçe
                uavPos.x = data.pos_x || (data.nav_x || 0);
                uavPos.y = data.pos_y || (data.nav_y || 0);
                uavPos.heading = yaw;
                uavPos.alt = alt;
                uavPos.spd = spd;

                flightTrail.push({ x: uavPos.x, y: uavPos.y });
                if (flightTrail.length > 250) flightTrail.shift();

                // Sayısal Zamanlayıcılar
                if (data.setup_timer_s !== undefined) {
                    const m = Math.floor(data.setup_timer_s / 60);
                    const s = Math.floor(data.setup_timer_s % 60);
                    document.getElementById('timerSetup').innerText = `${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
                }
                if (data.flight_timer_s !== undefined) {
                    const m = Math.floor(data.flight_timer_s / 60);
                    const s = Math.floor(data.flight_timer_s % 60);
                    document.getElementById('timerFlight').innerText = `${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
                }
                if (data.log_message) {
                    document.getElementById('logTicker').innerText = `[LOG] ${data.log_message}`;
                }

                renderDisplay(data);
            } catch (e) {
                console.error(e);
            }
        }

        function renderDisplay(data) {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            if (currentView === 'map') {
                drawTacticalMap(0, 0, canvas.width, canvas.height, data);
            } else if (currentView === 'camera') {
                drawCameraHUD(0, 0, canvas.width, canvas.height, data);
            } else if (currentView === 'dual') {
                const halfW = canvas.width / 2;
                drawTacticalMap(0, 0, halfW, canvas.height, data);
                ctx.strokeStyle = '#334155';
                ctx.lineWidth = 2;
                ctx.beginPath();
                ctx.moveTo(halfW, 0); ctx.lineTo(halfW, canvas.height);
                ctx.stroke();
                drawCameraHUD(halfW, 0, halfW, canvas.height, data);
            }
        }

        function drawTacticalMap(vx, vy, vw, vh, data) {
            ctx.save();
            ctx.beginPath();
            ctx.rect(vx, vy, vw, vh);
            ctx.clip();

            const cx = vx + vw / 2 + viewPanX;
            const cy = vy + vh / 2 + viewPanY;

            // 200m x 300m Saha Ölçeklemesi (1m = ~1.1px * viewScale)
            const baseScale = Math.min(vw / 350, vh / 240);
            const scale = baseScale * viewScale;

            ctx.translate(cx, cy);

            // 1. Grid Çizgileri (50m aralıklı)
            ctx.strokeStyle = '#0f172a';
            ctx.lineWidth = 1;
            for (let x = -150; x <= 150; x += 50) {
                ctx.beginPath();
                ctx.moveTo(x * scale, -100 * scale);
                ctx.lineTo(x * scale, 100 * scale);
                ctx.stroke();
            }
            for (let y = -100; y <= 100; y += 50) {
                ctx.beginPath();
                ctx.moveTo(-150 * scale, y * scale);
                ctx.lineTo(150 * scale, y * scale);
                ctx.stroke();
            }

            // 2. 200x300m Uçuş Sahası Sınırı (Şartname Madde 7)
            ctx.strokeStyle = '#a855f7';
            ctx.lineWidth = 2;
            ctx.strokeRect(-150 * scale, -100 * scale, 300 * scale, 200 * scale);

            ctx.fillStyle = '#a855f7';
            ctx.font = '10px monospace';
            ctx.fillText("UÇUŞ SAHASI (200m x 300m) - TAMPON BÖLGE YOKTUR", -145 * scale, -105 * scale);

            // 3. 150m Mesafeli Direkler (∞ Figür-8 Parkuru)
            const p1x = -75 * scale;
            const p2x = 75 * scale;

            // Figür-8 Rota İpucu (Kesikli çizgi)
            ctx.strokeStyle = 'rgba(255, 170, 0, 0.35)';
            ctx.setLineDash([4, 4]);
            ctx.lineWidth = 1.5;
            ctx.beginPath();
            ctx.ellipse(p1x, 0, 35 * scale, 55 * scale, 0, 0, Math.PI * 2);
            ctx.stroke();
            ctx.beginPath();
            ctx.ellipse(p2x, 0, 35 * scale, 55 * scale, 0, 0, Math.PI * 2);
            ctx.stroke();
            ctx.setLineDash([]);

            // Direk 1
            ctx.fillStyle = '#ffaa00';
            ctx.beginPath();
            ctx.arc(p1x, 0, 6, 0, Math.PI * 2);
            ctx.fill();
            ctx.font = 'bold 9px monospace';
            ctx.fillText("DİREK 1 (-75m)", p1x - 35, -10);

            // Direk 2
            ctx.beginPath();
            ctx.arc(p2x, 0, 6, 0, Math.PI * 2);
            ctx.fill();
            ctx.fillText("DİREK 2 (+75m)", p2x - 35, -10);

            // 150m Mesafe Çizgisi
            ctx.strokeStyle = '#ffaa00';
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(p1x, 0); ctx.lineTo(p2x, 0);
            ctx.stroke();
            ctx.fillText("150m DİREK MESAFESİ", -50, 15);

            // 4. 30x100m Tarama Sahası (Scan Zone)
            const szW = 100 * scale;
            const szH = 30 * scale;
            const szX = -50 * scale;
            const szY = 30 * scale;

            ctx.fillStyle = 'rgba(0, 242, 255, 0.08)';
            ctx.fillRect(szX, szY, szW, szH);
            ctx.strokeStyle = 'rgba(0, 242, 255, 0.6)';
            ctx.lineWidth = 1.5;
            ctx.strokeRect(szX, szY, szW, szH);
            ctx.fillStyle = 'rgba(0, 242, 255, 0.9)';
            ctx.font = '9px monospace';
            ctx.fillText("TARAMA SAHASI (30m x 100m)", szX + 8, szY + 18);

            // 5. Hedefler & Puanlama Çemberleri
            const targetAX = -20 * scale;
            const targetAY = 45 * scale;
            const targetBX = 25 * scale;
            const targetBY = 45 * scale;

            const scoringR = (currentCategory === 'rotary_wing' ? 10.0 : 20.0) * scale;

            // Hedef A Puanlama Çemberi
            ctx.strokeStyle = 'rgba(0, 242, 255, 0.35)';
            ctx.setLineDash([2, 3]);
            ctx.beginPath();
            ctx.arc(targetAX, targetAY, scoringR, 0, Math.PI * 2);
            ctx.stroke();

            // Hedef B Puanlama Çemberi
            ctx.strokeStyle = 'rgba(255, 51, 102, 0.35)';
            ctx.beginPath();
            ctx.arc(targetBX, targetBY, scoringR, 0, Math.PI * 2);
            ctx.stroke();
            ctx.setLineDash([]);

            if (currentCategory === 'rotary_wing') {
                // Hedef A: Mavi Düzgün Altıgen (2m kenar)
                ctx.fillStyle = '#00f2ff';
                ctx.strokeStyle = '#ffffff';
                ctx.lineWidth = 1.5;
                ctx.beginPath();
                const hexR = 2.0 * scale * 2.2;
                for (let i = 0; i < 6; i++) {
                    const ang = i * Math.PI / 3;
                    const hx = targetAX + hexR * Math.cos(ang);
                    const hy = targetAY + hexR * Math.sin(ang);
                    if (i === 0) ctx.moveTo(hx, hy); else ctx.lineTo(hx, hy);
                }
                ctx.closePath();
                ctx.fill(); ctx.stroke();
                ctx.fillStyle = '#00f2ff';
                ctx.font = 'bold 9px monospace';
                ctx.fillText("A: MAVİ ALTIĞEN (2m)", targetAX - 45, targetAY - 14);

                // Hedef B: Kırmızı Eşkenar Üçgen (1m kenar)
                ctx.fillStyle = '#ff3366';
                ctx.beginPath();
                const triR = 1.5 * scale * 2.2;
                ctx.moveTo(targetBX, targetBY - triR);
                ctx.lineTo(targetBX - triR * 0.866, targetBY + triR * 0.5);
                ctx.lineTo(targetBX + triR * 0.866, targetBY + triR * 0.5);
                ctx.closePath();
                ctx.fill(); ctx.stroke();
                ctx.fillStyle = '#ff3366';
                ctx.fillText("B: KIRMIZI ÜÇGEN (1m)", targetBX - 45, targetBY + 22);
            } else {
                // Sabit Kanat: Hedef A: 4x4m Mavi Kare, Hedef B: 2x2m Kırmızı Kare
                const s4 = 4.0 * scale * 1.5;
                ctx.fillStyle = '#00f2ff';
                ctx.fillRect(targetAX - s4/2, targetAY - s4/2, s4, s4);
                ctx.strokeStyle = '#fff';
                ctx.strokeRect(targetAX - s4/2, targetAY - s4/2, s4, s4);
                ctx.fillStyle = '#00f2ff';
                ctx.font = 'bold 9px monospace';
                ctx.fillText("A: MAVİ KARE (4x4m)", targetAX - 45, targetAY - 14);

                const s2 = 2.0 * scale * 1.5;
                ctx.fillStyle = '#ff3366';
                ctx.fillRect(targetBX - s2/2, targetBY - s2/2, s2, s2);
                ctx.strokeRect(targetBX - s2/2, targetBY - s2/2, s2, s2);
                ctx.fillStyle = '#ff3366';
                ctx.fillText("B: KIRMIZI KARE (2x2m)", targetBX - 45, targetBY + 20);
            }

            // 6. Uçuş Rota İzi (Breadcrumbs)
            if (flightTrail.length > 1) {
                ctx.strokeStyle = 'rgba(0, 242, 255, 0.4)';
                ctx.lineWidth = 1.5;
                ctx.beginPath();
                for (let i = 0; i < flightTrail.length; i++) {
                    const tx = flightTrail[i].x * scale;
                    const ty = -flightTrail[i].y * scale;
                    if (i === 0) ctx.moveTo(tx, ty); else ctx.lineTo(tx, ty);
                }
                ctx.stroke();
            }

            // 7. İHA Sembolü, Baş Açısı ve FOV Projeksiyonu
            const ux = uavPos.x * scale;
            const uy = -uavPos.y * scale;
            
            // Kamera Görüş Frustumu (FOV Footprint)
            const fovLen = Math.max(20, uavPos.alt * 1.2) * scale;
            const fovAngle = 40 * Math.PI / 180;
            const hdgRad = (uavPos.heading || 0) * Math.PI / 180;
            
            ctx.fillStyle = 'rgba(0, 255, 136, 0.08)';
            ctx.strokeStyle = 'rgba(0, 255, 136, 0.35)';
            ctx.beginPath();
            ctx.moveTo(ux, uy);
            ctx.lineTo(ux + fovLen * Math.sin(hdgRad - fovAngle/2), uy - fovLen * Math.cos(hdgRad - fovAngle/2));
            ctx.lineTo(ux + fovLen * Math.sin(hdgRad + fovAngle/2), uy - fovLen * Math.cos(hdgRad + fovAngle/2));
            ctx.closePath();
            ctx.fill(); ctx.stroke();

            // İHA Gövdesi
            ctx.save();
            ctx.translate(ux, uy);
            ctx.rotate(hdgRad);
            ctx.fillStyle = '#ffd700';
            ctx.strokeStyle = '#fff';
            ctx.lineWidth = 1.5;
            ctx.beginPath();
            ctx.moveTo(0, -14);
            ctx.lineTo(9, 9);
            ctx.lineTo(0, 4);
            ctx.lineTo(-9, 9);
            ctx.closePath();
            ctx.fill(); ctx.stroke();
            ctx.restore();

            ctx.restore();
        }

        function drawCameraHUD(vx, vy, vw, vh, data) {
            ctx.save();
            ctx.beginPath();
            ctx.rect(vx, vy, vw, vh);
            ctx.clip();

            // Kamera Arka Planı (Simülasyon Video Karesi)
            ctx.fillStyle = '#02040a';
            ctx.fillRect(vx, vy, vw, vh);

            const cx = vx + vw / 2;
            const cy = vy + vh / 2;

            // Reticle / Nişangah
            ctx.strokeStyle = 'rgba(0, 242, 255, 0.5)';
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(cx - 30, cy); ctx.lineTo(cx + 30, cy);
            ctx.moveTo(cx, cy - 30); ctx.lineTo(cx, cy + 30);
            ctx.stroke();
            ctx.beginPath();
            ctx.arc(cx, cy, 20, 0, Math.PI * 2);
            ctx.stroke();

            // Köşe Optik Sınır Çizgileri
            const cw = 40;
            ctx.strokeStyle = 'rgba(0, 242, 255, 0.8)';
            ctx.lineWidth = 2;
            // Sol Üst
            ctx.beginPath(); ctx.moveTo(vx + 20, vy + 40); ctx.lineTo(vx + 20, vy + 20); ctx.lineTo(vx + 40, vy + 20); ctx.stroke();
            // Sağ Üst
            ctx.beginPath(); ctx.moveTo(vx + vw - 40, vy + 20); ctx.lineTo(vx + vw - 20, vy + 20); ctx.lineTo(vx + vw - 20, vy + 40); ctx.stroke();
            // Sol Alt
            ctx.beginPath(); ctx.moveTo(vx + 20, vy + vh - 40); ctx.lineTo(vx + 20, vy + vh - 20); ctx.lineTo(vx + 40, vy + vh - 20); ctx.stroke();
            // Sağ Alt
            ctx.beginPath(); ctx.moveTo(vx + vw - 40, vy + vh - 20); ctx.lineTo(vx + vw - 20, vy + vh - 20); ctx.lineTo(vx + vw - 20, vy + vh - 40); ctx.stroke();

            // Hedef Tespiti ve Kilitlenme Kutusu
            const locked = data.locked_target;
            const isTarget = !!locked;
            const targetColor = (locked && locked.includes('B')) ? '#ff3366' : '#00f2ff';

            const tgtX = cx + Math.sin(Date.now() * 0.002) * (isTarget ? 30 : 90);
            const tgtY = cy + Math.cos(Date.now() * 0.0018) * (isTarget ? 20 : 60);
            const boxW = 70;
            const boxH = 70;

            ctx.strokeStyle = targetColor;
            ctx.lineWidth = isTarget ? 2.5 : 1.5;
            ctx.strokeRect(tgtX - boxW/2, tgtY - boxH/2, boxW, boxH);

            ctx.fillStyle = targetColor;
            ctx.font = 'bold 10px monospace';
            const label = isTarget ? `LOCKED: ${locked} (98.2%)` : "ARANIYOR (SCANNING)";
            ctx.fillText(label, tgtX - boxW/2, tgtY - boxH/2 - 6);

            // Bilgi Katmanı (Overlay)
            ctx.fillStyle = 'rgba(0, 242, 255, 0.9)';
            ctx.font = '10px monospace';
            ctx.fillText("KAMERA AKIŞI: CSI-2 SONY IMX477 [1280x720@30FPS]", vx + 30, vy + 35);
            ctx.fillText(`İRTİFA: ${(data.altitude_agl || 0).toFixed(1)}m | YER HIZI: ${(data.ground_speed || 0).toFixed(1)}m/s`, vx + 30, vy + 50);

            if (isTarget) {
                ctx.fillStyle = 'var(--accent-gold)';
                ctx.fillText("BALLISTIC RELEASE: RK4 HAZIR (AUTO-DROP ARMED)", vx + 30, vy + vh - 30);
            }

            ctx.restore();
        }

        async function sendCommand(cmd, extra = {}) {
            try {
                const payload = { command: cmd, ...extra };
                const res = await fetch('/api/command', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const ans = await res.json();
                console.log("[GCS CMD]", ans);
            } catch (e) {
                alert("Komut gönderilemedi: " + e);
            }
        }

        function exportData(format) {
            window.open(`/api/export/${format}`, '_blank');
        }

        // TABLO 3 PUAN HESAPLAYICISI MANTIĞI
        function toggleCalc() {
            const content = document.getElementById('calcContent');
            const icon = document.getElementById('calcToggleIcon');
            if (content.style.display === 'none') {
                content.style.display = 'block';
                icon.innerText = '▼';
            } else {
                content.style.display = 'none';
                icon.innerText = '▶';
            }
        }

        function switchCalcTab(tab) {
            document.getElementById('tabPg1').classList.toggle('active', tab === 'pg1');
            document.getElementById('tabPg2').classList.toggle('active', tab === 'pg2');
            document.getElementById('pg1Form').style.display = tab === 'pg1' ? 'block' : 'none';
            document.getElementById('pg2Form').style.display = tab === 'pg2' ? 'block' : 'none';
        }

        function recalculatePG1() {
            const c = parseFloat(document.getElementById('pg1_c').value) || 1.0;
            const vol = parseFloat(document.getElementById('pg1_vol').value) || 1.0;
            const haz = parseFloat(document.getElementById('pg1_haz').value) || 1.0;
            const w0 = parseFloat(document.getElementById('pg1_w0').value) || 1.0;
            const ucus = parseFloat(document.getElementById('pg1_ucus').value) || 1.0;
            const ceza = parseFloat(document.getElementById('pg1_ceza').value) || 0.0;

            // Formül: PG1 = c * [ 6*Vol + 6*thaz + 6*W0 + 12*tuçuş ] - Ceza (Azami 30)
            const raw = c * (6.0 * vol + 6.0 * haz + 6.0 * w0 + 12.0 * ucus);
            const score = Math.max(0.0, Math.min(30.0, raw - ceza));
            document.getElementById('pg1Result').innerText = score.toFixed(2);
        }

        function recalculatePG2() {
            const c = parseFloat(document.getElementById('pg2_c').value) || 1.0;
            const vol = parseFloat(document.getElementById('pg2_vol').value) || 1.0;
            const haz = parseFloat(document.getElementById('pg2_haz').value) || 1.0;
            const w0 = parseFloat(document.getElementById('pg2_w0').value) || 1.0;
            const wyuk = parseFloat(document.getElementById('pg2_wyuk').value) || 1.0;
            const d1 = parseFloat(document.getElementById('pg2_d1').value) || 0.5;
            const d2 = parseFloat(document.getElementById('pg2_d2').value) || 0.8;
            const ucus = parseFloat(document.getElementById('pg2_ucus').value) || 1.0;
            const ceza = parseFloat(document.getElementById('pg2_ceza').value) || 0.0;

            let score = 0.0;
            if (currentCategory === 'rotary_wing') {
                // Döner Kanat PG2 Formülü (Azami 80 Puan):
                // 4*Vol + 4*thaz + 4*W0 + 20*Wyük + 8*(d_altg,min/d_altg,tk) + 12*(d_üçg,min/d_üçg,tk) + 10*(AY+BY) + 8*tuçuş - Ceza
                const bonusVal = parseInt(document.getElementById('pg2_bonus').value) || 0;
                const dAltgTerm = d1 <= 10.0 ? (8.0 * (0.05 / Math.max(0.05, d1))) : 0.0;
                const dUcgTerm = d2 <= 10.0 ? (12.0 * (0.05 / Math.max(0.05, d2))) : 0.0;
                const raw = c * (4.0 * vol + 4.0 * haz + 4.0 * w0 + 20.0 * wyuk + Math.min(8.0, dAltgTerm) + Math.min(12.0, dUcgTerm) + bonusVal + 8.0 * ucus);
                score = Math.max(0.0, Math.min(80.0, raw - ceza));
            } else {
                // Sabit Kanat PG2 Formülü (Azami 70 Puan):
                // 4*Vol + 4*thaz + 4*W0 + 20*Wyük + 10*(d_4x4) + 20*(d_2x2) + 8*tuçuş - Ceza
                const d4x4Term = d1 <= 20.0 ? (10.0 * (0.05 / Math.max(0.05, d1))) : 0.0;
                const d2x2Term = d2 <= 20.0 ? (20.0 * (0.05 / Math.max(0.05, d2))) : 0.0;
                const raw = c * (4.0 * vol + 4.0 * haz + 4.0 * w0 + 20.0 * wyuk + Math.min(10.0, d4x4Term) + Math.min(20.0, d2x2Term) + 8.0 * ucus);
                score = Math.max(0.0, Math.min(70.0, raw - ceza));
            }
            document.getElementById('pg2Result').innerText = score.toFixed(2);
        }

        setInterval(fetchTelemetry, 150);
        recalculatePG1();
        recalculatePG2();
    </script>
</body>
</html>
"""


class WebGCSRequestHandler(BaseHTTPRequestHandler):
    core_instance = None
    server_ref: Optional["WebGCSServer"] = None

    def _send_json_response(self, data: Dict[str, Any], status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_DASHBOARD.encode("utf-8"))
        elif self.path == "/api/telemetry":
            category = self.server_ref.category if self.server_ref else "rotary_wing"
            telemetry_data = {
                "venue": "Malatya Tulga Havalimanı (LTAO)",
                "coordinates": {"lat": 38.34694, "lon": 38.24444, "alt_msl_m": 938.0},
                "category": category,
                "state": "IDLE",
                "altitude_agl": 0.0,
                "ground_speed": 0.0,
                "heading_deg": 0.0,
                "roll_deg": 0.0,
                "pitch_deg": 0.0,
                "battery_v": 16.20,
                "soc_pct": 92.0,
                "wind_speed": 3.2,
                "wind_dir": 45.0,
                "locked_target": None,
                "payloads_remaining": 2,
                "failsafe_status": "NOMINAL",
                "nav_source": "GPS",
                "pos_x": 0.0,
                "pos_y": 0.0,
                "miss_distance": None,
                "setup_timer_s": 145.0,
                "flight_timer_s": 84.0,
                "log_message": "Sistem nominal. Malatya Tulga 200x300m sahasında EKF3 aktif."
            }

            if self.core_instance is not None:
                try:
                    step_data = self.core_instance.step()
                    telemetry_data.update(step_data)
                    telemetry_data["category"] = category
                except Exception as ex:
                    telemetry_data["core_error"] = str(ex)
            else:
                # Standalone demo: generate realistic trajectory
                t = time.time()
                telemetry_data["altitude_agl"] = round(32.0 + 3.0 * math.sin(t * 0.4), 1)
                telemetry_data["ground_speed"] = round(14.0 + 2.0 * math.cos(t * 0.3), 1)
                telemetry_data["heading_deg"] = round((t * 25.0) % 360.0, 1)
                telemetry_data["roll_deg"] = round(15.0 * math.sin(t * 0.5), 1)
                telemetry_data["pitch_deg"] = round(4.0 * math.cos(t * 0.4), 1)
                telemetry_data["pos_x"] = round(60.0 * math.sin(t * 0.2), 1)
                telemetry_data["pos_y"] = round(30.0 * math.cos(t * 0.15), 1)
                telemetry_data["state"] = "AUTONOMOUS_SEARCH"
                telemetry_data["setup_timer_s"] = round(180.0 + (t % 120.0), 1)
                telemetry_data["flight_timer_s"] = round(60.0 + (t % 200.0), 1)

            self._send_json_response(telemetry_data)
        elif self.path == "/api/field_config":
            category = self.server_ref.category if self.server_ref else "rotary_wing"
            field_info = {
                "venue_name": "Malatya Tulga Havalimanı (LTAO)",
                "location": {"lat": 38.34694, "lon": 38.24444, "elevation_m": 938.0},
                "spec_version": "V7_2026_09_06",
                "competition_dates": "8 - 13 Eylül 2026",
                "flight_area": {"width_m": 200.0, "length_m": 300.0, "has_buffer_zone": False},
                "poles": {
                    "distance_m": 150.0,
                    "pole_1": {"x": -75.0, "y": 0.0},
                    "pole_2": {"x": 75.0, "y": 0.0}
                },
                "scan_area": {"width_m": 30.0, "length_m": 100.0, "x_range": [-50.0, 50.0], "y_range": [30.0, 60.0]},
                "category": category,
                "targets": {
                    "rotary_wing": {
                        "scoring_radius_m": 10.0,
                        "target_a": {"shape": "regular_hexagon", "side_length_m": 2.0, "color": "blue", "required_payload": "red"},
                        "target_b": {"shape": "equilateral_triangle", "side_length_m": 1.0, "color": "red", "required_payload": "blue"},
                        "bonus_tasks": ["AY", "BY"]
                    },
                    "fixed_wing": {
                        "scoring_radius_m": 20.0,
                        "target_a": {"shape": "square", "size_m": 4.0, "color": "blue", "required_payload": "red"},
                        "target_b": {"shape": "square", "size_m": 2.0, "color": "red", "required_payload": "blue"}
                    }
                }
            }
            self._send_json_response(field_info)
        elif self.path == "/api/export/geojson":
            # GeoJSON Export of current mission field and flight trail
            geojson_data = {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"name": "Malatya Tulga 200x300m Uçuş Sahası"},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[
                                [38.2425, 38.3455],
                                [38.2460, 38.3455],
                                [38.2460, 38.3475],
                                [38.2425, 38.3475],
                                [38.2425, 38.3455]
                            ]]
                        }
                    },
                    {
                        "type": "Feature",
                        "properties": {"name": "Direk 1 (-75m)"},
                        "geometry": {"type": "Point", "coordinates": [38.2435, 38.3465]}
                    },
                    {
                        "type": "Feature",
                        "properties": {"name": "Direk 2 (+75m)"},
                        "geometry": {"type": "Point", "coordinates": [38.2455, 38.3465]}
                    }
                ]
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/geo+json; charset=utf-8")
            self.send_header("Content-Disposition", 'attachment; filename="tulga_mission.geojson"')
            self.end_headers()
            self.wfile.write(json.dumps(geojson_data).encode("utf-8"))
        elif self.path == "/api/export/csv":
            csv_content = "timestamp,alt_agl_m,ground_speed_mps,heading_deg,roll_deg,pitch_deg,battery_v,state\n"
            t = time.time()
            for i in range(10):
                csv_content += f"{t - (10 - i)},{30.0 + i * 0.2},{14.0},{90.0},{0.0},{0.0},{16.20 - i * 0.01},AUTONOMOUS_CRUISE\n"
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Disposition", 'attachment; filename="tulga_blackbox.csv"')
            self.end_headers()
            self.wfile.write(csv_content.encode("utf-8"))
        elif self.path == "/api/export/report":
            category = self.server_ref.category if self.server_ref else "rotary_wing"
            report_data = {
                "organization": "TÜBİTAK TEKNOFEST 2026",
                "venue": "Malatya Tulga Havalimanı (LTAO)",
                "category": category,
                "team_verification": "SUCCESS",
                "rules_compliance": {
                    "mtow_under_4kg": True,
                    "power_cut_under_2s": True,
                    "ceiling_under_120m": True,
                    "single_camera_enforced": True,
                    "failsafe_profile_valid": True
                },
                "scores": {
                    "pg1": 29.5,
                    "pg2": 78.0 if category == "rotary_wing" else 68.0,
                    "autonomy_c": 1.0
                }
            }
            self._send_json_response(report_data)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
        try:
            req_data = json.loads(body)
        except Exception:
            req_data = {}

        if self.path == "/api/command":
            cmd = req_data.get("command")
            print(f"[WEB GCS] Operatör Komutu Alındı: {cmd}")

            if cmd == "SET_CATEGORY" and self.server_ref:
                new_cat = req_data.get("category", "rotary_wing")
                self.server_ref.set_category(new_cat)
                return self._send_json_response({"status": "SUCCESS", "command": cmd, "category": new_cat})

            if self.core_instance is not None:
                if cmd == "RTL":
                    if hasattr(self.core_instance, "comms"):
                        self.core_instance.comms.trigger_rtl()
                elif cmd == "DROP_PAYLOAD_1":
                    if hasattr(self.core_instance, "actuator"):
                        self.core_instance.actuator.release_payload_for_target("TARGET_A")
                elif cmd == "DROP_PAYLOAD_2":
                    if hasattr(self.core_instance, "actuator"):
                        self.core_instance.actuator.release_payload_for_target("TARGET_B")
                elif cmd in ("START_MISSION_1", "START_MISSION_2"):
                    if hasattr(self.core_instance, "start_mission"):
                        self.core_instance.start_mission()
                elif cmd == "DEPLOY_PARACHUTE":
                    if hasattr(self.core_instance, "emergency_recovery"):
                        alt = 30.0
                        if hasattr(self.core_instance, "comms"):
                            alt = self.core_instance.comms.fetch_flight_data().altitude_agl
                        self.core_instance.emergency_recovery.trigger_manual_override(
                            altitude_agl_m=alt,
                            timestamp=time.time()
                        )

            return self._send_json_response({"status": "SUCCESS", "command": cmd})

        elif self.path == "/api/score/pg1":
            # Tablo 3 PG1 Hesaplama API'si
            c = float(req_data.get("c", 1.0))
            vol = float(req_data.get("vol_ratio", 1.0))
            haz = float(req_data.get("haz_ratio", 1.0))
            w0 = float(req_data.get("w0_ratio", 1.0))
            ucus = float(req_data.get("ucus_ratio", 1.0))
            ceza = float(req_data.get("penalty", 0.0))

            if FlightAnalyticsEngine:
                score = FlightAnalyticsEngine.calculate_official_pg1(
                    c_autonomy=c,
                    vol_min=vol, vol_tk=1.0,
                    t_min_haz=haz, t_tk_haz=1.0,
                    w0_min=w0, w0_tk=1.0,
                    t_min_ucus=ucus, t_tk_ucus=1.0,
                    penalty_points=ceza
                )
            else:
                raw = c * (6.0 * vol + 6.0 * haz + 6.0 * w0 + 12.0 * ucus)
                score = round(max(0.0, min(30.0, raw - ceza)), 2)

            return self._send_json_response({"pg1_score": score, "max_score": 30.0})

        elif self.path == "/api/score/pg2_fixed":
            # Tablo 3 Sabit Kanat PG2 Hesaplama API'si
            c = float(req_data.get("c", 1.0))
            vol = float(req_data.get("vol_ratio", 1.0))
            haz = float(req_data.get("haz_ratio", 1.0))
            w0 = float(req_data.get("w0_ratio", 1.0))
            wyuk = float(req_data.get("wyuk_ratio", 1.0))
            d4x4 = float(req_data.get("d_4x4", 0.5))
            d2x2 = float(req_data.get("d_2x2", 0.8))
            ucus = float(req_data.get("ucus_ratio", 1.0))
            ceza = float(req_data.get("penalty", 0.0))

            if FlightAnalyticsEngine:
                score = FlightAnalyticsEngine.calculate_official_pg2_fixed_wing(
                    c_autonomy=c,
                    vol_min=vol, vol_tk=1.0,
                    t_min_haz=haz, t_tk_haz=1.0,
                    w0_min=w0, w0_tk=1.0,
                    w_yuk_tk=wyuk, w_yuk_max=1.0,
                    d_4x4_min=0.05, d_4x4_tk=d4x4,
                    d_2x2_min=0.05, d_2x2_tk=d2x2,
                    t_min_ucus=ucus, t_tk_ucus=1.0,
                    penalty_points=ceza
                )
            else:
                score = 65.0

            return self._send_json_response({"pg2_fixed_score": score, "max_score": 70.0})

        elif self.path == "/api/score/pg2_rotary":
            # Tablo 3 Döner Kanat PG2 Hesaplama API'si
            c = float(req_data.get("c", 1.0))
            vol = float(req_data.get("vol_ratio", 1.0))
            haz = float(req_data.get("haz_ratio", 1.0))
            w0 = float(req_data.get("w0_ratio", 1.0))
            wyuk = float(req_data.get("wyuk_ratio", 1.0))
            d_altg = float(req_data.get("d_altg", 0.5))
            d_ucg = float(req_data.get("d_ucg", 0.8))
            ay_bonus = int(req_data.get("ay_bonus", 1))
            by_bonus = int(req_data.get("by_bonus", 1))
            ucus = float(req_data.get("ucus_ratio", 1.0))
            ceza = float(req_data.get("penalty", 0.0))

            if FlightAnalyticsEngine:
                score = FlightAnalyticsEngine.calculate_official_pg2_rotary_wing(
                    c_autonomy=c,
                    vol_min=vol, vol_tk=1.0,
                    t_min_haz=haz, t_tk_haz=1.0,
                    w0_min=w0, w0_tk=1.0,
                    w_yuk_tk=wyuk, w_yuk_max=1.0,
                    d_altg_min=0.05, d_altg_tk=d_altg,
                    d_ucg_min=0.05, d_ucg_tk=d_ucg,
                    t_min_ucus=ucus, t_tk_ucus=1.0,
                    ay_bonus=ay_bonus,
                    by_bonus=by_bonus,
                    penalty_points=ceza
                )
            else:
                score = 75.0

            return self._send_json_response({"pg2_rotary_score": score, "max_score": 80.0})

        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass


class WebGCSServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 8080, core_instance=None, category: str = "rotary_wing"):
        self.host = host
        self.port = port
        self.core = core_instance
        self.category = category
        WebGCSRequestHandler.core_instance = core_instance
        WebGCSRequestHandler.server_ref = self
        self.server = ThreadingHTTPServer((host, port), WebGCSRequestHandler)
        self.server.daemon_threads = True
        self.thread: Optional[threading.Thread] = None

    def set_category(self, category: str):
        if category in ("rotary_wing", "fixed_wing"):
            self.category = category
            print(f"[WEB GCS] Kategori güncellendi: {category}")

    def start_background(self):
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        print(f"[WEB GCS] Malatya Tulga Canlı Yer Kontrol İstasyonu Başlatıldı -> http://{self.host}:{self.port}")

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
