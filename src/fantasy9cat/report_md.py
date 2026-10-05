"""Jinja2 ile templates/hesaplama.md.j2 → output/Hesaplama.md."""

import logging
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from fantasy9cat import config
from fantasy9cat.context import build_context

logger = logging.getLogger(__name__)


def make_environment() -> Environment:
    """Şablon klasörü için katı (tanımsız değişkende hata veren) Jinja2 ortamı kurar."""
    return Environment(
        loader=FileSystemLoader(config.TEMPLATES_DIR),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
        autoescape=False,
    )


def render_hesaplama(context: dict[str, Any]) -> str:
    """Hesaplama.md içeriğini veri bağlamından üretir."""
    return make_environment().get_template(config.HESAPLAMA_TEMPLATE).render(**context)


def run_report_md(processed_dir: Path, output_dir: Path) -> Path:
    """İşlenmiş verilerden Hesaplama.md'yi yazar ve dosya yolunu döndürür."""
    text = render_hesaplama(build_context(processed_dir))
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / config.HESAPLAMA_MD_FILENAME
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    logger.info("Yazıldı: %s", path)
    return path
