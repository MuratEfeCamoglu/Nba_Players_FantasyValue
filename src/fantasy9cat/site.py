"""Statik web sitesi: templates/site/*.html.j2 → output/site/ (F11–F14)."""

import html
import json
import logging
import re
import shutil
from pathlib import Path
from typing import Any

from fantasy9cat import config
from fantasy9cat.context import build_context
from fantasy9cat.formatting import CATEGORY_LABELS, CATEGORY_SHORT, CATEGORY_UNITS, fmt_date
from fantasy9cat.report_md import make_environment, render_hesaplama

logger = logging.getLogger(__name__)

_HEADING_RE = re.compile(r"^(#{1,3}) (.+)$")
_OL_RE = re.compile(r"^\d+\. ")
_SECTION_NUM_RE = re.compile(r"^(\d+)\.")


class SitePrerequisiteError(FileNotFoundError):
    """F13: sitenin ön koşulu olan dosyalardan biri veya birkaçı eksik."""

    def __init__(self, missing: list[str]) -> None:
        super().__init__("Site için eksik dosya(lar): " + ", ".join(missing))
        self.missing = missing


def missing_prerequisites(processed_dir: Path, output_dir: Path) -> list[str]:
    """Site üretilmeden önce bulunması gereken dosyalardan eksik olanları listeler."""
    required = [processed_dir / n for n in config.PROCESSED_FILES] + [
        output_dir / n for n in config.SITE_REQUIRED_OUTPUTS
    ]
    return [str(p) for p in required if not p.is_file()]


# --- Markdown → HTML (yalnızca hesaplama.md.j2'nin kullandığı alt küme) ---


def _inline(text: str) -> str:
    """Satır içi biçim: HTML kaçışı, `kod`, **kalın**, *eğik*."""
    parts = text.split("`")
    out = []
    for i, part in enumerate(parts):
        escaped = html.escape(part, quote=False)
        if i % 2 == 1:
            out.append(f"<code>{escaped}</code>")
            continue
        escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
        escaped = re.sub(r"(?<![\*\w])\*(?!\s)(.+?)(?<!\s)\*(?![\*\w])", r"<em>\1</em>", escaped)
        out.append(escaped)
    return "".join(out)


def _cells(line: str) -> list[str]:
    """Markdown tablo satırını hücrelere böler."""
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _is_block_start(line: str) -> bool:
    """Satır yeni bir blok (başlık, tablo, liste, kod, alıntı, yorum) başlatıyor mu?"""
    return bool(
        _HEADING_RE.match(line)
        or line.startswith(("|", "```", "> ", "- ", "<!--"))
        or _OL_RE.match(line)
    )


def markdown_to_html(md: str) -> str:
    """Hesaplama.md'nin kullandığı Markdown alt kümesini HTML'e çevirir."""
    lines = md.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
        elif line.startswith("```"):
            j = i + 1
            while j < len(lines) and not lines[j].startswith("```"):
                j += 1
            code = html.escape("\n".join(lines[i + 1 : j]), quote=False)
            out.append(f"<pre><code>{code}</code></pre>")
            i = j + 1
        elif line.startswith("<!--"):
            out.append(line.strip())
            i += 1
        elif m := _HEADING_RE.match(line):
            level, text = len(m.group(1)), m.group(2).strip()
            num = _SECTION_NUM_RE.match(text) if level == 2 else None
            attr = f' id="bolum-{num.group(1)}"' if num else ""
            out.append(f"<h{level}{attr}>{_inline(text)}</h{level}>")
            i += 1
        elif line.startswith("|"):
            block = []
            while i < len(lines) and lines[i].startswith("|"):
                block.append(lines[i])
                i += 1
            head = "".join(f"<th>{_inline(c)}</th>" for c in _cells(block[0]))
            body = "".join(
                "<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in _cells(row)) + "</tr>"
                for row in block[2:]
            )
            out.append(
                f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead>'
                f"<tbody>{body}</tbody></table></div>"
            )
        elif line.startswith("> "):
            block = []
            while i < len(lines) and lines[i].startswith("> "):
                block.append(lines[i][2:])
                i += 1
            out.append(f"<blockquote><p>{_inline(' '.join(block))}</p></blockquote>")
        elif line.startswith("- ") or _OL_RE.match(line):
            ordered = not line.startswith("- ")
            pattern = _OL_RE if ordered else re.compile(r"^- ")
            items = []
            while i < len(lines) and pattern.match(lines[i]):
                items.append(pattern.sub("", lines[i], count=1))
                i += 1
            tag = "ol" if ordered else "ul"
            out.append(f"<{tag}>" + "".join(f"<li>{_inline(t)}</li>" for t in items) + f"</{tag}>")
        else:
            block = []
            while i < len(lines) and lines[i].strip() and not _is_block_start(lines[i]):
                block.append(lines[i].strip())
                i += 1
            out.append(f"<p>{_inline(' '.join(block))}</p>")
    return "\n".join(out) + "\n"


# --- Sayfa verisi ---


def _json_for_script(data: Any) -> str:
    """<script type="application/json"> içine güvenle gömülebilen JSON metni."""
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return text.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")


def _players_payload(context: dict[str, Any]) -> dict[str, Any]:
    """index.html'e gömülen veri: kolon adları + satır dizileri, kategori ve meta bilgisi."""
    columns = list(config.VALUES_COLUMNS)
    players = {
        mode: [[p[c] for c in columns] for p in context["players"][mode]] for mode in config.MODES
    }
    return {
        "columns": columns,
        "players": players,
        "categories": [
            {
                "code": c,
                "zcol": z,
                "short": CATEGORY_SHORT[c],
                "label": CATEGORY_LABELS[c],
            }
            for c, z in zip(config.CATEGORIES, config.Z_COLUMNS, strict=True)
        ],
        "meta": context["meta"],
        "minGp": config.MIN_GP_POOL_PER_GAME,
        "poolSize": config.POOL_SIZE,
        "replacementRank": {
            mode: _replacement_rank(context["players"][mode]) for mode in config.MODES
        },
        "modes": {config.MODE_TOTAL: "Toplam", config.MODE_PER_GAME: "Maç başı"},
    }


def _replacement_rank(players: list[dict[str, Any]]) -> int:
    """Yedek seviyesindeki oyuncunun sırası: havuz adayları içinde (N+1). (yoksa son aday)."""
    candidates = [p for p in players if not p["low_sample"]]
    index = min(config.POOL_SIZE, len(candidates) - 1)
    return int(candidates[index]["rank"])


def _points_chart(context: dict[str, Any]) -> list[dict[str, Any]]:
    """F16: "1 birim = X sayı" grafiği satırları; çubuk genişliği en büyük değere göre yüzde."""
    rows = {mode: {r["code"]: r for r in context["multipliers"][mode]} for mode in config.MODES}
    largest = max(r["points_equivalent"] for mode in config.MODES for r in rows[mode].values())
    chart = []
    for cat in config.CATEGORIES:
        total, per_game = rows[config.MODE_TOTAL][cat], rows[config.MODE_PER_GAME][cat]
        chart.append(
            {
                "code": cat,
                "unit": CATEGORY_UNITS[cat],
                "short": total["short"],
                "total_text": total["points_equivalent_text"],
                "per_game_text": per_game["points_equivalent_text"],
                "total_width": f"{100 * total['points_equivalent'] / largest:.1f}",
                "per_game_width": f"{100 * per_game['points_equivalent'] / largest:.1f}",
            }
        )
    return chart


def _calculator_params(context: dict[str, Any]) -> dict[str, Any]:
    """F14: total modunun yüzde kategorisi havuz parametreleri (league_pct, μ_etki, σ_etki)."""
    mult = context["mult"][config.MODE_TOTAL]
    return {
        cat: {
            "label": CATEGORY_LABELS[cat],
            "league_pct": mult[cat]["league_pct"],
            "mu": mult[cat]["mu"],
            "sigma": mult[cat]["sigma"],
        }
        for cat in config.PERCENT_CATEGORIES
    }


def _clear_dir(path: Path) -> None:
    """Klasörün içini boşaltır, klasörün kendisini silmez (açık pencere kilitlese de çalışır)."""
    path.mkdir(parents=True, exist_ok=True)
    for child in path.iterdir():
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()


def build_site(context: dict[str, Any], site_dir: Path) -> list[Path]:
    """Veri bağlamından index.html ve hesaplama.html'i üretir, varlıkları kopyalar."""
    env = make_environment()
    body = markdown_to_html(render_hesaplama(context))
    before_calc, rest = body.split(config.CALCULATOR_MARKER, 1)
    before_chart, after_chart = rest.split(config.POINTS_CHART_MARKER, 1)
    page_context = {
        **context,
        "data_as_of": fmt_date(config.DATA_AS_OF),
        "players_json": _json_for_script(_players_payload(context)),
        "calc_json": _json_for_script(_calculator_params(context)),
        "points_chart": _points_chart(context),
        "hesaplama_parts": (before_calc, before_chart, after_chart),
    }
    _clear_dir(site_dir)
    (site_dir / "assets").mkdir(parents=True)
    written = []
    for filename, template in config.SITE_PAGES.items():
        text = env.get_template(template).render(page=filename, **page_context)
        path = site_dir / filename
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        written.append(path)
    for asset in config.SITE_ASSETS:
        target = site_dir / "assets" / asset
        shutil.copyfile(config.TEMPLATES_DIR / "site" / asset, target)
        written.append(target)
    (site_dir / "assets" / "fonts").mkdir()
    for font in config.SITE_FONT_FILES:
        target = site_dir / "assets" / "fonts" / font
        shutil.copyfile(config.FONTS_DIR / font, target)
        written.append(target)
    return written


def run_site(processed_dir: Path, output_dir: Path) -> Path:
    """F13 ön koşullarını denetler, siteyi output/site/ altına üretir; index yolunu döndürür."""
    missing = missing_prerequisites(processed_dir, output_dir)
    if missing:
        raise SitePrerequisiteError(missing)
    site_dir = output_dir / config.SITE_DIRNAME
    written = build_site(build_context(processed_dir), site_dir)
    size = sum(p.stat().st_size for p in written)
    logger.info("Site yazıldı: %s (%d dosya, %.0f KB)", site_dir, len(written), size / 1024)
    return site_dir / "index.html"
