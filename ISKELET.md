# Fantezi NBA 9-Cat Oyuncu Değerleme — Proje İskeleti ve Sınırları

## 0. Sözlük (tüm dosyalarda bu adlar kullanılır)

| Kullanıcının adı | Kod adı | Açıklama | Yön |
|---|---|---|---|
| PPG (Sayı) | `PTS` | Atılan sayı | Çok olan kazanır |
| RB (Rebound) | `REB` | Ribaund | Çok olan kazanır |
| Ast (Asist) | `AST` | Asist | Çok olan kazanır |
| 3P (Üçlük) | `FG3M` | İsabetli üçlük sayısı | Çok olan kazanır |
| STL (Top çalma) | `STL` | Top çalma | Çok olan kazanır |
| BLK (Blok) | `BLK` | Blok | Çok olan kazanır |
| TO (Top kaybı) | `TOV` | Top kaybı | **Az olan kazanır** |
| FG (Saha içi %) | `FG_PCT` | FGM / FGA | Yüksek olan kazanır |
| FT (Serbest atış %) | `FT_PCT` | FTM / FTA | Yüksek olan kazanır |
| Oynanan maç | `GP` | Kategori değil, toplam değeri etkiler | — |

Diğer terimler:
- **Havuz (P):** Değerlemenin ortalama ve standart sapmasının hesaplandığı, en değerli N oyuncu. N = 16 takım × 15 kadro = **240**. Havuz yalnızca μ ve σ'yı belirler; değerleme ve sıralama havuzdakilerle sınırlı değildir, sezonda en az 1 maç oynayan **her oyuncu** değerlenir.
- **Z-skor:** Bir oyuncunun bir kategoride havuz ortalamasından kaç standart sapma uzakta olduğu.
- **Çarpan:** Bir kategorideki 1 birimlik istatistiğin z-skor karşılığı = `1 / σ`.
- **Sayı eşdeğeri:** 1 birimlik istatistiğin kaç sayıya denk geldiği = `σ_PTS / σ_kategori`.
- **Etki (impact):** Yüzde kategorilerinde hacim ağırlıklı katkı (bkz. §3.3).
- **Ham değer:** 9 z-skorun toplamı.
- **Değer:** Ham değerin 0–100 ölçeğine taşınmış hali (bkz. §3.3).
- **Mod:** `total` (sezon toplamı, ana sıralama) ve `per_game` (maç başı, ek sıralama).

## 1. Amaç ve Hedef Kullanıcı

- **Sorun:** 9-cat fantezi liginde kategoriler eşit puan verir ama istatistikler eşit nadirlikte değildir (1 blok, 1 sayıdan çok daha değerlidir; 60/100 FG, 6/10 FG'den takım yüzdesini çok daha fazla etkiler). Oyuncuların gerçek fantezi değerini tek bir sayıya indirgeyen, nasıl hesaplandığı şeffaf bir sıralama yok.
- **Hedef kullanıcı:** Türkçe konuşan, 16 takımlı (15'er oyunculu kadro) H2H 9-cat ligde oynayan, draft/takas kararı için geçen sezonun verisine dayalı sıralama isteyen fantezi oyuncusu (proje sahibi ve lig arkadaşları).
- **Başarı ölçütü:**
  1. Tek komut (`python -m fantasy9cat all`) önbellekteki ham veriden 4 çıktıyı (values CSV'leri, `Hesaplama.md`, `Deger.pdf`, web sitesi) 60 saniye altında üretir.
  2. Her oyuncu için 9 kategorinin her birindeki katkı (z-skor) ve toplam değer görülebilir.
  3. `Hesaplama.md`'deki çalışılmış örnek, CSV'deki sonucu ±0,01 hata ile yeniden üretir.

## 2. Kapsam

### Kapsam İçi (MVP)

| # | Özellik | Öncelik | Kabul Kriteri |
|---|---|---|---|
| F1 | Veri çekme ve önbellek | Zorunlu | `python -m fantasy9cat fetch` 2025-26 normal sezon oyuncu toplamlarını `data/raw/players_2025-26_regular.csv` dosyasına yazar; dosya §3.4'teki 16 kolonun tamamını içerir, ≥ 400 satırdır, sayısal kolonlarda negatif/boş değer yoktur. Ağ hatasında 3 deneme yapar, sonra Türkçe hata mesajıyla çıkış kodu 1 döner. |
| F2 | Veri doğrulama | Zorunlu | `schema.validate()` eksik kolon, negatif değer, FGM > FGA, FTM > FTA, FG3M > FGM veya < 400 satır durumunda `DataValidationError` fırlatır (her durum için ayrı test). GP > 82 ise sadece uyarı loglar. |
| F3 | Değerleme motoru (sezon toplamı) | Zorunlu | §3.3 formülleriyle `data/processed/values_total.csv` üretilir; her oyuncu için 9 z-skor, ham değer, değer ve sıra vardır. Fikstür testlerinde `valuation` fonksiyon çıktısı ile elle hesaplanan z-skorlar arasındaki fark < 1e-9 (CSV'deki 6 hane yuvarlama bu teste dahil değildir). Aynı ham CSV ile iki çalıştırma byte-düzeyinde aynı dosyayı verir. |
| F4 | Yüzde kategorilerinde hacim etkisi | Zorunlu | Lig ortalaması %50 iken 6/10 yapan oyuncunun etkisi +1, 60/100 yapanın +10; lig ortalaması %65 iken 60/100 yapanın etkisi −5 olur (birim testleri). FGA = 0 ise etki 0'dır. |
| F5 | İteratif havuz | Zorunlu | Havuz başlangıçta §3.3 adım 5'teki gibi dakikaya göre ilk 240 oyuncudur; havuz değişmeyene kadar ya da en fazla 10 iterasyon tekrarlanır. İterasyon sayısı ve yakınsama durumu `meta.json`'a yazılır. |
| F6 | Çarpan tablosu | Zorunlu | `data/processed/multipliers.csv` her mod için 9 satır içerir: `mode, category, mu, sigma, multiplier, points_equivalent, mean_ratio_to_pts, league_pct`. `PTS` satırında `points_equivalent` = 1. `FG_PCT`/`FT_PCT` satırlarında `mean_ratio_to_pts` boştur (etki ortalaması ≈ 0 olduğundan oran anlamsız), `league_pct` doludur; diğer satırlarda `league_pct` boştur. |
| F7 | Maç başı değerleme | Zorunlu | Aynı algoritma maç başı verilerle çalışır ve `values_per_game.csv` üretir. GP ≥ 1 olan **tüm** oyuncular değerlenir (dosyanın satır sayısı `values_total.csv` ile aynıdır); yalnızca havuza aday olmak için GP ≥ 20 şartı aranır. GP < 20 olan satırlarda `low_sample = True`'dur (test). |
| F8 | Ölçekleme | Zorunlu | `total` modunda 1. sıradaki oyuncunun değeri 100,0; 241. sıradaki (yedek seviyesi) 0,0'dır. Yedek seviyesinin altındakiler negatif değer alır. `per_game`'de aynı kural GP ≥ 20 adaylar üzerinden uygulanır (en iyi aday 100,0, 241. aday 0,0; test). |
| F9 | `Hesaplama.md` | Zorunlu | `output/Hesaplama.md` §3.5'teki 11 başlığın tamamını içerir; içinde `{{` veya `{%` kalmaz; çarpan tablosundaki sayılar (ondalık virgül noktaya çevrilerek) `multipliers.csv` ile 3 ondalık hassasiyetle aynıdır; çalışılmış örneğin z toplamı CSV'deki ham değerle ±0,01 içinde eşleşir. |
| F10 | `Deger.pdf` | Zorunlu | `output/Deger.pdf` A4 yatay, < 5 MB; 3 bölüm içerir (yöntem özeti + çarpan tablosu, sezon toplamı sıralaması, maç başı sıralaması); `build_pdf()` her sıralama tablosu için yazdığı satır sayısını döndürür ve bu, ilgili CSV'nin satır sayısına eşittir (test); tablo başlığı her sayfada tekrarlanır; pypdf ile çıkarılan metinde her iki tablonun son sıradaki oyuncusunun adı ve fikstürdeki `Alperen Şengün` ile `Nikola Jokić` adları bozulmadan geçer. |
| F11 | Web sitesi — sıralama sayfası | Zorunlu | `output/site/index.html` tarayıcıda çift tıklamayla (file://) internet olmadan açılır. Gömülü JSON'daki oyuncu sayısı her mod için ilgili CSV'nin satır sayısına eşittir (test). Elle kontrol listesi: (a) mod geçişi Toplam/Maç başı çalışır, (b) isim araması her tuşta filtreler ve büyük/küçük harf ile aksan duyarsızdır (`sengun` → Alperen Şengün, `jokic` → Nikola Jokić, `İ/ı/i` eşit sayılır), (c) takım filtresi çalışır, (d) her kolon başlığı tıklanınca artan/azalan sıralar, (e) satıra tıklayınca ham istatistikler ve 9 kategorinin katkı çubukları görünür, (f) 360 px genişlikte tablo yatay kaydırılır ve sayfa taşmaz, (g) maç başı modda GP < 20 oyuncularda "az maç" rozeti görünür ve varsayılanı kapalı "Yalnızca GP ≥ 20" kutusu işaretlenince bu oyuncular gizlenir. |
| F12 | Web sitesi — hesaplama sayfası | Zorunlu | `output/site/hesaplama.html`, `Hesaplama.md` ile aynı 11 başlığı ve aynı sayıları içerir (aynı veri bağlamından üretilir; test 3 ondalık eşleşmeyi kontrol eder). |
| F13 | Site sırası kuralı | Zorunlu | `python -m fantasy9cat site`, `values_total.csv`, `values_per_game.csv`, `multipliers.csv`, `Hesaplama.md` ve `Deger.pdf` yoksa siteyi üretmez; eksik dosyaları listeleyip çıkış kodu 1 döner (test). |
| F14 | Etki hesaplayıcısı | Önemli | `hesaplama.html` içinde kullanıcı FGM/FGA (veya FTM/FTA) girer; sayfa etkiyi ve z-skoru `total` modunun havuz parametreleriyle (`league_pct`, μ_imp, σ_imp — sayfaya gömülü) gösterir. Elle kontrol: 6/10 ve 60/100 girişlerinde etki oranı 1:10'dur. |
| F16 | Site görsel tasarımı | Aşama 7 | Tüm renkler, aralıklar ve yazı boyutları `style.css` başında CSS değişkenleri (`--renk-*`, `--aralik-*`) olarak tanımlıdır. Açık ve koyu tema `prefers-color-scheme` ile otomatik seçilir ve elle değiştirilebilir. Metin/arka plan kontrastı ≥ 4.5:1 (WCAG AA; tarayıcı geliştirici araçlarıyla ölçülür). Fontlar `assets/fonts/` altında yerel woff2 dosyalarıdır, harici font isteği yoktur. İlk 10 oyuncu için öne çıkan kart görünümü vardır. `output/site/` toplamı < 3 MB. F11 ve F14'ün elle kontrol listeleri yeniden geçer. |
| F15 | Uçtan uca komut | Zorunlu | `python -m fantasy9cat all` ham CSV varsa ağa çıkmadan compute → report → site sırasıyla çalışır, toplam süre < 60 sn (komut bitince geçen süreyi saniye olarak loglar); ham CSV yoksa önce `fetch` çalıştırır. |

### Sonraki Sürümler
- Punt modu: kullanıcının seçtiği kategorilerin ağırlığını 0 yapma.
- Lig ayarlarını (takım sayısı, kadro, kategori seti) siteden değiştirme.
- Oyuncu kademeleri (tier) ve kademe sınırlarının görselleştirilmesi.
- Haftalık H2H simülasyonuyla kategori kazanma olasılığı.
- Birden fazla sezonun ağırlıklı ortalaması; 2026-27 projeksiyonu.

### Kapsam Dışı
- Canlı/güncel sezon verisi ve otomatik güncelleme — proje geçen sezonun kapanmış verisiyle çalışır.
- Playoff ve play-in istatistikleri — fantezi ligleri normal sezona göre oynanır.
- Sakatlık, rol değişikliği, takas sonrası rol ayarlaması — veri tabanlı, yorum içermeyen bir değer hedefleniyor.
- Puan (points) ligleri ve 8-cat/diğer formatlar — ölçüt yalnızca 9-cat.
- ESPN/Yahoo/Sleeper hesap entegrasyonu — kimlik doğrulama ve harici API kapsamı büyütür.
- Sunucu tarafı (backend), veritabanı, kullanıcı hesabı — çıktılar statik dosyalardır.
- stats.nba.com dışındaki sitelerden kazıma (scraping) — kullanım koşulu ve bakım riski.

## 3. Mimari

### 3.1 Genel yaklaşım
Tek Python paketi (`fantasy9cat`), komut satırından çalışan doğrusal bir boru hattı:

```
fetch ──► data/raw/*.csv ──► compute ──► data/processed/*.csv,json ──► report ──► output/Hesaplama.md, output/Deger.pdf ──► site ──► output/site/
```
Her aşama yalnızca bir önceki aşamanın dosyalarını okur; aşamalar ayrı ayrı çalıştırılabilir.

### 3.2 Bileşenler

| Modül | Sorumluluk |
|---|---|
| `__main__.py` | argparse CLI: `fetch`, `compute`, `report`, `site`, `all`; ortak `--season` (varsayılan `2025-26`). |
| `config.py` | Sabitler: `SEASON`, `SEASON_TYPE="Regular Season"`, `NUM_TEAMS=16`, `ROSTER_SIZE=15`, `POOL_SIZE=240` (= takım × kadro, elle değil çarpımla hesaplanır), `MIN_GP_POOL_PER_GAME=20`, `MAX_POOL_ITERATIONS=10`, yollar. |
| `fetch.py` | `nba_api.stats.endpoints.LeagueDashPlayerStats` (`per_mode_detailed="Totals"`) ile veri çeker; timeout 60 sn, 3 deneme, denemeler arası 5/10/20 sn bekleme. |
| `schema.py` | Ham CSV kolon/değer doğrulaması (F2). |
| `valuation.py` | Etki, z-skor, iteratif havuz, çarpanlar, ölçekleme, sıralama (saf fonksiyonlar, G/Ç yok). |
| `pipeline.py` | compute adımı: CSV oku → `valuation` → `data/processed/` yaz. |
| `formatting.py` | Türkçe sayı biçimi (`fmt_num`: ondalık virgül), kategori etiketleri. Tüm kullanıcıya dönük çıktılar bunu kullanır. |
| `context.py` | Rapor ve site için ortak veri bağlamı (çarpanlar, meta, çalışılmış örnek, oyuncu listeleri). Tek kaynak → md, pdf, html tutarlı. |
| `report_md.py` | Jinja2 ile `templates/hesaplama.md.j2` → `output/Hesaplama.md`. |
| `report_pdf.py` | ReportLab ile `output/Deger.pdf` (DejaVu Sans fontu gömülü). |
| `site.py` | Jinja2 ile `templates/site/*.html.j2` → `output/site/*.html`; `style.css` ve `app.js` değiştirilmeden `output/site/assets/` altına kopyalanır; F13 ön koşul kontrolü. |

### 3.3 Hesaplama yöntemi (bağlayıcı spesifikasyon)

Gösterim: P havuz, |P| = N = 240. Ortalama ve standart sapma havuz üzerinden, **popülasyon std (ddof=0)** ile hesaplanır. Formüller her iki modda aynıdır. `per_game` modunda önce `MIN, PTS, REB, AST, FG3M, STL, BLK, TOV, FGM, FGA, FTM, FTA` kolonlarının hepsi GP'ye bölünür, ardından aşağıdaki formüller bu maç başı değerlerle aynen uygulanır (dolayısıyla `p_lg` de maç başı isabet/deneme toplamlarından hesaplanır).

1. **Sayma kategorileri** (`PTS, REB, AST, FG3M, STL, BLK`): `z = (x − μ_P) / σ_P`
2. **Top kaybı** (`TOV`): `z = (μ_P − x) / σ_P` (işaret ters)
3. **Yüzde kategorileri** (`FG_PCT`, `FT_PCT`):
   - Lig yüzdesi: `p_lg = ΣFGM_P / ΣFGA_P` (havuzdaki toplam isabet / toplam deneme)
   - Etki: `imp = FGM − p_lg × FGA` (= `(oyuncu% − p_lg) × FGA`; FGA = 0 → 0)
   - `z = (imp − μ_imp,P) / σ_imp,P`
   - Böylece aynı yüzdede daha çok deneme, yüzde lig ortalamasının üstündeyse daha çok artı, altındaysa daha çok eksi yazar.
4. **Ham değer:** `ham = Σ 9 z-skor` (tüm kategori ağırlıkları 1).
5. **Havuz iterasyonu:** P₀ = havuz adayları içinde (adım 9) `MIN`'e göre ilk N (`total`: toplam dakika, `per_game`: maç başı dakika). Her adımda P_k'dan parametreler hesaplanır, tüm oyuncuların ham değeri bulunur, P_{k+1} = havuz adayları içinde ham değere göre ilk N. P_{k+1} = P_k olunca ya da 10 iterasyonda durulur; son P kullanılır.
6. **Sıralama:** ham azalan; eşitlikte `MIN` azalan; yine eşitse `PLAYER_ID` artan (deterministik).
7. **Ölçek:** `değer = 100 × (ham − ham_{N+1}) / (ham_1 − ham_{N+1})`; `ham_1` havuz adayları arasında en yüksek, `ham_{N+1}` havuz adayları arasında 241. sıradaki ham değerdir (`total`'da adaylar = herkes, yani genel sıralamadaki 1. ve 241.; `per_game`'de GP < 20 oyuncular ölçeği belirleyemez, ama değerleri bu ölçekle hesaplanır ve 100'ü aşabilir). Aday sayısı N+1'den azsa son aday yedek seviyesi kabul edilir ve `meta.json`'a uyarı yazılır.
8. **Çarpan:** `multiplier = 1/σ`; **sayı eşdeğeri:** `σ_PTS / σ_c`; bilgi amaçlı **ortalama oranı:** `μ_PTS / μ_c` (yalnızca 6 sayma kategorisi + `TOV` için; yüzde kategorilerinde boş). Yüzde kategorilerinde birim "lig ortalamasının üstündeki 1 isabet"tir.
9. **Kapsam ve havuz adaylığı:** Her iki modda GP ≥ 1 olan **herkes** z-skor, ham değer, değer ve sıra alır (olabildiğince çok oyuncu). Havuz adayı olma şartı: `total` modunda GP ≥ 1, `per_game` modunda GP ≥ 20 (birkaç maçlık örneklemin σ'yı bozmaması için). `per_game` modunda GP < 20 olan oyuncular sıralamada kalır ama `low_sample` ile işaretlenir.

### 3.4 Veri modeli

**Ham CSV** — `data/raw/players_{season}_regular.csv` (sezon toplamları; elle indirilen yedek CSV de aynı şemaya uymak zorunda):
`PLAYER_ID (int), PLAYER_NAME (str), TEAM_ABBREVIATION (str), GP, MIN, FGM, FGA, FG3M, FTM, FTA, REB, AST, STL, BLK, TOV, PTS` (sayısallar ≥ 0). Sezonda takım değiştiren oyuncu tek satırdır; takım = son takımı.

**İşlenmiş** — `data/processed/`:
- `values_total.csv`, `values_per_game.csv`: `rank, player_id, player_name, team, gp, min, pts, reb, ast, fg3m, stl, blk, tov, fgm, fga, fg_pct, ftm, fta, ft_pct, z_pts, z_reb, z_ast, z_fg3m, z_stl, z_blk, z_tov, z_fg_pct, z_ft_pct, raw_total, value, in_pool` (bool), `low_sample` (bool; `per_game`'de GP < 20 ise True, `total`'da her zaman False). `values_per_game.csv`'de sayma kolonları ve `min, fgm, fga, ftm, fta` maç başı değerlerdir; `gp` ve yüzdeler değişmez. Deneme sayısı 0 olan oyuncuda (`fga = 0` veya `fta = 0`) ilgili yüzde kolonu **boş** bırakılır (0 değil, çünkü %0 kötü şutör izlenimi verir); etki ve z-skoru yine tanımlıdır (etki = 0). Kullanıcıya dönük çıktılarda boş yüzde "—" olarak gösterilir. Ondalıklar 6 haneye yuvarlanır (deterministik çıktı için).
- `multipliers.csv`: `mode, category, mu, sigma, multiplier, points_equivalent, mean_ratio_to_pts, league_pct` (`league_pct` yalnızca yüzde kategorilerinde dolu, diğerlerinde boş).
- `meta.json`: `season, season_type, source_file, source_sha256, n_players_total, n_players_per_game, pool_size, iterations_total, converged_total, iterations_per_game, converged_per_game, replacement_raw_total, replacement_raw_per_game, warnings` (`warnings`: Türkçe uyarı metinlerinin listesi, sorun yoksa `[]`; ör. §3.3 adım 7'deki yetersiz aday durumu, yakınsamayan havuz iterasyonu). Zaman damgası **içermez**; anahtarlar sıralı (`sort_keys=True`) yazılır (deterministiklik için).

### 3.5 Çıktılar

- **`output/Hesaplama.md`** başlıkları (bu sırayla): 1. Kategoriler, 2. Neden Z-Skor?, 3. Oyuncu Havuzu, 4. Sayma Kategorileri, 5. Top Kaybı, 6. Yüzde Kategorileri ve Hacim (6/10 ve 60/100 sayısal örneğiyle), 7. Çarpan Tablosu (her iki mod: μ, σ, çarpan, sayı eşdeğeri, ortalama oranı ve neden σ'nın kullanıldığı), 8. Maç Sayısının Etkisi (toplam ve maç başı karşılaştırması), 9. Ölçekleme, 10. Çalışılmış Örnek (`total` modunda 1. sıradaki oyuncunun 9 z-skoru adım adım), 11. Sınırlamalar (az maç oynayanların toplam modda TOV'dan artı alması, ağırlıkların eşit olması, geçmiş verinin gelecek performansı garanti etmemesi dahil).
- **`output/Deger.pdf`** — F10'daki 3 bölüm. Sıralama kolonları: Sıra, Oyuncu, Takım, MS, PTS, REB, AST, 3P, STL, BLK, TO, FG%, FT% (z-skorları), Ham, Değer. Pozitif z yeşil, negatif kırmızı tonlu hücre. Maç başı tablosunda `low_sample` oyuncuların adının yanında `*` vardır ve tablo altında "* 20 maçtan az oynadı, maç başı değeri az örnekleme dayanır" notu yer alır.
- **`output/site/`** — `index.html`, `hesaplama.html`, `assets/style.css`, `assets/app.js`. Her iki modun oyuncu verisi ve `meta.json` içeriği `index.html` içine `<script type="application/json" id="players-data">` olarak gömülür (file:// altında `fetch()` çalışmadığı için).

### 3.6 Dış bağımlılıklar
- `nba_api` (stats.nba.com istemcisi) — sadece `fetch` adımında, ağ gerektirir.
- DejaVu Sans TTF (normal + kalın) — kaynak: github.com/dejavu-fonts/dejavu-fonts sürüm 2.37 `dejavu-fonts-ttf-2.37.zip`; `assets/fonts/` altına lisans dosyasıyla birlikte konur, Türkçe ve aksanlı karakterler için PDF'e gömülür.

## 4. Klasör Yapısı

```
fantasy-9cat/
├── CLAUDE.md
├── ISKELET.md
├── AGENT.md
├── README.md
├── pyproject.toml              # bağımlılıklar, ruff ve pytest ayarları
├── .gitignore                  # .venv/, output/, __pycache__/
├── assets/
│   └── fonts/
│       ├── DejaVuSans.ttf
│       ├── DejaVuSans-Bold.ttf
│       └── LICENSE             # DejaVu lisansı (dağıtım koşulu)
├── data/
│   ├── raw/                    # git'e eklenir (tekrarlanabilirlik)
│   └── processed/              # compute çıktısı, git'e eklenir
├── src/
│   └── fantasy9cat/
│       ├── __init__.py
│       ├── __main__.py
│       ├── config.py
│       ├── fetch.py
│       ├── schema.py
│       ├── valuation.py
│       ├── pipeline.py
│       ├── formatting.py
│       ├── context.py
│       ├── report_md.py
│       ├── report_pdf.py
│       └── site.py
├── templates/
│   ├── hesaplama.md.j2
│   └── site/
│       ├── base.html.j2
│       ├── index.html.j2
│       ├── hesaplama.html.j2
│       ├── style.css
│       └── app.js
├── output/                     # üretilen teslimatlar (git'e eklenmez)
│   ├── Hesaplama.md
│   ├── Deger.pdf
│   └── site/
└── tests/
    ├── fixtures/
    │   ├── make_sample_players.py  # numpy seed=42 ile deterministik üretici
    │   └── sample_players.csv      # üreticinin çıktısı: 500 satır sentetik veri (≥ 300'ü GP ≥ 20, ≥ 30'u GP < 20), Şengün ve Jokić dahil
    ├── test_fetch.py           # nba_api mock'lanır, ağa çıkmaz
    ├── test_schema.py
    ├── test_valuation.py
    ├── test_pipeline.py
    ├── test_report_md.py
    ├── test_report_pdf.py
    └── test_site.py
```

## 5. Kısıtlar

- **Teknik:** Python ≥ 3.11; yalnızca açık kaynak kütüphaneler: pandas, numpy, nba_api, jinja2, reportlab (çalışma), pytest, pypdf, ruff (geliştirme). Web sitesi harici kütüphane/CDN kullanmaz (vanilla JS + CSS).
- **Performans:** `compute + report + site` (fetch hariç) ≤ 60 sn; `Deger.pdf` < 5 MB; `output/site/` toplamı < 2 MB (Aşama 7'den sonra < 3 MB, F16); sitede sıralama/filtre işlemi 600 satırda < 200 ms (`app.js` süreyi `console.debug` ile yazar).
- **Çevrimdışı:** `fetch` dışındaki tüm komutlar ve site ağ bağlantısı olmadan çalışır; sitede `http://` veya `https://` ile başlayan `src`/`href` yoktur (test).
- **Tekrarlanabilirlik:** Aynı ham CSV → byte-düzeyinde aynı `data/processed/` dosyaları.
- **Güvenlik/gizlilik:** API anahtarı veya gizli bilgi yok; kişisel veri toplanmaz.
- **Dil:** Kullanıcıya dönük tüm metinler Türkçe, ondalık ayırıcı virgül; kod, dosya adları, CSV kolonları İngilizce, CSV'de ondalık nokta.
- **Zaman/bütçe:** Belirtilmedi; her aşama tek çalışma oturumunda bitirilebilecek büyüklükte tutulur.

## 6. Geliştirme Aşamaları

| Aşama | İçerik | Bitti Kriteri |
|---|---|---|
| 0 | Proje kurulumu: `pyproject.toml`, paket iskeleti, `.gitignore`, fontlar + lisans, `make_sample_players.py` ve ürettiği `sample_players.csv`, CLI iskeleti (uygulanmamış alt komutlar "henüz uygulanmadı" yazıp çıkış kodu 2 döner) | `pip install -e ".[dev]"` hatasız; `python -m fantasy9cat --help` 5 alt komutu listeler; `python tests/fixtures/make_sample_players.py` iki kez çalışınca aynı CSV'yi üretir; `pytest` ve `ruff check .` geçer. |
| 1 | `fetch.py`, `schema.py` (F1, F2) | F1, F2 kabul kriterleri; `data/raw/players_2025-26_regular.csv` mevcut. |
| 2 | `valuation.py`, `pipeline.py` (F3–F8) | F3–F8 kabul kriterleri; `data/processed/` dört dosyası üretildi. |
| 3 | `formatting.py`, `context.py`, `report_md.py` (F9) | F9 kabul kriteri. |
| 4 | `report_pdf.py` (F10) | F10 kabul kriteri. |
| 5 | `site.py` ve şablonlar (F11–F14) — **yalnızca Aşama 2–4 bittikten sonra** | F11–F14 kabul kriterleri ve elle kontrol listesi. |
| 6 | `all` komutu, README, son doğrulama (F15) | F15; tüm testler geçer; README kurulum adımlarıyla temiz klonda çalışır. |
| 7 | Site görsel tasarımı (F16) — **yalnızca Aşama 6 bittikten sonra** | F16 kabul kriteri; tüm testler geçer. |

## 7. Riskler

| Risk | Etki | Önlem |
|---|---|---|
| stats.nba.com istekleri engeller/zaman aşımına uğrar | Veri çekilemez | 3 deneme + bekleme; tarayıcı benzeri başlıklar (`nba_api` varsayılanı); ham CSV git'e eklenir; elle indirilen CSV §3.4 şemasıyla kullanılabilir (README'de anlatılır). |
| PDF'te Türkçe/aksanlı karakter bozulması | Oyuncu adları okunmaz | DejaVu Sans gömülür; `Şengün`, `Jokić` içeren test. |
| Az maç oynayan oyuncuların maç başı değerinin şişmesi | Yanıltıcı sıralama | Bu oyuncular havuza giremez (σ korunur), sıralamada kalır ama PDF'te `*`, sitede rozetle işaretlenir; sitede isteğe bağlı "Yalnızca GP ≥ 20" filtresi vardır. |
| 240'lık havuzun gerçek veride (özellikle maç başı modda GP ≥ 20 adaylar) 241 oyuncudan azına düşmesi | Yedek seviyesi tanımsızlaşır | §3.3 adım 7'deki geri dönüş kuralı (son aday yedek seviyesi) + `meta.json`'a uyarı; normal sezonda GP ≥ 20 oyuncu sayısı tipik olarak 400'ün üzerindedir. |
| Havuz iterasyonu salınıma girer | Belirsiz sonuç | En fazla 10 iterasyon, son havuz kullanılır, `meta.json`'a `converged=false` yazılır ve Hesaplama.md'de belirtilir. |
| "Varyans" isteğinin yanlış yorumlanması | Kullanıcının beklediği değer çıkmaz | Yorum V4 olarak kayıtlı; Hesaplama.md §6'da sayısal örnekle açıklanır; formül tek fonksiyonda, değiştirmesi kolay. |
| Sezon parametresinin (`2025-26`) API'de bulunmaması / eksik sezon | Yanlış ya da boş veri | F2 doğrulaması (≥ 400 oyuncu); `--season` ile değiştirilebilir. |
| nba_api sürüm değişikliği | `fetch` kırılır | Sürüm aralığı sabitlenir (`>=1.10,<2`); hesaplama kodu nba_api'ye bağımlı değildir. |

## 8. Varsayımlar

- **V1:** "Geçen sene" = **2025-26 NBA normal sezonu** (playoff ve play-in hariç). `--season` ile değiştirilebilir.
- **V2:** Lig formatı 16 takım × 15 oyuncu H2H 9-cat (kullanıcı tarafından belirlendi); havuz N = 240; yedek seviyesi 241. sıra.
- **V3:** Değerleme yöntemi standart sapma tabanlı z-skor; kategori ağırlıkları eşit (her kategori 1 puan). Çarpan = 1/σ.
- **V4:** "6/10 ile 60/100 aynı yüzde ama 60/100 daha etkili" ifadesi hacim ağırlıklı **etki** ile modellenir: `(oyuncu% − lig%) × deneme`. Yüksek hacim, yüzde ortalamanın altındaysa daha çok eksi, üstündeyse daha çok artı yazar.
- **V5:** Maç sayısının etkisi için ana sıralama **sezon toplamı** üzerindendir (çok oynayan daha çok katkı ve daha çok top kaybı üretir). Ek olarak **maç başı** sıralama verilir; bu sıralamada da herkes yer alır, GP < 20 olanlar işaretlenir.
- **V6:** Ölçek: 1. oyuncu = 100, yedek seviyesi = 0; altındakiler negatif.
- **V7:** Veri kaynağı `nba_api` (stats.nba.com); erişilemezse aynı şemada elle indirilmiş CSV.
- **V8:** Teknoloji: Python + pandas; PDF için ReportLab + DejaVu Sans; site statik HTML + vanilla JS, çevrimdışı da çalışır. Canlı yayını kullanıcı kendisi yapar; agent yayın/deploy işlemi yapmaz. `output/site/` herhangi bir statik barındırma servisine olduğu gibi yüklenebilir durumdadır (göreli yollar, sunucu kodu yok).
- **V9:** Sezon içinde takım değiştiren oyuncu tek satır, takım = son takım.
- **V10:** Kullanıcıya dönük çıktılar Türkçe ve ondalık virgüllü; kod/CSV İngilizce ve ondalık noktalı.
- **V11:** Teslimat dosya adları Türkçe karaktersiz: `Hesaplama.md`, `Deger.pdf`.
- **V12:** Ham ve işlenmiş veri git'e eklenir; `output/` eklenmez (her an yeniden üretilebilir).
- **V13:** Sitenin JS etkileşimleri otomatik tarayıcı testi (Playwright vb.) yerine F11'deki elle kontrol listesiyle doğrulanır; Python testleri yalnızca üretilen HTML'i ve gömülü veriyi denetler (ek bağımlılık ve tarayıcı kurulumu gerekmesin diye).
- **V14:** Testler gerçek veri yerine seed=42 ile üretilmiş 500 satırlık sentetik fikstür kullanır; böylece testler ağsız ve deterministik çalışır.
- **V15:** Python ≥ 3.11 ve pip + venv; ek paket yöneticisi (uv, poetry) kullanılmaz.
- **V16:** "Olabildiğince çok oyuncu üzerinden hesapla" şöyle yorumlandı: GP ≥ 1 olan tüm oyuncular her iki modda değerlenip sıralanır; ancak μ ve σ yalnızca 240 kişilik havuzdan hesaplanır. Tüm oyuncuları havuza almak, kadroya hiç girmeyecek yüzlerce yedeğin ortalamayı düşürüp σ'yı şişirmesine ve çarpanların lig gerçeğinden kopmasına yol açar. Havuz büyüklüğü `config.py`'de tek sabittir; değiştirmek kolaydır.
- **V17:** Oyuncu adları API'den geldiği haliyle kullanılır (ör. "Alperen Sengun" aksansız, "Nikola Jokić" aksanlı); ham veride ad düzeltmesi yapılmaz. Tutarlılık için sitedeki arama aksan duyarsızdır.
