![Teknofest 2026 UAV Banner](assets/banner.png)

# 🛸 UAV-ARCHITECT-GLOBAL: ELİT KOMUTA MERKEZİ
### *Uluslararası İHA ve Otonom Sistemler Stratejik Mimarisi*

<div align="center">

![TEKNOFEST 2026](https://img.shields.io/badge/TEKNOFEST-2026-EE1C25?style=for-the-badge&logo=rocket&logoColor=white)
![Kategori](https://img.shields.io/badge/KATEGORİ-ULUSLARARASI_İHA-00F2FF?style=for-the-badge&logo=airbus&logoColor=white)
![Durum](https://img.shields.io/badge/GÖREV-HAZIR-00FF41?style=for-the-badge&logo=statuspage&logoColor=white)
![Mimari](https://img.shields.io/badge/MİMARİ-ELİT-blueviolet?style=for-the-badge&logo=azure-artifacts&logoColor=white)

---

"Göklerin otonom geleceği, mükemmel bir mimari ile başlar."

[2026 Görev Şartnamesi](docs/2026_SPEC_REQUIREMENTS.md) • [Sistem Mimarisi](docs/ARCH_OVERVIEW.md) • [Rakip Analizi](docs/competitor_analysis.md)

</div>

---

**UAV-Architect-Global**, sadece bir yazılım koleksiyonu değil; 2026 TEKNOFEST standartlarında karmaşık görevleri yöneten **Yüksek Performanslı bir Stratejik Mimari Rehberidir**.

### ⚡ 2026 Mission Dashboard
| Özellik | Detay |
| :--- | :--- |
| **Hedef Tespiti** | YOLOv10 + OpenCV Geometrik Analiz |
| **Yük Mekanizması** | Dual-Color Hassas Bırakma Sistemi |
| **Teknik Kısıt** | Max 4kg / 8 Dakika Kurulum Süresi |
| **Mimari** | Observer-Executor (Jetson + Pixhawk) |

---

## � GÖREV STRATEJİSİ (MISSION STRATEGY)

2026 şartnamesindeki dual-payload (çift yük) ve farklı geometrik hedefler (altıgen/üçgen) için geliştirilen strateji üç ana aşamadan oluşur:

1.  **Geniş Alan Taraması (Wide-Scan):** İHA, belirlenen irtifada (AGL 30-50m) GPS tabanlı otonom rota izleyerek hedef alanını tarar.
2.  **Hassas Kilitlenme (Precision Lock):** Hedef tespit edildiğinde (YOLOv10), İHA "Visual Servoing" moduna geçer. Kamera verisi kullanılarak hedef dikey eksende merkezlenir.
3.  **Dinamik Bırakma (Dynamic Drop):** İrtifa ve anlık hız verileri kullanılarak `core.py` içerisindeki balistik şablon tetiklenir ve servo mekanizması aktive edilir.

---

## 💻 GELİŞMİŞ TEKNOLOJİ YIĞINI

| Katman | Teknoloji | Amaç |
| :--- | :--- | :--- |
| **Donanım** | NVIDIA Jetson Orin Nano | Kenar (Edge) Yapay Zeka İşleme |
| **Uçuş Kontrol** | Pixhawk 6C + ArduPilot | Gerçek Zamanlı Stabilizasyon |
| **Algılama** | YOLOv10 + TensorRT | Gerçek Zamanlı Nesne Tespiti (60+ FPS) |
| **Haberleşme** | MAVLink + Micro-ROS | Güvenilir Veri Senkronizasyonu |
| **Simülasyon** | Gazebo / AirSim | Risk Bilgisiz Test Ortamı |

---

## �🇺🇸 GENEL BAKIŞ

**UAV-Architect-Global**, uçtan uca karmaşık İHA görevlerini yönetmek için tasarlanmış yüksek performanslı bir **Sistem Mimari Rehberidir**. İHA'yı bir "Uçan Sunucu" (Flying Server) olarak ele alır; gelişmiş yapay zeka çıkarımlarını güvenilir uçuş kontrol protokolleriyle entegre eder.

### 🏗️ Ana Mimari
Depo, maksimum modülerlik için "Elit Çekirdek" yapısında kurgulanmıştır:
- **`src/main_brain/`**: Yapay zeka görev mantığı ve karar alma.
- **`src/telemetry/`**: Yer Kontrol İstasyonu (GCS) ve MavLink haberleşme köprüsü.
- **`src/avionics/`**: Donanım soyutlama ve acil durum protokolleri.

---

## 📊 SİSTEM ENTEGRASYON AKIŞI

```mermaid
graph LR
    subgraph "VERİ EDİNİMİ"
        CAM[4K Kamera] -- CSI/USB --> GPU[NVIDIA Jetson]
        SEN[IMU/Baro] -- Dahili Veri Yolu --> FC[Uçuş Kontrol Kartı]
    end

    subgraph "ZEKA KATMANI"
        GPU -- "YOLOv10 / TensorRT" --> AI[Nesne Tespiti]
        AI -- "Görev Mantığı" --> DEC[Karar Mekanizması]
    end

    subgraph "EYLEM VE TELEMETRİ"
        DEC -- MavLink --> FC
        FC -- PWM --> PWM[Motorlar/Servolar]
        FC -- RF --> GCS[Yer Kontrol İstasyonu]
    end

    style GPU fill:#76B900,stroke:#333,stroke-width:2px
    style FC fill:#FF4B4B,stroke:#333,stroke-width:2px
    style GCS fill:#00A4EF,stroke:#333,stroke-width:2px
```

---

## 🛠️ DEPO YAPISI (PROJE MİMARİSİ)

```text
├── .github/                # Issue ve PR şablonları
├── assets/                 # Yüksek çözünürlüklü görseller
├── docs/                   # Teknik dokümanlar
│   ├── 2026_SPEC_REQUIREMENTS.md # 2026 Kuralları ve Hedefleri
│   ├── ARCH_OVERVIEW.md    # Sistem Mimari Detayları
├── src/                    # "Elit Çekirdek" kaynak kodlar
│   ├── main_brain/        # Yapay Zeka ve Görev Mantığı
│   ├── telemetry/         # Haberleşme Merkezi
│   └── avionics/          # Donanım Kontrol
├── CONTRIBUTING.md         # Katkı sağlama rehberi
├── LICENSE                 # MIT Lisansı
└── README.md               # Komuta Merkezi
```

---

## 🚀 BAŞLARKEN (HIZLI BAŞLANGIÇ)

### 1. Mimariyi Klonlayın
```bash
git clone https://github.com/bahattinyunus/teknofest_uluslararasi_iha.git
cd teknofest_uluslararasi_iha
```

### 2. Bağımlılıkları Kurun
Sistemin çalışması için OpenCV ve MAVProxy gereklidir:
```bash
pip install opencv-python numpy pymavlink
```

### 3. Simülasyon Testi
SITL (Software In The Loop) modunda çalıştırmak için:
```bash
python -m src.main_brain.core --mode simulation
```

---

## 🛠️ GELİŞTİRİCİ DENEYİMİ (DX) & HATA AYIKLAMA

Proje, geliştiricilerin sistemi hızlıca debug edebilmesi için gelişmiş loglama ve görselleştirme araçları sunar:

-   **Log Sistemi:** `logs/` dizini altında her uçuş için detaylı telemetri kayıtları tutulur.
-   **Kamera Testi:** `scripts/camera_check.py` ile görüntü işleme pipeline'ı uçuş yapmadan test edilebilir.
-   **MavLink Görüntüleyici:** `telemetry/visualizer.py` ile anlık paket akışı izlenebilir.

---

## 👨‍💻 GELİŞTİRİCİ PROFİLİ

### **Bahattin Yunus Çetin**
*BT Mimarı Adayı | Havacılık Vizyoneri*

*   🌍 **Konum:** Trabzon, Türkiye
*   🔗 **LinkedIn:** [linkedin.com/in/bahattinyunus](https://www.linkedin.com/in/bahattinyunus/)
*   💻 **GitHub:** [github.com/bahattinyunus](https://github.com/bahattinyunus)
*   📧 **İletişim:** [E-posta Gönder](mailto:bahattinyunuscetin@gmail.com)

---

<div align="center">

*“Otonom uçuş, özgürlüğün kodlanmış halidir.”*

**© 2026 Bahattin Yunus Çetin. Of, Trabzon.**


</div>
<p align="center">
  <img src="https://img.shields.io/badge/Powered%20By-TEKNOFEST-red?style=for-the-badge&logo=rocket&logoColor=white" alt="TEKNOFEST Support">
</p>
