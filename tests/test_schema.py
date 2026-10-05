"""schema.validate() testleri (F2) ve fikstür sözleşmesi."""

import hashlib
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from fantasy9cat import config
from fantasy9cat.schema import DataValidationError, validate

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
SAMPLE_CSV = FIXTURE_DIR / "sample_players.csv"


@pytest.fixture
def players() -> pd.DataFrame:
    return pd.read_csv(SAMPLE_CSV)


# --- Geçerli veri ---


def test_valid_fixture_passes(players: pd.DataFrame) -> None:
    validate(players)


def test_extra_columns_are_allowed(players: pd.DataFrame) -> None:
    players["EXTRA"] = 1
    validate(players)


# --- F2 hata durumları (her biri ayrı test) ---


def test_missing_column_raises(players: pd.DataFrame) -> None:
    with pytest.raises(DataValidationError, match="FG3M"):
        validate(players.drop(columns=["FG3M"]))


def test_negative_value_raises(players: pd.DataFrame) -> None:
    players.loc[5, "STL"] = -1
    with pytest.raises(DataValidationError, match="negatif"):
        validate(players)


def test_empty_numeric_value_raises(players: pd.DataFrame) -> None:
    players.loc[5, "REB"] = np.nan
    with pytest.raises(DataValidationError, match="boş"):
        validate(players)


def test_non_numeric_value_raises(players: pd.DataFrame) -> None:
    players["AST"] = players["AST"].astype(object)
    players.loc[5, "AST"] = "abc"
    with pytest.raises(DataValidationError, match="AST"):
        validate(players)


def test_fgm_greater_than_fga_raises(players: pd.DataFrame) -> None:
    players.loc[5, "FGM"] = players.loc[5, "FGA"] + 1
    with pytest.raises(DataValidationError, match="FGM > FGA"):
        validate(players)


def test_ftm_greater_than_fta_raises(players: pd.DataFrame) -> None:
    players.loc[5, "FTM"] = players.loc[5, "FTA"] + 1
    with pytest.raises(DataValidationError, match="FTM > FTA"):
        validate(players)


def test_fg3m_greater_than_fgm_raises(players: pd.DataFrame) -> None:
    players.loc[5, "FG3M"] = players.loc[5, "FGM"] + 1
    with pytest.raises(DataValidationError, match="FG3M > FGM"):
        validate(players)


def test_too_few_rows_raises(players: pd.DataFrame) -> None:
    short = players.head(config.MIN_RAW_ROWS - 1)
    with pytest.raises(DataValidationError, match=str(config.MIN_RAW_ROWS)):
        validate(short)


def test_exactly_min_rows_passes(players: pd.DataFrame) -> None:
    validate(players.head(config.MIN_RAW_ROWS))


# --- Uyarı (hata değil) ---


def test_gp_over_82_only_warns(players: pd.DataFrame, caplog: pytest.LogCaptureFixture) -> None:
    players.loc[5, "GP"] = config.MAX_REGULAR_SEASON_GP + 1
    with caplog.at_level(logging.WARNING, logger="fantasy9cat.schema"):
        validate(players)
    assert any("GP" in r.getMessage() for r in caplog.records if r.levelno == logging.WARNING)


# --- Fikstür sözleşmesi (ISKELET.md §4) ---


def test_fixture_contract(players: pd.DataFrame) -> None:
    assert len(players) == 500
    assert (players["GP"] >= 20).sum() >= 300
    assert (players["GP"] < 20).sum() >= 30
    names = set(players["PLAYER_NAME"])
    assert {"Alperen Şengün", "Nikola Jokić"} <= names
    assert list(players.columns) == list(config.RAW_COLUMNS)


def test_fixture_generator_is_deterministic(tmp_path: Path) -> None:
    expected = hashlib.sha256(SAMPLE_CSV.read_bytes()).hexdigest()
    sys.path.insert(0, str(FIXTURE_DIR))
    try:
        import make_sample_players as gen
    finally:
        sys.path.pop(0)
    out = tmp_path / "sample.csv"
    gen.make_sample_players().to_csv(out, index=False, lineterminator="\n", encoding="utf-8")
    assert hashlib.sha256(out.read_bytes()).hexdigest() == expected
