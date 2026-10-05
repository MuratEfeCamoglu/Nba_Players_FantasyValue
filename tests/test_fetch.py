"""fetch.py (F1) ve CLI iskeleti testleri. nba_api çağrısı her zaman mock'lanır."""

from pathlib import Path
from unittest import mock

import pandas as pd
import pytest
import requests

from fantasy9cat import config, fetch
from fantasy9cat.__main__ import main

SAMPLE_CSV = Path(__file__).resolve().parent / "fixtures" / "sample_players.csv"


def _api_frame() -> pd.DataFrame:
    """nba_api yanıtını taklit eder: ek kolonlar ve farklı kolon sırası."""
    df = pd.read_csv(SAMPLE_CSV)
    df["TEAM_ID"] = 1610612700
    df["AGE"] = 25.0
    df["FG_PCT"] = df["FGM"] / df["FGA"]
    df["MIN"] = df["MIN"] + 0.123456789
    return df[list(reversed(df.columns))].sample(frac=1.0, random_state=1)


def _endpoint_returning(frame: pd.DataFrame) -> mock.MagicMock:
    instance = mock.MagicMock()
    instance.get_data_frames.return_value = [frame]
    return mock.MagicMock(return_value=instance)


# --- fetch_players ---


def test_fetch_players_calls_endpoint_with_spec_params() -> None:
    endpoint = _endpoint_returning(_api_frame())
    with mock.patch.object(fetch, "LeagueDashPlayerStats", endpoint):
        fetch.fetch_players("2025-26", sleep=lambda s: None)
    endpoint.assert_called_once_with(
        season="2025-26",
        season_type_all_star="Regular Season",
        per_mode_detailed="Totals",
        timeout=60,
    )


def test_fetch_players_returns_schema_columns_sorted() -> None:
    endpoint = _endpoint_returning(_api_frame())
    with mock.patch.object(fetch, "LeagueDashPlayerStats", endpoint):
        df = fetch.fetch_players("2025-26", sleep=lambda s: None)
    assert list(df.columns) == list(config.RAW_COLUMNS)
    assert df["PLAYER_ID"].is_monotonic_increasing
    assert len(df) == 500
    assert df["GP"].dtype.kind == "i"
    assert df["MIN"].dtype.kind == "f"


def test_fetch_retries_then_succeeds() -> None:
    instance = mock.MagicMock()
    instance.get_data_frames.return_value = [_api_frame()]
    endpoint = mock.MagicMock(
        side_effect=[requests.exceptions.ReadTimeout("zaman aşımı"), instance]
    )
    sleeps: list[float] = []
    with mock.patch.object(fetch, "LeagueDashPlayerStats", endpoint):
        df = fetch.fetch_players("2025-26", sleep=sleeps.append)
    assert endpoint.call_count == 2
    assert sleeps == [5]
    assert len(df) == 500


def test_fetch_gives_up_after_three_attempts() -> None:
    endpoint = mock.MagicMock(side_effect=requests.exceptions.ConnectionError("bağlantı yok"))
    sleeps: list[float] = []
    with mock.patch.object(fetch, "LeagueDashPlayerStats", endpoint):
        with pytest.raises(fetch.FetchError, match="3 deneme"):
            fetch.fetch_players("2025-26", sleep=sleeps.append)
    assert endpoint.call_count == config.FETCH_MAX_ATTEMPTS == 3
    assert sleeps == [5, 10]


def test_fetch_invalid_json_is_retried() -> None:
    endpoint = mock.MagicMock(side_effect=ValueError("Expecting value: line 1 column 1"))
    with mock.patch.object(fetch, "LeagueDashPlayerStats", endpoint):
        with pytest.raises(fetch.FetchError):
            fetch.fetch_players("2025-26", sleep=lambda s: None)
    assert endpoint.call_count == 3


# --- run_fetch (doğrula + yaz) ---


def test_run_fetch_writes_valid_csv(tmp_path: Path) -> None:
    out = tmp_path / "raw" / "players.csv"
    endpoint = _endpoint_returning(_api_frame())
    with mock.patch.object(fetch, "LeagueDashPlayerStats", endpoint):
        n = fetch.run_fetch("2025-26", out, sleep=lambda s: None)
    assert n == 500
    df = pd.read_csv(out)
    assert list(df.columns) == list(config.RAW_COLUMNS)
    assert (df[list(config.NUMERIC_COLUMNS)] >= 0).all().all()
    assert not df.isna().any().any()
    assert out.read_bytes().count(b"\r\n") == 0


def test_run_fetch_is_deterministic(tmp_path: Path) -> None:
    outs = [tmp_path / "a.csv", tmp_path / "b.csv"]
    for out in outs:
        endpoint = _endpoint_returning(_api_frame())
        with mock.patch.object(fetch, "LeagueDashPlayerStats", endpoint):
            fetch.run_fetch("2025-26", out, sleep=lambda s: None)
    assert outs[0].read_bytes() == outs[1].read_bytes()


def test_run_fetch_does_not_write_invalid_data(tmp_path: Path) -> None:
    out = tmp_path / "players.csv"
    endpoint = _endpoint_returning(_api_frame().head(10))
    with mock.patch.object(fetch, "LeagueDashPlayerStats", endpoint):
        with pytest.raises(fetch.DataValidationError):
            fetch.run_fetch("2025-26", out, sleep=lambda s: None)
    assert not out.exists()


def test_run_fetch_refuses_to_overwrite_existing(tmp_path: Path) -> None:
    out = tmp_path / "players.csv"
    out.write_text("eski", encoding="utf-8")
    endpoint = _endpoint_returning(_api_frame())
    with mock.patch.object(fetch, "LeagueDashPlayerStats", endpoint):
        with pytest.raises(FileExistsError):
            fetch.run_fetch("2025-26", out, sleep=lambda s: None)
    endpoint.assert_not_called()
    assert out.read_text(encoding="utf-8") == "eski"


# --- CLI ---


def test_cli_fetch_network_error_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(config, "RAW_DIR", tmp_path)
    monkeypatch.setattr(fetch.time, "sleep", lambda s: None)
    endpoint = mock.MagicMock(side_effect=requests.exceptions.ConnectionError("bağlantı yok"))
    with mock.patch.object(fetch, "LeagueDashPlayerStats", endpoint):
        assert main(["fetch"]) == 1
    assert endpoint.call_count == 3
    assert "Veri çekilemedi" in capsys.readouterr().err


def test_cli_fetch_success_exits_0(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "RAW_DIR", tmp_path)
    endpoint = _endpoint_returning(_api_frame())
    with mock.patch.object(fetch, "LeagueDashPlayerStats", endpoint):
        assert main(["fetch", "--season", "2025-26"]) == 0
    assert (tmp_path / "players_2025-26_regular.csv").exists()


def test_cli_fetch_validation_error_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(config, "RAW_DIR", tmp_path)
    endpoint = _endpoint_returning(_api_frame().head(10))
    with mock.patch.object(fetch, "LeagueDashPlayerStats", endpoint):
        assert main(["fetch"]) == 1
    assert "doğrulama" in capsys.readouterr().err.lower()


def test_cli_help_lists_five_commands(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    for command in ("fetch", "compute", "report", "site", "all"):
        assert command in out
