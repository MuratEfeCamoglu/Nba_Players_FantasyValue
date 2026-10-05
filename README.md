# fantasy9cat — Fantezi NBA 9-Cat Oyuncu Değerleme

2025-26 NBA normal sezonu verisinden, 16 takım × 15 kadroluk H2H 9-cat lig için z-skor tabanlı
oyuncu değerlemesi. Kapsam ve formüller: [ISKELET.md](ISKELET.md).

> Durum: Aşama 0 (kurulum) ve Aşama 1 (veri: `fetch`, doğrulama) tamam. `compute`, `report`,
> `site`, `all` henüz uygulanmadı (çıkış kodu 2).

## Kurulum

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Veri çekme

```bash
python -m fantasy9cat fetch        # → data/raw/players_2025-26_regular.csv
```

`fetch` mevcut ham CSV'nin üzerine yazmaz; yeniden çekmek için dosyayı önce elle kaldırın.

### stats.nba.com erişilemezse: elle CSV

stats.nba.com bazı ağları (özellikle bulut IP'lerini) engeller. Bu durumda ham dosyayı elle
hazırlayıp `data/raw/players_2025-26_regular.csv` adıyla koyun. Dosya şu şemaya uymalıdır
(ISKELET.md §3.4):

| Kolon | Tip | Açıklama |
|---|---|---|
| `PLAYER_ID` | tamsayı | NBA oyuncu kimliği |
| `PLAYER_NAME` | metin | Oyuncu adı |
| `TEAM_ABBREVIATION` | metin | Son takımı (takım değiştiren oyuncu tek satır) |
| `GP, MIN, FGM, FGA, FG3M, FTM, FTA, REB, AST, STL, BLK, TOV, PTS` | sayı ≥ 0 | Sezon **toplamları** (maç başı değil) |

- Kaynak: nba.com/stats → Players → Traditional Stats, Season `2025-26`, Season Type
  `Regular Season`, Per Mode `Totals`.
- UTF-8, virgülle ayrılmış, ondalık ayırıcı nokta, başlık satırı yukarıdaki kolon adlarıyla.
- Kurallar: en az 400 satır; boş/negatif değer yok; `FGM ≤ FGA`, `FTM ≤ FTA`, `FG3M ≤ FGM`.

Dosyayı denetlemek için:

```bash
python -c "import pandas as pd; from fantasy9cat.schema import validate; validate(pd.read_csv('data/raw/players_2025-26_regular.csv')); print('geçerli')"
```

## Kalite

```bash
pytest -q
ruff check .
ruff format --check .
```

Test fikstürü: `python tests/fixtures/make_sample_players.py` (seed=42, deterministik).
