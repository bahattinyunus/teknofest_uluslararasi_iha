"""
TEKNOFEST 2026 Uluslararası İHA - Web Yer Kontrol İstasyonu Sunucusu (Web GCS)
------------------------------------------------------------------------------
Resmi TÜBİTAK TEKNOFEST 2026 İHA Şartnamesi (V7) ile Birebir Uyumlu:
- Yarışma Alanı: Malatya Tulga Havalimanı (38.34694° N, 38.24444° E, 938m MSL)
- 200x300m Uçuş Sahası (Tampon bölge yoktur)
- 150m Mesafeli Direkler (Direk 1 & Direk 2 - ∞ Figür-8 Parkuru)
- 30x100m Tarama ve Yük Bırakma Sahası
- Kategori Seçici / Geçişi (Sabit Kanat vs Döner Kanat)
  * Sabit Kanat: Hedef A (4x4m Mavi Kare -> Kırmızı Yük), Hedef B (2x2m Kırmızı Kare -> Mavi Yük), 20m Puanlama Çemberi
  * Döner Kanat: Hedef A (2m Kenar Mavi Düzgün Altıgen -> Kırmızı Yük), Hedef B (1m Kenar Kırmızı Üçgen -> Mavi Yük), 10m Puanlama Çemberi
- TÜBİTAK Tablo 3 Resmi PG1 ve PG2 Puanlama Hesaplayıcıları (c çarpanı, AY/BY bonusları)
- 120m AGL Üst İrtifa Sınırı ve 25 km/h Rüzgar Limiti Canlı Takibi
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import math
import threading
import time
from typing import Dict, Any, Optional

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
            --bg-dark: #070b14;
            --panel-bg: rgba(14, 23, 42, 0.92);
            --panel-card: rgba(22, 34, 60, 0.8);
            --border-glow: #00f2ff;
            --accent-cyan: #00f2ff;
            --accent-red: #ff3366;
            --accent-green: #00ff88;
            --accent-gold: #ffd700;
            --accent-purple: #a855f7;
            --text-main: #f1f5f9;
            --text-dim: #94a3b8;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, monospace, sans-serif; }
        body { background: var(--bg-dark); color: var(--text-main); min-height: 100vh; padding: 12px 18px; }
        
        /* HEADER */
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 2px solid var(--border-glow);
            padding-bottom: 12px;
            margin-bottom: 16px;
            background: linear-gradient(90deg, rgba(0,242,255,0.08) 0%, rgba(14,23,42,0) 100%);
            border-radius: 4px;
        }
        .header-title-box { display: flex; flex-direction: column; gap: 4px; }
        .logo { font-size: 20px; font-weight: 900; letter-spacing: 1.5px; color: var(--accent-cyan); text-shadow: 0 0 12px rgba(0,242,255,0.6); }
        .spec-tag { font-size: 11px; color: var(--text-dim); letter-spacing: 0.8px; }
        .venue-pill {
            background: rgba(168,85,247,0.18);
            border: 1px solid var(--accent-purple);
            color: #d8b4fe;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
            display: inline-flex;
            align-items: center;
            gap: 5px;
        }
        .header-controls { display: flex; align-items: center; gap: 12px; }
        .category-toggle {
            display: inline-flex;
            background: #0f172a;
            border: 1px solid #334155;
            border-radius: 8px;
            padding: 3px;
        }
        .cat-btn {
            background: transparent;
            border: none;
            color: var(--text-dim);
            padding: 6px 14px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        .cat-btn.active {
            background: var(--accent-cyan);
            color: #070b14;
            box-shadow: 0 0 10px rgba(0,242,255,0.5);
        }
        .badge {
            background: rgba(0,255,136,0.15);
            color: var(--accent-green);
            padding: 5px 12px;
            border-radius: 6px;
            border: 1px solid var(--accent-green);
            font-size: 12px;
            font-weight: 700;
            letter-spacing: 0.5px;
        }
        .clock-box { font-size: 12px; color: var(--text-dim); font-family: monospace; }

        /* GRID LAYOUT */
        .grid {
            display: grid;
            grid-template-columns: 310px 1fr 340px;
            gap: 16px;
        }
        @media (max-width: 1200px) {
            .grid { grid-template-columns: 1fr; }
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid rgba(0,242,255,0.22);
            border-radius: 10px;
            padding: 16px;
            box-shadow: 0 4px 24px rgba(0,0,0,0.6);
            backdrop-filter: blur(8px);
        }
        .panel h2 {
            font-size: 13px;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            color: var(--accent-cyan);
            margin-bottom: 12px;
            border-bottom: 1px solid rgba(255,255,255,0.08);
            padding-bottom: 6px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .panel h2 .sub { font-size: 10px; color: var(--text-dim); }

        /* METRICS & GAUGES */
        .tape-container { display: flex; justify-content: space-between; gap: 10px; margin: 10px 0; }
        .tape-box {
            flex: 1;
            text-align: center;
            background: rgba(0,0,0,0.45);
            padding: 8px 10px;
            border-radius: 6px;
            border-left: 3px solid var(--accent-cyan);
        }
        .tape-box.warning-limit { border-left-color: var(--accent-red); }
        .tape-num { font-size: 24px; font-weight: 800; color: var(--accent-cyan); font-family: monospace; }
        .tape-label { font-size: 10px; text-transform: uppercase; color: var(--text-dim); margin-top: 2px; }
        .metric-row { display: flex; justify-content: space-between; margin-bottom: 8px; font-size: 13px; }
        .metric-val { font-weight: 700; color: #fff; font-family: monospace; }

        /* PROGRESS BARS */
        .progress-bar-bg { width: 100%; height: 6px; background: #1e293b; border-radius: 3px; overflow: hidden; margin-top: 2px; margin-bottom: 10px; }
        .progress-bar-fill { height: 100%; background: var(--accent-cyan); width: 0%; transition: width 0.3s; }
        .progress-bar-fill.danger { background: var(--accent-red); }
        .progress-bar-fill.success { background: var(--accent-green); }

        /* ARTIFICIAL HORIZON */
        .horizon-box {
            text-align: center;
            margin: 10px 0 14px 0;
            background: #000;
            border-radius: 6px;
            border: 1px solid #334155;
            position: relative;
            height: 130px;
            overflow: hidden;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .horizon-ladder {
            position: absolute;
            width: 120px;
            height: 2px;
            background: var(--accent-green);
            box-shadow: 0 0 8px var(--accent-green);
            transition: transform 0.08s linear;
        }
        .horizon-center { width: 10px; height: 10px; border: 2px solid var(--accent-gold); border-radius: 50%; z-index: 2; }

        /* FAILSAFE BANNER */
        .failsafe-banner {
            background: rgba(255,51,102,0.12);
            border: 1px solid rgba(255,51,102,0.4);
            border-radius: 6px;
            padding: 8px 10px;
            font-size: 11px;
            line-height: 1.4;
            color: #fca5a5;
            margin-top: 10px;
        }
        .failsafe-banner strong { color: var(--accent-red); }

        /* RADAR / MAP CANVAS */
        .radar-card { position: relative; background: #040711; border-radius: 8px; border: 1px solid #1e293b; overflow: hidden; }
        #radarCanvas { width: 100%; height: 420px; display: block; background: #030610; }
        .map-legend {
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
            justify-content: space-between;
            margin-top: 10px;
            padding: 8px 12px;
            background: rgba(0,0,0,0.3);
            border-radius: 6px;
            font-size: 11px;
        }
        .legend-item { display: inline-flex; align-items: center; gap: 6px; }
        .legend-dot { width: 10px; height: 10px; border-radius: 2px; display: inline-block; }

        /* BUTTONS */
        .btn-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 12px; }
        button {
            background: rgba(0,242,255,0.08);
            border: 1px solid var(--accent-cyan);
            color: #fff;
            padding: 8px 12px;
            border-radius: 6px;
            cursor: pointer;
            font-weight: 700;
            transition: all 0.2s;
            font-size: 11px;
            text-align: center;
        }
        button:hover {
            background: var(--accent-cyan);
            color: #070b14;
            box-shadow: 0 0 12px rgba(0,242,255,0.5);
        }
        button.btn-danger {
            border-color: var(--accent-red);
            background: rgba(255,51,102,0.12);
            color: var(--accent-red);
        }
        button.btn-danger:hover { background: var(--accent-red); color: #fff; box-shadow: 0 0 12px rgba(255,51,102,0.6); }
        button.btn-success {
            border-color: var(--accent-green);
            background: rgba(0,255,136,0.12);
            color: var(--accent-green);
        }
        button.btn-success:hover { background: var(--accent-green); color: #070b14; }

        /* SCORE CALCULATOR CARD */
        .calc-panel {
            margin-top: 14px;
            background: rgba(15, 23, 42, 0.95);
            border: 1px solid rgba(255,215,0,0.3);
            border-radius: 8px;
            padding: 12px;
        }
        .calc-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            cursor: pointer;
            color: var(--accent-gold);
            font-size: 12px;
            font-weight: 800;
            letter-spacing: 1px;
        }
        .calc-content { margin-top: 10px; font-size: 11px; }
        .calc-tabs { display: flex; gap: 6px; margin-bottom: 8px; }
        .calc-tab {
            flex: 1;
            padding: 5px;
            background: #1e293b;
            border: 1px solid #334155;
            color: var(--text-dim);
            font-size: 10px;
            border-radius: 4px;
            text-align: center;
            cursor: pointer;
        }
        .calc-tab.active { background: var(--accent-gold); color: #000; font-weight: bold; border-color: var(--accent-gold); }
        .calc-row { display: grid; grid-template-columns: 1fr 70px; gap: 8px; align-items: center; margin-bottom: 5px; }
        .calc-row input, .calc-row select {
            background: #0b1120;
            border: 1px solid #334155;
            color: #fff;
            padding: 3px 6px;
            border-radius: 4px;
            font-size: 11px;
            font-family: monospace;
            text-align: right;
        }
        .calc-result-box {
            margin-top: 10px;
            padding: 8px;
            background: rgba(0,0,0,0.4);
            border-radius: 6px;
            border-left: 3px solid var(--accent-gold);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .calc-result-val { font-size: 18px; font-weight: 900; color: var(--accent-gold); font-family: monospace; }
    </style>
</head>
<body>
    <header>
        <div class="header-title-box">
            <div class="logo">🛸 TEKNOFEST 2026 | MALATYA TULGA GCS</div>
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
        <!-- SOL PANEL: Uçuş Telemetrisi & Enstrümanlar -->
        <div class="panel">
            <h2>UÇUŞ ENSTRÜMANLARI <span class="sub">120m AGL & 25 km/h LİMİT</span></h2>
            
            <div class="tape-container">
                <div class="tape-box" id="altBox">
                    <div class="tape-num" id="altVal">0.0</div>
                    <div class="tape-label">İRTİFA (AGL m)</div>
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
                <span class="metric-val" id="windVal">0.0 m/s (0.0 km/h) @ 0°</span>
            </div>
            <div class="metric-row">
                <span>Batarya (4S LiPo):</span>
                <span class="metric-val" id="batVal" style="color:var(--accent-green)">16.20 V (90%)</span>
            </div>
            <div class="metric-row">
                <span>Aviyonik / FDIR:</span>
                <span class="metric-val" id="fsVal">NOMİNAL / GPS</span>
            </div>
            <div class="metric-row">
                <span>MTOW / Yük Sınırı:</span>
                <span class="metric-val" id="mtowVal">3.65 kg / ≤ 4.0 kg ✅</span>
            </div>

            <!-- Failsafe Profili Açıklaması -->
            <div class="failsafe-banner" id="failsafeInfo">
                <strong>V7 ARALIKSIZ FAIL-SAFE KURALI:</strong><br>
                <span id="failsafeDetail">Döner Kanat: Yarım gaz kontrollü alçalma. RTL kesinlikle YASAKTIR!</span>
            </div>
        </div>

        <!-- ORTA PANEL: Taktik Saha, 200x300m Alan, 150m Direkler & Tarama Bölgesi -->
        <div class="panel">
            <h2>
                <span>TAKTIK UÇUŞ SAHASI (MALATYA TULGA)</span>
                <span class="sub" id="fieldDimensions">200m x 300m SAHA | 150m DİREK MESAFESİ</span>
            </h2>
            <div class="radar-card">
                <canvas id="radarCanvas" width="700" height="420"></canvas>
            </div>
            <div class="map-legend">
                <div class="legend-item">
                    <span class="legend-dot" style="background:var(--accent-purple)"></span>
                    <span>200x300m Uçuş Sahası</span>
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
                    <span id="legendTargetA">Hedef A (Mavi Altıgen)</span>
                </div>
                <div class="legend-item">
                    <span class="legend-dot" style="background:#ff3366"></span>
                    <span id="legendTargetB">Hedef B (Kırmızı Üçgen)</span>
                </div>
                <div class="legend-item">
                    <span class="legend-dot" style="background:#ffd700"></span>
                    <span>İHA Konumu & Yönü</span>
                </div>
            </div>
            <div style="display:flex; justify-content:space-between; margin-top:8px; font-size:12px; color:var(--text-dim);">
                <span>Hedef Kilidi: <b id="lockStatus" style="color:var(--accent-gold)">YOK</b></span>
                <span>Hedefe Kalan Sapma: <b id="missVal" style="color:var(--accent-cyan)">---</b></span>
                <span>Puanlama Çemberi: <b id="scoreRadiusLabel">10m Yarıçap</b></span>
            </div>
        </div>

        <!-- SAĞ PANEL: Görev Komutları & Tablo 3 Hesaplayıcı -->
        <div class="panel">
            <h2>2026 GÖREV VE YÜK YÖNETİMİ</h2>
            
            <div class="metric-row">
                <span>Kalan Yük Sayısı:</span>
                <span class="metric-val" id="payloadVal" style="font-size:18px; color:var(--accent-gold)">2</span>
            </div>
            <div class="metric-row">
                <span>Hedef A Yükü (Kırmızı):</span>
                <span class="metric-val" id="slot1Val" style="color:var(--accent-green)">HAZIRDA (ARMED)</span>
            </div>
            <div class="metric-row">
                <span>Hedef B Yükü (Mavi):</span>
                <span class="metric-val" id="slot2Val" style="color:var(--accent-green)">HAZIRDA (ARMED)</span>
            </div>

            <div class="btn-grid">
                <button onclick="sendCommand('START_MISSION_1')">∞ 1. GÖREV (150m DİREK)</button>
                <button onclick="sendCommand('START_MISSION_2')">🎯 2. GÖREV (TARAMA)</button>
                <button onclick="sendCommand('DROP_PAYLOAD_1')">🔴 1. YÜKÜ BIRAK (A)</button>
                <button onclick="sendCommand('DROP_PAYLOAD_2')">🔵 2. YÜKÜ BIRAK (B)</button>
                <button id="rtlBtn" class="btn-danger" onclick="sendCommand('RTL')">🏠 OTONOM RTL</button>
                <button class="btn-danger" onclick="sendCommand('DEPLOY_PARACHUTE')">🚨 ACİL FTS / PARAŞÜT</button>
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

    <script>
        let currentCategory = 'rotary_wing';
        let uavPos = { x: 0, y: 0, heading: 0, alt: 0, spd: 0 };
        const canvas = document.getElementById('radarCanvas');
        const ctx = canvas.getContext('2d');

        function updateClock() {
            document.getElementById('clock').innerText = new Date().toLocaleTimeString();
        }
        setInterval(updateClock, 1000);

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

                // Göstergeleri güncelle
                document.getElementById('stateBadge').innerText = data.state || 'IDLE';
                const alt = data.altitude_agl || 0;
                const spd = data.ground_speed || 0;
                document.getElementById('altVal').innerText = alt.toFixed(1);
                document.getElementById('spdVal').innerText = spd.toFixed(1);

                // 120m AGL Üst İrtifa Denetimi
                const altPct = Math.min(100, (alt / 120.0) * 100);
                const altBar = document.getElementById('altBar');
                altBar.style.width = altPct + '%';
                if (alt > 120.0) {
                    altBar.className = 'progress-bar-fill danger';
                    document.getElementById('altBox').className = 'tape-box warning-limit';
                } else {
                    altBar.className = 'progress-bar-fill';
                    document.getElementById('altBox').className = 'tape-box';
                }

                // 25 km/h Rüzgar Limiti
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

                document.getElementById('attVal').innerText = (data.roll_deg || 0).toFixed(1) + '° / ' + (data.pitch_deg || 0).toFixed(1) + '°';
                document.getElementById('hdgVal').innerText = (data.heading_deg || 0).toFixed(1) + '°';
                document.getElementById('batVal').innerText = (data.battery_v || 0).toFixed(2) + ' V (' + (data.soc_pct || 90).toFixed(0) + '%)';
                document.getElementById('fsVal').innerText = (data.failsafe_status || 'NOMİNAL') + ' / ' + (data.nav_source || 'GPS');
                document.getElementById('payloadVal').innerText = data.payloads_remaining ?? 2;
                document.getElementById('lockStatus').innerText = data.locked_target || 'YOK';

                const miss = data.miss_distance;
                if (miss !== undefined && miss < 100) {
                    const maxR = currentCategory === 'rotary_wing' ? 10.0 : 20.0;
                    const inside = miss <= maxR;
                    document.getElementById('missVal').innerText = miss.toFixed(2) + ' m ' + (inside ? '✅' : '❌ DIŞINDA');
                } else {
                    document.getElementById('missVal').innerText = '---';
                }

                // Suni ufuk
                const roll = data.roll_deg || 0;
                const pitch = data.pitch_deg || 0;
                document.getElementById('horizonBar').style.transform = `rotate(${-roll}deg) translateY(${pitch * 1.5}px)`;

                // UAV Pozisyonu ve Radar Çizimi
                uavPos.x = data.pos_x || (data.nav_x || 0);
                uavPos.y = data.pos_y || (data.nav_y || 0);
                uavPos.heading = data.heading_deg || 0;
                uavPos.alt = alt;
                uavPos.spd = spd;

                drawTacticalMap(data);
            } catch (e) {
                console.error(e);
            }
        }

        function drawTacticalMap(data) {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            const w = canvas.width;
            const h = canvas.height;
            const cx = w / 2;
            const cy = h / 2;

            // 200m x 300m Saha Ölçeklemesi (Canvas'a göre yaklaşık 1m = 1.1px)
            const scale = Math.min(w / 340, h / 240); // 300m uzunluk x eksenine, 200m genişlik y eksenine

            ctx.save();
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

            // 2. 200x300m Uçuş Sahası Sınırı (Madde 7: 200m En x 300m Boy)
            ctx.strokeStyle = '#a855f7';
            ctx.lineWidth = 2;
            ctx.strokeRect(-150 * scale, -100 * scale, 300 * scale, 200 * scale);

            ctx.fillStyle = '#a855f7';
            ctx.font = '10px monospace';
            ctx.fillText("UÇUŞ SAHASI (200m x 300m) - TAMPON BÖLGE YOKTUR", -145 * scale, -105 * scale);

            // 3. 150m Mesafeli Direkler (∞ Figür-8 Parkuru)
            // Direk 1: x = -75m, Direk 2: x = +75m
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
            ctx.font = 'bold 10px monospace';
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
            ctx.fillText("150m DİREK MESAFESİ", -45, 15);

            // 4. 30x100m Tarama Sahası (Scan Zone)
            // Konum: x: [-50m, +50m], y: [25m, 55m] -> 100m x 30m
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
            ctx.font = '10px monospace';
            ctx.fillText("TARAMA SAHASI (30m x 100m)", szX + 10, szY + 18);

            // 5. Hedefler & Puanlama Çemberleri (Kategoriye Göre)
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
                const hexR = 2.0 * scale * 2.5; // Görsellik için hafif vurgulu
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
                const triR = 1.5 * scale * 2.5;
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

            // 6. İHA Sembolü ve Yönü (Real-time Pozisyon)
            const ux = uavPos.x * scale;
            const uy = -uavPos.y * scale; // Haritada +y yukarı
            ctx.save();
            ctx.translate(ux, uy);
            ctx.rotate((uavPos.heading || 0) * Math.PI / 180);

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
        self.wfile.write(json.dumps(data).encode("utf-8"))

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
                "miss_distance": None
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
        self.server = HTTPServer((host, port), WebGCSRequestHandler)
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
