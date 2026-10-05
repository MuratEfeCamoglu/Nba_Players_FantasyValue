# Fantezi NBA 9-Cat Oyuncu Değerleme

## Proje
2025-26 NBA normal sezonu verisinden, en az 1 maç oynamış her oyuncunun 16 takım × 15 kadroluk H2H 9-cat ligdeki fantezi değerini z-skor yöntemiyle hesaplar (havuz 240).
Çıktılar: `output/Hesaplama.md` (yöntem ve çarpanlar), `output/Deger.pdf` (sıralama ve kategori katkıları), `output/site/` (statik web sitesi).
Kapsam, formüller ve kabul kriterleri: @ISKELET.md — Agent kuralları: @AGENT.md

## Teknoloji Yığını
- Dil: Python ≥ 3.11
- Veri: pandas, numpy
- Veri kaynağı: nba_api (yalnızca `fetch` adımı)
- Şablon: Jinja2 (md ve html)
- PDF: ReportLab + DejaVu Sans (`assets/fonts/`)
- Site: statik HTML + vanilla JS + CSS (CDN/harici kütüphane yok)
- Test: pytest, pypdf · Lint/format: ruff
- Paket yönetimi: pip + venv, tek kaynak `pyproject.toml`

## Komutlar
```bash
# Kurulum
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# Boru hattı
python -m fantasy9cat fetch        # ağdan ham veri → data/raw/
python -m fantasy9cat compute      # → data/processed/
python -m fantasy9cat report       # → output/Hesaplama.md, output/Deger.pdf
python -m fantasy9cat site         # → output/site/ (report bitmiş olmalı)
python -m fantasy9cat all          # compute → report → site (ham veri yoksa önce fetch)

# Kalite
pytest -q
ruff check .
ruff format --check .              # düzeltmek için: ruff format .
```
Siteyi görmek için `output/site/index.html` dosyasını tarayıcıda açın (sunucu gerekmez).

## Kod Kuralları
- Klasör yapısı ISKELET.md §4 ile birebir aynı kalır; yeni modül eklemek onay gerektirir.
- İsimlendirme: modül/fonksiyon/değişken `snake_case`, sınıf `PascalCase`, sabit `UPPER_CASE`.
- Kategori kodları her yerde aynı: `PTS, REB, AST, FG3M, STL, BLK, TOV, FG_PCT, FT_PCT` (ISKELET.md §0).
- Tüm sabitler `config.py`'de; başka modülde sihirli sayı (240, 20, 16, 15) yazma.
- `valuation.py` saf fonksiyonlardan oluşur: dosya okuma/yazma, ağ, print yok. G/Ç `pipeline.py`, `report_*.py`, `site.py`'de.
- Formüller ISKELET.md §3.3'e birebir uyar; std hesabında `ddof=0`.
- Kullanıcıya dönük sayılar yalnızca `formatting.fmt_num()` ile biçimlenir (ondalık virgül).
- Rapor ve site aynı `context.build_context()` çıktısından üretilir; şablonlarda hesaplama yapma.
- ruff ayarı: `line-length = 100`, kurallar `E, F, I, B, UP`; `pyproject.toml`'da setuptools `where = ["src"]`.
- Tip ipuçları tüm public fonksiyonlarda zorunlu; her public fonksiyonda tek satırlık Türkçe docstring.
- Hatalar: veri sorunlarında `schema.DataValidationError`; CLI bunu yakalayıp Türkçe mesaj basar ve çıkış kodu 1 döner. Çıplak `except:` yasak.
- Log: `logging` modülü, INFO seviyesi; `print` yalnızca `__main__.py`'de.
- CSV yazarken ondalıkları 6 haneye yuvarla, satır sırası `rank`'e göre, `index=False`, `lineterminator="\n"` (deterministik çıktı).

## Test Kuralları
- Testler ağa çıkmaz; `tests/fixtures/sample_players.csv` kullanılır (yeniden üretmek için `python tests/fixtures/make_sample_players.py`; elle düzenleme). `fetch` testleri `nba_api` çağrısını mock'lar.
- Her formül için elle hesaplanmış küçük veriyle birim testi yaz (ör. 6/10, 60/100 örneği).
- Beklenen değeri testi geçirmek için değiştirme; önce formülün ISKELET.md §3.3'e uyduğunu doğrula.

## Çalışma Kuralları
- Her değişiklikten sonra: `pytest -q`, `ruff check .`, `ruff format --check .`.
- Aşamaları ISKELET.md §6 sırasıyla yap; Aşama 5 (site) Aşama 2–4 bitmeden başlamaz.
- Kapsam dışı (ISKELET.md §2) bir ihtiyaç doğarsa uygulamadan önce rapora not düş.
- Formül, sabit veya çıktı şeması değişirse ISKELET.md'yi ve `templates/hesaplama.md.j2`'yi aynı commit'te güncelle.
- Commit mesajı: Conventional Commits, İngilizce (`feat: add impact calculation for FG_PCT`).

## Önemli Notlar
- stats.nba.com bulut IP'lerini sık engeller; `fetch` başarısızsa ham CSV'yi elle ISKELET.md §3.4 şemasıyla `data/raw/` altına koy.
- `file://` altında `fetch()` çalışmaz; site verisi `index.html` içine JSON olarak gömülür.
- ReportLab varsayılan fontları `ş, ğ, ı, ć` gibi harfleri basamaz; her zaman DejaVu Sans'ı kaydet.
- `TOV` z-skoru ters işaretlidir; yüzde kategorileri yüzdeyle değil **etki** ile z'lenir.
- `meta.json` ve CSV'lere zaman damgası yazma (byte-düzeyi tekrarlanabilirlik bozulur).
