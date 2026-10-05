"""Ham oyuncu CSV'sinin kolon ve değer doğrulaması (F2)."""

import logging

import pandas as pd

from fantasy9cat import config

logger = logging.getLogger(__name__)

_MAX_EXAMPLES = 5


class DataValidationError(ValueError):
    """Ham veri ISKELET.md §3.4 şemasına veya F2 kurallarına uymadığında fırlatılır."""


def _examples(df: pd.DataFrame, mask: pd.Series) -> str:
    """Hatalı satırlardan birkaç oyuncu adını okunur biçimde döndürür."""
    names = df.loc[mask, "PLAYER_NAME"].astype(str).head(_MAX_EXAMPLES).tolist()
    more = int(mask.sum()) - len(names)
    suffix = f" ve {more} oyuncu daha" if more > 0 else ""
    return ", ".join(names) + suffix


def validate(df: pd.DataFrame) -> None:
    """Ham oyuncu verisini doğrular; F2 ihlalinde DataValidationError fırlatır."""
    missing = [c for c in config.RAW_COLUMNS if c not in df.columns]
    if missing:
        raise DataValidationError(f"Eksik kolon(lar): {', '.join(missing)}")

    if len(df) < config.MIN_RAW_ROWS:
        raise DataValidationError(
            f"Satır sayısı {len(df)}; en az {config.MIN_RAW_ROWS} oyuncu bekleniyor."
        )

    numeric = df[list(config.NUMERIC_COLUMNS)].apply(pd.to_numeric, errors="coerce")
    for col in config.NUMERIC_COLUMNS:
        bad = numeric[col].isna()
        if bad.any():
            raise DataValidationError(
                f"{col} kolonunda boş veya sayısal olmayan değer var: {_examples(df, bad)}"
            )
        neg = numeric[col] < 0
        if neg.any():
            raise DataValidationError(f"{col} kolonunda negatif değer var: {_examples(df, neg)}")

    for made, attempted in (("FGM", "FGA"), ("FTM", "FTA"), ("FG3M", "FGM")):
        bad = numeric[made] > numeric[attempted]
        if bad.any():
            raise DataValidationError(f"{made} > {attempted} olan satır(lar): {_examples(df, bad)}")

    over = numeric["GP"] > config.MAX_REGULAR_SEASON_GP
    if over.any():
        logger.warning(
            "GP > %d olan oyuncu(lar) var (hata değil): %s",
            config.MAX_REGULAR_SEASON_GP,
            _examples(df, over),
        )
