#!/usr/bin/env python3
"""
Audit du cœur Dual Momentum selon la méthode backtest-expert (17/11/2026).

Objectif : "punir" la stratégie réellement en prod (agent_dual_momentum.py)
et voir ce qui survit, AVANT tout euro réel (suivi forward prévu le 08/12).

Config live reproduite : rotation World vs USA, momentum 12 mois, anti-whipsaw
+3 %, socle 0 %, refuge monétaire si le meilleur momentum <= 0.

Écarts testés un par un, par rapport à la recette du 08/09 (piste1/piste2) :
  1. Décalage d'un mois : dans les recettes, la position détenue au mois M est
     décidée avec le momentum de fin M-2. Le live décide le 1er du mois avec le
     momentum de fin M-1. On teste les deux.
  2. Refuge monétaire : la recette suppose 2 %/an constant. Or les taux courts
     euro ont été nuls ou négatifs de 2012 à 2022. On teste avec un taux
     historique approximatif (moyennes annuelles EONIA/€STR, de mémoire,
     précision ~0,1 pt, suffisant pour l'ordre de grandeur).
  3. Devise : la recette calcule tout en dollars. Le PEA est en euros
     (CW8, ESE). On convertit avec EURUSD.
  4. Frais : la recette prend 0,1 % par bascule. On punit à 1 % par bascule
     (vente + achat à 0,5 %, plafond légal PEA, comme le reste du projet).
Puis plateaux de paramètres (lookback, buffer), année par année, sous-périodes.

World = 70 % SPY + 30 % EFA (MSCI World = pays développés, sans émergents).
"""

import warnings
warnings.filterwarnings("ignore")

import json
import numpy as np
import pandas as pd
import yfinance as yf

# Taux court euro moyen annuel approximatif (EONIA puis €STR), en %
TAUX_EUR = {2003: 2.3, 2004: 2.05, 2005: 2.1, 2006: 2.8, 2007: 3.85, 2008: 3.85,
            2009: 0.7, 2010: 0.45, 2011: 0.85, 2012: 0.25, 2013: 0.1, 2014: 0.1,
            2015: -0.1, 2016: -0.3, 2017: -0.35, 2018: -0.36, 2019: -0.39,
            2020: -0.47, 2021: -0.49, 2022: 0.0, 2023: 3.3, 2024: 3.65,
            2025: 2.2, 2026: 1.9}
FRAIS_FONDS_MONETAIRE = 0.10  # % / an


def charger():
    px = yf.download(["SPY", "EFA", "EURUSD=X"], start="2003-01-01",
                     auto_adjust=True, progress=False)["Close"]
    m = px.resample("ME").last()
    r = m[["SPY", "EFA"]].pct_change()
    df = pd.DataFrame(index=m.index)
    df["usa_usd"] = r["SPY"]
    df["world_usd"] = 0.70 * r["SPY"] + 0.30 * r["EFA"]
    fx = m["EURUSD=X"]                    # dollars pour 1 euro
    fx_r = fx.pct_change()
    # Rendement en euros d'un actif en dollars : (1+r) / (1+variation EURUSD) - 1
    df["usa_eur"] = (1 + df["usa_usd"]) / (1 + fx_r) - 1
    df["world_eur"] = (1 + df["world_usd"]) / (1 + fx_r) - 1
    df["cash_2pct"] = 0.02 / 12
    df["cash_hist"] = [(TAUX_EUR.get(d.year, 2.0) - FRAIS_FONDS_MONETAIRE) / 100 / 12
                       for d in df.index]
    return df.dropna()


def strategie(df, devise="usd", refuge="cash_2pct", lag=1, lookback=12,
              buffer=0.03, frais=0.001):
    """lag=1 : reproduit la recette (position du mois M décidée sur fin M-2).
    lag=0 : comme le live (décision sur fin M-1 pour le mois M)."""
    rw, ru = df[f"world_{devise}"], df[f"usa_{devise}"]
    px = pd.DataFrame({"World": (1 + rw).cumprod(), "USA": (1 + ru).cumprod()})
    mom = px / px.shift(lookback) - 1
    rends, pos, trades = [], None, 0
    debut = lookback + 1 + lag
    for i in range(debut, len(df)):
        m = mom.iloc[i - 1 - lag]
        best = m.idxmax()
        if m[best] <= 0:
            cible = "Cash"
        elif pos in ("World", "USA") and m[pos] > 0 and m[best] < m[pos] + buffer:
            cible = pos
        else:
            cible = best
        cout = 0.0
        if cible != pos:
            cout = frais if pos is not None else 0.0
            trades += pos is not None
            pos = cible
        r = {"World": rw.iloc[i], "USA": ru.iloc[i], "Cash": df[refuge].iloc[i]}[pos]
        rends.append((1 + r) * (1 - cout) - 1)
    return pd.Series(rends, index=df.index[debut:]), trades


def metriques(r):
    c = (1 + r).cumprod()
    ans = len(r) / 12
    cagr = c.iloc[-1] ** (1 / ans) - 1
    dd = (c / c.cummax() - 1).min()
    vol = r.std() * np.sqrt(12)
    return {"cagr": round(cagr * 100, 2), "dd": round(dd * 100, 1),
            "vol": round(vol * 100, 1),
            "sharpe": round((cagr - 0.015) / vol, 2) if vol else 0,
            "ans": round(ans, 1)}


def ligne(nom, r, trades=None):
    m = metriques(r)
    t = f"{trades / m['ans']:.1f}" if trades is not None else "-"
    print(f"{nom:46}{m['cagr']:>7.2f}%{m['dd']:>9.1f}%{m['sharpe']:>8.2f}{t:>9}")
    return m


if __name__ == "__main__":
    df = charger()
    print(f"Données {df.index[0].date()} -> {df.index[-1].date()} ({len(df)} mois)\n")
    res = {}

    print("=" * 79)
    print("1. DE LA RECETTE AU RÉEL, UN ÉCART À LA FOIS")
    print(f"{'':46}{'CAGR':>8}{'PireChute':>9}{'Sharpe':>8}{'Bascul/an':>9}")
    print("-" * 79)
    etapes = [
        ("a. Recette 08/09 (USD, lag 1, cash 2%, 0,1%)", dict()),
        ("b. + décision comme le live (lag 0)", dict(lag=0)),
        ("c. + taux monétaire historique", dict(lag=0, refuge="cash_hist")),
        ("d. + calcul en euros", dict(lag=0, refuge="cash_hist", devise="eur")),
        ("e. + frais punitifs 1% / bascule", dict(lag=0, refuge="cash_hist", devise="eur", frais=0.01)),
    ]
    series = {}
    for nom, kw in etapes:
        r, t = strategie(df, **kw)
        series[nom] = r
        res[nom] = ligne(nom, r, t)
    ref_idx = series[etapes[-1][0]].index
    print("-" * 79)
    w_eur = df["world_eur"].loc[ref_idx]
    w_usd = df["world_usd"].loc[ref_idx]
    res["World B&H EUR"] = ligne("World buy & hold (EUR, même période)", w_eur)
    res["World B&H USD"] = ligne("World buy & hold (USD, même période)", w_usd)

    REEL = dict(lag=0, refuge="cash_hist", devise="eur", frais=0.01)

    print("\n" + "=" * 79)
    print("2. PLATEAU OU PIC ? (config réelle e, on fait varier un paramètre)")
    print("-" * 79)
    plateau = {}
    for lb in [6, 9, 10, 11, 12, 15]:
        r, t = strategie(df, **{**REEL, "lookback": lb})
        r = r.loc[r.index >= ref_idx[0]] if lb <= 12 else r
        plateau[f"lookback {lb}"] = ligne(f"lookback {lb} mois", r, t)
    print("-" * 79)
    for b in [0.0, 0.01, 0.02, 0.03, 0.05, 0.07, 0.10]:
        r, t = strategie(df, **{**REEL, "buffer": b})
        plateau[f"buffer {b}"] = ligne(f"buffer {int(b*100)} %", r, t)
    res["plateau"] = plateau

    print("\n" + "=" * 79)
    print("3. ANNÉE PAR ANNÉE (config réelle e vs World B&H, en euros)")
    print("-" * 79)
    r_e = series[etapes[-1][0]]
    an = pd.DataFrame({"DM": (1 + r_e).groupby(r_e.index.year).prod() - 1,
                       "World": (1 + w_eur).groupby(w_eur.index.year).prod() - 1})
    an["ecart"] = an["DM"] - an["World"]
    for y, row in an.iterrows():
        print(f"  {y}  DM {row.DM*100:+6.1f}%   World {row.World*100:+6.1f}%   écart {row.ecart*100:+6.1f} pts")
    gagnees = int((an["ecart"] > 0).sum())
    print(f"  Années où le DM bat le World : {gagnees}/{len(an)}")
    res["annees_gagnees"] = f"{gagnees}/{len(an)}"
    res["par_annee"] = {int(y): {k: round(v * 100, 1) for k, v in row.items()} for y, row in an.iterrows()}

    print("\n" + "=" * 79)
    print("4. SOUS-PÉRIODES (config réelle e vs World B&H)")
    print("-" * 79)
    periodes = {"2005-2012 (krach 2008)": ("2005", "2012"),
                "2013-2019 (taux négatifs)": ("2013", "2019"),
                "2020-2026 (COVID, 2022)": ("2020", "2026")}
    sp = {}
    for nom, (a, b) in periodes.items():
        dm = metriques(r_e.loc[a:b]); wb = metriques(w_eur.loc[a:b])
        sp[nom] = {"dm": dm, "world": wb}
        print(f"  {nom:28} DM {dm['cagr']:+6.2f}%/an, chute {dm['dd']:6.1f}%  |  "
              f"World {wb['cagr']:+6.2f}%/an, chute {wb['dd']:6.1f}%")
    res["sous_periodes"] = sp

    with open("audit_dm_backtest_expert_resultats.json", "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2, default=str)
    print("\nRésultats : audit_dm_backtest_expert_resultats.json")
