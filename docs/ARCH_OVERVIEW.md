# Sistem Mimarisi Derin Dalış

## Üst Düzey Vizyon
**UAV-Architect-Global** sistemi, **Observer-Executor** (Gözlemci-Yürütücü) modeli üzerine inşa edilmiştir. Yardımcı bilgisayar (Gözlemci), yüksek bant genişlikli verileri (video, LiDAR) işlerken, uçuş kontrol kartı (Yürütücü) gerçek zamanlı stabilizasyonu yönetir.

## Veri Akışı
1. **Sensörler** RAW verileri CPU/GPU'ya iletir.
2. **Yapay Zeka Çıkarımı** (YOLO) hedefleri belirler.
3. **Görev Mantığı**, yük bırakma parametrelerinin karşılanıp karşılanmadığını belirler.
4. **MavLink Komutları**, yunuslama/sapma (pitch/yaw) düzeltmeleri yapmak veya servoları tetiklemek için Pixhawk'a gönderilir.

## Entegrasyon Protokolleri
- **Baud Rate:** 57600/921600 (Mesafeye göre değişken).
- **Gecikme Hedefi:** Uçtan uca işleme için < 50ms.

---
*Hazırlayan: Bahattin Yunus Çetin*
