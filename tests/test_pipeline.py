"""pipeline.py (compute adımı) ve `compute` CLI testleri (F3, F5, F6, F7)."""

import hashlib
import json
import re
import shutil
from pathlib import Path

import pandas as pd
import pytest

from fantasy9cat import config
from fantasy9cat.__main__ import main
from fantasy9cat.pipeline import run_compute
from fantasy9cat.schema import DataValidationError
from fantasy9cat.valuation import value_players

SAMPLE_CSV = Path(__file__).resolve().parent / "fixtures" / "sample_players.csv"
OUTPUT_FILES = ("values_total.csv", "values_per_game.csv", "multipliers.csv", "meta.json")
META_KEYS = {
    "season",
    "season_type",
    "source_file",
    "source_sha256",
    "n_players_total",
    "n_players_per_game",
    "pool_size",
    "iterations_total",
    "converged_total",
    "iterations_per_game",
    "converged_per_game",
    "replacement_raw_total",
    "replacement_raw_per_game",
    "warnings",
}


@pytest.fixture(scope="module")
def computed(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("processed")
    run_compute(SAMPLE_CSV, out)
    return out


def test_writes_four_files(computed: Path) -> None:
    for name in OUTPUT_FILES:
        assert (computed / name).is_file(), name


@pytest.mark.parametrize("name", ["values_total.csv", "values_per_game.csv"])
def test_values_csv_schema(computed: Path, name: str) -> None:
    df = pd.read_csv(computed / name)
    assert list(df.columns) == list(config.VALUES_COLUMNS)
    assert len(df) == 500
    assert df["rank"].tolist() == list(range(1, 501))
    assert df["in_pool"].dtype == bool
    assert df["low_sample"].dtype == bool
    assert df["in_pool"].sum() == config.POOL_SIZE


def test_values_rounded_to_6_decimals(computed: Path) -> None:
    text = (computed / "values_total.csv").read_text(encoding="utf-8")
    first = text.splitlines()[1].split(",")
    z_pts = first[config.VALUES_COLUMNS.index("z_pts")]
    assert len(z_pts.split(".")[1]) == 6
    assert "\r\n" not in text


def test_csv_matches_valuation_within_rounding(computed: Path) -> None:
    res = value_players(pd.read_csv(SAMPLE_CSV), config.MODE_TOTAL)
    df = pd.read_csv(computed / "values_total.csv")
    for col in (*config.Z_COLUMNS, "raw_total", "value"):
        assert (df[col] - res.players[col]).abs().max() <= 5e-7, col


def test_per_game_file_flags_low_sample(computed: Path) -> None:
    df = pd.read_csv(computed / "values_per_game.csv")
    assert (df["low_sample"] == (df["gp"] < config.MIN_GP_POOL_PER_GAME)).all()
    total = pd.read_csv(computed / "values_total.csv")
    assert not total["low_sample"].any()


def test_zero_attempts_written_as_empty_cell(tmp_path: Path) -> None:
    raw = pd.read_csv(SAMPLE_CSV)
    target = raw.index[raw["PLAYER_ID"] == 1000001][0]
    raw.loc[target, ["FGM", "FGA", "FG3M"]] = 0
    raw_path = tmp_path / "raw.csv"
    raw.to_csv(raw_path, index=False)
    run_compute(raw_path, tmp_path / "out")
    for name in ("values_total.csv", "values_per_game.csv"):
        # Ham metin olarak oku: boş hücre "" kalır, NaN'a dönüşmez
        df = pd.read_csv(tmp_path / "out" / name, dtype=str, keep_default_na=False)
        zero_fga = df[df["fga"].astype(float) == 0]
        zero_fta = df[df["fta"].astype(float) == 0]
        assert len(zero_fga) == 1 and len(zero_fta) >= 1, name
        assert (zero_fga["fg_pct"] == "").all()  # 0 değil, boş
        assert (zero_fta["ft_pct"] == "").all()
        assert (zero_fga["z_fg_pct"] != "").all() and (zero_fta["z_ft_pct"] != "").all()
        assert (df.loc[df["fga"].astype(float) > 0, "fg_pct"] != "").all()


def test_multipliers_csv(computed: Path) -> None:
    df = pd.read_csv(computed / "multipliers.csv")
    assert list(df.columns) == list(config.MULTIPLIERS_COLUMNS)
    assert len(df) == 18
    assert df.groupby("mode").size().to_dict() == {"per_game": 9, "total": 9}
    pts = df[df["category"] == "PTS"]
    assert (pts["points_equivalent"] == 1.0).all()
    pct = df["category"].isin(config.PERCENT_CATEGORIES)
    assert df.loc[pct, "mean_ratio_to_pts"].isna().all()
    assert df.loc[pct, "league_pct"].notna().all()
    assert df.loc[~pct, "league_pct"].isna().all()


def test_meta_json(computed: Path) -> None:
    text = (computed / "meta.json").read_text(encoding="utf-8")
    meta = json.loads(text)
    assert set(meta) == META_KEYS
    assert list(meta) == sorted(meta)
    assert meta["season"] == config.SEASON
    assert meta["season_type"] == config.SEASON_TYPE
    assert meta["pool_size"] == config.POOL_SIZE == 240
    assert meta["n_players_total"] == meta["n_players_per_game"] == 500
    assert meta["source_sha256"] == hashlib.sha256(SAMPLE_CSV.read_bytes()).hexdigest()
    assert 1 <= meta["iterations_total"] <= config.MAX_POOL_ITERATIONS
    assert isinstance(meta["converged_total"], bool)
    assert isinstance(meta["converged_per_game"], bool)
    assert meta["warnings"] == []
    total = pd.read_csv(computed / "values_total.csv")
    assert meta["replacement_raw_total"] == pytest.approx(total["raw_total"].iloc[240], abs=1e-6)


def test_byte_identical_reruns(computed: Path, tmp_path: Path) -> None:
    run_compute(SAMPLE_CSV, tmp_path)
    for name in OUTPUT_FILES:
        assert (tmp_path / name).read_bytes() == (computed / name).read_bytes(), name


def test_invalid_raw_raises_and_writes_nothing(tmp_path: Path) -> None:
    bad = tmp_path / "bad.csv"
    pd.read_csv(SAMPLE_CSV).head(10).to_csv(bad, index=False)
    out = tmp_path / "out"
    with pytest.raises(DataValidationError):
        run_compute(bad, out)
    assert not out.exists() or not any(out.iterdir())


# --- CLI ---


def _use_dirs(monkeypatch: pytest.MonkeyPatch, raw_dir: Path, processed_dir: Path) -> None:
    monkeypatch.setattr(config, "RAW_DIR", raw_dir)
    monkeypatch.setattr(config, "PROCESSED_DIR", processed_dir)


def test_cli_compute_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    raw_dir, processed = tmp_path / "raw", tmp_path / "processed"
    raw_dir.mkdir()
    shutil.copy(SAMPLE_CSV, raw_dir / "players_2025-26_regular.csv")
    _use_dirs(monkeypatch, raw_dir, processed)
    assert main(["compute"]) == 0
    for name in OUTPUT_FILES:
        assert (processed / name).is_file()


def test_cli_compute_missing_raw_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _use_dirs(monkeypatch, tmp_path / "raw", tmp_path / "processed")
    assert main(["compute"]) == 1
    assert "bulunamadı" in capsys.readouterr().err


def test_cli_compute_invalid_raw_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    pd.read_csv(SAMPLE_CSV).head(10).to_csv(raw_dir / "players_2025-26_regular.csv", index=False)
    _use_dirs(monkeypatch, raw_dir, tmp_path / "processed")
    assert main(["compute"]) == 1
    assert "doğrulama" in capsys.readouterr().err.lower()


# --- F15: uçtan uca `all` komutu ---


def _all_dirs(monkeypatch: pytest.MonkeyPatch, root: Path) -> tuple[Path, Path, Path]:
    raw_dir, processed, output = root / "raw", root / "processed", root / "output"
    monkeypatch.setattr(config, "RAW_DIR", raw_dir)
    monkeypatch.setattr(config, "PROCESSED_DIR", processed)
    monkeypatch.setattr(config, "OUTPUT_DIR", output)
    return raw_dir, processed, output


def _assert_all_outputs(processed: Path, output: Path) -> None:
    for name in OUTPUT_FILES:
        assert (processed / name).is_file(), name
    for rel in ("Hesaplama.md", "Deger.pdf", "site/index.html", "site/hesaplama.html"):
        assert (output / rel).is_file(), rel


def test_cli_all_with_raw_csv_skips_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    from fantasy9cat import fetch

    raw_dir, processed, output = _all_dirs(monkeypatch, tmp_path)
    raw_dir.mkdir()
    shutil.copy(SAMPLE_CSV, raw_dir / "players_2025-26_regular.csv")

    def no_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("ham CSV varken ağa çıkıldı")

    monkeypatch.setattr(fetch, "LeagueDashPlayerStats", no_network)
    monkeypatch.setattr(fetch, "run_fetch", no_network)
    with caplog.at_level("INFO", logger="fantasy9cat"):
        assert main(["all"]) == 0
    _assert_all_outputs(processed, output)
    elapsed = [r for r in caplog.records if "Toplam süre" in r.getMessage()]
    assert len(elapsed) == 1
    seconds = float(re.search(r"([\d.]+) sn", elapsed[0].getMessage()).group(1))
    assert seconds < 60


def test_cli_all_runs_steps_in_order(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from fantasy9cat import __main__ as cli

    raw_dir, _, _ = _all_dirs(monkeypatch, tmp_path)
    raw_dir.mkdir()
    shutil.copy(SAMPLE_CSV, raw_dir / "players_2025-26_regular.csv")
    calls: list[str] = []
    for name in ("fetch", "compute", "report", "site"):
        monkeypatch.setattr(cli, f"_cmd_{name}", lambda args, n=name: calls.append(n) or 0)
    assert cli.main(["all"]) == 0
    assert calls == ["compute", "report", "site"]


def test_cli_all_without_raw_csv_fetches_first(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fantasy9cat import fetch

    raw_dir, processed, output = _all_dirs(monkeypatch, tmp_path)
    fetched: list[str] = []

    def fake_run_fetch(season: str) -> int:
        fetched.append(season)
        raw_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(SAMPLE_CSV, config.raw_csv_path(season))
        return 500

    monkeypatch.setattr(fetch, "run_fetch", fake_run_fetch)
    assert main(["all"]) == 0
    assert fetched == [config.SEASON]
    _assert_all_outputs(processed, output)


def test_cli_all_stops_when_fetch_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from fantasy9cat import fetch

    _, processed, output = _all_dirs(monkeypatch, tmp_path)

    def failing_fetch(season: str) -> int:
        raise fetch.FetchError("3 denemede alınamadı")

    monkeypatch.setattr(fetch, "run_fetch", failing_fetch)
    assert main(["all"]) == 1
    assert "Veri çekilemedi" in capsys.readouterr().err
    assert not processed.exists() and not output.exists()
