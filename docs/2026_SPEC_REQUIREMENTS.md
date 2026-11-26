# 🛸 TÜBİTAK TEKNOFEST 2026 Uluslararası İHA Yarışması V7 Şartname Analizi ve Sistem Gereksinimleri

> **Resmi Kaynak:** TÜBİTAK TEKNOFEST 2026 İHA Yarışmaları Şartnamesi (Versiyon 7 / V2 Güncellemesi)  
> **Konum / Tesis:** Malatya Tulga Havalimanı (LTAO / Tulga Kışlası)  
> **Koordinatlar:** $38.34694^\circ\text{ N}, 38.24444^\circ\text{ E}$, Rakım: $\sim 938\text{m MSL}$  
> **Yarışma Tarihleri:** 8 – 13 Eylül 2026 | **Ödül Töreni:** 30 Eylül – 4 Ekim 2026  
> **Kapsam:** Sabit Kanat ve Döner Kanat Uluslararası İHA Kategorileri  
> **Durum:** Tam Uyum ve Sistem Mühendisliği Doğrulama Spesifikasyonu

---

## 📑 İçindekiler
1. [Genel Yarışma Parametreleri ve Sayısal Sınırlar](#1-genel-yarışma-parametreleri-ve-sayısal-sınırlar)
2. [Saha Yerleşimi ve Malatya Tulga Koordinasyon Mimarisi](#2-saha-yerleşimi-ve-malatya-tulga-koordinasyon-mimarisi)
3. [Muhafaza Kutusu (Storage Box) Tasarım Kriterleri](#3-muhafaza-kutusu-storage-box-tasarım-kriterleri)
4. [Süre Sınırları, Hazırlık ve Ek Müdahale Cezaları](#4-süre-sınırları-hazırlık-ve-ek-müdahale-cezaları)
5. [Aviyonik, Kamera, Emniyet ve Fail-Safe Kontrol Profilleri](#5-aviyonik-kamera-emniyet-ve-fail-safe-kontrol-profilleri)
6. [Görev Tanımları ve Uçuş Rotaları](#6-görev-tanımları-ve-uçuş-rotaları)
7. [Görüntü İşleme, Hedef Tanımları ve Balistik Bırakma](#7-görüntü-işleme-hedef-tanımları-ve-balistik-bırakma)
8. [Resmi Puanlama Sistemi (Tablo 2 ve Tablo 3 Formülleri)](#8-resmi-puanlama-sistemi-tablo-2-ve-tablo-3-formülleri)
9. [Ceza Puanları, İhlaller ve Elenme (Diskalifiye) Kriterleri](#9-ceza-puanları-ihlaller-ve-elenme-diskalifiye-kriterleri)
10. [Uçuş Öncesi Teknik Kontrol ve SHGM Denetim Matrisi](#10-uçuş-öncesi-teknik-kontrol-ve-shgm-denetim-matrisi)

---

## 1. Genel Yarışma Parametreleri ve Sayısal Sınırlar

| Parametre | Değer / Kısıt | Şartname Maddesi / Açıklama |
| :--- | :--- | :--- |
| **Yarışma Konumu** | Malatya Tulga Havalimanı (LTAO) | $38.34694^\circ\text{ N}, 38.24444^\circ\text{ E}$, Rakım: $938\text{m MSL}$ |
| **Yarışma Tarihleri** | 8 – 13 Eylül 2026 | Uçuşlar ve saha değerlendirmeleri; Ödül Töreni: 30 Eylül – 4 Ekim 2026 |
| **Azami Kalkış Ağırlığı (MTOW)** | **$\le 4.0\text{ kg}$** | Sabit ve Döner Kanat için yükler dahil üst ağırlık sınırı (§9.3.1) |
| **Üst İrtifa Limiti (Ceiling)** | **$120\text{ m}$ AGL** | SHGM mevzuatı tavan sınırı; ihlali derhal kırım/diskalifiye (§8.3.1) |
| **Alt İrtifa Limiti** | Yere temas etmemek kaydıyla serbest | Tamamen otonom/manuel irtifa yönetimi serbestisi (§8.3.1) |
| **Meteorolojik Rüzgâr Limiti** | **$25\text{ km/h}$** ($6.94\text{ m/s}$) | Rüzgâr hızı eşik değeri aşıldığında hakem heyeti uçuşları durdurur (§8.3) |
| **Referans Direkleri Arası Mesafe** | **$150\text{ m}$** | 1. ve 2. pylon arası merkez eksen açıklığı (§8.3.1) |
| **Hedef Tarama Alanı** | **$30\text{ m} \times 100\text{ m}$** | 2. direğin dışından dönüldükten sonra başlanan tespit koridoru (§8.3.1) |
| **Tampon Bölge** | **Bulunmamaktadır** | Tarama sahasında güvenlik tamponu tahsis edilmemiştir (§8.3.1) |
| **Uçuş Alanı Boyutları** | **$200\text{ m} \times 300\text{ m}$** | Genel uçuş ve güvenlik sahası ölçüleri |
| **Uçuş Hakkı** | **En fazla 4 deneme** | Görev 1 ve Görev 2 için takıma tanınan toplam uçuş hakkı (§8.3.1) |
| **Puanlama Esası** | Her görev için en yüksek puan | 4 haktan ilgili görevde alınan en yüksek skor baz alınır (§8.3.1) |
| **Saha Takım Kotası** | En fazla 4 üye | Pilot, GCS operatörü ve 2 teknisyen (Danışmanlar sahaya giremez) (§8.3.1) |

---

## 2. Saha Yerleşimi ve Malatya Tulga Koordinasyon Mimarisi

Uçuş alanı, Malatya Tulga Havalimanı sahasında $200\text{m} \times 300\text{m}$ genişliğindeki uçuş koridorunda yapılandırılmıştır.

```
       [ 150m Eksen ]
 (Direk 1) ------------------------ (Direk 2)
    |                                   |
    |  <----- Uçuş Koridoru ----->      |  ===> 2. Direk Dış Dönüşü
    |                                   |
[Kalkış / İniş Çizgisi]             [Tarama Alanı: 30m x 100m]
                                    Hedef A & Hedef B Konumları
```

### Saha Geometrisi Kuralları
1. **İki Direk Arası Mesafe (150m):** İki pylon arasındaki mesafe 150 metre olarak sabitlenmiştir. Sabit ve döner kanat araçları dönüş manevralarında direkleri dışarıdan dolaşmak zorundadır.
2. **2. Direk Dış Dönüş Zorunluluğu:** Görev 2'de hedef arama koridoruna girmeden önce hava aracının 2. direği mutlaka dışarıdan katetmesi mecburidir. Direği içten dönen takımlara **Ceza Puanı 2** ($0-10$ puan) tatbik edilir.
3. **Tarama Alanı ($30\text{m} \times 100\text{m}$):** Hakemler tarafından uçuş öncesinde 30m × 100m sınırları içerisine hedefler rastgele yerleştirilir. Dönüş pylonlarına yakın alanlara hedef konulmaz.

---

## 3. Muhafaza Kutusu (Storage Box) Tasarım Kriterleri

Araçlar uçuş alanına montajsız ve kapalı kutu içerisinde getirilmek zorundadır (§8.3.4):

```
       SABİT KANAT                            DÖNER KANAT
   [Silindirik Geometri]               [Dikdörtgen/Kare Prizma]
       .---------.                            .---------.
      /           \                          /         /|
     |             |                        +---------+ |
     |             |  h                     |         | | c
     |             |                        |         | /
      \           /                         +---------+
       '---------'                               a    b
          D = 2r
   Vol = pi * r^2 * h                       Vol = a * b * c
```

### Kutu Özellikleri ve Kısıtlamaları
- **Sabit Kanat:** Dairesel kesitli **Silindirik** kutu zorunludur. Kesit kesinlikle elips olamaz.
  $$\text{Vol}_{tk} = \pi \cdot r^2 \cdot h = \pi \cdot \left(\frac{D}{2}\right)^2 \cdot h$$
- **Döner Kanat:** **Dikdörtgen veya Kare Prizma** kutu zorunludur.
  $$\text{Vol}_{tk} = a \cdot b \cdot c$$
- **Hacim Hesabı Kriteri:** Kutunun en dış ölçüleri esas alınır. Tutma sapı, kulp ve tekerlek gibi taşıma aparatları kutu hacmine **dahil edilmez**.
- **İçerik Kuralı:** İHA gövdesi, kanatlar, pervaneler, faydalı yükler ve bataryalar kutunun içinde yer almalıdır. Yalnızca Yer Kontrol İstasyonu (GCS) bilgisayarı ve pilot RC kumandası kutu dışındadır.
- **Harici Parça İhlali:** Muhafaza kutusunda yer almayan ve sahada araca sonradan eklendiği tespit edilen parçalar için takıma **0 ila 5 puan Ceza Puanı 1** verilir (§8.3.4).

---

## 4. Süre Sınırları, Hazırlık ve Ek Müdahale Cezaları

| Aşama | Azami Süre | Kural ve Yaptırım |
| :--- | :--- | :--- |
| **Kurulum Süresi ($t_{tk,haz}$)** | **$\le 8$ Dakika** | Hakemin "Başla" komutuyla başlar, pilotun "Hazırız" beyanıyla biter. Aşan takım uçuş hakkını kaybeder (§8.3.5). |
| **Uçuşa Hazırlık Süresi** | **$\le 8$ Dakika** | GPS lock, telemetri eşleşmesi, sensör kalibrasyonu ve motor arm hazırlığı (§8.3.5). |
| **Görev 1 Uçuş Süresi ($t_{tk,uçuş}$)** | **$\le 5$ Dakika** | Başlangıç çizgisinden hareketle başlar, bitiş çizgisini geçince durur. Süre aşımı görevi geçersiz kılar (§8.3.5). |
| **Görev 2 Uçuş Süresi ($t_{tk,uçuş}$)** | **$\le 10$ Dakika** | Hedef tespit, yük bırakma ve geri dönüş manevrası tamamlanmalıdır. Süre aşımı görevi geçersiz kılar (§8.3.5). |
| **Kalkış Başlatma Sınırı** | **5 Dakika** | Uçuş izni verildikten sonra 5 dk içinde kalkış başlamalıdır; geciken takıma takım bilinci uyarısı/puan kesintisi uygulanır. |
| **İptal Eşiği** | **8 Dakika** | 8 dakika içinde kalkış yapamayan takım bir uçuş hakkını zayi etmiş sayılır (§8.1). |

### ⚠️ Kritik Süre Cezası: Ek Müdahale Kuralı
> Uçuşa hazırlık sırasında İHA'ya güç verme/kesme dışında yapılan **her ek müdahalenin süresi + 10 saniye**, takımın toplam kurulum süresine ($t_{tk,haz}$) ceza olarak ilave edilir:
> $$t_{tk,haz,\text{efektif}} = t_{tk,haz,\text{ölçülen}} + \sum \left( \Delta t_{\text{müdahale}} + 10\text{ sn} \right)$$
> Bu durum formüldeki $\frac{t_{min,haz}}{t_{tk,haz}}$ oranını doğrudan düşürerek Görev 1 ve Görev 2 puanlarını ciddi oranda eritir!

---

## 5. Aviyonik, Kamera, Emniyet ve Fail-Safe Kontrol Profilleri

Teknik kontrol aşamasında otopilot, kamera ve alıcı fail-safe mekanizmaları titizlikle test edilir (§9.2, §9.3).

### 5.1. Tek Kamera Zorunluluğu (Single Camera Rule)
- Görev bilgisayarı (Companion Computer - Jetson) üzerinde **yalnızca tek bir kamera** bulunabilir. Birden fazla kamera kullanımı kural dışıdır.

### 5.2. 2 Saniye Kuralı: Acil Güç Kesme Mekanizması (Kill Switch)
- İHA gövdesi üzerinde, harici alet gerektirmeksizin kolayca erişilebilen entegre fiziksel bir **Power On/Off** anahtarı bulunmalıdır.
- Anahtar kapatıldığında ana güç en geç **2 saniye** içerisinde tamamen kesilmelidir.
- Hakem heyeti önünde 2 saniyede güç kesemeyen araçların uçuşuna **asla izin verilmez** (§9.3.4).

### 5.3. Şartnameye Uygun Fail-Safe Aktüatör Profilleri
Radyo sinyal kaybı (azami 5 saniye) veya yer istasyonundan acil durum tetiklemesinde otopilot aşağıdaki profili seçmek zorundadır:

```
+-----------------------------------------------------------------------------------------+
|                               FAIL-SAFE KONTROL PROFİLLERİ                               |
+------------------------------------+----------------------------------------------------+
| SABİT KANAT PROFİLİ (FIXED WING)   | DÖNER KANAT PROFİLİ (ROTARY WING)                  |
+------------------------------------+----------------------------------------------------+
| 1. Gaz: %0 (Motor derhal kesilir)  | 1. Gaz: %50 (Yarım gaz ile kontrollü alçalma)      |
| 2. İrtifa Dümeni: Tam YUKARI       | 2. Eve Dönüş (RTL): KESİNLİKLE YASAKTIR / SEÇİLEMEZ|
| 3. İstikamet Dümeni: Tam SAĞ       | 3. Hakem Komutu: Gazı tamamen kesme (%0 throttle)  |
| 4. Kanatçık (Aileron): Tam SAĞ     |                                                    |
| 5. Flaplar: Tam AŞAĞI              |                                                    |
+------------------------------------+----------------------------------------------------+
```

> [!CAUTION]
> **Döner Kanatta RTL Yasağı:** Döner kanat kategorisinde Fail-Safe durumunda **RTL (Return to Launch) modu seçilemez**. Otopilotun doğrudan yarı gazla kontrollü dikey inişe geçmesi veya hakem emriyle motorları susturması şarttır (§9.2).

### 5.4. Emniyet ve İletişim Şartları
- **Baret Zorunluluğu:** Uçuş hattında bulunan tüm takım üyelerinin TÜBİTAK tarafından dağıtılan baretleri takması mecburidir (§9.4).
- **Uçtan Uca Şifreli Telemetri:** Radyo frekans karışmalarını ve sabotajı önlemek amacıyla telemetri ve kumanda linki AES-128 / AES-256 şifreli olmalıdır (§9.4).
- **Kasıtlı Karıştırma Yasağı:** Jamming, frekans tacizi veya GPS spoofing girişiminde bulunan takım derhal diskalifiye edilir (§9.3.2).

---

## 6. Görev Tanımları ve Uçuş Rotaları

Yarışma iki ana görevden ve döner kanat için ilave bonus görevinden oluşur.

```
       GÖREV 1: OTONOM ∞ (YATAY SEKİZ)               GÖREV 2: HEDEF TARAMA VE BIRAKMA
       
          Pylon 1          Pylon 2                     Pylon 1          Pylon 2
          (150m)           (150m)                      (150m)           (150m)
          .-----.          .-----.                     .-----.          .-----.
         /       \        /       \                   /       \        /       \
        |    X    \      /    X    |                 |    X    |      |    X    |
         \         \    /         /                   \       /        \       /  ==> Dıştan dönüş!
          '-----.   \  /   .-----'                     '-----'          '-----'
                 \   \/   /                                                |
                  \  /\  /                                         [ Tarama Alanı ]
                   '    '                                          [  30m x 100m  ]
             2 Tam Tur Yatay ∞                                     [Hedef A/Hedef B]
```

### Görev 1: Otonom Uçuş ve ∞ Manevrası Sıralaması
1. **Kalkış:** Başlangıç çizgisinden otonom (veya manuel) kalkış icra edilir.
2. **2. Direğe Doğru Düz Uçuş:** Araç 2. direğe doğru intikal eder.
3. **2. Direk Dış Dönüşü:** 2. direğin arkasından dış dönüş yapılır.
4. **2 Tam Tur Yatay ∞ Manevrası:** 150m aralıklı iki referans direğini içeride bırakacak şekilde 2 tam tur yatay sekiz (∞) çizilir.
5. **Son Dış Dönüş:** 2. turun ardından 2. direğin arkasından son dış dönüş yapılır.
6. **Bitiş Çizgisi & İniş:** Başlangıç/bitiş çizgisi geçilerek süre durdurulur ve 1. ile 2. direk arasına kırımsız iniş gerçekleştirilir.
- **Geçiş Koşulu:** Görev 1'i başarıyla tamamlayamayan takım Görev 2'ye geçemez ve derece ödüllerinden elenir (§10.1, §10.2).

### Görev 2: Otonom Tespit ve Hassas Yük Bırakma
1. **Konfigürasyon:** Araçlar teknik kontrolde beyan edilen **2 adet özdeş kütleli** yük taşır (örn. 800g / 1200g).
2. **Manevra:** Kalkış sonrası 2. direk dışarıdan dönülür ve 30m × 100m'lik alanda hedefler görüntü işleme ile taranır.
3. **Sıra:** Hedeflerin tespit sırası serbesttir; önce tespit edilen hedefe uygun renkteki yük bırakılır.
4. **Dönüş ve İniş:** Bitiş çizgisi geçilerek görev tamamlanır.

---

## 7. Görüntü İşleme, Hedef Tanımları ve Balistik Bırakma

| Kategori | Hedef A (Mavi) | Hedef B (Kırmızı) | Bırakılacak Yükler | Geçerli İsabet Yarıçapı |
| :--- | :--- | :--- | :--- | :--- |
| **Sabit Kanat** | $4\text{m} \times 4\text{m}$ Mavi Kare | $2\text{m} \times 2\text{m}$ Kırmızı Kare | Hedef A'ya **KIRMIZI** yük<br>Hedef B'ye **MAVİ** yük | **$r \le 20\text{ Metre}$**<br>($>20\text{m} \rightarrow 0$ puan) |
| **Döner Kanat** | Kenarı $2\text{m}$ Mavi Altıgen | Kenarı $1\text{m}$ Kırmızı Eşkenar Üçgen | Hedef A'ya **KIRMIZI** yük<br>Hedef B'ye **MAVİ** yük | **$r \le 10\text{ Metre}$**<br>($>10\text{m} \rightarrow 0$ puan) |

### 🎯 Kritik Kural: Durma Noktası (Resting Point) Prensibi
> Şartname §8.3.3 uyarınca: Yükün merkeze olan uzaklığı hesaplanırken **yükün ilk temas ettiği nokta değil, yerde yuvarlanıp tamamen durduğu en son nokta** baz alınır.  
> - Yük yere çarptığında parçalanır veya yapısal bütünlüğünü kaybederse mesafe ölçümü **yapılmaz ve 0 puan verilir**.
> - Paraşüt veya hava freni kullanılabilir; ancak kullanılan mekanizma yükle tamamen aynı renkte olmalı ve elektronik kontrol içermemelidir.

### 🚁 Döner Kanat Bonus Görevi (Görev 3): Yerden Yük Alma ve Taşıma
Döner kanat araçları iki yükü bıraktıktan sonra:
1. İlk bıraktıkları altıgen hedefe geri dönüp yerdeki yükü otonom/yarı-otonom kavraması durumunda: **$AY_{altg,yük} = 1$ (+10 Puan)**
2. Kavranan bu yükü üçgen hedefe taşıyıp başarılı şekilde bırakması durumunda: **$BY_{üçg,yük} = 1$ (+10 Puan)**
3. Bu görev takıma toplamda **+20 bonus puan** kazandırır.

---

## 8. Resmi Puanlama Sistemi (Tablo 2 ve Tablo 3 Formülleri)

### 8.1. Genel Puan Dağılımı (Şartname Tablo 2)

| Kategori | Hazırlık & Görev Videosu | Görev 1 Puanı | Görev 2 Puanı | Teorik Maksimum Puan | Ceza 1 Aralığı | Ceza 2 Aralığı |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Sabit Kanat** | 10 | 30 | 70 | **110 Puan** | $0 - 5$ | $0 - 10$ |
| **Döner Kanat** | 10 | 30 | 80 | **120 Puan** | $0 - 5$ | $0 - 10$ |

---

### 8.2. Otonomi Katsayısı ($c$)
Uçuşun icra ediliş biçimine göre formüllerdeki $c$ çarpanı belirlenir:
- **$c = 1.0$:** Tam Otonom Uçuş (Otonom kalkış + Otonom görev seyri + Otonom iniş)
- **$c = 0.7$:** Yarı Otonom Uçuş (Manuel kalkış ve/veya manuel iniş, otonom seyir)

---

### 8.3. Görev 1 Puanlama Formülü (Sabit ve Döner Kanat Ortak)

$$P_{G1} = c \cdot \left[ 6 \cdot \frac{Vol_{min}}{Vol_{tk}} + 6 \cdot \frac{t_{min,haz}}{t_{tk,haz}} + 6 \cdot \frac{W_{0,min}}{W_{0,tk}} + 12 \cdot \frac{t_{min,uçuş}}{t_{tk,uçuş}} \right] - \text{Ceza Puanı}$$

- **Kutu Hacim Katkısı ($6\text{ Puan}$):** En küçük kutu hacmine sahip takıma göre normalize edilir.
- **Kurulum Hız Katkısı ($6\text{ Puan}$):** En hızlı kurulum yapan takıma göre normalize edilir.
- **Hafiflik Katkısı ($6\text{ Puan}$):** En hafif yüksüz İHA'ya göre normalize edilir.
- **Uçuş Hızı Katkısı ($12\text{ Puan}$):** 2 tur $\infty$ manevrasını en kısa sürede bitiren takıma göre normalize edilir.

---

### 8.4. Görev 2 Puanlama Formülü (Sabit Kanat)

$$P_{G2,\text{Sabit}} = c \cdot \left[ 4 \cdot \frac{Vol_{min}}{Vol_{tk}} + 4 \cdot \frac{t_{min,haz}}{t_{tk,haz}} + 4 \cdot \frac{W_{0,min}}{W_{0,tk}} + 20 \cdot \frac{W_{yük,tk}}{W_{yük,max}} + 10 \cdot \frac{d_{4x4,min}}{d_{4x4,tk}} + 20 \cdot \frac{d_{2x2m,min}}{d_{2x2m,tk}} + 8 \cdot \frac{t_{min,uçuş}}{t_{tk,uçuş}} \right] - \text{Ceza Puanı}$$

- **Kutu, Hazırlık ve Boş Ağırlık ($4 + 4 + 4 = 12\text{ Puan}$)**
- **Taşınan Faydalı Yük Ağırlığı ($20\text{ Puan}$):** Takımın taşıdığı yük ağırlığının yarışmadaki en büyük yüke oranı.
- **$4\text{m} \times 4\text{m}$ Mavi Hedef İsabeti ($10\text{ Puan}$):** Merkeze olan mesafenin normalize skoru ($d \le 20\text{m}$).
- **$2\text{m} \times 2\text{m}$ Kırmızı Hedef İsabeti ($20\text{ Puan}$):** Küçük ve zorlu hedefe yapılan isabetin skoru ($d \le 20\text{m}$).
- **Uçuş Hızı ($8\text{ Puan}$):** Görevi tamamlama süresi.

---

### 8.5. Görev 2 Puanlama Formülü (Döner Kanat)

$$P_{G2,\text{Döner}} = c \cdot \left[ 4 \cdot \frac{Vol_{min}}{Vol_{tk}} + 4 \cdot \frac{t_{min,haz}}{t_{tk,haz}} + 4 \cdot \frac{W_{0,min}}{W_{0,tk}} + 20 \cdot \frac{W_{yük,tk}}{W_{yük,max}} + 8 \cdot \frac{d_{altg,min}}{d_{altg,tk}} + 12 \cdot \frac{d_{üçg,min}}{d_{üçg,tk}} + 10 \cdot (AY_{altg,yük} + BY_{üçg,yük}) + 8 \cdot \frac{t_{min,uçuş}}{t_{tk,uçuş}} \right] - \text{Ceza Puanı}$$

- **Kutu, Hazırlık ve Boş Ağırlık ($4 + 4 + 4 = 12\text{ Puan}$)**
- **Taşınan Faydalı Yük Ağırlığı ($20\text{ Puan}$)**
- **Mavi Altıgen Hedef İsabeti ($8\text{ Puan}$):** $d \le 10\text{m}$ sınırında merkez mesafesi oranı.
- **Kırmızı Üçgen Hedef İsabeti ($12\text{ Puan}$):** $d \le 10\text{m}$ sınırında merkez mesafesi oranı.
- **Yerden Alma & Geri Bırakma Bonusu ($20\text{ Puan}$):** $10 \cdot (AY + BY)$ katkısı ($AY=1 \rightarrow +10$, $BY=1 \rightarrow +10$).
- **Uçuş Hızı ($8\text{ Puan}$)**

---

## 9. Ceza Puanları, İhlaller ve Elenme (Diskalifiye) Kriterleri

### 9.1. Puan Kesen Cezalar (Penalties)
1. **Ceza Puanı 1 ($0 - 5\text{ Puan}$):**
   - Centilmenlik dışı ve sportmenliğe aykırı tutumlar sergilenmesi.
   - Muhafaza kutusunda yer almayan harici malzeme veya ekipmanın sahada araca entegre edilmesi.
2. **Ceza Puanı 2 ($0 - 10\text{ Puan}$):**
   - Referans pylon direğini içten almak veya direğin dışından dolaşmamak.
   - Dönüş koridoru ihlalleri.

### 9.2. Uçuşun Geçersiz Sayılması Durumları (0 Puan)
- Görev 1'de 8 manevrasını yapamamak veya direkleri içeride bırakmamak.
- Azami uçuş sürelerinin aşılması (Görev 1 $> 5$ dakika, Görev 2 $> 10$ dakika).
- Bitiş çizgisi geçildikten sonra aracın kırıma uğraması.
- Bırakılan yükün hedefin ölçüm yarıçapı dışına çıkması (Sabit $>20\text{m}$, Döner $>10\text{m}$).
- Yükün yere çarpma esnasında parçalanması / yapısal bütünlüğünü kaybetmesi.

### 9.3. Doğrudan Elenme (Diskalifiye - DQ) Nedenleri
- İHA toplam kalkış ağırlığının $4.0\text{ kg}$'ı geçmesi.
- 120 metre AGL irtifa tavanının aşılması ve uyarılara rağmen alçalınmaması.
- İHA üzerinde en fazla 2 saniye içinde gücü kesen entegre anahtar bulunmaması.
- Fail-Safe testinde şartnameye uygun kontrol tepkilerinin verilememesi (özellikle döner kanatta RTL modu bulunması).
- Yetkisiz alanlarda habersiz motor çalıştırmak veya test uçuşu yapmak.
- Kasıtlı frekans karıştırma (jamming), GPS aldatma (spoofing) veya telemetri sabotajı.
- DDK onayı olmadan motor, ESC veya pervane değiştirmek.
- Hazır ticari/kopya hava aracı ile yarışmaya katılmak.
- Görev bilgisayarında tek kamera kuralını ihlal ederek çoklu kamera kullanmak.

---

## 10. Uçuş Öncesi Teknik Kontrol ve SHGM Denetim Matrisi

Teknik kontrolden geçemeyen hava araçları kesinlikle uçuş hattına alınmaz.

```
                      +-----------------------------+
                      | 1. SHGM Kaydı & QR Kontrolü  |
                      | (iha.shgm.gov.tr - Pilot/İHA)|
                      +--------------+--------------+
                                     |
                      +--------------v--------------+
                      | 2. Kutu ve Boyut Kontrolü   |
                      | Sabit: Silindir | Döner: Prizma|
                      +--------------+--------------+
                                     |
                      +--------------v--------------+
                      | 3. Tartım: MTOW <= 4.0 kg   |
                      | (Gövde + Batarya + Yükler)  |
                      +--------------+--------------+
                                     |
                      +--------------v--------------+
                      | 4. 2 Saniye Güç Kesme Testi |
                      | (Power Switch -> Entegre)   |
                      +--------------+--------------+
                                     |
                      +--------------v--------------+
                      | 5. Fail-Safe Fonksiyon Testi|
                      | Kumanda Kapatılarak Yer Testi|
                      +--------------+--------------+
                                     |
                      +--------------v--------------+
                      | 6. Uçuş Hattı Baret Kontrolü|
                      | (TÜBİTAK Onaylı Baretler)   |
                      +-----------------------------+
```

### Mühendislik Doğrulama Kontrol Listesi
- [x] Otopilot parametrelerinde RTL devre dışı bırakıldı; fail-safe profili %50 gaz kontrollü inişe ayarlandı.
- [x] İki adet yükün dış renk kaplamaları (Kırmızı ve Mavi) ve mekanik kilitleri test edildi.
- [x] Görüntü işleme pipeline'ı tek kamera üzerinde hem Sabit (Mavi/Kırmızı Kare) hem Döner (Mavi Altıgen / Kırmızı Üçgen) hedefleri tanıyacak şekilde uyarlandı.
- [x] Web GCS harita merkez koordinatı Malatya Tulga meydanına ($38.34694^\circ\text{ N}, 38.24444^\circ\text{ E}$), 150m pylonlara ve 30m × 100m arama bölgesine göre uyarlandı.
- [x] Telemetri analiz motoru Tablo 3 katsayıları ile güncellendi.
- [x] Sahada görev alacak 4 kişilik ekip (Pilot, GCS Operatörü, 2 Teknisyen) görev dağılımı yapıldı.
