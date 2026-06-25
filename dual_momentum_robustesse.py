#!/usr/bin/env python3
"""
Test de robustesse du Dual Momentum.
Objectif : vérifier que l'edge ne dépend pas d'un réglage chanceux du buffer.
- Balaye plusieurs valeurs de buffer anti-whipsaw.
- Teste aussi 2 sous-périodes (1ere moitié / 2e moitié) pour voir si ça tient partout.
Si l'edge n'existe qu'à 3% pile, c'est du sur-ajustement et on s'en méfie.
"""

import warnings
warnings.filterwarnings("ignore")

import pandas as pd
from dual_momentum_backtest import (
    telecharger, backtest_dual_momentum, backtest_world, metriques,
    RISK_ASSETS, SAFE_ASSET, LOOKBACK_MOIS,
)


def stats_sur(prix, buffer):
    courbe, nb_trades, _ = backtest_dual_momentum(prix, buffer=buffer)
    m = metriques(courbe)
    m["trades_an"] = round(nb_trades / m["n_annees"], 1)
    return m


if __name__ == "__main__":
    tickers = list(RISK_ASSETS.values()) + list(SAFE_ASSET.values())
    prix = telecharger(tickers)
    print(f"Données : {prix.index[0].date()} → {prix.index[-1].date()}\n")

    # ─── 1. Balayage du buffer sur toute la période ───
    print("="*72)
    print(f"{'1. SENSIBILITÉ AU BUFFER (toute la période)':^72}")
    print("="*72)
    print(f"{'Buffer':>8} {'CAGR':>9} {'Drawdown':>10} {'Sharpe':>8} {'Trades/an':>11}")
    print("-"*72)
    for b in [0.0, 0.01, 0.02, 0.03, 0.04, 0.05, 0.07, 0.10]:
        m = stats_sur(prix, b)
        print(f"{int(b*100):>6}%  {m['cagr_pct']:>7.2f}% {m['max_drawdown_pct']:>9.1f}% "
              f"{m['sharpe']:>8.2f} {m['trades_an']:>11.1f}")

    # Référence World pour comparaison
    mw = metriques(backtest_world(prix))
    print("-"*72)
    print(f"{'World B&H':>8} {mw['cagr_pct']:>7.2f}% {mw['max_drawdown_pct']:>9.1f}% "
          f"{mw['sharpe']:>8.2f} {'0.0':>11}")

    # ─── 2. Test sur 2 sous-périodes (buffer 3%) ───
    print("\n" + "="*72)
    print(f"{'2. STABILITÉ DANS LE TEMPS (buffer 3%)':^72}")
    print("="*72)
    milieu = prix.index[len(prix)//2]
    p1 = prix.loc[:milieu]
    p2 = prix.loc[milieu:]
    for label, p in [("1ere moitié", p1), ("2e moitié", p2)]:
        if len(p) < LOOKBACK_MOIS + 12:
            continue
        m  = stats_sur(p, 0.03)
        mw = metriques(backtest_world(p))
        print(f"\n{label} ({p.index[0].date()} → {p.index[-1].date()})")
        print(f"  Dual Momentum : CAGR {m['cagr_pct']:+.2f}% | drawdown {m['max_drawdown_pct']:.1f}% | Sharpe {m['sharpe']:.2f}")
        print(f"  World B&H     : CAGR {mw['cagr_pct']:+.2f}% | drawdown {mw['max_drawdown_pct']:.1f}% | Sharpe {mw['sharpe']:.2f}")

    print("\n" + "="*72)
    print("Lecture : si le DM bat le World sur les DEUX moitiés et pour PLUSIEURS")
    print("valeurs de buffer, l'edge est robuste. Si ça ne marche qu'à 3% pile ou")
    print("sur une seule moitié, c'est suspect.")
    print("="*72)
