"""Z-skor tabanlı 9-cat değerleme (ISKELET.md §3.3). Saf fonksiyonlar: G/Ç yok."""

from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np
import pandas as pd
from numpy.typing import ArrayLike

from fantasy9cat import config


@dataclass(frozen=True)
class CategoryParams:
    """Bir kategorinin havuz parametreleri (yüzde kategorilerinde etki üzerinden)."""

    mu: float
    sigma: float
    league_pct: float | None = None


@dataclass(frozen=True)
class ValuationResult:
    """Tek bir modun değerleme sonucu; `players` rank sırasında ve yuvarlanmamıştır."""

    mode: str
    players: pd.DataFrame
    params: dict[str, CategoryParams]
    iterations: int
    converged: bool
    top_raw: float
    replacement_raw: float
    warnings: tuple[str, ...]


def to_per_game(df: pd.DataFrame) -> pd.DataFrame:
    """Sayma kolonlarını ve MIN, FGM, FGA, FTM, FTA'yı GP'ye bölünmüş haliyle döndürür."""
    out = df.copy()
    gp = df["GP"].astype(float)
    for col in config.PER_GAME_COLUMNS:
        out[col] = df[col].astype(float) / gp
    return out


def percent_impact(made: ArrayLike, attempted: ArrayLike, league_pct: float) -> np.ndarray:
    """Hacim ağırlıklı etki: isabet − lig% × deneme; deneme 0 ise 0."""
    made_arr = np.asarray(made, dtype=float)
    att_arr = np.asarray(attempted, dtype=float)
    return np.where(att_arr > 0, made_arr - league_pct * att_arr, 0.0)


def league_percentage(made: ArrayLike, attempted: ArrayLike) -> float:
    """Toplam isabetin toplam denemeye oranını (lig yüzdesi) döndürür."""
    total_att = float(np.sum(np.asarray(attempted, dtype=float)))
    if total_att <= 0:
        raise ValueError("Havuzda hiç deneme yok; lig yüzdesi hesaplanamaz.")
    return float(np.sum(np.asarray(made, dtype=float))) / total_att


def _mu_sigma(values: np.ndarray, category: str) -> tuple[float, float]:
    """Popülasyon ortalaması ve standart sapması (ddof=0); σ = 0 ise hata."""
    mu = float(np.mean(values))
    sigma = float(np.std(values, ddof=0))
    if not np.isfinite(sigma) or sigma == 0:
        raise ValueError(f"{category} kategorisinde havuz standart sapması 0; z-skor tanımsız.")
    return mu, sigma


def compute_pool_params(stats: pd.DataFrame, pool_mask: ArrayLike) -> dict[str, CategoryParams]:
    """Havuzdaki oyunculardan 9 kategorinin μ, σ ve (yüzdelerde) lig yüzdesini hesaplar."""
    pool = np.asarray(pool_mask, dtype=bool)
    params: dict[str, CategoryParams] = {}
    for cat in (*config.COUNTING_CATEGORIES, config.TURNOVER_CATEGORY):
        mu, sigma = _mu_sigma(stats[cat].to_numpy(dtype=float)[pool], cat)
        params[cat] = CategoryParams(mu, sigma)
    for cat, (made_col, att_col) in config.PERCENT_SOURCE_COLUMNS.items():
        made = stats[made_col].to_numpy(dtype=float)
        att = stats[att_col].to_numpy(dtype=float)
        p_lg = league_percentage(made[pool], att[pool])
        mu, sigma = _mu_sigma(percent_impact(made, att, p_lg)[pool], cat)
        params[cat] = CategoryParams(mu, sigma, p_lg)
    return params


def compute_z_scores(stats: pd.DataFrame, params: dict[str, CategoryParams]) -> pd.DataFrame:
    """Tüm oyuncuların 9 kategorideki z-skorlarını (kolonlar: kategori kodları) döndürür."""
    z = pd.DataFrame(index=stats.index)
    for cat in config.COUNTING_CATEGORIES:
        p = params[cat]
        z[cat] = (stats[cat].to_numpy(dtype=float) - p.mu) / p.sigma
    p = params[config.TURNOVER_CATEGORY]
    z[config.TURNOVER_CATEGORY] = (p.mu - stats[config.TURNOVER_CATEGORY].to_numpy(dtype=float)) / (
        p.sigma
    )
    for cat, (made_col, att_col) in config.PERCENT_SOURCE_COLUMNS.items():
        p = params[cat]
        imp = percent_impact(stats[made_col], stats[att_col], p.league_pct)
        z[cat] = (imp - p.mu) / p.sigma
    return z[list(config.CATEGORIES)]


def rank_order(raw: ArrayLike, minutes: ArrayLike, player_id: ArrayLike) -> np.ndarray:
    """Sıralama indeksleri: ham azalan, eşitlikte MIN azalan, sonra PLAYER_ID artan."""
    return np.lexsort(
        (
            np.asarray(player_id),
            -np.asarray(minutes, dtype=float),
            -np.asarray(raw, dtype=float),
        )
    )


def _top_candidates(
    score: np.ndarray, stats: pd.DataFrame, candidate_mask: np.ndarray, pool_size: int
) -> np.ndarray:
    """Adaylar arasında skora göre (eşitlikte MIN, PLAYER_ID) ilk N'yi maske olarak döndürür."""
    idx = np.flatnonzero(candidate_mask)
    order = rank_order(score[idx], stats["MIN"].to_numpy()[idx], stats["PLAYER_ID"].to_numpy()[idx])
    mask = np.zeros(len(stats), dtype=bool)
    mask[idx[order[:pool_size]]] = True
    return mask


def initial_pool(stats: pd.DataFrame, candidate_mask: ArrayLike, pool_size: int) -> np.ndarray:
    """P₀: havuz adayları içinde MIN'e göre ilk N oyuncu."""
    minutes = stats["MIN"].to_numpy(dtype=float)
    return _top_candidates(minutes, stats, np.asarray(candidate_mask, dtype=bool), pool_size)


def iterate_pool(
    stats: pd.DataFrame, candidate_mask: ArrayLike, pool_size: int, max_iterations: int
) -> tuple[np.ndarray, dict[str, CategoryParams], pd.DataFrame, int, bool]:
    """Havuz değişmeyene ya da en fazla max_iterations adıma kadar havuzu yeniler."""
    candidates = np.asarray(candidate_mask, dtype=bool)
    pool = initial_pool(stats, candidates, pool_size)
    for iteration in range(1, max_iterations + 1):
        params = compute_pool_params(stats, pool)
        z = compute_z_scores(stats, params)
        new_pool = _top_candidates(z.sum(axis=1).to_numpy(), stats, candidates, pool_size)
        if np.array_equal(new_pool, pool):
            return pool, params, z, iteration, True
        pool = new_pool
    # Yakınsamadı: son havuz (P_max) kullanılır, parametreler ondan hesaplanır.
    params = compute_pool_params(stats, pool)
    return pool, params, compute_z_scores(stats, params), max_iterations, False


def scale_values(
    raw_ranked: ArrayLike, candidate_ranked: ArrayLike, pool_size: int
) -> tuple[np.ndarray, float, float, tuple[str, ...]]:
    """Ham değeri 0–100 ölçeğine taşır: en iyi aday 100, (N+1). aday 0."""
    raw = np.asarray(raw_ranked, dtype=float)
    cand_raw = raw[np.asarray(candidate_ranked, dtype=bool)]
    if len(cand_raw) < 2:
        raise ValueError("Ölçek için en az 2 havuz adayı gerekir.")
    warnings: tuple[str, ...] = ()
    if len(cand_raw) > pool_size:
        replacement = float(cand_raw[pool_size])
    else:
        replacement = float(cand_raw[-1])
        warnings = (
            f"Havuz adayı sayısı ({len(cand_raw)}) N+1 = {pool_size + 1} değerinden az; "
            "yedek seviyesi olarak son aday kullanıldı.",
        )
    top = float(cand_raw[0])
    if top == replacement:
        raise ValueError("En iyi aday ile yedek seviyesi aynı ham değerde; ölçek tanımsız.")
    values = config.SCALE_TOP_VALUE * (raw - replacement) / (top - replacement)
    return values, top, replacement, warnings


def _safe_ratio(made: pd.Series, attempted: pd.Series) -> np.ndarray:
    """İsabet/deneme oranı; deneme 0 ise NaN (yüzde tanımsız)."""
    att = attempted.to_numpy(dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(att > 0, made.to_numpy(dtype=float) / att, np.nan)


def value_players(
    raw: pd.DataFrame,
    mode: str,
    pool_size: int = config.POOL_SIZE,
    min_gp_pool_per_game: int = config.MIN_GP_POOL_PER_GAME,
    max_iterations: int = config.MAX_POOL_ITERATIONS,
) -> ValuationResult:
    """GP ≥ 1 olan herkesi verilen modda değerler ve rank sırasında sonuç döndürür."""
    if mode not in config.MODES:
        raise ValueError(f"Bilinmeyen mod: {mode}")
    df = raw[raw["GP"] >= config.MIN_GP_VALUED].reset_index(drop=True)
    per_game = mode == config.MODE_PER_GAME
    stats = to_per_game(df) if per_game else df
    min_gp_candidate = min_gp_pool_per_game if per_game else config.MIN_GP_VALUED
    candidates = (df["GP"] >= min_gp_candidate).to_numpy()

    pool, params, z, iterations, converged = iterate_pool(
        stats, candidates, pool_size, max_iterations
    )
    raw_total = z.sum(axis=1).to_numpy()
    order = rank_order(raw_total, stats["MIN"], stats["PLAYER_ID"])
    values, top, replacement, scale_warnings = scale_values(
        raw_total[order], candidates[order], pool_size
    )
    warnings = scale_warnings
    if not converged:
        warnings = (
            f"Havuz {max_iterations} iterasyonda yakınsamadı; son havuz kullanıldı.",
            *warnings,
        )

    s = stats.iloc[order].reset_index(drop=True)
    d = df.iloc[order].reset_index(drop=True)
    players = pd.DataFrame(
        {
            "rank": np.arange(1, len(s) + 1),
            "player_id": s["PLAYER_ID"].to_numpy(),
            "player_name": s["PLAYER_NAME"].to_numpy(),
            "team": s["TEAM_ABBREVIATION"].to_numpy(),
            "gp": s["GP"].to_numpy(),
            **{col.lower(): s[col].to_numpy() for col in config.PER_GAME_COLUMNS},
            "fg_pct": _safe_ratio(d["FGM"], d["FGA"]),
            "ft_pct": _safe_ratio(d["FTM"], d["FTA"]),
            **{
                zcol: z[cat].to_numpy()[order]
                for cat, zcol in zip(config.CATEGORIES, config.Z_COLUMNS, strict=True)
            },
            "raw_total": raw_total[order],
            "value": values,
            "in_pool": pool[order],
            "low_sample": per_game & (s["GP"] < min_gp_pool_per_game).to_numpy(),
        }
    )[list(config.VALUES_COLUMNS)]
    return ValuationResult(
        mode=mode,
        players=players,
        params=params,
        iterations=iterations,
        converged=converged,
        top_raw=top,
        replacement_raw=replacement,
        warnings=warnings,
    )


def build_multipliers(results: Iterable[ValuationResult]) -> pd.DataFrame:
    """Her mod için 9 satırlık çarpan tablosunu (μ, σ, 1/σ, sayı eşdeğeri, oranlar) üretir."""
    rows = []
    for res in results:
        pts = res.params["PTS"]
        for cat in config.CATEGORIES:
            p = res.params[cat]
            is_pct = cat in config.PERCENT_CATEGORIES
            rows.append(
                {
                    "mode": res.mode,
                    "category": cat,
                    "mu": p.mu,
                    "sigma": p.sigma,
                    "multiplier": 1.0 / p.sigma,
                    "points_equivalent": pts.sigma / p.sigma,
                    "mean_ratio_to_pts": np.nan if is_pct else pts.mu / p.mu,
                    "league_pct": p.league_pct if is_pct else np.nan,
                }
            )
    return pd.DataFrame(rows, columns=list(config.MULTIPLIERS_COLUMNS))
