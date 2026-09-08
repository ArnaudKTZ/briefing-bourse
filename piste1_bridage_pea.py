#!/usr/bin/env python3
"""
Piste 1 — Combien coûte le bridage PEA du cœur Dual Momentum ?

Constat (08/09/2026) : l'agent live (agent_dual_momentum.py) tourne une version
AFFAIBLIE de la stratégie validée par dual_momentum_backtest.py :
  - univers rotatif = World vs USA (or le World, c'est ~70% de USA : quasi-jumeaux)
  - refuge = CASH (dort à 0%) au lieu d'obligations qui rapportent.

Cette recette garde EXACTEMENT la structure du live (50% socle World toujours
investi + 50% poche rotative, momentum absolu 12 mois, anti-whipsaw +3%) et ne
fait varier QUE deux leviers, pour isoler leur effet chacun :
  A  LIVE actuel        : rotatif {World, USA}          refuge CASH
  B  + refuge obligataire: rotatif {World, USA}          refuge OBLIG (IEF)
  C  + univers élargi   : rotatif {USA, exUS, Émergents} refuge CASH
  D  complet            : rotatif {USA, exUS, Émergents} refuge OBLIG (IEF)

Références : World buy&hold, S&P buy&hold, et le GEM pur (100% rotatif, la
version d'Antonacci) pour situer le plafond.

Params a priori (littérature), jamais optimisés sur les données. Frais 0,1% par
rotation, appliqués sur la seule moitié rotative qui bouge.
"""

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import yfinance as yf

LOOKBACK = 12
FRAIS = 0.001          # 0,1% par changement de poche rotative
BUFFER = 0.03          # anti-whipsaw : +3% pour basculer
SOCLE_W = 0.50         # 50% toujours sur le World (comme le live)
CAP = 10000.0

# Proxies longue histoire (dividendes inclus). En PEA on achète les UCITS équivalents.
TICKERS = ["SPY", "EFA", "EEM", "IEF"]      # USA, développés ex-US, émergents, oblig US 7-10a
POIDS_WORLD = {"SPY": 0.60, "EFA": 0.30, "EEM": 0.10}   # proxy ACWI rééquilibré


def charger():
    px = yf.download(TICKERS, start="2003-01-01", auto_adjust=True, progress=False)["Close"]
    mens = px.resample("ME").last().dropna(how="all")
    # Construit un indice "WORLD" (panier ACWI rééquilibré mensuellement)
    rr = mens[list(POIDS_WORLD)].pct_change().fillna(0)
    poids = np.array([POIDS_WORLD[c] for c in POIDS_WORLD])
    world = [100.0]
    for _, row in rr.iloc[1:].iterrows():
        world.append(world[-1] * (1 + float(np.dot(poids, row[list(POIDS_WORLD)].values))))
    mens["WORLD"] = world
    return mens.dropna()


def moteur(prix, rotatif, refuge, socle_w=SOCLE_W, buffer=BUFFER):
    """Réplique la logique du live : socle World fixe + poche rotative sur momentum.
    refuge = 'CASH' (rendement 0) ou un ticker (ex 'IEF')."""
    rends = prix.pct_change()
    mom = prix.pct_change(LOOKBACK)
    dates = prix.index[LOOKBACK:]
    valeur, position, nb_trades = CAP, None, 0
    courbe = {}
    for i, date in enumerate(dates):
        date_prec = dates[i-1] if i > 0 else date
        m = mom.loc[date_prec, rotatif]
        best = m.idxmax(); mbest = m[best]
        if mbest <= 0:
            cible = refuge
        elif (buffer > 0 and position in rotatif and m[position] > 0
              and mbest < m[position] + buffer):
            cible = position
        else:
            cible = best
        # rendement du mois sur la position rotative détenue + socle World
        r_socle = rends.loc[date, "WORLD"]
        if position is None or position == "CASH":
            r_rot = 0.0
        else:
            r_rot = rends.loc[date, position]
        r_rot = 0.0 if np.isnan(r_rot) else r_rot
        valeur *= (1 + socle_w * r_socle + (1 - socle_w) * r_rot)
        if cible != position:
            valeur *= (1 - FRAIS * (1 - socle_w))   # frais sur la moitié rotative
            nb_trades += 1
            position = cible
        courbe[str(date.date())] = round(valeur, 2)
    return courbe, nb_trades


def buy_hold(prix, col):
    p = prix[col].dropna()
    p = p.loc[p.index[LOOKBACK]:]
    base = p.iloc[0]
    return {str(d.date()): round(CAP * v / base, 2) for d, v in p.items()}


def metriques(courbe):
    vals = np.array(list(courbe.values()))
    dts = list(courbe.keys())
    n = (pd.to_datetime(dts[-1]) - pd.to_datetime(dts[0])).days / 365.25
    cagr = (vals[-1] / vals[0]) ** (1 / n) - 1
    pic = np.maximum.accumulate(vals)
    max_dd = ((vals - pic) / pic).min()
    r = np.diff(vals) / vals[:-1]
    vol = r.std() * np.sqrt(12)
    sharpe = (cagr - 0.02) / vol if vol > 0 else 0
    return {"final": round(float(vals[-1])), "cagr": round(float(cagr)*100, 2),
            "dd": round(float(max_dd)*100, 1), "vol": round(float(vol)*100, 1),
            "sharpe": round(float(sharpe), 2), "ans": round(n, 1)}


if __name__ == "__main__":
    prix = charger()
    print(f"Données : {prix.index[0].date()} → {prix.index[-1].date()} ({len(prix)} mois)\n")

    configs = {
        "A LIVE (World/USA, cash)":      (["WORLD", "SPY"],          "CASH"),
        "B + refuge oblig (World/USA)":  (["WORLD", "SPY"],          "IEF"),
        "C + univers élargi (cash)":     (["SPY", "EFA", "EEM"],     "CASH"),
        "D complet (élargi + oblig)":    (["SPY", "EFA", "EEM"],     "IEF"),
    }
    res = {}
    for nom, (rot, ref) in configs.items():
        c, nt = moteur(prix, rot, ref)
        res[nom] = (metriques(c), nt)

    # GEM pur (100% rotatif, la version Antonacci) et références buy & hold
    c_gem, nt_gem = moteur(prix, ["SPY", "EFA", "EEM"], "IEF", socle_w=0.0)
    res["GEM pur (Antonacci)"] = (metriques(c_gem), nt_gem)
    res["World buy & hold"] = (metriques(buy_hold(prix, "WORLD")), 0)
    res["S&P 500 buy & hold"] = (metriques(buy_hold(prix, "SPY")), 0)

    print("="*92)
    print(f"{'':32}{'Valeur':>10}{'CAGR':>9}{'PireChute':>11}{'Vol':>8}{'Sharpe':>8}{'Trades/an':>11}")
    print("-"*92)
    for nom, (m, nt) in res.items():
        tpy = f"{nt/m['ans']:.1f}" if nt else "-"
        print(f"{nom:32}{m['final']:>10}{m['cagr']:>8.2f}%{m['dd']:>10.1f}%"
              f"{m['vol']:>7.1f}%{m['sharpe']:>8.2f}{tpy:>11}")
    print("="*92)

    a = res["A LIVE (World/USA, cash)"][0]
    d = res["D complet (élargi + oblig)"][0]
    print(f"\nCoût du bridage PEA (A → D) sur {a['ans']} ans :")
    print(f"  Rendement annuel : {a['cagr']:+.2f}%  →  {d['cagr']:+.2f}%   "
          f"(écart {d['cagr']-a['cagr']:+.2f} pts/an)")
    print(f"  Capital final    : {a['final']:>7}€  →  {d['final']:>7}€   "
          f"(x{d['final']/a['final']:.2f})")
    print(f"  Pire chute       : {a['dd']:+.1f}%  →  {d['dd']:+.1f}%")
