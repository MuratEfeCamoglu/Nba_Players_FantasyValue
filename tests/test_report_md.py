"""formatting.py, context.py ve report_md.py testleri (F9)."""

import math
import re
import shutil
from pathlib import Path

import pandas as pd
import pytest

from fantasy9cat import config
from fantasy9cat.__main__ import main
from fantasy9cat.context import build_context, build_worked_example
from fantasy9cat.formatting import (
    CATEGORY_LABELS,
    CATEGORY_SHORT,
    CATEGORY_UNITS,
    fmt_date,
    fmt_num,
    fmt_pct,
)
from fantasy9cat.pipeline import run_compute
from fantasy9cat.report_md import render_hesaplama, run_report_md

SAMPLE_CSV = Path(__file__).resolve().parent / "fixtures" / "sample_players.csv"
EXPECTED_SECTIONS = [
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
]
NUM_RE = r"[+-]?%?\d+(?:,\d+)?"


def parse_num(text: str) -> float:
    """Türkçe biçimli sayıyı (ondalık virgül, isteğe bağlı %) float'a çevirir."""
    text = text.strip().replace("−", "-")
    if "%" in text:
        return float(text.replace("%", "").replace(",", ".")) / 100
    return float(text.replace(",", "."))


@pytest.fixture(scope="module")
def processed(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("processed")
    run_compute(SAMPLE_CSV, out)
    return out


@pytest.fixture(scope="module")
def context(processed: Path) -> dict:
    return build_context(processed)


@pytest.fixture(scope="module")
def markdown(context: dict) -> str:
    return render_hesaplama(context)


# --- formatting ---


@pytest.mark.parametrize(
    ("value", "decimals", "expected"),
    [
        (1234.5678, 2, "1234,57"),
        (0.5, 3, "0,500"),
        (-1.26, 1, "-1,3"),
        (5, 0, "5"),
        (-0.0001, 3, "0,000"),  # −0 yazılmaz
    ],
)
def test_fmt_num_uses_decimal_comma(value: float, decimals: int, expected: str) -> None:
    assert fmt_num(value, decimals) == expected


def test_fmt_num_signed() -> None:
    assert fmt_num(2.0, 1, signed=True) == "+2,0"
    assert fmt_num(-2.0, 1, signed=True) == "-2,0"
    assert fmt_num(0.0, 1, signed=True) == "0,0"


@pytest.mark.parametrize("missing", [float("nan"), None])
def test_missing_values_shown_as_dash(missing: float | None) -> None:
    assert fmt_num(missing) == "—"
    assert fmt_pct(missing) == "—"


def test_fmt_pct() -> None:
    assert fmt_pct(0.480736) == "%48,1"
    assert fmt_pct(0.5, 0) == "%50"


def test_category_labels_cover_all_categories() -> None:
    assert set(CATEGORY_LABELS) == set(CATEGORY_UNITS) == set(config.CATEGORIES)
    assert [CATEGORY_SHORT[c] for c in config.CATEGORIES] == [
        "PTS", "REB", "AST", "3P", "STL", "BLK", "TO", "FG%", "FT%",
    ]  # fmt: skip


def test_fmt_date() -> None:
    assert fmt_date("2026-10-05") == "05.10.2026"


# --- context ---


def test_context_sections(context: dict) -> None:
    assert list(context["sections"]) == EXPECTED_SECTIONS


def test_context_impact_examples_match_f4(context: dict) -> None:
    impacts = [e["impact"] for e in context["impact_examples"]]
    assert impacts == pytest.approx([1.0, 10.0, -5.0])


def test_worked_example_reproduces_csv(context: dict, processed: Path) -> None:
    ex = context["worked_example"]
    total = pd.read_csv(processed / "values_total.csv")
    row = total.iloc[config.WORKED_EXAMPLE_RANK - 1]
    assert ex["player_name"] == row["player_name"]
    assert [r["code"] for r in ex["rows"]] == list(config.CATEGORIES)
    for r, zcol in zip(ex["rows"], config.Z_COLUMNS, strict=True):
        assert r["z"] == pytest.approx(row[zcol], abs=1e-4), r["code"]
    assert abs(ex["z_sum"] - row["raw_total"]) <= 0.01


def test_worked_example_zero_attempts_shows_dash(processed: Path) -> None:
    total = pd.read_csv(processed / "values_total.csv")
    mult = pd.read_csv(processed / "multipliers.csv")
    row = total.iloc[0].copy()
    row[["ftm", "fta"]] = 0
    row["ft_pct"] = float("nan")
    ex = build_worked_example(row, mult[mult["mode"] == config.MODE_TOTAL])
    ft = next(r for r in ex["rows"] if r["code"] == "FT_PCT")
    assert "—" in ft["value_text"]
    assert ft["impact"] == 0.0
    params = mult[(mult["mode"] == "total") & (mult["category"] == "FT_PCT")].iloc[0]
    assert ft["z"] == pytest.approx((0.0 - params["mu"]) / params["sigma"])
    assert math.isfinite(ex["z_sum"])


def test_context_players_lists(context: dict, processed: Path) -> None:
    for mode in config.MODES:
        df = pd.read_csv(processed / config.VALUES_FILENAMES[mode])
        players = context["players"][mode]
        assert len(players) == len(df)
        assert players[0]["rank"] == 1
        assert all(p["ft_pct"] is None or isinstance(p["ft_pct"], float) for p in players)


def test_build_context_missing_files_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="multipliers.csv"):
        build_context(tmp_path)


# --- Hesaplama.md (F9) ---


def test_markdown_has_all_sections_in_order(markdown: str) -> None:
    headings = re.findall(r"^## (.+)$", markdown, flags=re.MULTILINE)
    assert headings == EXPECTED_SECTIONS


def test_markdown_has_no_template_syntax(markdown: str) -> None:
    assert "{{" not in markdown
    assert "{%" not in markdown
    assert "{#" not in markdown


def _multiplier_tables(markdown: str) -> dict[str, dict[str, list[str]]]:
    """Bölüm 7'deki çarpan tablolarını {mod: {kategori: hücreler}} olarak ayrıştırır."""
    section = markdown.split("## 7. Çarpan Tablosu")[1].split("## 8.")[0]
    tables: dict[str, dict[str, list[str]]] = {}
    for mode in config.MODES:
        block = section.split(f"<!-- mode:{mode} -->")[1].split("<!-- /mode -->")[0]
        rows = {}
        for line in block.strip().splitlines():
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            code = re.search(r"`(\w+)`", cells[0])
            if code and code.group(1) in config.CATEGORIES:
                rows[code.group(1)] = cells[1:]
        tables[mode] = rows
    return tables


def test_multiplier_table_matches_csv_to_3_decimals(markdown: str, processed: Path) -> None:
    csv = pd.read_csv(processed / "multipliers.csv")
    tables = _multiplier_tables(markdown)
    numeric_cols = ["mu", "sigma", "multiplier", "points_equivalent", "mean_ratio_to_pts"]
    for mode in config.MODES:
        assert list(tables[mode]) == list(config.CATEGORIES)
        for _, row in csv[csv["mode"] == mode].iterrows():
            cells = tables[mode][row["category"]]
            for col, cell in zip([*numeric_cols, "league_pct"], cells, strict=True):
                if pd.isna(row[col]):
                    assert cell == "—", (mode, row["category"], col)
                else:
                    assert abs(parse_num(cell) - row[col]) <= 5e-4 + 1e-9, (
                        mode,
                        row["category"],
                        col,
                    )


def test_worked_example_sum_matches_csv(markdown: str, processed: Path) -> None:
    section = markdown.split("## 10. Çalışılmış Örnek")[1].split("## 11.")[0]
    match = re.search(rf"Toplam z \(ham değer\): \*\*({NUM_RE})\*\*", section)
    assert match, "Toplam satırı bulunamadı"
    total = pd.read_csv(processed / "values_total.csv")
    assert abs(parse_num(match.group(1)) - total["raw_total"].iloc[0]) <= 0.01
    assert total["player_name"].iloc[0] in section


def test_impact_examples_in_section_6(markdown: str) -> None:
    section = markdown.split("## 6. Yüzde Kategorileri ve Hacim")[1].split("## 7.")[0]
    for text in ("6/10", "60/100", "+1,0", "+10,0", "-5,0"):
        assert text in section


def test_render_is_deterministic(context: dict, markdown: str) -> None:
    assert render_hesaplama(context) == markdown


def test_run_report_md_writes_file(processed: Path, tmp_path: Path) -> None:
    path = run_report_md(processed, tmp_path)
    assert path == tmp_path / "Hesaplama.md"
    assert path.read_bytes().count(b"\r\n") == 0
    assert path.read_text(encoding="utf-8").startswith("# ")


# --- CLI ---


def test_cli_report_writes_markdown(
    processed: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    proc = tmp_path / "processed"
    shutil.copytree(processed, proc)
    monkeypatch.setattr(config, "PROCESSED_DIR", proc)
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "output")
    assert main(["report"]) == 0
    assert (tmp_path / "output" / "Hesaplama.md").is_file()


def test_cli_report_missing_processed_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(config, "PROCESSED_DIR", tmp_path / "yok")
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "output")
    assert main(["report"]) == 1
    err = capsys.readouterr().err
    assert "values_total.csv" in err and "compute" in err
