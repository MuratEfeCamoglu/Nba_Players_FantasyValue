"""site.py testleri (F11–F14). JS etkileşimleri elle kontrol listesiyle doğrulanır (V13)."""

import json
import re
import shutil
from pathlib import Path

import pandas as pd
import pytest

from fantasy9cat import config
from fantasy9cat.__main__ import main
from fantasy9cat.pipeline import run_compute
from fantasy9cat.report_md import run_report_md
from fantasy9cat.report_pdf import run_report_pdf
from fantasy9cat.site import (
    SitePrerequisiteError,
    markdown_to_html,
    missing_prerequisites,
    run_site,
)

SAMPLE_CSV = Path(__file__).resolve().parent / "fixtures" / "sample_players.csv"
TEMPLATE_SITE = config.TEMPLATES_DIR / "site"
F13_FILES = (
    "values_total.csv",
    "values_per_game.csv",
    "multipliers.csv",
    "Hesaplama.md",
    "Deger.pdf",
)


@pytest.fixture(scope="module")
def dirs(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    """Fikstürden compute + report çalıştırılmış (processed, output) klasörleri."""
    root = tmp_path_factory.mktemp("site")
    processed, output = root / "processed", root / "output"
    run_compute(SAMPLE_CSV, processed)
    run_report_md(processed, output)
    run_report_pdf(processed, output)
    return processed, output


@pytest.fixture(scope="module")
def site_dir(dirs: tuple[Path, Path]) -> Path:
    processed, output = dirs
    run_site(processed, output)
    return output / "site"


@pytest.fixture(scope="module")
def index_html(site_dir: Path) -> str:
    return (site_dir / "index.html").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def hesaplama_html(site_dir: Path) -> str:
    return (site_dir / "hesaplama.html").read_text(encoding="utf-8")


def _embedded_json(html: str, element_id: str) -> dict:
    m = re.search(
        rf'<script type="application/json" id="{element_id}">(.*?)</script>', html, re.DOTALL
    )
    assert m, element_id
    return json.loads(m.group(1))


def _copy_dirs(dirs: tuple[Path, Path], tmp_path: Path) -> tuple[Path, Path]:
    processed, output = tmp_path / "processed", tmp_path / "output"
    shutil.copytree(dirs[0], processed)
    shutil.copytree(dirs[1], output)
    shutil.rmtree(output / "site", ignore_errors=True)
    return processed, output


# --- F13: site sırası kuralı ---


def test_no_missing_prerequisites_after_report(dirs: tuple[Path, Path]) -> None:
    assert missing_prerequisites(*dirs) == []


@pytest.mark.parametrize("name", F13_FILES)
def test_site_refused_when_file_missing(name: str, dirs: tuple[Path, Path], tmp_path: Path) -> None:
    processed, output = _copy_dirs(dirs, tmp_path)
    target = (output if name in config.SITE_REQUIRED_OUTPUTS else processed) / name
    target.unlink()
    with pytest.raises(SitePrerequisiteError) as exc:
        run_site(processed, output)
    assert any(name in m for m in exc.value.missing)
    assert not (output / "site").exists()


def test_cli_site_missing_files_exits_1(
    dirs: tuple[Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    processed, output = _copy_dirs(dirs, tmp_path)
    (output / "Deger.pdf").unlink()
    (processed / "multipliers.csv").unlink()
    monkeypatch.setattr(config, "PROCESSED_DIR", processed)
    monkeypatch.setattr(config, "OUTPUT_DIR", output)
    assert main(["site"]) == 1
    err = capsys.readouterr().err
    assert "Deger.pdf" in err and "multipliers.csv" in err
    assert not (output / "site").exists()


def test_cli_site_success(
    dirs: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    processed, output = _copy_dirs(dirs, tmp_path)
    monkeypatch.setattr(config, "PROCESSED_DIR", processed)
    monkeypatch.setattr(config, "OUTPUT_DIR", output)
    assert main(["site"]) == 0
    assert (output / "site" / "index.html").is_file()


# --- Dosya yapısı ve kısıtlar (§3.5, §5) ---


def test_site_files(site_dir: Path) -> None:
    for rel in ("index.html", "hesaplama.html", "assets/style.css", "assets/app.js"):
        assert (site_dir / rel).is_file(), rel
    for name in config.SITE_FONT_FILES:
        target = site_dir / "assets" / "fonts" / name
        assert target.read_bytes() == (config.FONTS_DIR / name).read_bytes(), name


@pytest.mark.parametrize("asset", config.SITE_ASSETS)
def test_assets_copied_unchanged(site_dir: Path, asset: str) -> None:
    assert (site_dir / "assets" / asset).read_bytes() == (TEMPLATE_SITE / asset).read_bytes()


def test_site_size_under_limit(site_dir: Path) -> None:
    total = sum(p.stat().st_size for p in site_dir.rglob("*") if p.is_file())
    assert total < config.SITE_MAX_BYTES


def test_no_external_urls(site_dir: Path) -> None:
    for page in site_dir.rglob("*.html"):
        html = page.read_text(encoding="utf-8")
        assert not re.search(r"""(src|href)\s*=\s*["']?\s*(https?:)?//""", html, re.I), page.name
    for asset in site_dir.rglob("*.css"):
        assert not re.search(r"url\(\s*['\"]?(https?:)?//", asset.read_text(encoding="utf-8"))
    js = (site_dir / "assets" / "app.js").read_text(encoding="utf-8")
    assert "fetch(" not in js and "XMLHttpRequest" not in js and "http" not in js


def test_site_is_deterministic(dirs: tuple[Path, Path], site_dir: Path, tmp_path: Path) -> None:
    processed, output = _copy_dirs(dirs, tmp_path)
    run_site(processed, output)
    for page in ("index.html", "hesaplama.html"):
        assert (output / "site" / page).read_bytes() == (site_dir / page).read_bytes()


# --- F11: sıralama sayfası (gömülü veri) ---


def test_embedded_player_counts_match_csv(index_html: str, dirs: tuple[Path, Path]) -> None:
    data = _embedded_json(index_html, "players-data")
    assert data["columns"] == list(config.VALUES_COLUMNS)
    for mode in config.MODES:
        csv = pd.read_csv(dirs[0] / config.VALUES_FILENAMES[mode])
        rows = data["players"][mode]
        assert len(rows) == len(csv), mode
        first = dict(zip(data["columns"], rows[0], strict=True))
        assert first["player_name"] == csv["player_name"].iloc[0]
        assert first["raw_total"] == pytest.approx(csv["raw_total"].iloc[0])


def test_embedded_meta_matches_meta_json(index_html: str, dirs: tuple[Path, Path]) -> None:
    data = _embedded_json(index_html, "players-data")
    meta = json.loads((dirs[0] / "meta.json").read_text(encoding="utf-8"))
    assert data["meta"] == meta


def test_embedded_json_cannot_close_script(index_html: str) -> None:
    m = re.search(r'id="players-data">(.*?)</script>', index_html, re.DOTALL)
    assert "<" not in m.group(1)


def test_embedded_empty_percent_is_null(index_html: str) -> None:
    data = _embedded_json(index_html, "players-data")
    cols = data["columns"]
    fta, ft_pct = cols.index("fta"), cols.index("ft_pct")
    zero = [r for r in data["players"]["total"] if r[fta] == 0]
    assert zero and all(r[ft_pct] is None for r in zero)


def test_index_has_controls(index_html: str) -> None:
    for element_id in ("search", "team", "only-enough", "ranking", "count"):
        assert f'id="{element_id}"' in index_html, element_id
    assert 'data-mode="total"' in index_html and 'data-mode="per_game"' in index_html
    assert f"Yalnızca GP ≥ {config.MIN_GP_POOL_PER_GAME}" in index_html
    assert 'src="assets/app.js"' in index_html and 'href="assets/style.css"' in index_html


# --- F12: hesaplama sayfası ---


def test_hesaplama_has_same_11_headings(hesaplama_html: str, dirs: tuple[Path, Path]) -> None:
    h2 = [re.sub(r"<[^>]+>", "", h) for h in re.findall(r"<h2[^>]*>(.*?)</h2>", hesaplama_html)]
    assert h2 == list(config.REPORT_SECTIONS)
    md = (dirs[1] / "Hesaplama.md").read_text(encoding="utf-8")
    assert re.findall(r"^## (.+)$", md, flags=re.MULTILINE) == h2


def _html_multiplier_rows(html: str, mode: str) -> dict[str, list[str]]:
    block = html.split(f"<!-- mode:{mode} -->")[1].split("<!-- /mode -->")[0]
    rows = {}
    for tr in re.findall(r"<tr>(.*?)</tr>", block, re.DOTALL):
        cells = [re.sub(r"<[^>]+>", "", c).strip() for c in re.findall(r"<td>(.*?)</td>", tr)]
        code = re.search(r"\((\w+)\)$", cells[0]) if cells else None
        if code and code.group(1) in config.CATEGORIES:
            rows[code.group(1)] = cells[1:]
    return rows


def _num(text: str) -> float:
    if "%" in text:
        return float(text.replace("%", "").replace(",", ".")) / 100
    return float(text.replace(",", "."))


def test_hesaplama_multipliers_match_csv_to_3_decimals(
    hesaplama_html: str, dirs: tuple[Path, Path]
) -> None:
    csv = pd.read_csv(dirs[0] / "multipliers.csv")
    cols = ["mu", "sigma", "multiplier", "points_equivalent", "mean_ratio_to_pts", "league_pct"]
    for mode in config.MODES:
        rows = _html_multiplier_rows(hesaplama_html, mode)
        assert list(rows) == list(config.CATEGORIES)
        for _, r in csv[csv["mode"] == mode].iterrows():
            for col, cell in zip(cols, rows[r["category"]], strict=True):
                if pd.isna(r[col]):
                    assert cell == "—"
                else:
                    assert abs(_num(cell) - r[col]) <= 5e-4 + 1e-9, (mode, r["category"], col)


def test_hesaplama_numbers_identical_to_markdown(
    hesaplama_html: str, dirs: tuple[Path, Path]
) -> None:
    md = (dirs[1] / "Hesaplama.md").read_text(encoding="utf-8")
    # F16 görselleri (sayı eşdeğeri grafiği) tablodaki sayıları bilerek tekrarlar; hariç tutulur.
    body = re.sub(
        r'<figure class="pe-chart[^"]*".*?</figure>', " ", hesaplama_html, flags=re.DOTALL
    )
    text = re.sub(r"<[^>]+>", " ", body).replace("&amp;", "&")
    numbers_md = re.findall(r"[+-]?%?\d+,\d+", md)
    numbers_html = re.findall(r"[+-]?%?\d+,\d+", text)
    assert numbers_md and numbers_md == numbers_html[: len(numbers_md)]


def test_hesaplama_worked_example_sum(hesaplama_html: str, dirs: tuple[Path, Path]) -> None:
    m = re.search(r"Toplam z \(ham değer\): <strong>([-\d,]+)</strong>", hesaplama_html)
    assert m
    total = pd.read_csv(dirs[0] / "values_total.csv")
    assert abs(_num(m.group(1)) - total["raw_total"].iloc[0]) <= 0.01


# --- F14: etki hesaplayıcısı ---


def test_calculator_params_embedded(hesaplama_html: str, dirs: tuple[Path, Path]) -> None:
    params = _embedded_json(hesaplama_html, "calc-params")
    csv = pd.read_csv(dirs[0] / "multipliers.csv")
    total = csv[csv["mode"] == config.MODE_TOTAL].set_index("category")
    for cat in config.PERCENT_CATEGORIES:
        for key in ("league_pct", "mu", "sigma"):
            assert params[cat][key] == pytest.approx(total.loc[cat, key], abs=1e-9), (cat, key)
    for element_id in ("calc-category", "calc-made", "calc-attempts", "calc-impact", "calc-z"):
        assert f'id="{element_id}"' in hesaplama_html
    assert config.CALCULATOR_MARKER not in hesaplama_html
    section6 = hesaplama_html.split('id="bolum-6"')[1].split('id="bolum-7"')[0]
    assert 'id="calc-params"' in section6


# --- Markdown → HTML dönüştürücü ---


def test_markdown_headings_and_paragraphs() -> None:
    html = markdown_to_html("# Başlık\n\n## 3. Havuz\n\nBir satır\nikinci satır.\n")
    assert "<h1>Başlık</h1>" in html
    assert '<h2 id="bolum-3">3. Havuz</h2>' in html
    assert "<p>Bir satır ikinci satır.</p>" in html


def test_markdown_inline_and_escaping() -> None:
    html = markdown_to_html("A & B <x> **kalın** ve `kod` ve *eğik*\n")
    assert "A &amp; B &lt;x&gt; <strong>kalın</strong> ve <code>kod</code> ve <em>eğik</em>" in html


def test_markdown_table() -> None:
    html = markdown_to_html("| a | b |\n|---|---|\n| 1,5 | — |\n")
    assert "<thead><tr><th>a</th><th>b</th></tr></thead>" in html
    assert "<tbody><tr><td>1,5</td><td>—</td></tr></tbody>" in html
    assert 'class="table-wrap"' in html


def test_markdown_lists_code_quote_comment() -> None:
    md = "- x\n- y\n\n1. bir\n2. iki\n\n```\nz = (x − μ) / σ\n```\n\n> **Uyarı:** a\n\n<!-- c -->\n"
    html = markdown_to_html(md)
    assert "<ul><li>x</li><li>y</li></ul>" in html
    assert "<ol><li>bir</li><li>iki</li></ol>" in html
    assert "<pre><code>z = (x − μ) / σ</code></pre>" in html
    assert "<blockquote><p><strong>Uyarı:</strong> a</p></blockquote>" in html
    assert "<!-- c -->" in html


# --- F16: görsel tasarım ---

CSS_PATH = TEMPLATE_SITE / "style.css"
COLOR_LITERAL = re.compile(r"#[0-9a-fA-F]{3,8}\b|\b(?:rgba?|hsla?)\(\s*\d")


def _css() -> str:
    return CSS_PATH.read_text(encoding="utf-8")


def test_css_tokens_defined_at_top() -> None:
    css = _css()
    first_rule = css.index("{")
    assert css[:first_rule].strip().endswith(":root")
    root = css[first_rule : css.index("}")]
    for prefix in ("--renk-", "--aralik-", "--yazi-"):
        assert prefix in root, prefix


def test_all_colors_live_in_css_variables() -> None:
    offenders = []
    for n, line in enumerate(_css().splitlines(), start=1):
        code = line.split("/*")[0].strip()
        if COLOR_LITERAL.search(code) and not code.startswith("--"):
            offenders.append((n, code))
    assert offenders == []
    js = (TEMPLATE_SITE / "app.js").read_text(encoding="utf-8")
    assert not re.search(r"#[0-9a-fA-F]{6}\b|rgba?\(\s*\d", js)


def test_spacing_uses_variables() -> None:
    props = r"(?:margin|padding|gap|row-gap|column-gap)(?:-[a-z]+)?"
    offenders = []
    for n, line in enumerate(_css().splitlines(), start=1):
        m = re.match(rf"\s*{props}\s*:\s*(.+?);", line)
        if m and re.search(r"\d+(?:\.\d+)?(px|rem|em)", m.group(1)):
            offenders.append((n, line.strip()))
    assert offenders == []


def test_light_and_dark_themes() -> None:
    css = _css()
    assert "prefers-color-scheme: light" in css
    assert ':root[data-theme="light"]' in css and ':root[data-theme="dark"]' in css


def test_motion_is_short_and_respects_reduced_motion() -> None:
    css = _css()
    durations = [int(d) for d in re.findall(r"--sure-[a-z-]+:\s*(\d+)ms", css)]
    assert durations and all(150 <= d <= 250 for d in durations)
    for decl in re.findall(r"(?:transition|animation)\s*:\s*([^;]+);", css):
        assert "var(--sure-" in decl or decl.strip().startswith("none"), decl
    assert "prefers-reduced-motion: reduce" in css


def test_fonts_are_local_woff2() -> None:
    css = _css()
    srcs = re.findall(r"url\(\s*['\"]?([^'\")]+)", css)
    assert srcs and all(s.startswith("fonts/") and s.endswith(".woff2") for s in srcs)
    for src in srcs:
        assert (config.FONTS_DIR / src.removeprefix("fonts/")).is_file(), src
    assert "@import" not in css
    assert "tabular-nums" in css


def test_page_chrome(index_html: str, hesaplama_html: str) -> None:
    for html in (index_html, hesaplama_html):
        assert 'id="theme-toggle"' in html
        assert "16 takım × 15" in html
        assert "05.10.2026" in html
    for element_id in ("top-cards", "filters-toggle", "controls"):
        assert f'id="{element_id}"' in index_html, element_id


def test_replacement_ranks_embedded(index_html: str, dirs: tuple[Path, Path]) -> None:
    data = _embedded_json(index_html, "players-data")
    for mode in config.MODES:
        csv = pd.read_csv(dirs[0] / config.VALUES_FILENAMES[mode])
        candidates = csv[~csv["low_sample"]]
        expected = int(candidates["rank"].iloc[config.POOL_SIZE])
        assert data["replacementRank"][mode] == expected, mode
        row = csv[csv["rank"] == expected].iloc[0]
        assert row["value"] == pytest.approx(0.0, abs=1e-6)


def test_points_equivalent_chart(hesaplama_html: str, dirs: tuple[Path, Path]) -> None:
    m = re.search(r'<figure class="pe-chart[^"]*".*?</figure>', hesaplama_html, re.DOTALL)
    assert m, "sayı eşdeğeri grafiği yok"
    chart = m.group(0)
    section7 = hesaplama_html.split('id="bolum-7"')[1].split('id="bolum-8"')[0]
    assert chart in section7
    csv = pd.read_csv(dirs[0] / "multipliers.csv")
    rows = re.findall(
        r'data-category="(\w+)".*?data-total="([\d,]+)".*?data-per-game="([\d,]+)"',
        chart,
        re.DOTALL,
    )
    assert [r[0] for r in rows] == list(config.CATEGORIES)
    for cat, tot, pg in rows:
        for mode, cell in (("total", tot), ("per_game", pg)):
            expected = csv[(csv["mode"] == mode) & (csv["category"] == cat)][
                "points_equivalent"
            ].iloc[0]
            assert abs(_num(cell) - expected) <= 5e-4 + 1e-9, (cat, mode)
    assert "1 blok" in chart
    assert config.POINTS_CHART_MARKER not in hesaplama_html


def test_calculator_is_a_card(hesaplama_html: str) -> None:
    assert re.search(r'<section class="calculator card', hesaplama_html)


def test_rebuild_keeps_site_dir_and_removes_stale_files(
    dirs: tuple[Path, Path], tmp_path: Path
) -> None:
    processed, output = _copy_dirs(dirs, tmp_path)
    run_site(processed, output)
    site = output / "site"
    stale = site / "eski.html"
    stale.write_text("eski", encoding="utf-8")
    inode_before = site.stat().st_ctime_ns
    run_site(processed, output)
    assert not stale.exists()
    assert (site / "index.html").is_file()
    assert site.stat().st_ctime_ns == inode_before  # klasörün kendisi silinmedi


def test_cli_site_filesystem_error_exits_1(
    dirs: tuple[Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from fantasy9cat import site as site_module

    processed, output = _copy_dirs(dirs, tmp_path)
    monkeypatch.setattr(config, "PROCESSED_DIR", processed)
    monkeypatch.setattr(config, "OUTPUT_DIR", output)

    def locked(*args: object, **kwargs: object) -> None:
        raise PermissionError("dosya başka bir işlem tarafından kullanılıyor")

    monkeypatch.setattr(site_module, "build_site", locked)
    assert main(["site"]) == 1
    assert "Site yazılamadı" in capsys.readouterr().err


def test_all_links_relative_and_resolvable(site_dir: Path) -> None:
    """Sunucusuz (file://) ve herhangi bir alt klasörden yayında çalışma: yalnızca göreli yollar."""
    refs: list[tuple[Path, str]] = []
    for page in site_dir.rglob("*.html"):
        html = page.read_text(encoding="utf-8")
        refs += [(page, r) for r in re.findall(r"""(?:src|href)\s*=\s*["']([^"']+)["']""", html)]
    css = site_dir / "assets" / "style.css"
    refs += [(css, r) for r in re.findall(r"""url\(\s*["']?([^"')]+)""", css.read_text("utf-8"))]
    assert refs
    for source, ref in refs:
        assert not ref.startswith("/"), (source.name, ref)
        target = ref.split("#")[0]
        if not target:
            continue
        resolved = (source.parent / target).resolve()
        if target == "../Deger.pdf":
            continue  # site/ dışındaki rapor; F13 gereği site üretilmeden önce var
        assert resolved.is_file(), (source.name, ref)


def test_favicon_is_local_svg(site_dir: Path, index_html: str, hesaplama_html: str) -> None:
    for html in (index_html, hesaplama_html):
        assert '<link rel="icon" href="assets/favicon.svg" type="image/svg+xml">' in html
    svg = (site_dir / "assets" / "favicon.svg").read_text(encoding="utf-8")
    assert svg.lstrip().startswith("<svg") and svg.rstrip().endswith("</svg>")
