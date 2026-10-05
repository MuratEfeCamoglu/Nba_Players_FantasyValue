"""compute adımı: ham CSV → valuation → data/processed/ (ISKELET.md §3.4)."""

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd

from fantasy9cat import config
from fantasy9cat.schema import validate
from fantasy9cat.valuation import ValuationResult, build_multipliers, value_players

logger = logging.getLogger(__name__)


def _round_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Ondalık kolonları 6 haneye yuvarlar; −0,0'ı 0,0 yapar (deterministik çıktı)."""
    out = df.copy()
    float_cols = out.select_dtypes(include="float").columns
    out[float_cols] = out[float_cols].round(config.CSV_DECIMALS) + 0.0
    return out


def _write_csv(df: pd.DataFrame, path: Path) -> None:
    """CSV'yi deterministik biçimde (6 ondalık, \\n satır sonu, index yok) yazar."""
    _round_frame(df).to_csv(
        path,
        index=False,
        lineterminator="\n",
        encoding="utf-8",
        float_format=f"%.{config.CSV_DECIMALS}f",
    )


def _source_label(path: Path) -> str:
    """meta.json için makineden bağımsız kaynak dosya adı (proje köküne göre)."""
    resolved = path.resolve()
    try:
        return resolved.relative_to(config.PROJECT_ROOT).as_posix()
    except ValueError:
        return resolved.name


def build_meta(raw_path: Path, season: str, results: dict[str, ValuationResult]) -> dict[str, Any]:
    """meta.json içeriğini (zaman damgasız) oluşturur."""
    total = results[config.MODE_TOTAL]
    per_game = results[config.MODE_PER_GAME]
    return {
        "season": season,
        "season_type": config.SEASON_TYPE,
        "source_file": _source_label(raw_path),
        "source_sha256": hashlib.sha256(raw_path.read_bytes()).hexdigest(),
        "n_players_total": len(total.players),
        "n_players_per_game": len(per_game.players),
        "pool_size": config.POOL_SIZE,
        "iterations_total": total.iterations,
        "converged_total": total.converged,
        "iterations_per_game": per_game.iterations,
        "converged_per_game": per_game.converged,
        "replacement_raw_total": round(total.replacement_raw, config.CSV_DECIMALS) + 0.0,
        "replacement_raw_per_game": round(per_game.replacement_raw, config.CSV_DECIMALS) + 0.0,
        "warnings": [f"{res.mode}: {w}" for res in results.values() for w in res.warnings],
    }


def run_compute(raw_path: Path, out_dir: Path, season: str = config.SEASON) -> dict[str, Any]:
    """Ham CSV'yi doğrulayıp iki modda değerler, dört çıktı dosyasını yazar ve meta'yı döndürür."""
    raw = pd.read_csv(raw_path)
    validate(raw)
    results = {mode: value_players(raw, mode) for mode in config.MODES}
    meta = build_meta(raw_path, season, results)

    out_dir.mkdir(parents=True, exist_ok=True)
    for mode, res in results.items():
        _write_csv(res.players, out_dir / config.VALUES_FILENAMES[mode])
    _write_csv(build_multipliers(results.values()), out_dir / config.MULTIPLIERS_FILENAME)
    with open(out_dir / config.META_FILENAME, "w", encoding="utf-8", newline="\n") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")

    for res in results.values():
        logger.info(
            "%s: %d oyuncu, %d iterasyon (yakınsadı: %s), yedek ham değer %.6f",
            res.mode,
            len(res.players),
            res.iterations,
            res.converged,
            res.replacement_raw,
        )
        for warning in res.warnings:
            logger.warning("%s: %s", res.mode, warning)
    logger.info("Çıktılar yazıldı: %s", out_dir)
    return meta
