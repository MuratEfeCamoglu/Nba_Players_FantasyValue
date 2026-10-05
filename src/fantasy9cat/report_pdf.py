"""ReportLab ile output/Deger.pdf (A4 yatay, DejaVu Sans gömülü)."""

import logging
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from fantasy9cat import config
from fantasy9cat.context import build_context
from fantasy9cat.formatting import fmt_num

logger = logging.getLogger(__name__)

PAGE_SIZE = landscape(A4)
MARGIN = 1.2 * cm
Z_COLOR_CAP = 3.0  # |z| bu değerde en koyu tona ulaşır
MAX_TINT = 0.6  # en koyu tonda baz rengin payı (geri kalanı beyaz)
POSITIVE_BASE = (0.13, 0.55, 0.27)
NEGATIVE_BASE = (0.80, 0.15, 0.15)
HEADER_BG = colors.Color(0.17, 0.24, 0.36)
GRID_COLOR = colors.Color(0.80, 0.80, 0.80)
TABLE_FONT_SIZE = 7
RANKING_COL_WIDTHS = (28, 150, 36, 26, *([46] * 9), 46, 46)
MULTIPLIER_HEADERS = (
    "Kategori",
    "μ",
    "σ",
    "Çarpan (1/σ)",
    "Sayı eşdeğeri",
    "Ortalama oranı",
    "Lig %",
)
MULTIPLIER_COL_WIDTHS = (170, 75, 75, 85, 85, 85, 70)
Z_DECIMALS = 2
VALUE_DECIMALS = 1


def register_fonts() -> None:
    """DejaVu Sans normal ve kalın fontlarını ReportLab'e (bir kez) kaydeder."""
    registered = pdfmetrics.getRegisteredFontNames()
    for name, filename in (
        (config.FONT_REGULAR, "DejaVuSans.ttf"),
        (config.FONT_BOLD, "DejaVuSans-Bold.ttf"),
    ):
        if name not in registered:
            pdfmetrics.registerFont(TTFont(name, str(config.FONTS_DIR / filename)))


def z_cell_color(z: float) -> colors.Color | None:
    """Pozitif z için yeşil, negatif için kırmızı ton; |z| büyüdükçe koyulaşır, 0'da renk yok."""
    if z == 0:
        return None
    t = min(abs(z) / Z_COLOR_CAP, 1.0) * MAX_TINT
    base = POSITIVE_BASE if z > 0 else NEGATIVE_BASE
    return colors.Color(*(1.0 - t * (1.0 - c) for c in base))


def _styles() -> dict[str, ParagraphStyle]:
    """Paragraf stilleri (tümü DejaVu Sans)."""
    body = ParagraphStyle("body", fontName=config.FONT_REGULAR, fontSize=9, leading=12.5)
    return {
        "title": ParagraphStyle(
            "title", parent=body, fontName=config.FONT_BOLD, fontSize=16, leading=20
        ),
        "h1": ParagraphStyle(
            "h1", parent=body, fontName=config.FONT_BOLD, fontSize=13, leading=17, spaceAfter=6
        ),
        "h2": ParagraphStyle(
            "h2", parent=body, fontName=config.FONT_BOLD, fontSize=10, leading=14, spaceBefore=6
        ),
        "body": body,
        "mono": ParagraphStyle("mono", parent=body, leftIndent=12, fontSize=8.5),
        "note": ParagraphStyle("note", parent=body, fontSize=8),
    }


def _base_table_style(n_cols: int) -> list[tuple]:
    """Başlık satırı koyu, ızgara ince, yazılar DejaVu olan tablo stili."""
    return [
        ("FONT", (0, 0), (-1, -1), config.FONT_REGULAR, TABLE_FONT_SIZE),
        ("FONT", (0, 0), (-1, 0), config.FONT_BOLD, TABLE_FONT_SIZE),
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.25, GRID_COLOR),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (n_cols - 1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
    ]


def _multiplier_table(rows: list[dict[str, Any]]) -> Table:
    """Bir modun çarpan tablosu."""
    data = [list(MULTIPLIER_HEADERS)] + [
        [
            f"{r['label']} ({r['short']})",
            r["mu_text"],
            r["sigma_text"],
            r["multiplier_text"],
            r["points_equivalent_text"],
            r["mean_ratio_text"],
            r["league_pct_text"],
        ]
        for r in rows
    ]
    table = Table(data, colWidths=MULTIPLIER_COL_WIDTHS, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle(_base_table_style(len(MULTIPLIER_HEADERS))))
    return table


def _ranking_table(players: list[dict[str, Any]], mark_low_sample: bool) -> tuple[Table, int]:
    """Sıralama tablosu ve yazılan oyuncu satırı sayısı; başlık her sayfada tekrarlanır."""
    style = _base_table_style(len(config.PDF_RANKING_HEADERS))
    style.append(("ALIGN", (1, 0), (2, -1), "LEFT"))
    data = [list(config.PDF_RANKING_HEADERS)]
    first_z_col = 4
    for row_idx, p in enumerate(players, start=1):
        name = p["player_name"]
        if mark_low_sample and p["low_sample"]:
            name = f"{name} {config.LOW_SAMPLE_MARK}"
        zs = [float(p[zcol]) for zcol in config.Z_COLUMNS]
        data.append(
            [
                str(p["rank"]),
                name,
                p["team"],
                str(p["gp"]),
                *(fmt_num(z, Z_DECIMALS) for z in zs),
                fmt_num(p["raw_total"], Z_DECIMALS),
                fmt_num(p["value"], VALUE_DECIMALS),
            ]
        )
        for offset, z in enumerate(zs):
            color = z_cell_color(z)
            if color is not None:
                cell = (first_z_col + offset, row_idx)
                style.append(("BACKGROUND", cell, cell, color))
    table = Table(data, colWidths=RANKING_COL_WIDTHS, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle(style))
    return table, len(data) - 1


def _method_section(context: dict[str, Any], st: dict[str, ParagraphStyle]) -> list:
    """Bölüm 1: yöntem özeti ve iki modun çarpan tablosu."""
    lg, pool = context["league"], context["pool"]
    conv = {True: "yakınsadı", False: "yakınsamadı"}
    story: list = [
        Paragraph(escape(config.PDF_SECTIONS[0]), st["h1"]),
        Paragraph(
            escape(
                f"Her oyuncunun değeri, 9 kategorideki z-skorlarının toplamıdır (ham değer). "
                f"μ ve σ, {lg['num_teams']} takım × {lg['roster_size']} kadro = "
                f"{lg['pool_size']} oyunculuk havuzdan (popülasyon std) hesaplanır; sezonda en az "
                f"1 maç oynayan herkes ({pool['n_players']} oyuncu) değerlenir. Havuz iteratif "
                f"bulunur: sezon toplamında {pool['iterations_total']} iterasyonda "
                f"{conv[pool['converged_total']]}, maç başında {pool['iterations_per_game']} "
                f"iterasyonda {conv[pool['converged_per_game']]}. Maç başı modda havuza aday "
                f"olmak için en az {lg['min_gp_pool_per_game']} maç gerekir."
            ),
            st["body"],
        ),
        Spacer(1, 4),
        Paragraph("Sayma kategorileri (PTS, REB, AST, 3P, STL, BLK): z = (x − μ) / σ", st["mono"]),
        Paragraph("Top kaybı (TO): z = (μ − x) / σ  — az olan kazanır", st["mono"]),
        Paragraph(
            "Yüzdeler (FG%, FT%): etki = isabet − lig% × deneme;  z = (etki − μ) / σ", st["mono"]
        ),
        Paragraph(
            escape(
                f"Değer = 100 × (ham − ham_yedek) / (ham_1 − ham_yedek);  1. aday = 100, "
                f"{lg['replacement_rank']}. aday (yedek seviyesi) = 0"
            ),
            st["mono"],
        ),
        Spacer(1, 4),
    ]
    for w in pool["warnings"]:
        story.append(Paragraph(escape(f"Uyarı: {w}"), st["body"]))
    story.append(
        Paragraph(
            "Sıralama tablolarında kategori kolonları z-skorudur: yeşil hücre artı, kırmızı "
            "hücre eksi katkıdır; ton |z| büyüdükçe koyulaşır. Çarpan = 1/σ, sayı eşdeğeri = "
            "σ_PTS/σ. Ayrıntılı açıklama ve çalışılmış örnek: Hesaplama.md.",
            st["body"],
        )
    )
    for mode, title in ((config.MODE_TOTAL, "Sezon toplamı"), (config.MODE_PER_GAME, "Maç başı")):
        story.append(
            KeepTogether(
                [
                    Paragraph(f"Çarpan tablosu — {title}", st["h2"]),
                    Spacer(1, 2),
                    _multiplier_table(context["multipliers"][mode]),
                ]
            )
        )
    return story


def _footer(season: str):
    """Her sayfanın altına sezon ve sayfa numarası yazan geri çağırma."""

    def draw(canvas: Canvas, doc: SimpleDocTemplate) -> None:
        canvas.saveState()
        canvas.setFont(config.FONT_REGULAR, 7)
        canvas.drawString(MARGIN, MARGIN / 2, f"Fantezi NBA 9-Cat Oyuncu Değerleme · {season}")
        canvas.drawRightString(PAGE_SIZE[0] - MARGIN, MARGIN / 2, f"Sayfa {doc.page}")
        canvas.restoreState()

    return draw


def build_pdf(context: dict[str, Any], out_path: Path) -> dict[str, int]:
    """Deger.pdf'i yazar; her sıralama tablosuna yazılan oyuncu satırı sayısını döndürür."""
    register_fonts()
    st = _styles()
    season = context["season"]
    story: list = [
        Paragraph(escape(f"Fantezi NBA 9-Cat Oyuncu Değerleme — {season}"), st["title"]),
        Paragraph(
            escape(
                f"{season} NBA normal sezonu · {context['league']['num_teams']} takım × "
                f"{context['league']['roster_size']} oyunculuk H2H 9-cat lig"
            ),
            st["body"],
        ),
        Spacer(1, 8),
        *_method_section(context, st),
    ]
    counts: dict[str, int] = {}
    sections = {
        config.MODE_TOTAL: config.PDF_SECTIONS[1],
        config.MODE_PER_GAME: config.PDF_SECTIONS[2],
    }
    for mode, title in sections.items():
        players = context["players"][mode]
        per_game = mode == config.MODE_PER_GAME
        table, counts[mode] = _ranking_table(players, mark_low_sample=per_game)
        story += [PageBreak(), Paragraph(escape(title), st["h1"]), table]
        if per_game:
            story += [Spacer(1, 4), Paragraph(escape(config.LOW_SAMPLE_NOTE), st["note"])]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=PAGE_SIZE,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=MARGIN,
        title=f"Fantezi NBA 9-Cat Oyuncu Değerleme {season}",
        author="fantasy9cat",
        invariant=True,  # zaman damgası ve rastgele kimlik yok → tekrarlanabilir
    )
    footer = _footer(season)
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    logger.info("Yazıldı: %s (%s)", out_path, counts)
    return counts


def run_report_pdf(processed_dir: Path, output_dir: Path) -> tuple[Path, dict[str, int]]:
    """İşlenmiş verilerden Deger.pdf'i yazar; yol ve satır sayılarını döndürür."""
    path = output_dir / config.DEGER_PDF_FILENAME
    counts = build_pdf(build_context(processed_dir), path)
    return path, counts
