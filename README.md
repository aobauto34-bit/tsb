# Sigorta Pusula — Streamlit sürümü

TSB'nin şirket bazında mali ve teknik tablolarını doğrudan okuyarak hayat dışı sigortacılık için yönetici analizi sunar. Excel yüklemesi, API anahtarı veya ayrı bir Node.js sunucusu gerekmez. Mevcut tasarım, Streamlit'in v2 bileşeni içinde çalışır; veri bağlantısı Python sunucusundadır.

## Streamlit Community Cloud'da yayımlama

1. Bu ZIP'i bilgisayarınızda açın.
2. [GitHub](https://github.com/new) üzerinde `sigorta-pusula` adında bir depo oluşturun. Kodun görünürlüğüne göre public veya private seçebilirsiniz. Streamlit'e bu depoyu okuma erişimi verin.
3. GitHub'da **Add file → Upload files** ile ZIP'in içindeki dosya ve klasörleri yükleyip **Commit changes** düğmesine basın. ZIP dosyasının kendisini yüklemeyin. `streamlit_app.py` ve `requirements.txt` deponun ana dizininde görünmeli; `frontend`, `data` ve `.streamlit` klasörlerini koruyun.
4. [share.streamlit.io](https://share.streamlit.io/) adresine girin. **Create app → Yup, I have an app** yolunu izleyin.
5. Aşağıdaki alanları doldurun.

| Alan | Değer |
| --- | --- |
| Repository | `GITHUB_KULLANICI_ADINIZ/sigorta-pusula` |
| Branch | `main` (deponuzdaki gerçek dal adı) |
| Main file path | `streamlit_app.py` |
| Advanced settings → Python version | `3.12` |
| Secrets | Boş bırakın; bu uygulamada gerekli değil |
| App URL | Müsait bir alt alan adı seçin |

6. **Deploy** düğmesine basın. Kurulum tamamlanınca verilen `https://…streamlit.app` adresini paylaşabilirsiniz.
7. İlk açılışta **Veri merkezi** ekranını kontrol edin. Canlı bağlantı başarılıysa durum **TSB'den doğrulandı**, kaynak dosyalar ve yeni veri alım zamanı görünür. **TSB’den yenile** düğmesi önbelleği atlayarak tekrar okur. Kaynaklara erişilemezse uygulama bunu belirtir ve tarihli kaydı gösterir.

GitHub'a sonraki kod güncellemelerini gönderdiğinizde Streamlit uygulamayı günceller. Depo görünürlüğü ile uygulama erişimi ayrı ayarlardır; uygulamanın paylaşımını Streamlit ayarlarından düzenleyin.

**Kalıcı adres / kesintisiz çalışma:** Community Cloud, 12 saat trafik almayan uygulamaları uyutabilir. Ziyaretçi uygulamayı uyandırabilir. URL kalıcı olabilir; ücretsiz hizmet kesintisiz 7/24 çalışma garantisi değildir. Bu paket bulutta henüz yayımlanmış değildir.

Resmi rehberler (19 Kasım 2026):

- https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy
- https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app
- https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/file-organization

## Veri akışı

- TSB kataloğu uygulama açıldığında kontrol edilir; yayımlanan yeni dönemler listelenir.
- Seçilen dönemin gelir tablosu, bilanço, satış kanalları ve hasar/prim dosyaları sunucuda indirilir ve okunur.
- Katalog ve dönem verileri en fazla 6 saat önbellekte tutulur. Manuel yenileme bu süreyi beklemez.
- Kaynak erişilemezse aynı oturumda son alınan veri veya paketle gelen doğrulanmış kayıt kullanılır. Durum, tarih ve kaynaklar görünürdür. Paket, 2026/9 ay ile 2024/9 ay arasında dokuz dönem kaydı içerir; katalog daha eski dönemleri de listeler.
- Uygulama kapalıyken çalışan zamanlanmış veri toplama görevi yoktur. Bulutun yerel diski kalıcı veri tabanı olarak kullanılmaz. Yeni kayıtların uygulama yeniden başlatıldıktan sonra da saklanması gerekiyorsa ayrıca kalıcı veri deposu kurulmalıdır.
- Bağlantı yalnız TSB'nin herkese açık HTTPS kaynaklarına yapılır. TSB erişim veya dosya şemasını değiştirirse bağlantının uyarlanması gerekebilir.

## 13 analiz ekranı

Yönetici özeti, teknik kârlılık, branş analizi, şirket karşılaştırma, şirket karnesi, pazar ve büyüme, sermaye ve likidite, dağıtım kanalları, senaryo laboratuvarı, analist tablosu, yönetim raporu, veri merkezi ve hesaplama rehberi.

Şirket ve branş karşılaştırmaları, hesaplamaya dayalı yönetici yorumları, seçime uygun CSV raporları ve tarayıcıdan yazdırma/PDF bulunur. 2026/9 ay kaydında 48 şirket ve 18 ana branş vardır. Trafik/kasko alt kırılımları ana branş toplamına ikinci kez eklenmez.

## Hesaplamaların sınırları

- Tutarlar TL ve yılbaşından seçili dönem sonuna kadar kümülatiftir. Farklı uzunluktaki dönemlerde karşılaştırma uyarısı gösterilir.
- Brüt yazılan prim: 60001. Brüt kazanılmış prim: 60001 + 60003 + 60101 + 60103 + 60201. Gerçekleşen brüt hasar: -(61001 + 61101). Faaliyet gideri: -614.
- Teknik sonuç: 60 + 61. Aktarım hariç teknik sonuç: teknik sonuç - 603. Dönem net kârı yalnız MALI sayfasındaki 69 hesabından gelir; branşlara tahsis edilmez.
- Eksik hücreler sıfıra çevrilmez. Sıfır/negatif uygun olmayan paydalarda oran hesaplanmaz.
- Senaryo teknik sonuç etkisi net kazanılmış prim ve net hasar değişimleri üzerinden hesaplanır. Reasüransın oransal etkisi ve diğer teknik hesaplar sabittir; vergi, dinamik reasürans ve rezerv yeniden ölçümü modellenmez.
- Net kâr / dönem sonu özkaynak oranı yıllıklandırılmış ROE değildir. Cari oran veya özkaynak/aktif oranı düzenleyici sermaye yeterliliği değildir.
- TÜFE ile reel büyüme sadece kaynak değeri tanımlı aynı çeyrek/yıllık karşılaştırmalarda hesaplanır. Yeni dönemlerin TÜFE değeri `frontend/analytics.mjs` içinde doğrulanarak eklenmelidir; bilinmeyen değerler uydurulmaz. TSB mali verilerinin otomatik yenilenmesi bundan bağımsızdır.
- IFRS 17 CSM, rezerv gelişim üçgeni, poliçe hasar frekansı, müşteri yenilemesi ve düzenleyici sermaye yeterliliği için bu TSB dosyaları yeterli değildir. Bu göstergeler hesaplanmış gibi sunulmaz.
- Yorumlar kurala ve hesaplamaya dayanır; harici bir üretken yapay zekâ servisi çağrılmaz.

## Bilgisayarda çalıştırma

Python 3.12 kurulu bir bilgisayarda, bu klasörde:

```shell
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
# source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run streamlit_app.py
```

## Doğrulama ve geliştirme

Python 3.12 / Streamlit 1.67.0 ile yerelde çalıştırıldı. Python Excel okuyucusunun 18.081 alan/değeri resmi TSB dosyalarından elde edilen doğrulanmış kayıtla karşılaştırıldı; beş mutabakat kontrolü geçti. Dokuz dönem üzerinde 47 finansal/senaryo kontrolü, beş CSV rapor türü ve Streamlit veri köprüsünün yeniden çalıştırma testleri geçti.

Hazırlama ortamındaki dış bağlantı kısıtı nedeniyle Python'dan canlı TSB indirme bu ortamda uçtan uca doğrulanamadı. Bu nedenle yayından sonra Veri merkezi ekranında canlı durumun ve tarihlerin kontrol edilmesi gerekir. Kayıtlı veriye geçiş ve dönem seçimleri gerçek Streamlit arayüzünde kontrol edildi.

Kaynak arayüz dosyalarını değiştirdikten sonra `python build_frontend.py` çalıştırın ve uygulamayı yeniden başlatın. Hazır pakette derlenmiş `component.js` / `component.css` vardır; yayın sırasında derleme gerekmez.

Geliştirici kontrolleri (Node.js yalnız bu JS testleri için gereklidir):

```shell
node tests/test.mjs
node tests/test-export.mjs
node tests/test-bridge.mjs
python tests/test_parser.py RESMI_TSB_XLSX_KLASORU
```

Python regresyon testi resmi 5637, 5642, 5633 ve 5636 numaralı Excel dosyalarını bekler. Bu dosyalar uygulamanın çalışması veya yayınlanması için gerekli değildir; uygulama kendisi TSB'den okur.
