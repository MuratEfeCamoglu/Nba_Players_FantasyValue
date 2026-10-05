"""Proje genelindeki tüm sabitler ve yollar."""

from pathlib import Path

# Sezon
SEASON = "2025-26"
SEASON_TYPE = "Regular Season"

# Lig formatı
NUM_TEAMS = 16
ROSTER_SIZE = 15
POOL_SIZE = NUM_TEAMS * ROSTER_SIZE
MIN_GP_POOL_PER_GAME = 20
MAX_POOL_ITERATIONS = 10

# Kategoriler (ISKELET.md §0)
COUNTING_CATEGORIES = ("PTS", "REB", "AST", "FG3M", "STL", "BLK")
TURNOVER_CATEGORY = "TOV"
PERCENT_CATEGORIES = ("FG_PCT", "FT_PCT")
CATEGORIES = (*COUNTING_CATEGORIES, TURNOVER_CATEGORY, *PERCENT_CATEGORIES)

# Ham CSV şeması (ISKELET.md §3.4)
ID_COLUMNS = ("PLAYER_ID", "PLAYER_NAME", "TEAM_ABBREVIATION")
NUMERIC_COLUMNS = (
    "GP",
    "MIN",
    "FGM",
    "FGA",
    "FG3M",
    "FTM",
    "FTA",
    "REB",
    "AST",
    "STL",
    "BLK",
    "TOV",
    "PTS",
)
RAW_COLUMNS = (*ID_COLUMNS, *NUMERIC_COLUMNS)

# Doğrulama
MIN_RAW_ROWS = 400
MAX_REGULAR_SEASON_GP = 82

# Veri çekme
FETCH_TIMEOUT_SECONDS = 60
FETCH_MAX_ATTEMPTS = 3
FETCH_RETRY_DELAYS_SECONDS = (5, 10, 20)

# Yollar
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
OUTPUT_DIR = PROJECT_ROOT / "output"
SITE_DIR = OUTPUT_DIR / "site"
TEMPLATES_DIR = PROJECT_ROOT / "templates"
FONTS_DIR = PROJECT_ROOT / "assets" / "fonts"


def raw_csv_path(season: str = SEASON) -> Path:
    """Verilen sezonun ham CSV dosya yolunu döndürür."""
    return RAW_DIR / f"players_{season}_regular.csv"


# Değerleme modları ve çıktı şemaları (ISKELET.md §3.3, §3.4)
MODE_TOTAL = "total"
MODE_PER_GAME = "per_game"
MODES = (MODE_TOTAL, MODE_PER_GAME)
PER_GAME_COLUMNS = (
    "MIN",
    "PTS",
    "REB",
    "AST",
    "FG3M",
    "STL",
    "BLK",
    "TOV",
    "FGM",
    "FGA",
    "FTM",
    "FTA",
)
PERCENT_SOURCE_COLUMNS = {"FG_PCT": ("FGM", "FGA"), "FT_PCT": ("FTM", "FTA")}
MIN_GP_VALUED = 1
Z_COLUMNS = tuple(f"z_{c.lower()}" for c in CATEGORIES)
VALUES_COLUMNS = (
    "rank",
    "player_id",
    "player_name",
    "team",
    "gp",
    "min",
    "pts",
    "reb",
    "ast",
    "fg3m",
    "stl",
    "blk",
    "tov",
    "fgm",
    "fga",
    "fg_pct",
    "ftm",
    "fta",
    "ft_pct",
    *Z_COLUMNS,
    "raw_total",
    "value",
    "in_pool",
    "low_sample",
)
MULTIPLIERS_COLUMNS = (
    "mode",
    "category",
    "mu",
    "sigma",
    "multiplier",
    "points_equivalent",
    "mean_ratio_to_pts",
    "league_pct",
)
SCALE_TOP_VALUE = 100.0
CSV_DECIMALS = 6
VALUES_FILENAMES = {MODE_TOTAL: "values_total.csv", MODE_PER_GAME: "values_per_game.csv"}
MULTIPLIERS_FILENAME = "multipliers.csv"
META_FILENAME = "meta.json"

# Rapor (ISKELET.md §3.5)
HESAPLAMA_MD_FILENAME = "Hesaplama.md"
HESAPLAMA_TEMPLATE = "hesaplama.md.j2"
PROCESSED_FILES = (*VALUES_FILENAMES.values(), MULTIPLIERS_FILENAME, META_FILENAME)
REPORT_SECTIONS = (
    "1. Kategoriler",
    "2. Neden Z-Skor?",
    "3. Oyuncu Havuzu",
    "4. Sayma Kategorileri",
    "5. Top Kaybı",
    "6. Yüzde Kategorileri ve Hacim",
    "7. Çarpan Tablosu",
    "8. Maç Sayısının Etkisi",
    "9. Ölçekleme",
    "10. Çalışılmış Örnek",
    "11. Sınırlamalar",
)
# (isabet, deneme, lig yüzdesi) — F4 / V4 sayısal örnekleri
IMPACT_EXAMPLES = ((6, 10, 0.50), (60, 100, 0.50), (60, 100, 0.65))
WORKED_EXAMPLE_RANK = 1
SCALE_EXAMPLE_RANK = 100
COMPARISON_TOP_N = 10
COMPARISON_MOVERS_N = 5

# PDF (ISKELET.md §3.5, F10)
DEGER_PDF_FILENAME = "Deger.pdf"
PDF_SECTIONS = (
    "1. Yöntem Özeti ve Çarpan Tablosu",
    "2. Sezon Toplamı Sıralaması",
    "3. Maç Başı Sıralaması",
)
PDF_RANKING_HEADERS = (
    "Sıra",
    "Oyuncu",
    "Takım",
    "MS",
    "PTS",
    "REB",
    "AST",
    "3P",
    "STL",
    "BLK",
    "TO",
    "FG%",
    "FT%",
    "Ham",
    "Değer",
)
PDF_MAX_BYTES = 5 * 1024 * 1024
LOW_SAMPLE_MARK = "*"
LOW_SAMPLE_NOTE = f"* {MIN_GP_POOL_PER_GAME} maçtan az oynadı, maç başı değeri az örnekleme dayanır"
FONT_REGULAR = "DejaVuSans"
FONT_BOLD = "DejaVuSans-Bold"

# Site (ISKELET.md §3.5, F11–F14)
SITE_DIRNAME = "site"
SITE_ASSETS = ("style.css", "app.js", "favicon.svg")
SITE_PAGES = {"index.html": "site/index.html.j2", "hesaplama.html": "site/hesaplama.html.j2"}
SITE_MAX_BYTES = 3 * 1024 * 1024  # F16 (Aşama 7) sonrası sınır
# F13: site yalnızca bu dosyalar varsa üretilir (işlenmiş veriler + rapor çıktıları)
SITE_REQUIRED_OUTPUTS = (HESAPLAMA_MD_FILENAME, DEGER_PDF_FILENAME)
CALCULATOR_MARKER = "<!-- etki-hesaplayici -->"
POINTS_CHART_MARKER = "<!-- sayi-esdegeri-grafigi -->"
SITE_FONT_FILES = (
    "Inter-Regular.woff2",
    "Inter-SemiBold.woff2",
    "BarlowCondensed-Bold.woff2",
    "OFL-Inter.txt",
    "OFL-Barlow.txt",
)
# Sitede gösterilen veri tarihi: ham verinin stats.nba.com'dan çekildiği gün (sabit; çalıştırma
# anı değil, çünkü çıktılara zaman damgası yazılmaz).
DATA_AS_OF = "2026-10-05"
