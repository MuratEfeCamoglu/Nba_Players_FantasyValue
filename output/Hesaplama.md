# Fantezi NBA 9-Cat Oyuncu Değerleme — Hesaplama Yöntemi

2025-26 NBA normal sezonu · 16 takım × 15 oyunculuk H2H 9-cat lig · 582 oyuncu değerlendi

Bu belge, `values_total.csv`, `values_per_game.csv` ve `multipliers.csv` dosyalarındaki her sayının nasıl hesaplandığını anlatır. Tüm sayılar aynı veri bağlamından üretilir; ondalık ayırıcı virgüldür, boş değerler "—" ile gösterilir.

## 1. Kategoriler

9-cat ligde her hafta 9 kategorinin her biri ayrı ayrı kazanılır; her kategori eşit puan değerindedir.

| Kategori | Kod | Kısa ad | Yön |
|---|---|---|---|
| Sayı | `PTS` | PTS | Çok olan kazanır |
| Ribaund | `REB` | REB | Çok olan kazanır |
| Asist | `AST` | AST | Çok olan kazanır |
| Üçlük | `FG3M` | 3P | Çok olan kazanır |
| Top çalma | `STL` | STL | Çok olan kazanır |
| Blok | `BLK` | BLK | Çok olan kazanır |
| Top kaybı | `TOV` | TO | Az olan kazanır |
| Saha içi yüzdesi | `FG_PCT` | FG% | Yüksek olan kazanır |
| Serbest atış yüzdesi | `FT_PCT` | FT% | Yüksek olan kazanır |

Oynanan maç sayısı (`GP`) bir kategori değildir; ama sezon toplamlarını doğrudan etkiler (bkz. bölüm 8).

## 2. Neden Z-Skor?

Kategoriler eşit puan verir ama istatistikler eşit nadirlikte değildir. Bir oyuncunun 100 sayı fazla atması ile 100 blok fazla yapması aynı şey değildir: ligde oyuncular arasındaki blok farkları sayı farklarından çok daha küçüktür, bu yüzden bir blok farkı kategoriyi kazanmaya çok daha fazla katkı yapar.

Z-skor bu farkı ölçer: bir oyuncunun bir kategoride havuz ortalamasından kaç **standart sapma (σ)** uzakta olduğunu söyler. Böylece farklı birimlerdeki 9 kategori aynı ölçeğe gelir ve toplanabilir.

Sezon toplamı modunda (bkz. bölüm 7):

- 1 blok ≈ **13,948** sayı,
- 1 top çalma ≈ **16,309** sayı,
- 1 üçlük ≈ **6,270** sayı değerindedir.

## 3. Oyuncu Havuzu

Ortalama (μ) ve standart sapma (σ), tüm oyunculardan değil, **havuzdaki 240 oyuncudan** hesaplanır (16 takım × 15 kadro). Kadroya hiç girmeyecek yüzlerce yedek oyuncu ortalamayı düşürür ve σ'yı şişirirdi; havuz, ligde gerçekten rekabet eden oyuncuları temsil eder. Havuz yalnızca μ ve σ'yı belirler: sezonda en az 1 maç oynayan **herkes** (582 oyuncu) değerlenir ve sıralanır.

Havuz kendini belirleyen bir döngüyle bulunur:

1. Başlangıç havuzu: dakikaya göre ilk 240 aday.
2. Bu havuzdan μ ve σ hesaplanır, herkesin ham değeri bulunur.
3. Yeni havuz: ham değere göre ilk 240 aday.
4. Havuz değişmeyene kadar (en fazla 10 kez) 2–3 tekrarlanır.

| Mod | Havuz adayları | İterasyon | Yakınsadı mı? |
|---|---|---|---|
| Sezon toplamı | GP ≥ 1 (582 oyuncu) | 3 | Evet |
| Maç başı | GP ≥ 20 (452 oyuncu) | 5 | Evet |

Maç başı modda havuza aday olmak için en az 20 maç gerekir; birkaç maçlık örneklemin σ'yı bozmaması için.

## 4. Sayma Kategorileri

Sayı, ribaund, asist, üçlük, top çalma ve blok için:

```
z = (x − μ) / σ
```

`x` oyuncunun istatistiği, `μ` ve `σ` havuzun ortalaması ve popülasyon standart sapmasıdır. Örneğin sezon toplamı modunda `PTS` için μ = 911,508, σ = 403,776: ortalamadan 403,776 sayı fazla atan oyuncu bu kategoride +1 z alır.

## 5. Top Kaybı

Top kaybında az olan kazanır, bu yüzden işaret terstir:

```
z = (μ − x) / σ
```

Sezon toplamı modunda `TOV` için μ = 104,454, σ = 52,716. Ortalamadan az top kaybı yapan artı, çok yapan eksi alır.

## 6. Yüzde Kategorileri ve Hacim

Yüzde kategorileri yüzdeyle değil, **hacim ağırlıklı etki** ile z'lenir. Takımın haftalık yüzdesi toplam isabet / toplam denemedir; çok deneme yapan oyuncu takım yüzdesini çok daha fazla oynatır.

```
p_lg = havuzdaki toplam isabet / havuzdaki toplam deneme
etki = isabet − p_lg × deneme        (= (oyuncu% − p_lg) × deneme; deneme 0 ise etki 0)
z    = (etki − μ_etki) / σ_etki
```

Aynı yüzdeyi tutturan iki oyuncudan çok deneme yapanın etkisi, yüzde lig ortalamasının üstündeyse daha çok artı, altındaysa daha çok eksidir:

| Atış | Oyuncu % | Lig % | Etki |
|---|---|---|---|
| 6/10 | %60 | %50 | +1,0 |
| 60/100 | %60 | %50 | +10,0 |
| 60/100 | %60 | %65 | -5,0 |

6/10 ile 60/100 aynı yüzdedir (%60) ama 60/100'ün etkisi 10 kat büyüktür. Lig ortalaması %65 olsaydı aynı 60/100 takımın yüzdesini düşürür ve eksi yazardı.

Gerçek veride sezon toplamı modunda saha içi lig yüzdesi %48,1. Bu değerle:

| Atış | Etki | z (`FG_PCT`) |
|---|---|---|
| 6/10 | +1,19 | +0,033 |
| 60/100 | +11,93 | +0,327 |

Deneme sayısı 0 olan oyuncunun yüzdesi tanımsızdır ve "—" ile gösterilir; etkisi 0 kabul edilir, z-skoru yine hesaplanır.

<!-- etki-hesaplayici -->

## 7. Çarpan Tablosu

- **μ, σ:** havuzun ortalaması ve popülasyon standart sapması (yüzde kategorilerinde etkinin).
- **Çarpan = 1 / σ:** bir kategorideki 1 birimlik istatistiğin z-skor karşılığı. Yüzde kategorilerinde birim "lig ortalamasının üstündeki 1 isabet"tir.
- **Sayı eşdeğeri = σ_PTS / σ:** 1 birimin kaç sayıya denk geldiği.
- **Ortalama oranı = μ_PTS / μ:** yalnızca bilgi amaçlı; yüzde kategorilerinde etki ortalaması ≈ 0 olduğundan boştur.

**Neden ortalama değil de σ?** Kategoriyi kazanmak, rakiplerden *ne kadar ayrıştığına* bağlıdır. Ortalama oranı bir istatistiğin ne kadar sık olduğunu söyler; σ ise oyuncuların o kategoride birbirinden ne kadar farklılaştığını. Örneğin bloklarda ortalama düşüktür ama asıl önemli olan, bir oyuncunun bloklarla havuzdan ne kadar ayrışabildiğidir; bunu σ ölçer.

<!-- sayi-esdegeri-grafigi -->

### Sezon toplamı

<!-- mode:total -->
| Kategori | μ | σ | Çarpan (1/σ) | Sayı eşdeğeri | Ortalama oranı | Lig % |
|---|---|---|---|---|---|---|
| Sayı (`PTS`) | 911,508 | 403,776 | 0,002477 | 1,000 | 1,000 | — |
| Ribaund (`REB`) | 333,246 | 150,285 | 0,006654 | 2,687 | 2,735 | — |
| Asist (`AST`) | 206,900 | 131,410 | 0,007610 | 3,073 | 4,406 | — |
| Üçlük (`FG3M`) | 100,221 | 64,402 | 0,015527 | 6,270 | 9,095 | — |
| Top çalma (`STL`) | 63,087 | 24,759 | 0,040390 | 16,309 | 14,448 | — |
| Blok (`BLK`) | 38,212 | 28,948 | 0,034544 | 13,948 | 23,854 | — |
| Top kaybı (`TOV`) | 104,454 | 52,716 | 0,018970 | 7,659 | 8,726 | — |
| Saha içi yüzdesi (`FG_PCT`) | 0,000 | 36,516 | 0,027385 | 11,057 | — | %48,07 |
| Serbest atış yüzdesi (`FT_PCT`) | 0,000 | 17,095 | 0,058496 | 23,619 | — | %78,93 |
<!-- /mode -->

### Maç başı

<!-- mode:per_game -->
| Kategori | μ | σ | Çarpan (1/σ) | Sayı eşdeğeri | Ortalama oranı | Lig % |
|---|---|---|---|---|---|---|
| Sayı (`PTS`) | 14,416 | 5,832 | 0,171475 | 1,000 | 1,000 | — |
| Ribaund (`REB`) | 5,145 | 2,168 | 0,461305 | 2,690 | 2,802 | — |
| Asist (`AST`) | 3,196 | 1,936 | 0,516622 | 3,013 | 4,511 | — |
| Üçlük (`FG3M`) | 1,544 | 0,923 | 1,083828 | 6,321 | 9,338 | — |
| Top çalma (`STL`) | 0,965 | 0,347 | 2,881533 | 16,804 | 14,934 | — |
| Blok (`BLK`) | 0,593 | 0,439 | 2,280172 | 13,297 | 24,318 | — |
| Top kaybı (`TOV`) | 1,638 | 0,791 | 1,264163 | 7,372 | 8,799 | — |
| Saha içi yüzdesi (`FG_PCT`) | 0,000 | 0,569 | 1,756186 | 10,242 | — | %48,17 |
| Serbest atış yüzdesi (`FT_PCT`) | 0,000 | 0,282 | 3,548184 | 20,692 | — | %79,23 |
<!-- /mode -->

## 8. Maç Sayısının Etkisi

Ana sıralama **sezon toplamı** üzerindendir: çok maç oynayan daha çok katkı (ve daha çok top kaybı) üretir, fantezi takımına da o kadar çok hafta katkı verir. **Maç başı** sıralama, oyuncunun sahadayken ne ürettiğini gösterir; sakatlık nedeniyle az oynayanlar burada yükselir. Maç başı modda 20 maçtan az oynayan 130 oyuncu sıralamada yer alır ama "az maç" olarak işaretlenir ve havuza giremez.

Sezon toplamında ilk 10:

| Oyuncu | Takım | MS | Toplam sırası | Toplam değer | Maç başı sırası | Maç başı değer |
|---|---|---|---|---|---|---|
| Nikola Jokić | DEN | 65 | 1 | 100,0 | 1 | 100,0 |
| Shai Gilgeous-Alexander | OKC | 68 | 2 | 94,5 | 3 | 86,2 |
| Victor Wembanyama | SAS | 64 | 3 | 92,6 | 2 | 93,6 |
| Tyrese Maxey | PHI | 70 | 4 | 84,7 | 5 | 75,3 |
| Kawhi Leonard | LAC | 65 | 5 | 78,2 | 4 | 76,9 |
| Scottie Barnes | TOR | 80 | 6 | 76,7 | 13 | 53,9 |
| Kevin Durant | HOU | 78 | 7 | 74,0 | 14 | 52,5 |
| Jamal Murray | DEN | 75 | 8 | 73,2 | 11 | 56,4 |
| Luka Dončić | LAL | 64 | 9 | 67,4 | 6 | 69,7 |
| Donovan Mitchell | CLE | 70 | 10 | 67,4 | 7 | 58,4 |

Maç başı sıralamada en çok yükselen 5 oyuncu (GP ≥ 20):

| Oyuncu | Takım | MS | Toplam sırası | Maç başı sırası | Fark |
|---|---|---|---|---|---|
| Anthony Davis | WAS | 20 | 289 | 22 | +267 |
| Keegan Murray | SAC | 23 | 309 | 88 | +221 |
| Ja Morant | MEM | 20 | 348 | 143 | +205 |
| Tyler Herro | MIA | 33 | 226 | 48 | +178 |
| Kristaps Porziņģis | GSW | 32 | 254 | 76 | +178 |

## 9. Ölçekleme

Ham değer (9 z-skorun toplamı) 0–100 ölçeğine taşınır:

```
değer = 100 × (ham − ham_yedek) / (ham_1 − ham_yedek)
```

- `ham_1`: havuz adayları arasında en yüksek ham değer (Nikola Jokić, 12,418) → 100.
- `ham_yedek`: havuz adayları arasında 241. sıradaki ham değer (-3,904) → 0. Bu, 16 takımın toplam 240 kadro yerine giremeyen ilk oyuncu, yani serbest oyuncu (yedek) seviyesidir.
- Yedek seviyesinin altındaki oyuncular negatif değer alır.

Örnek: 100. sıradaki Quentin Grimes, ham -0,256 → 100 × (-0,256 − (-3,904)) / (12,418 − (-3,904)) = **22,4** (CSV: 22,4).

Maç başı modda ölçeği yalnızca GP ≥ 20 adaylar belirler (ham_1 = 12,753, ham_yedek = -3,386). Daha az maç oynayanların değeri aynı ölçekle hesaplanır ve 100'ü aşabilir (bu sezon 0 oyuncu).

## 10. Çalışılmış Örnek

Sezon toplamı modunda 1. sıradaki oyuncu: **Nikola Jokić** (DEN, 65 maç). μ ve σ, bölüm 7'deki tablodan alınır.

| Kategori | Oyuncu | μ | σ | Hesap | z |
|---|---|---|---|---|---|
| Sayı (`PTS`) | 1799 | 911,508 | 403,776 | (1799 − 911,508) / 403,776 | +2,198 |
| Ribaund (`REB`) | 836 | 333,246 | 150,285 | (836 − 333,246) / 150,285 | +3,345 |
| Asist (`AST`) | 697 | 206,900 | 131,410 | (697 − 206,900) / 131,410 | +3,730 |
| Üçlük (`FG3M`) | 112 | 100,221 | 64,402 | (112 − 100,221) / 64,402 | +0,183 |
| Top çalma (`STL`) | 92 | 63,087 | 24,759 | (92 − 63,087) / 24,759 | +1,168 |
| Blok (`BLK`) | 53 | 38,212 | 28,948 | (53 − 38,212) / 28,948 | +0,511 |
| Top kaybı (`TOV`) | 243 | 104,454 | 52,716 | (104,454 − 243) / 52,716 | -2,628 |
| Saha içi yüzdesi (`FG_PCT`) | 644/1132 (%56,9) | 0,000 | 36,516 | etki = 644 − 0,4807 × 1132 = +99,807; z = (+99,807 − 0,000) / 36,516 | +2,733 |
| Serbest atış yüzdesi (`FT_PCT`) | 399/480 (%83,1) | 0,000 | 17,095 | etki = 399 − 0,7893 × 480 = +20,147; z = (+20,147 − 0,000) / 17,095 | +1,179 |

Toplam z (ham değer): **12,418** (CSV'deki `raw_total`: 12,418). Ölçeklenmiş değer: **100,0**.

Küçük farklar, tablodaki μ ve σ'nın 6 ondalığa yuvarlanmış olmasından gelir.

## 11. Sınırlamalar

- **Az maç oynayanlar toplam modda top kaybından artı alır.** Top kaybı sezon toplamı olarak sayıldığı için az oynayan oyuncunun top kaybı da azdır. Örneğin Haywood Highsmith 7 maçta 0 top kaybıyla bu kategoride en yüksek z'yi aldı (+1,981). Diğer kategorilerdeki eksi değerler bunu genellikle dengeler, ama sıralamanın alt kısmında etkisi görülebilir.
- **Kategori ağırlıkları eşittir.** Her kategori 1 puan sayılır; "punt" (bir kategoriyi bilerek bırakma) stratejileri hesaba katılmaz.
- **Geçmiş veri geleceği garanti etmez.** Değerler 2025-26 normal sezonunun kapanmış verisine dayanır; yaş, sakatlık, rol ve takım değişiklikleri yansıtılmaz.
- **Maç başı değer az örneklemde yanıltıcı olabilir.** 20 maçtan az oynayan oyuncular işaretlenir; değerleri dikkatle yorumlanmalıdır.
- **Tanımsız yüzdeler.** Hiç deneme yapmayan oyuncuların ilgili yüzdesi "—" ile gösterilir (19 oyuncu); etkileri 0 kabul edilir.
- **Havuz yaklaşıktır.** 240 kişilik havuz, gerçek liglerdeki kadro seçimlerini birebir yansıtmaz; havuz büyüklüğü tek bir ayarla değiştirilebilir.
