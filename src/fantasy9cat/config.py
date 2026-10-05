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
