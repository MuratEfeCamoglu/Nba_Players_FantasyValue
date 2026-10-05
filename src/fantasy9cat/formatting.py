"""Kullanıcıya dönük Türkçe sayı biçimi ve kategori etiketleri."""

import math

MISSING = "—"

CATEGORY_LABELS = {
    "PTS": "Sayı",
    "REB": "Ribaund",
    "AST": "Asist",
    "FG3M": "Üçlük",
    "STL": "Top çalma",
    "BLK": "Blok",
    "TOV": "Top kaybı",
    "FG_PCT": "Saha içi yüzdesi",
    "FT_PCT": "Serbest atış yüzdesi",
}

CATEGORY_SHORT = {
    "PTS": "PTS",
    "REB": "REB",
    "AST": "AST",
    "FG3M": "3P",
    "STL": "STL",
    "BLK": "BLK",
    "TOV": "TO",
    "FG_PCT": "FG%",
    "FT_PCT": "FT%",
}


# "1 birim = X sayı" karşılaştırmasında birimin adı
CATEGORY_UNITS = {
    "PTS": "1 sayı",
    "REB": "1 ribaund",
    "AST": "1 asist",
    "FG3M": "1 üçlük",
    "STL": "1 top çalma",
    "BLK": "1 blok",
    "TOV": "1 top kaybı daha az",
    "FG_PCT": "Ortalamanın üstünde 1 saha içi isabet",
    "FT_PCT": "Ortalamanın üstünde 1 serbest atış isabeti",
}


def _is_missing(value: float | None) -> bool:
    """Değer boş (None veya NaN) mu?"""
    return value is None or (isinstance(value, float) and math.isnan(value))


def fmt_num(value: float | None, decimals: int = 2, signed: bool = False) -> str:
    """Sayıyı ondalık virgülle biçimler; boş değer için '—' döndürür."""
    if _is_missing(value):
        return MISSING
    text = f"{float(value):.{decimals}f}"
    if text.lstrip("-").strip("0.") == "":
        text = text.lstrip("-")  # −0,000 yerine 0,000
    elif signed and not text.startswith("-"):
        text = "+" + text
    return text.replace(".", ",")


def fmt_pct(value: float | None, decimals: int = 1) -> str:
    """Oranı Türkçe yüzde olarak biçimler (0,4807 → '%48,1'); boşsa '—'."""
    if _is_missing(value):
        return MISSING
    return "%" + fmt_num(float(value) * 100, decimals)


def fmt_date(iso_date: str) -> str:
    """ISO tarihi (2026-10-05) Türkçe gün.ay.yıl biçimine (05.10.2026) çevirir."""
    year, month, day = iso_date.split("-")
    return f"{day}.{month}.{year}"
