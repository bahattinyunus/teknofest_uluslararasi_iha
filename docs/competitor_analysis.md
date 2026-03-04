# 📊 Rakip Analizi ve Araştırma Raporu (UAV/İHA)

Bu rapor, TEKNOFEST Uluslararası İHA Yarışması kapsamında benzer ulusal ve uluslararası yarışmaları, kullanılan teknolojileri ve açık kaynaklı projeleri analiz eder.

---

## 1. Benzer Uluslararası Yarışmalar

### AUVSI SUAS (Student Unmanned Aerial Systems) - ABD
*   **Kapsam:** Dünyanın en prestijli otonom İHA yarışmalarından biridir.
*   **Görevler:** Otonom uçuş, engel sakınma (statik/dinamik), nesne tespiti/sınıflandırma, yük bırakma ve otomatik iniş.
*   **Öne Çıkan Özellik:** "Interoperability" (Birlikte Çalışabilirlik) sistemi ile yer istasyonu ve yarışma sunucusu arasında veri alışverişi zorunludur.
*   **Kaynak Kodlar:** [BYU AUVSI](https://github.com/byu-auvsi), [Missouri S&T SUAS](https://github.com/MissouriMRR/SUAS-2022).

### IMAV (International Micro Air Vehicle Conference and Flight Competition)
*   **Kapsam:** Hem kapalı hem açık alan görevlerine odaklanır.
*   **Görevler:** Labirent çözme, afet bölgesinde haritalama, hareketli platformdan kalkış/iniş.
*   **Kaynak Kodlar:** [AerialRobotics-IITK IMAV 2019](https://github.com/AerialRobotics-IITK/imav2019).

### MBZIRC (Mohamed Bin Zayed International Robotics Challenge) - BAE
*   **Kapsam:** Çok yüksek bütçeli ve karmaşık robotik sistemler (İHA + İKA + İDA).
*   **Görevler:** Hareketli hedefleri yakalama (Drone-to-Drone), duvar örme (hassas kontrol).
*   **Kaynak Kodlar:** [CTU-MRS MBZIRC 2020](https://github.com/ctu-mrs/mbzirc2020_ball_planner).

---

## 2. Benzer Yerel Yarışmalar (TEKNOFEST)

| Yarışma Adı | Odak Noktası | Teknik Gereksinim |
| :--- | :--- | :--- |
| **Savaşan İHA** | Hava-Hava Muharebesi | İt dalaşı, hedef kilitleme, hızlı görüntü işleme. |
| **Sürü İHA** | İşbirlikçi Robotik | Sürü algoritması, merkezi olmayan haberleşme. |
| **İHA Destekli İKA** | Karma Operasyonlar | İHA'dan keşif, İKA'ya yol tarifi, senkronizasyon. |

---

## 3. Açık Kaynaklı Teknoloji Yığını ve Kaynaklar

### Otopilot ve Yazılım Katmanları
*   **PX4 / ArduPilot:** Endüstri standardı açık kaynak otopilot yazılımları.
*   **ROS / ROS2:** Robotik işletim sistemi, modüler yapı için vazgeçilmez.
*   **MAVSDK / MAVLink:** İHA ile programatik haberleşme protokolleri.

### Görüntü İşleme / Yapay Zeka
*   **YOLO (You Only Look Once):** Real-time nesne tespiti için en popüler algoritma (v8 ve v10 güncel).
*   **OpenCV:** Geleneksel görüntü işleme algoritmaları için temel kütüphane.

### Önemli Repolar
*   **[aerial-autonomy-stack](https://github.com/JacopoPan/aerial-autonomy-stack):** ROS2, PX4 ve YOLO içeren hepsi bir arada otonom çözüm.
*   **[Teach-Repeat-Replan](https://github.com/HKUST-Aerial-Robotics/Teach-Repeat-Replan):** HKUST ekibinin gelişmiş otonom sürüş ve rota planlama sistemi.
*   **[Eflatun-IHA](https://github.com/sezer-muhammed/Eflatun-IHA):** TEKNOFEST Savaşan İHA kategorisinden yerel bir örnek.

---

## 4. Analiz ve Stratejik Çıkarımlar

1.  **Simülasyonun Önemi:** Başarılı takımların neredeyse tamamı (özellikle MBZIRC ve SUAS galipleri) Gazebo veya AirSim üzerinde binlerce saat simülasyon testi yapmaktadır.
2.  **Modüler Mimari:** ROS2 kullanımı, kodun taşınabilirliğini ve farklı sensörlerin (LiDAR, Stereo Kamera) entegrasyonunu kolaylaştırır.
3.  **Haberleşme Güvenliği:** Birlikte çalışabilirlik ve telemetri verilerinin sağlıklı iletimi, puanlamada kritik rol oynamaktadır.
