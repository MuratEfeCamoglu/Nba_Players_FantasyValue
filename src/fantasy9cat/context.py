"""Rapor ve site için ortak veri bağlamı: tek kaynak → md, pdf, html tutarlı."""

import json
from pathlib import Path
from typing import Any

import pandas as pd

from fantasy9cat import config
from fantasy9cat.formatting import CATEGORY_LABELS, CATEGORY_SHORT, fmt_num, fmt_pct
from fantasy9cat.valuation import percent_impact

STAT_DECIMALS = 3
Z_DECIMALS = 3
MULTIPLIER_DECIMALS = 6
PCT_TABLE_DECIMALS = 2
VALUE_DECIMALS = 1

CATEGORY_DIRECTIONS = {
    **{c: "Çok olan kazanır" for c in config.COUNTING_CATEGORIES},
    config.TURNOVER_CATEGORY: "Az olan kazanır",
    **{c: "Yüksek olan kazanır" for c in config.PERCENT_CATEGORIES},
}


def load_processed(processed_dir: Path) -> tuple[dict[str, pd.DataFrame], pd.DataFrame, dict]:
    """data/processed/ dosyalarını okur; eksik dosya varsa FileNotFoundError fırlatır."""
    missing = [name for name in config.PROCESSED_FILES if not (processed_dir / name).is_file()]
    if missing:
        raise FileNotFoundError(f"Eksik işlenmiş dosya(lar): {', '.join(missing)}")
    values = {
        mode: pd.read_csv(processed_dir / config.VALUES_FILENAMES[mode]) for mode in config.MODES
    }
    multipliers = pd.read_csv(processed_dir / config.MULTIPLIERS_FILENAME)
    meta = json.loads((processed_dir / config.META_FILENAME).read_text(encoding="utf-8"))
    return values, multipliers, meta


def _stat_text(value: float) -> str:
    """İstatistiği tam sayıysa ondalıksız, değilse 3 ondalıkla biçimler."""
    value = float(value)
    return fmt_num(value, 0) if value.is_integer() else fmt_num(value, STAT_DECIMALS)


def _multiplier_rows(multipliers: pd.DataFrame, mode: str) -> list[dict[str, Any]]:
    """Bir modun çarpan tablosu satırlarını biçimlenmiş metinlerle döndürür."""
    rows = []
    for _, r in multipliers[multipliers["mode"] == mode].iterrows():
        rows.append(
            {
                "code": r["category"],
                "label": CATEGORY_LABELS[r["category"]],
                "short": CATEGORY_SHORT[r["category"]],
                "mu": float(r["mu"]),
                "sigma": float(r["sigma"]),
                "points_equivalent": float(r["points_equivalent"]),
                "mu_text": fmt_num(r["mu"], STAT_DECIMALS),
                "sigma_text": fmt_num(r["sigma"], STAT_DECIMALS),
                "multiplier_text": fmt_num(r["multiplier"], MULTIPLIER_DECIMALS),
                "points_equivalent_text": fmt_num(r["points_equivalent"], STAT_DECIMALS),
                "mean_ratio_text": fmt_num(r["mean_ratio_to_pts"], STAT_DECIMALS),
                "league_pct_text": fmt_pct(r["league_pct"], PCT_TABLE_DECIMALS),
                "league_pct": None if pd.isna(r["league_pct"]) else float(r["league_pct"]),
            }
        )
    return rows


def build_worked_example(row: pd.Series, multipliers: pd.DataFrame) -> dict[str, Any]:
    """Bir oyuncunun 9 z-skorunu çarpan tablosundaki μ ve σ ile adım adım yeniden hesaplar."""
    params = multipliers.set_index("category")
    rows = []
    for cat, zcol in zip(config.CATEGORIES, config.Z_COLUMNS, strict=True):
        mu, sigma = float(params.loc[cat, "mu"]), float(params.loc[cat, "sigma"])
        mu_t, sigma_t = fmt_num(mu, STAT_DECIMALS), fmt_num(sigma, STAT_DECIMALS)
        impact = None
        if cat in config.PERCENT_CATEGORIES:
            made_col, att_col = (c.lower() for c in config.PERCENT_SOURCE_COLUMNS[cat])
            made, att = float(row[made_col]), float(row[att_col])
            p_lg = float(params.loc[cat, "league_pct"])
            impact = float(percent_impact(made, att, p_lg))
            z = (impact - mu) / sigma
            value_text = f"{_stat_text(made)}/{_stat_text(att)} ({fmt_pct(row[cat.lower()])})"
            imp_t = fmt_num(impact, STAT_DECIMALS, signed=True)
            calc = (
                f"etki = {_stat_text(made)} − {fmt_num(p_lg, 4)} × {_stat_text(att)} = {imp_t}; "
                f"z = ({imp_t} − {mu_t}) / {sigma_t}"
            )
        else:
            x = float(row[cat.lower()])
            value_text = _stat_text(x)
            if cat == config.TURNOVER_CATEGORY:
                z = (mu - x) / sigma
                calc = f"({mu_t} − {value_text}) / {sigma_t}"
            else:
                z = (x - mu) / sigma
                calc = f"({value_text} − {mu_t}) / {sigma_t}"
        rows.append(
            {
                "code": cat,
                "label": CATEGORY_LABELS[cat],
                "short": CATEGORY_SHORT[cat],
                "value_text": value_text,
                "mu_text": mu_t,
                "sigma_text": sigma_t,
                "calc_text": calc,
                "impact": impact,
                "z": z,
                "z_text": fmt_num(z, Z_DECIMALS, signed=True),
                "csv_z": float(row[zcol]),
            }
        )
    z_sum = sum(r["z"] for r in rows)
    return {
        "rank": int(row["rank"]),
        "player_name": row["player_name"],
        "team": row["team"],
        "gp": int(row["gp"]),
        "rows": rows,
        "z_sum": z_sum,
        "z_sum_text": fmt_num(z_sum, Z_DECIMALS),
        "csv_raw_total": float(row["raw_total"]),
        "csv_raw_total_text": fmt_num(row["raw_total"], Z_DECIMALS),
        "value_text": fmt_num(row["value"], VALUE_DECIMALS),
    }


def _impact_examples(total_mult: dict[str, dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """6/10 ve 60/100 örneklerinin etki (ve gerçek lig yüzdesiyle z) değerleri."""
    fixed = []
    for made, att, p_lg in config.IMPACT_EXAMPLES:
        impact = float(percent_impact(made, att, p_lg))
        fixed.append(
            {
                "shot_text": f"{made}/{att}",
                "player_pct_text": fmt_pct(made / att, 0),
                "league_pct_text": fmt_pct(p_lg, 0),
                "impact": impact,
                "impact_text": fmt_num(impact, 1, signed=True),
            }
        )
    fg = total_mult["FG_PCT"]
    real = []
    for made, att, _ in config.IMPACT_EXAMPLES[:2]:
        impact = float(percent_impact(made, att, fg["league_pct"]))
        z = (impact - fg["mu"]) / fg["sigma"]
        real.append(
            {
                "shot_text": f"{made}/{att}",
                "impact_text": fmt_num(impact, 2, signed=True),
                "z_text": fmt_num(z, Z_DECIMALS, signed=True),
            }
        )
    return {"fixed": fixed, "real": real, "league_pct_text": fmt_pct(fg["league_pct"])}


def _comparison(values: dict[str, pd.DataFrame]) -> dict[str, Any]:
    """Toplam ve maç başı sıralamalarını karşılaştıran tablolar."""
    t = values[config.MODE_TOTAL][["player_id", "player_name", "team", "gp", "rank", "value"]]
    g = values[config.MODE_PER_GAME][["player_id", "rank", "value", "low_sample"]]
    m = t.merge(g, on="player_id", suffixes=("_total", "_pg"))
    m["diff"] = m["rank_total"] - m["rank_pg"]

    def rows(df: pd.DataFrame) -> list[dict[str, Any]]:
        return [
            {
                "player_name": r["player_name"],
                "team": r["team"],
                "gp": int(r["gp"]),
                "rank_total": int(r["rank_total"]),
                "value_total_text": fmt_num(r["value_total"], VALUE_DECIMALS),
                "rank_pg": int(r["rank_pg"]),
                "value_pg_text": fmt_num(r["value_pg"], VALUE_DECIMALS),
                "diff_text": fmt_num(r["diff"], 0, signed=True),
            }
            for _, r in df.iterrows()
        ]

    movers = m[~m["low_sample"]].sort_values(
        ["diff", "rank_pg"], ascending=[False, True], kind="mergesort"
    )
    return {
        "top": rows(m.sort_values("rank_total", kind="mergesort").head(config.COMPARISON_TOP_N)),
        "risers": rows(movers.head(config.COMPARISON_MOVERS_N)),
        "n_low_sample": int(g["low_sample"].sum()),
    }


def _scale(values: dict[str, pd.DataFrame], meta: dict) -> dict[str, Any]:
    """Ölçekleme bölümü için en iyi aday, yedek seviyesi ve örnek hesap."""
    total = values[config.MODE_TOTAL]
    per_game = values[config.MODE_PER_GAME]
    top = float(total["raw_total"].iloc[0])
    repl = float(meta["replacement_raw_total"])
    ex = total.iloc[min(config.SCALE_EXAMPLE_RANK, len(total)) - 1]
    computed = config.SCALE_TOP_VALUE * (float(ex["raw_total"]) - repl) / (top - repl)
    pg_top = float(per_game.loc[~per_game["low_sample"], "raw_total"].iloc[0])
    over_100 = per_game[per_game["value"] > config.SCALE_TOP_VALUE]
    return {
        "top_raw_text": fmt_num(top, Z_DECIMALS),
        "top_name": total["player_name"].iloc[0],
        "replacement_rank": config.POOL_SIZE + 1,
        "replacement_raw_text": fmt_num(repl, Z_DECIMALS),
        "example_rank": int(ex["rank"]),
        "example_name": ex["player_name"],
        "example_raw_text": fmt_num(ex["raw_total"], Z_DECIMALS),
        "example_value_text": fmt_num(computed, VALUE_DECIMALS),
        "example_csv_value_text": fmt_num(ex["value"], VALUE_DECIMALS),
        "pg_top_raw_text": fmt_num(pg_top, Z_DECIMALS),
        "pg_replacement_raw_text": fmt_num(meta["replacement_raw_per_game"], Z_DECIMALS),
        "pg_over_100": int(len(over_100)),
    }


def _limitations(values: dict[str, pd.DataFrame]) -> dict[str, Any]:
    """Sınırlamalar bölümündeki somut örnekler."""
    total = values[config.MODE_TOTAL]
    tov = total.loc[total["z_tov"].idxmax()]
    empty_pct = int(((total["fga"] == 0) | (total["fta"] == 0)).sum())
    return {
        "tov_name": tov["player_name"],
        "tov_gp": int(tov["gp"]),
        "tov_value_text": _stat_text(tov["tov"]),
        "tov_z_text": fmt_num(tov["z_tov"], Z_DECIMALS, signed=True),
        "n_empty_pct": empty_pct,
    }


def _records(df: pd.DataFrame) -> list[dict[str, Any]]:
    """DataFrame'i NaN → None olan Python sözlük listesine çevirir."""
    return df.astype(object).where(df.notna(), None).to_dict("records")


def build_context(processed_dir: Path) -> dict[str, Any]:
    """İşlenmiş dosyalardan rapor ve site için tek veri bağlamını oluşturur."""
    values, multipliers, meta = load_processed(processed_dir)
    mult = {mode: _multiplier_rows(multipliers, mode) for mode in config.MODES}
    mult_by_code = {mode: {r["code"]: r for r in rows} for mode, rows in mult.items()}
    total = values[config.MODE_TOTAL]
    per_game = values[config.MODE_PER_GAME]
    worked_row = total.iloc[config.WORKED_EXAMPLE_RANK - 1]
    impact = _impact_examples(mult_by_code[config.MODE_TOTAL])
    return {
        "sections": config.REPORT_SECTIONS,
        "meta": meta,
        "season": meta["season"],
        "league": {
            "num_teams": config.NUM_TEAMS,
            "roster_size": config.ROSTER_SIZE,
            "pool_size": config.POOL_SIZE,
            "replacement_rank": config.POOL_SIZE + 1,
            "min_gp_pool_per_game": config.MIN_GP_POOL_PER_GAME,
            "max_iterations": config.MAX_POOL_ITERATIONS,
        },
        "categories": [
            {
                "code": c,
                "label": CATEGORY_LABELS[c],
                "short": CATEGORY_SHORT[c],
                "direction": CATEGORY_DIRECTIONS[c],
            }
            for c in config.CATEGORIES
        ],
        "pool": {
            "n_players": meta["n_players_total"],
            "n_candidates_per_game": int((~per_game["low_sample"]).sum()),
            "iterations_total": meta["iterations_total"],
            "converged_total": meta["converged_total"],
            "iterations_per_game": meta["iterations_per_game"],
            "converged_per_game": meta["converged_per_game"],
            "warnings": meta["warnings"],
        },
        "multipliers": mult,
        "mult": mult_by_code,
        "impact_examples": impact["fixed"],
        "impact": impact,
        "comparison": _comparison(values),
        "scale": _scale(values, meta),
        "worked_example": build_worked_example(
            worked_row, multipliers[multipliers["mode"] == config.MODE_TOTAL]
        ),
        "limitations": _limitations(values),
        "players": {mode: _records(df) for mode, df in values.items()},
    }
