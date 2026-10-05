"""valuation.py testleri (F3–F8). Beklenen değerler ISKELET.md §3.3'e göre elle hesaplanır."""

import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from fantasy9cat import config
from fantasy9cat.valuation import (
    CategoryParams,
    ValuationResult,
    build_multipliers,
    compute_pool_params,
    compute_z_scores,
    initial_pool,
    league_percentage,
    percent_impact,
    rank_order,
    scale_values,
    to_per_game,
    value_players,
)

SAMPLE_CSV = Path(__file__).resolve().parent / "fixtures" / "sample_players.csv"
N = config.POOL_SIZE


@pytest.fixture(scope="module")
def sample() -> pd.DataFrame:
    return pd.read_csv(SAMPLE_CSV)


@pytest.fixture(scope="module")
def total(sample: pd.DataFrame) -> ValuationResult:
    return value_players(sample, config.MODE_TOTAL)


@pytest.fixture(scope="module")
def per_game(sample: pd.DataFrame) -> ValuationResult:
    return value_players(sample, config.MODE_PER_GAME)


def small() -> pd.DataFrame:
    """Elle hesaplama için 4 oyunculuk ham tablo."""
    return pd.DataFrame(
        {
            "PLAYER_ID": [1, 2, 3, 4],
            "PLAYER_NAME": ["A", "B", "C", "D"],
            "TEAM_ABBREVIATION": ["AAA", "BBB", "CCC", "DDD"],
            "GP": [10, 20, 30, 40],
            "MIN": [100.0, 200.0, 300.0, 400.0],
            "FGM": [5, 6, 12, 0],
            "FGA": [10, 10, 20, 0],
            "FG3M": [0, 1, 2, 0],
            "FTM": [3, 4, 0, 9],
            "FTA": [4, 5, 0, 10],
            "REB": [4, 8, 2, 6],
            "AST": [1, 2, 3, 10],
            "STL": [1, 1, 2, 4],
            "BLK": [0, 2, 0, 2],
            "TOV": [2, 4, 6, 8],
            "PTS": [10, 20, 30, 40],
        }
    )


ALL = np.array([True, True, True, True])


# --- F4: yüzde kategorilerinde hacim etkisi ---


def test_impact_6_of_10_at_50_percent_is_plus_1() -> None:
    assert percent_impact(6, 10, 0.50) == pytest.approx(1.0, abs=1e-12)


def test_impact_60_of_100_at_50_percent_is_plus_10() -> None:
    assert percent_impact(60, 100, 0.50) == pytest.approx(10.0, abs=1e-12)


def test_impact_60_of_100_at_65_percent_is_minus_5() -> None:
    assert percent_impact(60, 100, 0.65) == pytest.approx(-5.0, abs=1e-12)


def test_impact_zero_attempts_is_zero() -> None:
    assert percent_impact(0, 0, 0.50) == 0.0
    out = percent_impact(np.array([0, 6]), np.array([0, 10]), 0.5)
    assert out.tolist() == pytest.approx([0.0, 1.0])


def test_league_percentage_is_sum_made_over_sum_attempted() -> None:
    df = small()
    assert league_percentage(df["FGM"], df["FGA"]) == pytest.approx(23 / 40)


# --- §3.3 adım 1–3: z-skorlar (popülasyon std, ddof=0) ---


def test_counting_z_scores_by_hand() -> None:
    df = small()
    z = compute_z_scores(df, compute_pool_params(df, ALL))
    sigma = math.sqrt((15**2 + 5**2 + 5**2 + 15**2) / 4)  # ddof=0
    expected = [(10 - 25) / sigma, (20 - 25) / sigma, (30 - 25) / sigma, (40 - 25) / sigma]
    assert z["PTS"].tolist() == pytest.approx(expected, abs=1e-12)


def test_turnover_z_sign_is_reversed() -> None:
    df = small()
    z = compute_z_scores(df, compute_pool_params(df, ALL))
    sigma = math.sqrt((9 + 1 + 1 + 9) / 4)
    expected = [(5 - 2) / sigma, (5 - 4) / sigma, (5 - 6) / sigma, (5 - 8) / sigma]
    assert z["TOV"].tolist() == pytest.approx(expected, abs=1e-12)
    assert z["TOV"].iloc[0] > 0  # en az top kaybı yapan artı alır


def test_fg_pct_z_uses_volume_impact() -> None:
    df = small()
    params = compute_pool_params(df, ALL)
    p_lg = 23 / 40
    imp = [5 - p_lg * 10, 6 - p_lg * 10, 12 - p_lg * 20, 0.0]  # D: FGA=0 → 0
    mu = sum(imp) / 4
    sigma = math.sqrt(sum((x - mu) ** 2 for x in imp) / 4)
    assert params["FG_PCT"].league_pct == pytest.approx(p_lg)
    assert params["FG_PCT"].mu == pytest.approx(mu, abs=1e-12)
    assert params["FG_PCT"].sigma == pytest.approx(sigma, abs=1e-12)
    z = compute_z_scores(df, params)
    assert z["FG_PCT"].tolist() == pytest.approx([(x - mu) / sigma for x in imp], abs=1e-12)


def test_ft_pct_z_uses_volume_impact() -> None:
    df = small()
    p_lg = 16 / 19
    imp = [3 - p_lg * 4, 4 - p_lg * 5, 0.0, 9 - p_lg * 10]
    mu = sum(imp) / 4
    sigma = math.sqrt(sum((x - mu) ** 2 for x in imp) / 4)
    z = compute_z_scores(df, compute_pool_params(df, ALL))
    assert z["FT_PCT"].tolist() == pytest.approx([(x - mu) / sigma for x in imp], abs=1e-12)


def test_params_come_from_pool_only() -> None:
    df = small()
    pool = np.array([True, True, True, False])
    params = compute_pool_params(df, pool)
    assert params["PTS"].mu == pytest.approx(20.0)
    assert params["PTS"].sigma == pytest.approx(math.sqrt(200 / 3))
    assert params["FG_PCT"].league_pct == pytest.approx(23 / 40)
    # Havuz dışı oyuncu da z-skor alır
    z = compute_z_scores(df, params)
    assert z["PTS"].iloc[3] == pytest.approx((40 - 20) / math.sqrt(200 / 3))


def test_zero_sigma_raises() -> None:
    df = small()
    df["BLK"] = 1
    with pytest.raises(ValueError, match="BLK"):
        compute_pool_params(df, ALL)


# --- Maç başı dönüşüm ---


def test_to_per_game_divides_counting_columns_by_gp() -> None:
    df = small()
    pg = to_per_game(df)
    for col in config.PER_GAME_COLUMNS:
        assert pg[col].tolist() == pytest.approx((df[col] / df["GP"]).tolist())
    assert pg["GP"].tolist() == df["GP"].tolist()
    assert pg["PLAYER_NAME"].tolist() == df["PLAYER_NAME"].tolist()


# --- §3.3 adım 6: sıralama ---


def test_rank_order_tie_breaks_min_then_player_id() -> None:
    raw = np.array([1.0, 2.0, 2.0, 2.0])
    minutes = np.array([50.0, 10.0, 30.0, 30.0])
    ids = np.array([1, 2, 9, 4])
    assert rank_order(raw, minutes, ids).tolist() == [3, 2, 1, 0]


# --- §3.3 adım 7: ölçek (F8) ---


def test_scale_total_top_is_100_replacement_is_0() -> None:
    raw = np.array([5.0, 3.0, 1.0, 0.0, -2.0])
    values, top, repl, warnings = scale_values(raw, np.ones(5, dtype=bool), pool_size=2)
    assert values.tolist() == pytest.approx([100.0, 50.0, 0.0, -25.0, -75.0])
    assert (top, repl) == (5.0, 1.0)
    assert warnings == ()


def test_scale_uses_candidates_only() -> None:
    raw = np.array([9.0, 5.0, 3.0, 1.0, 0.0])
    candidates = np.array([False, True, True, True, True])
    values, top, repl, _ = scale_values(raw, candidates, pool_size=2)
    assert (top, repl) == (5.0, 1.0)
    assert values.tolist() == pytest.approx([200.0, 100.0, 50.0, 0.0, -25.0])


def test_scale_falls_back_to_last_candidate_with_warning() -> None:
    raw = np.array([5.0, 3.0, 1.0])
    candidates = np.array([True, True, False])
    values, top, repl, warnings = scale_values(raw, candidates, pool_size=2)
    assert repl == 3.0
    assert values.tolist() == pytest.approx([100.0, 0.0, -100.0])
    assert len(warnings) == 1


# --- F5: iteratif havuz ---


def test_initial_pool_is_top_n_candidates_by_minutes() -> None:
    df = small()
    candidates = np.array([True, True, True, False])
    pool = initial_pool(df, candidates, pool_size=2)
    assert pool.tolist() == [False, True, True, False]


def test_iterations_bounded_and_reported(total: ValuationResult) -> None:
    assert 1 <= total.iterations <= config.MAX_POOL_ITERATIONS
    assert isinstance(total.converged, bool)


def test_converged_pool_is_top_n_candidates_by_raw(total: ValuationResult) -> None:
    assert total.converged
    players = total.players
    assert players["in_pool"].sum() == N
    assert players["in_pool"].tolist() == [True] * N + [False] * (len(players) - N)


def test_max_iterations_caps_loop(sample: pd.DataFrame) -> None:
    res = value_players(sample, config.MODE_TOTAL, max_iterations=1)
    assert res.iterations == 1
    assert res.converged is False
    assert res.players["in_pool"].sum() == N


def test_non_convergence_adds_warning(sample: pd.DataFrame, total: ValuationResult) -> None:
    res = value_players(sample, config.MODE_TOTAL, max_iterations=1)
    assert any("yakınsamadı" in w for w in res.warnings)
    assert total.warnings == ()  # yakınsayan çalıştırmada uyarı yok


# --- F3: fikstürde bağımsız yeniden hesaplama ---


def _manual_z(stats: pd.DataFrame, pool: np.ndarray) -> dict[str, np.ndarray]:
    """§3.3 formüllerinin numpy ile doğrudan, bağımsız uygulaması."""
    out = {}
    for cat in config.COUNTING_CATEGORIES:
        x = stats[cat].to_numpy(float)
        out[cat] = (x - x[pool].mean()) / x[pool].std(ddof=0)
    x = stats["TOV"].to_numpy(float)
    out["TOV"] = (x[pool].mean() - x) / x[pool].std(ddof=0)
    for cat, (m, a) in config.PERCENT_SOURCE_COLUMNS.items():
        made, att = stats[m].to_numpy(float), stats[a].to_numpy(float)
        p = made[pool].sum() / att[pool].sum()
        imp = np.where(att > 0, made - p * att, 0.0)
        out[cat] = (imp - imp[pool].mean()) / imp[pool].std(ddof=0)
    return out


@pytest.mark.parametrize("mode", config.MODES)
def test_z_scores_match_manual_calculation(sample: pd.DataFrame, mode: str) -> None:
    res = value_players(sample, mode)
    players = res.players
    raw = sample.set_index("PLAYER_ID").loc[players["player_id"]].reset_index()
    stats = to_per_game(raw) if mode == config.MODE_PER_GAME else raw
    manual = _manual_z(stats, players["in_pool"].to_numpy())
    for cat, zcol in zip(config.CATEGORIES, config.Z_COLUMNS, strict=True):
        assert np.max(np.abs(players[zcol].to_numpy() - manual[cat])) < 1e-9, cat
    raw_sum = sum(manual[c] for c in config.CATEGORIES)
    assert np.max(np.abs(players["raw_total"].to_numpy() - raw_sum)) < 1e-9


def test_players_sorted_by_rank(total: ValuationResult) -> None:
    p = total.players
    assert list(p.columns) == list(config.VALUES_COLUMNS)
    assert p["rank"].tolist() == list(range(1, len(p) + 1))
    assert p["raw_total"].is_monotonic_decreasing


def test_valuation_is_deterministic(sample: pd.DataFrame, total: ValuationResult) -> None:
    again = value_players(sample, config.MODE_TOTAL)
    pd.testing.assert_frame_equal(again.players, total.players)


# --- F7: maç başı değerleme ---


def test_everyone_with_gp_valued_in_both_modes(
    sample: pd.DataFrame, total: ValuationResult, per_game: ValuationResult
) -> None:
    n = int((sample["GP"] >= 1).sum())
    assert len(total.players) == len(per_game.players) == n


def test_players_with_zero_gp_are_excluded(sample: pd.DataFrame) -> None:
    df = sample.copy()
    df.loc[0, ["GP", "MIN", "PTS"]] = 0
    res = value_players(df, config.MODE_PER_GAME)
    assert len(res.players) == len(df) - 1


def test_low_sample_flag(per_game: ValuationResult, total: ValuationResult) -> None:
    p = per_game.players
    assert (p["low_sample"] == (p["gp"] < config.MIN_GP_POOL_PER_GAME)).all()
    assert p["low_sample"].any()
    assert not total.players["low_sample"].any()


def test_per_game_pool_only_has_enough_games(per_game: ValuationResult) -> None:
    p = per_game.players
    assert p["in_pool"].sum() == N
    assert (p.loc[p["in_pool"], "gp"] >= config.MIN_GP_POOL_PER_GAME).all()


def test_per_game_stats_are_per_game(sample: pd.DataFrame, per_game: ValuationResult) -> None:
    p = per_game.players.set_index("player_id")
    s = sample.set_index("PLAYER_ID")
    assert p.loc[203999, "pts"] == pytest.approx(s.loc[203999, "PTS"] / s.loc[203999, "GP"])
    assert p.loc[203999, "gp"] == s.loc[203999, "GP"]
    assert p.loc[203999, "fg_pct"] == pytest.approx(s.loc[203999, "FGM"] / s.loc[203999, "FGA"])


# --- §3.4: deneme sayısı 0 → yüzde boş, etki 0, z tanımlı ---


@pytest.mark.parametrize("mode", config.MODES)
def test_zero_attempts_percent_is_empty_but_z_defined(mode: str) -> None:
    df = small()
    df["GP"] = 10  # maç başı değerler toplamlarla orantılı kalsın (σ = 0 olmasın)
    df.loc[2, "FGM"] = 11  # hiçbir 3'lü havuzda FG etkileri hep 0 olmasın
    res = value_players(df, mode, pool_size=3, min_gp_pool_per_game=1)
    p = res.players.set_index("player_name")
    # D: FGA = 0, C: FTA = 0
    assert np.isnan(p.loc["D", "fg_pct"])
    assert np.isnan(p.loc["C", "ft_pct"])
    assert p.loc["A", "fg_pct"] == pytest.approx(0.5)
    fg, ft = res.params["FG_PCT"], res.params["FT_PCT"]
    assert p.loc["D", "z_fg_pct"] == pytest.approx((0.0 - fg.mu) / fg.sigma, abs=1e-12)
    assert p.loc["C", "z_ft_pct"] == pytest.approx((0.0 - ft.mu) / ft.sigma, abs=1e-12)
    assert np.isfinite(p[list(config.Z_COLUMNS)].to_numpy()).all()
    assert np.isfinite(p["raw_total"]).all() and np.isfinite(p["value"]).all()


# --- F8: ölçekleme ---


def test_total_scale(total: ValuationResult) -> None:
    v = total.players["value"].to_numpy()
    assert v[0] == pytest.approx(100.0, abs=1e-9)
    assert v[N] == pytest.approx(0.0, abs=1e-9)  # 241. sıra
    raw = total.players["raw_total"].to_numpy()
    below = raw < raw[N]
    assert (v[below] < 0).all()
    assert total.replacement_raw == pytest.approx(raw[N])


def test_per_game_scale_uses_candidates(per_game: ValuationResult) -> None:
    p = per_game.players
    cand = p[~p["low_sample"]]
    assert cand["value"].iloc[0] == pytest.approx(100.0, abs=1e-9)
    assert cand["value"].iloc[N] == pytest.approx(0.0, abs=1e-9)  # 241. aday
    assert per_game.replacement_raw == pytest.approx(cand["raw_total"].iloc[N])
    assert per_game.warnings == ()


# --- F6: çarpan tablosu ---


def test_multipliers_table(total: ValuationResult, per_game: ValuationResult) -> None:
    m = build_multipliers([total, per_game])
    assert list(m.columns) == list(config.MULTIPLIERS_COLUMNS)
    assert len(m) == 18
    for mode in config.MODES:
        rows = m[m["mode"] == mode].set_index("category")
        assert list(rows.index) == list(config.CATEGORIES)
        assert rows.loc["PTS", "points_equivalent"] == pytest.approx(1.0)
        assert (rows["multiplier"] - 1 / rows["sigma"]).abs().max() < 1e-12
        pts_sigma = rows.loc["PTS", "sigma"]
        assert (rows["points_equivalent"] - pts_sigma / rows["sigma"]).abs().max() < 1e-12
        pct = list(config.PERCENT_CATEGORIES)
        others = [c for c in config.CATEGORIES if c not in pct]
        assert rows.loc[pct, "mean_ratio_to_pts"].isna().all()
        assert rows.loc[pct, "league_pct"].notna().all()
        assert rows.loc[others, "league_pct"].isna().all()
        assert rows.loc[others, "mean_ratio_to_pts"].notna().all()
        pts_mu = rows.loc["PTS", "mu"]
        assert rows.loc["REB", "mean_ratio_to_pts"] == pytest.approx(pts_mu / rows.loc["REB", "mu"])


def test_multipliers_match_result_params(total: ValuationResult) -> None:
    m = build_multipliers([total]).set_index("category")
    for cat in config.CATEGORIES:
        p: CategoryParams = total.params[cat]
        assert m.loc[cat, "mu"] == p.mu
        assert m.loc[cat, "sigma"] == p.sigma
