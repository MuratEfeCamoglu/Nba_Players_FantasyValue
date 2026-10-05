# fantasy9cat — Fantezi NBA 9-Cat Oyuncu Değerleme

2025-26 NBA normal sezonu verisinden, **16 takım × 15 kadroluk H2H 9-cat** lig için her oyuncunun
fantezi değerini z-skor yöntemiyle hesaplar. Sezonda en az 1 maç oynayan herkes değerlenir; μ ve σ,
en değerli 240 oyuncudan oluşan havuzdan hesaplanır. Her sayının nasıl hesaplandığı
`output/Hesaplama.md`'de adım adım anlatılır.

- Kapsam, formüller ve kabul kriterleri: [ISKELET.md](ISKELET.md)
- Kod kuralları: [CLAUDE.md](CLAUDE.md) · Geliştirme süreci: [AGENT.md](AGENT.md)

## Çıktılar

| Dosya | İçerik |
|---|---|
| `data/processed/values_total.csv` | Sezon toplamı sıralaması: 9 z-skor, ham değer, 0–100 değer, sıra |
| `data/processed/values_per_game.csv` | Maç başı sıralaması (GP < 20 olanlar `low_sample`) |
| `data/processed/multipliers.csv` | Her mod için μ, σ, çarpan (1/σ), sayı eşdeğeri |
| `data/processed/meta.json` | Havuz iterasyonu, yedek seviyesi, kaynak dosyanın SHA-256'sı, uyarılar |
| `output/Hesaplama.md` | Yöntem, çarpan tablosu ve çalışılmış örnek (11 bölüm) |
| `output/Deger.pdf` | A4 yatay: yöntem özeti + iki sıralama tablosu |
| `output/site/` | Çevrimdışı çalışan statik site: ilk 10 kartları, aranabilir/sıralanabilir ısı haritası tablosu, hesaplama sayfası ve etki hesaplayıcısı; açık/koyu tema |

Ham ve işlenmiş veri git'e eklenir; `output/` eklenmez, her an yeniden üretilebilir.

## Kurulum

Gerekenler: Python ≥ 3.11 ve pip (ek paket yöneticisi gerekmez).

```bash
git clone <depo-adresi> fantasy-9cat
cd fantasy-9cat
python -m venv .venv
source .venv/bin/activate          # Windows (PowerShell): .venv\Scripts\Activate.ps1
                                   # Windows (cmd):        .venv\Scripts\activate.bat
pip install -e ".[dev]"
```

## Hızlı başlangıç

```bash
python -m fantasy9cat all
```

Ham veri (`data/raw/players_2025-26_regular.csv`) depoda olduğu için `all` ağa çıkmadan
`compute → report → site` adımlarını çalıştırır ve geçen süreyi loglar (birkaç saniye). Ham veri
yoksa önce `fetch` ile stats.nba.com'dan çeker.

Bittiğinde `output/site/index.html` dosyasını tarayıcıda **çift tıklayarak** açın; sunucu ve
internet gerekmez.

`output/site/` yalnızca göreli yollar kullanır ve sunucu kodu içermez; klasör olduğu gibi herhangi
bir statik barındırma servisine yüklenebilir. Üst menüdeki "PDF" bağlantısı `../Deger.pdf`'i
gösterir; yayında da çalışması için `Deger.pdf`'i sitenin bir üst klasörüne koyun.

## Komutlar

Her adım yalnızca bir önceki adımın dosyalarını okur; adımlar ayrı ayrı da çalıştırılabilir. Tüm
komutlar `--season` alır (varsayılan `2025-26`).

```bash
python -m fantasy9cat fetch        # stats.nba.com → data/raw/
python -m fantasy9cat compute      # data/raw/ → data/processed/
python -m fantasy9cat report       # data/processed/ → output/Hesaplama.md, output/Deger.pdf
python -m fantasy9cat site         # → output/site/ (compute ve report çıktıları yoksa çalışmaz)
python -m fantasy9cat all          # (gerekirse fetch) → compute → report → site
```

Çıkış kodları: `0` başarılı, `1` hata (Türkçe mesaj stderr'e yazılır).

- `fetch` mevcut ham CSV'nin üzerine yazmaz; yeniden çekmek için dosyayı önce elle kaldırın.
- `site`, işlenmiş dosyalar ile `Hesaplama.md` ve `Deger.pdf` yoksa eksikleri listeler ve durur.
- Aynı ham CSV her zaman byte-düzeyinde aynı `data/processed/`, `Hesaplama.md`, `Deger.pdf` ve
  site dosyalarını üretir (zaman damgası yok).

## stats.nba.com erişilemezse: elle CSV

stats.nba.com bazı ağları (özellikle bulut IP'lerini) engeller. `fetch` 3 denemeden sonra Türkçe
hata mesajıyla çıkar. Bu durumda ham dosyayı elle hazırlayıp
`data/raw/players_2025-26_regular.csv` adıyla koyun. Dosya şu şemaya uymalıdır (ISKELET.md §3.4):

| Kolon | Tip | Açıklama |
|---|---|---|
| `PLAYER_ID` | tamsayı | NBA oyuncu kimliği |
| `PLAYER_NAME` | metin | Oyuncu adı (API'deki haliyle) |
| `TEAM_ABBREVIATION` | metin | Son takımı (takım değiştiren oyuncu tek satır) |
| `GP, MIN, FGM, FGA, FG3M, FTM, FTA, REB, AST, STL, BLK, TOV, PTS` | sayı ≥ 0 | Sezon **toplamları** (maç başı değil) |

- Kaynak: nba.com/stats → Players → Traditional Stats; Season `2025-26`, Season Type
  `Regular Season`, Per Mode `Totals`.
- UTF-8, virgülle ayrılmış, ondalık ayırıcı nokta, başlık satırı yukarıdaki kolon adlarıyla.
- Kurallar: en az 400 satır; boş/negatif değer yok; `FGM ≤ FGA`, `FTM ≤ FTA`, `FG3M ≤ FGM`.
  `GP > 82` yalnızca uyarı verir.

Dosyayı denetlemek için:

```bash
python -c "import pandas as pd; from fantasy9cat.schema import validate; validate(pd.read_csv('data/raw/players_2025-26_regular.csv')); print('geçerli')"
```

Ardından `python -m fantasy9cat all` ağa çıkmadan devam eder.

## Yöntem (özet)

- **Sayma kategorileri** (PTS, REB, AST, 3P, STL, BLK): `z = (x − μ) / σ`
- **Top kaybı** (TO): `z = (μ − x) / σ` — az olan kazanır
- **Yüzdeler** (FG%, FT%): `etki = isabet − lig% × deneme`, `z = (etki − μ) / σ` — aynı yüzdede
  çok deneme, ortalamanın üstündeyse daha çok artı, altındaysa daha çok eksi yazar
- **Ham değer** = 9 z-skorun toplamı · **Değer** = 1. aday 100, 241. aday (yedek seviyesi) 0
- **Havuz**: dakikaya göre ilk 240 ile başlar, ham değere göre ilk 240 değişmeyene kadar (en fazla
  10 kez) yenilenir. Maç başı modda havuza aday olmak için GP ≥ 20 gerekir.

Ayrıntılar, çarpan tablosu ve çalışılmış örnek: `output/Hesaplama.md` veya sitedeki "Hesaplama"
sayfası.

## Geliştirme

```bash
pytest -q                          # testler ağa çıkmaz; nba_api mock'lanır
ruff check .
ruff format --check .              # düzeltmek için: ruff format .
```

- Testler `tests/fixtures/sample_players.csv` sentetik verisini kullanır (500 oyuncu, seed=42).
  Yeniden üretmek için: `python tests/fixtures/make_sample_players.py` (elle düzenlemeyin).
- Site etkileşimleri (arama, sıralama, filtre, ayrıntı satırı, mobil görünüm) ISKELET.md F11'deki
  elle kontrol listesiyle doğrulanır.

## Sorun giderme

- **Windows konsolunda bazı harfler `?` görünüyor** (ör. `Jokić`): konsol kod sayfası bu harfleri
  basamaz; dosyalardaki veriler etkilenmez. İsterseniz `chcp 65001` ile konsolu UTF-8'e alın.
- **`site` "eksik dosya" diyor**: önce `compute` ve `report` çalıştırın (veya doğrudan `all`).
- **`fetch` "zaten var" diyor**: ham veri korunur; yeniden çekmek için dosyayı elle silin.

## Lisanslar

Fontlar `assets/fonts/` altındadır ve kendi lisanslarıyla dağıtılır:

- DejaVu Sans (PDF'e gömülür): [assets/fonts/LICENSE](assets/fonts/LICENSE)
- Inter ve Barlow Condensed (sitede yerel woff2, SIL Open Font License 1.1):
  [assets/fonts/OFL-Inter.txt](assets/fonts/OFL-Inter.txt),
  [assets/fonts/OFL-Barlow.txt](assets/fonts/OFL-Barlow.txt)

Veri kaynağı stats.nba.com'dur (`nba_api`).
