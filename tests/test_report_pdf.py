"""report_pdf.py testleri (F10)."""

import shutil
from pathlib import Path

import pandas as pd
import pytest
from pypdf import PdfReader

from fantasy9cat import config
from fantasy9cat.__main__ import main
from fantasy9cat.context import build_context
from fantasy9cat.pipeline import run_compute
from fantasy9cat.report_pdf import build_pdf, run_report_pdf, z_cell_color

SAMPLE_CSV = Path(__file__).resolve().parent / "fixtures" / "sample_players.csv"
A4_LANDSCAPE = (841.89, 595.28)


@pytest.fixture(scope="module")
def processed(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("processed")
    run_compute(SAMPLE_CSV, out)
    return out


@pytest.fixture(scope="module")
def context(processed: Path) -> dict:
    return build_context(processed)


@pytest.fixture(scope="module")
def built(context: dict, tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict[str, int]]:
    path = tmp_path_factory.mktemp("pdf") / "Deger.pdf"
    counts = build_pdf(context, path)
    return path, counts


@pytest.fixture(scope="module")
def pages(built: tuple[Path, dict[str, int]]) -> list[str]:
    return [p.extract_text() for p in PdfReader(built[0]).pages]


# --- z hücre rengi ---


def test_positive_z_is_green_negative_is_red() -> None:
    pos, neg = z_cell_color(1.5), z_cell_color(-1.5)
    assert pos.green > pos.red and pos.green > pos.blue
    assert neg.red > neg.green and neg.red > neg.blue


def test_zero_z_has_no_color() -> None:
    assert z_cell_color(0.0) is None


def test_color_intensity_grows_with_abs_z_and_is_capped() -> None:
    weak, strong = z_cell_color(0.5), z_cell_color(2.5)
    assert strong.red < weak.red  # daha koyu yeşil: kırmızı bileşen azalır
    capped_a, capped_b = z_cell_color(10.0), z_cell_color(50.0)
    assert (capped_a.red, capped_a.green, capped_a.blue) == (
        capped_b.red,
        capped_b.green,
        capped_b.blue,
    )


# --- F10 ---


def test_build_pdf_row_counts_equal_csv(
    built: tuple[Path, dict[str, int]], processed: Path
) -> None:
    _, counts = built
    for mode in config.MODES:
        n_csv = len(pd.read_csv(processed / config.VALUES_FILENAMES[mode]))
        assert counts[mode] == n_csv, mode


def test_a4_landscape_and_size(built: tuple[Path, dict[str, int]]) -> None:
    path, _ = built
    assert path.stat().st_size < config.PDF_MAX_BYTES
    for page in PdfReader(path).pages:
        w, h = float(page.mediabox.width), float(page.mediabox.height)
        assert (w, h) == pytest.approx(A4_LANDSCAPE, abs=0.5)


def test_three_sections_in_order(pages: list[str]) -> None:
    text = "\n".join(pages)
    positions = [text.find(title) for title in config.PDF_SECTIONS]
    assert all(p >= 0 for p in positions), positions
    assert positions == sorted(positions)


def test_method_section_has_multiplier_table(pages: list[str], context: dict) -> None:
    first = "\n".join(pages[:2])
    assert "Çarpan" in first and "Sayı eşdeğeri" in first
    assert context["mult"]["total"]["PTS"]["sigma_text"] in first
    assert context["mult"]["per_game"]["BLK"]["multiplier_text"] in first


def test_ranking_header_repeats_on_every_page(pages: list[str]) -> None:
    start = next(i for i, t in enumerate(pages) if config.PDF_SECTIONS[1] in t)
    ranking_pages = pages[start:]
    assert len(ranking_pages) >= 4  # 2 × 500 satır birden çok sayfaya yayılır
    for i, text in enumerate(ranking_pages, start=start + 1):
        for header in ("Sıra", "Oyuncu", "Takım", "MS", "Ham", "Değer"):
            assert header in text, (i, header)


def test_names_survive_text_extraction(pages: list[str], context: dict) -> None:
    text = "\n".join(pages)
    assert "Alperen Şengün" in text
    assert "Nikola Jokić" in text
    for mode in config.MODES:
        assert context["players"][mode][-1]["player_name"] in text, mode


def test_per_game_low_sample_marked(pages: list[str], context: dict) -> None:
    start = next(i for i, t in enumerate(pages) if config.PDF_SECTIONS[2] in t)
    text = "\n".join(pages[start:])
    assert config.LOW_SAMPLE_NOTE in text.replace("\n", " ")
    low = next(p for p in context["players"]["per_game"] if p["low_sample"])
    assert f"{low['player_name']} {config.LOW_SAMPLE_MARK}" in text
    total_start = next(i for i, t in enumerate(pages) if config.PDF_SECTIONS[1] in t)
    total_text = "\n".join(pages[total_start:start])
    assert config.LOW_SAMPLE_NOTE not in total_text.replace("\n", " ")


def test_pdf_is_byte_identical_across_runs(
    built: tuple[Path, dict[str, int]], context: dict, tmp_path: Path
) -> None:
    again = tmp_path / "Deger.pdf"
    build_pdf(context, again)
    assert again.read_bytes() == built[0].read_bytes()


def test_run_report_pdf(processed: Path, tmp_path: Path) -> None:
    path, counts = run_report_pdf(processed, tmp_path)
    assert path == tmp_path / config.DEGER_PDF_FILENAME
    assert path.is_file()
    assert counts == {"total": 500, "per_game": 500}


# --- CLI ---


def test_cli_report_writes_md_and_pdf(
    processed: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    proc = tmp_path / "processed"
    shutil.copytree(processed, proc)
    monkeypatch.setattr(config, "PROCESSED_DIR", proc)
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "output")
    assert main(["report"]) == 0
    assert (tmp_path / "output" / "Hesaplama.md").is_file()
    assert (tmp_path / "output" / "Deger.pdf").is_file()
