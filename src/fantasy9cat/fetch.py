"""stats.nba.com'dan sezon toplamlarını çekip ham CSV'ye yazar (F1)."""

import logging
import time
from collections.abc import Callable
from pathlib import Path

import pandas as pd
import requests
from nba_api.stats.endpoints.leaguedashplayerstats import LeagueDashPlayerStats

from fantasy9cat import config
from fantasy9cat.schema import DataValidationError, validate

__all__ = ["DataValidationError", "FetchError", "fetch_players", "run_fetch"]

logger = logging.getLogger(__name__)

# Ağ/yanıt sorunları: bağlantı, zaman aşımı, HTTP hatası, JSON çözümleme (ValueError),
# beklenen sonuç kümesinin yanıtta olmaması (KeyError, IndexError).
_RETRYABLE_ERRORS = (requests.exceptions.RequestException, ValueError, KeyError, IndexError)


class FetchError(RuntimeError):
    """Tüm denemelere rağmen veri çekilemediğinde fırlatılır."""


def _request_totals(season: str) -> pd.DataFrame:
    """Tek bir LeagueDashPlayerStats isteği atar ve ham DataFrame döndürür."""
    endpoint = LeagueDashPlayerStats(
        season=season,
        season_type_all_star=config.SEASON_TYPE,
        per_mode_detailed="Totals",
        timeout=config.FETCH_TIMEOUT_SECONDS,
    )
    return endpoint.get_data_frames()[0]


def _to_raw_schema(df: pd.DataFrame) -> pd.DataFrame:
    """API yanıtını ISKELET.md §3.4 kolonlarına indirger, tipleri ve sırayı sabitler."""
    missing = [c for c in config.RAW_COLUMNS if c not in df.columns]
    if missing:
        raise DataValidationError(f"API yanıtında eksik kolon(lar): {', '.join(missing)}")
    out = df[list(config.RAW_COLUMNS)].copy()
    out["PLAYER_ID"] = pd.to_numeric(out["PLAYER_ID"], errors="raise").astype("int64")
    out["PLAYER_NAME"] = out["PLAYER_NAME"].astype(str)
    out["TEAM_ABBREVIATION"] = out["TEAM_ABBREVIATION"].astype(str)
    int_cols = [c for c in config.NUMERIC_COLUMNS if c != "MIN"]
    numeric = out[list(config.NUMERIC_COLUMNS)].apply(pd.to_numeric, errors="coerce")
    if numeric.isna().any().any():
        bad = [c for c in config.NUMERIC_COLUMNS if numeric[c].isna().any()]
        raise DataValidationError(f"API yanıtında boş sayısal değer: {', '.join(bad)}")
    out[int_cols] = numeric[int_cols].round().astype("int64")
    out["MIN"] = numeric["MIN"].astype("float64").round(6)
    return out.sort_values("PLAYER_ID", kind="mergesort", ignore_index=True)


def fetch_players(
    season: str = config.SEASON, sleep: Callable[[float], None] | None = None
) -> pd.DataFrame:
    """Sezon toplamlarını en fazla 3 denemeyle çeker; §3.4 şemasında DataFrame döndürür."""
    sleep = sleep or time.sleep
    attempts = config.FETCH_MAX_ATTEMPTS
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            logger.info("stats.nba.com isteği (%s, deneme %d/%d)", season, attempt, attempts)
            frame = _request_totals(season)
            break
        except _RETRYABLE_ERRORS as exc:
            last_error = exc
            logger.warning("Deneme %d başarısız: %s: %s", attempt, type(exc).__name__, exc)
            if attempt < attempts:
                delay = config.FETCH_RETRY_DELAYS_SECONDS[attempt - 1]
                logger.info("%d sn sonra yeniden denenecek", delay)
                sleep(delay)
    else:
        raise FetchError(
            f"stats.nba.com'dan {season} verisi {attempts} denemede alınamadı. "
            f"Son hata: {type(last_error).__name__}: {last_error}"
        ) from last_error
    return _to_raw_schema(frame)


def run_fetch(
    season: str = config.SEASON,
    output_path: Path | None = None,
    sleep: Callable[[float], None] | None = None,
) -> int:
    """Veriyi çeker, doğrular ve ham CSV'ye yazar; yazılan satır sayısını döndürür."""
    path = output_path or config.raw_csv_path(season)
    if path.exists():
        raise FileExistsError(
            f"{path} zaten var. Ham veri tekrarlanabilirliğin kaynağıdır; "
            "üzerine yazmak için dosyayı elle kaldırın."
        )
    df = fetch_players(season, sleep=sleep)
    validate(df)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".csv.tmp")
    df.to_csv(tmp, index=False, lineterminator="\n", encoding="utf-8")
    tmp.replace(path)
    logger.info("%d oyuncu yazıldı: %s", len(df), path)
    return len(df)
