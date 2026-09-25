# İstatistikçi Agent Sistemi

Excel (`.xlsx`) verisi üzerinde üç uzman rolü birlikte çalıştıran MVP:

1. **Excel okuyucu ve İstatistikçi**: Excel'in 1. satırını ana başlık/şema olarak kabul eder, altındaki tüm satırları okur ve her başlık için frekans, tekrar, yüzde ve boş yanıt tablosu üretir.
2. **Çapraz İlişki Analisti**: Şehir–katılım sıklığı gibi seçilen başlık çiftlerini karşılıklı değerlendirir; yaş aralıkları ve kategorik contingency tabloları üretir.
3. **Raporlama ve Yorum Uzmanı**: Her ana başlık için önce tabloyu, ardından kısa yorumu oluşturur; çapraz sonuçları da birleştirerek indirilebilir stdlib OOXML `.docx` raporuna dönüştürür.

## Çalıştırma

Python 3.11+ ve `openpyxl` gerekir. `.xls` eski ikili formatı özellikle reddedilir; Excel'de **Farklı Kaydet → .xlsx** kullanın.

```powershell
pip install -r requirements.txt
python app.py
```

Ardından `http://127.0.0.1:8000` adresini açın. Alternatif olarak:

```powershell
python -m unittest discover -s tests -v
```

## Kullanım

Ana akışta `.xlsx` seçin; ilk çalışma sayfasının **ilk satırı başlık şemasıdır ve veri satırı olarak analiz edilmez**. Boş başlıklar `Column N`, tekrar eden başlıklar `Başlık (2)` gibi deterministik adlara dönüştürülür; özgün-normalize eşleşmesi temizleme raporunda saklanır. Yaş başlığı veya yaş benzeri kolonlar hazır yaş kategorilerini `18 yaş altı`, `18-24`, `25-34`, `35-44`, `45-54`, `55-64`, `65+` sırasıyla gösterir; ham sayısal yaşlar aynı aralıklara atanır. Boş/kişisel alanlar `Yanıt yok` olarak görünür; zaman damgası sütunu özetlenir fakat frekans grafiği olarak öne çıkarılmaz. `.xls` için kullanıcıya açık dönüşüm uyarısı verilir. Örnek veri de kullanılabilir. Kolonları ve ilişki çiftlerini seçip **Analizi çalıştır** düğmesine basın. Sonuçlar ham JSON yerine temizleme özeti, frekans tabloları, yatay yüzde etiketli bar grafikler ve responsive çapraz tablolar olarak gösterilir.
Excel yükleme `POST /api/upload` (multipart `file`) endpoint'iyle yapılır; `/api/analyze` ve `/api/report` mevcut JSON gövdesini korur. Geçerli bir analiz gövdesiyle **Word raporunu indir** düğmesi `/api/report` endpoint'ini çağırır.

Metin/uzun yanıt başlıkları için arayüz, upload veya örnek veri sonrasında deterministik tema önerileri üretir. Tema adı ve virgülle ayrılmış anahtar kelimeler düzenlenebilir; aynı yanıt birden çok temaya girebilir. Boş yanıtlar `Yanıt yok`, eşleşmeyenler `Diğer` olur. Kişisel, zaman damgası, yaş ve sayısal/rating alanları varsayılan tema analizine alınmaz. Değişiklikler `theme_config` alanıyla `/api/analyze` ve `/api/report` isteklerine gönderilir:

```json
{
  "theme_config": [
    {
      "column": "Görüş ve öneriler",
      "enabled": true,
      "themes": [
        {"name": "Olumlu", "keywords": ["iyi", "memnun"]},
        {"name": "Ulaşım", "keywords": ["servis", "otobüs"]}
      ]
    }
  ]
}
```

API:

```http
POST /api/analyze
Content-Type: application/json

{
  "question": "Excel sütun frekans analizi",
  "columns": ["grup", "puan"],
  "rows": [{"grup": "A", "puan": 72}, {"grup": "B", "puan": 61}]
}
```

`GET /api/sample` örnek veri döndürür. Hatalı veya eksik girişler `400` ve makinece okunabilir `{ "error": { "code": "...", "message": "..." } }` gövdesiyle yanıtlanır.

## Mimari ve gerçek model entegrasyonu

`statistical_agents/models.py` typed JSON sözleşmelerini, `analysis.py` deterministik temel istatistikleri, `providers.py` ise sağlayıcı abstraction'ını içerir. Varsayılan `MockProvider`, API anahtarı olmadan kaynak analizleri ve sistem özetini üretir. Gerçek bir LLM eklemek için `AnalysisProvider` protokolünü uygulayan bir sınıf yazıp `create_provider()` içinde `LLM_API_KEY` gibi bir ortam değişkeniyle seçin; istatistik hesaplarını LLM'ye bırakmayın, yalnızca açıklama/özet üretiminde kullanın.

Ortam değişkenleri:

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `HOST` | `127.0.0.1` | Dinleme adresi |
| `PORT` | `8000` | Dinleme portu |
| `PROVIDER` | `mock` | `mock` veya eklenen gerçek sağlayıcı |
| `LLM_API_KEY` | boş | Gerçek sağlayıcı için anahtar |
