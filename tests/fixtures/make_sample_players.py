"""Testler için deterministik sentetik oyuncu verisi üretir (numpy seed=42).

Kullanım: python tests/fixtures/make_sample_players.py
Çıktı: bu dosyanın yanındaki sample_players.csv (ISKELET.md §3.4 ham CSV şeması).
"""

from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
N_PLAYERS = 500
N_LOW_GP = 100  # GP < 20 olan oyuncu sayısı (≥ 30 şartı)
OUTPUT_PATH = Path(__file__).resolve().parent / "sample_players.csv"

COLUMNS = [
    "PLAYER_ID",
    "PLAYER_NAME",
    "TEAM_ABBREVIATION",
    "GP",
    "MIN",
    "FGM",
    "FGA",
    "FG3M",
    "FTM",
    "FTA",
    "REB",
    "AST",
    "STL",
    "BLK",
    "TOV",
    "PTS",
]

TEAMS = [
    "ATL", "BOS", "BKN", "CHA", "CHI", "CLE", "DAL", "DEN", "DET", "GSW",
    "HOU", "IND", "LAC", "LAL", "MEM", "MIA", "MIL", "MIN", "NOP", "NYK",
    "OKC", "ORL", "PHI", "PHX", "POR", "SAC", "SAS", "TOR", "UTA", "WAS",
]  # fmt: skip

# Adı sabit, istatistikleri elle verilen oyuncular (PDF/site aksan testleri için).
# (PLAYER_ID, ad, takım, GP, dakika/maç, FGA/maç, FG%, 3P isabet/maç, FTA/maç, FT%,
#  REB/maç, AST/maç, STL/maç, BLK/maç, TOV/maç)
NAMED_PLAYERS = [
    (203999, "Nikola Jokić", "DEN", 70, 36.5, 19.0, 0.58, 2.0, 6.5, 0.80,
     12.5, 10.0, 1.6, 0.7, 3.2),
    (1630578, "Alperen Şengün", "HOU", 76, 33.0, 16.0, 0.50, 0.4, 5.5, 0.69,
     10.0, 5.0, 1.2, 1.0, 3.0),
]  # fmt: skip


def _counts(rng: np.random.Generator, rate_per_game: np.ndarray, gp: np.ndarray) -> np.ndarray:
    """Maç başı orana ve maç sayısına göre Poisson toplamı üretir."""
    return rng.poisson(rate_per_game * gp)


def make_sample_players(seed: int = SEED) -> pd.DataFrame:
    """Sentetik oyuncu toplamlarını içeren DataFrame döndürür."""
    rng = np.random.default_rng(seed)
    n_random = N_PLAYERS - len(NAMED_PLAYERS)
    n_high = n_random - N_LOW_GP

    gp = np.concatenate([rng.integers(20, 83, size=n_high), rng.integers(1, 20, size=N_LOW_GP)])
    rng.shuffle(gp)

    mpg = rng.uniform(6.0, 37.0, size=n_random)
    usage = rng.uniform(0.25, 0.65, size=n_random)  # FGA / dakika
    fga = rng.poisson(usage * mpg * gp)
    fgm = rng.binomial(fga, rng.uniform(0.38, 0.62, size=n_random))
    fg3m = rng.binomial(fgm, rng.uniform(0.0, 0.45, size=n_random))
    fta = rng.poisson(rng.uniform(0.03, 0.30, size=n_random) * mpg * gp)
    ftm = rng.binomial(fta, rng.uniform(0.55, 0.92, size=n_random))

    df = pd.DataFrame(
        {
            "PLAYER_ID": np.arange(1_000_001, 1_000_001 + n_random),
            "PLAYER_NAME": [f"Sentetik Oyuncu {i:03d}" for i in range(1, n_random + 1)],
            "TEAM_ABBREVIATION": rng.choice(TEAMS, size=n_random),
            "GP": gp,
            "MIN": np.round(mpg * gp, 1),
            "FGM": fgm,
            "FGA": fga,
            "FG3M": fg3m,
            "FTM": ftm,
            "FTA": fta,
            "REB": _counts(rng, rng.uniform(0.10, 0.35, size=n_random) * mpg, gp),
            "AST": _counts(rng, rng.uniform(0.04, 0.25, size=n_random) * mpg, gp),
            "STL": _counts(rng, rng.uniform(0.01, 0.05, size=n_random) * mpg, gp),
            "BLK": _counts(rng, rng.uniform(0.005, 0.06, size=n_random) * mpg, gp),
            "TOV": _counts(rng, rng.uniform(0.03, 0.10, size=n_random) * mpg, gp),
        }
    )

    named_rows = []
    for pid, name, team, g, m, fga_pg, fg_pct, fg3m_pg, fta_pg, ft_pct, *rest in NAMED_PLAYERS:
        reb, ast, stl, blk, tov = (round(v * g) for v in rest)
        p_fga = round(fga_pg * g)
        p_fgm = round(p_fga * fg_pct)
        p_fta = round(fta_pg * g)
        named_rows.append(
            {
                "PLAYER_ID": pid,
                "PLAYER_NAME": name,
                "TEAM_ABBREVIATION": team,
                "GP": g,
                "MIN": round(m * g, 1),
                "FGM": p_fgm,
                "FGA": p_fga,
                "FG3M": round(fg3m_pg * g),
                "FTM": round(p_fta * ft_pct),
                "FTA": p_fta,
                "REB": reb,
                "AST": ast,
                "STL": stl,
                "BLK": blk,
                "TOV": tov,
            }
        )

    df = pd.concat([pd.DataFrame(named_rows), df], ignore_index=True)
    df["PTS"] = 2 * df["FGM"] + df["FG3M"] + df["FTM"]
    return df[COLUMNS].sort_values("PLAYER_ID", ignore_index=True)


def main() -> None:
    """Fikstürü üretip CSV olarak yazar."""
    df = make_sample_players()
    df.to_csv(OUTPUT_PATH, index=False, lineterminator="\n", encoding="utf-8")
    print(f"{len(df)} satır yazıldı: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
