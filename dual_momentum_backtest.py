#!/usr/bin/env python3
"""
Backtest Dual Momentum (style GEM - Global Equities Momentum, Gary Antonacci).

Principe simple :
  - Chaque mois, on classe les actifs risqués par leur performance sur 12 mois.
  - On garde le gagnant SEULEMENT si sa perf 12 mois est positive (momentum absolu).
  - Sinon, on se met à l'abri sur les obligations (ou cash).
  - Rééquilibrage mensuel uniquement. Peu de trades.

On compare cette stratégie à un simple "acheter et ne rien faire" (buy & hold).
Données dividendes incluses (auto_adjust). Test sur ~20 ans avec 2008, 2020, 2022.
"""

import warnings
warnings.filterwarnings("ignore")

import json
import numpy as np
import pandas as pd
import yfinance as yf

# ─── PARAMÈTRES ───────────────────────────────────────────────────────────────

# Actifs risqués (proxies longue histoire, dividendes inclus).
# En live sur PEA : on remplace par les ETF équivalents éligibles PEA.
RISK_ASSETS = {
    "USA (S&P 500)":        "SPY",   # depuis 1993
    "Développés ex-US":     "EFA",   # depuis 2001
    "Émergents":            "EEM",   # depuis 2003
}
# Actif refuge quand tout baisse
SAFE_ASSET = {"Obligations US (7-10a)": "IEF"}  # depuis 2002

LOOKBACK_MOIS = 12          # fenêtre de momentum
BENCHMARK     = "SPY"       # référence buy & hold
CAPITAL_DEPART = 10000.0
FRAIS_PAR_TRADE = 0.001     # 0,1% par changement de position (réaliste ETF)
BUFFER_SWITCH = 0.03        # ne change que si le nouveau bat l'actuel de +3% (anti-whipsaw)

# Proxy "World" (type ACWI) : pondération marché approximative, rééquilibrée
POIDS_WORLD = {"SPY": 0.60, "EFA": 0.30, "EEM": 0.10}

# ─── TÉLÉCHARGEMENT ───────────────────────────────────────────────────────────

def telecharger(tickers):
    print(f"Téléchargement {tickers}...")
    data = yf.download(tickers, start="2003-01-01", auto_adjust=True,
                       progress=False)["Close"]
    if isinstance(data, pd.Series):
        data = data.to_frame()
    # Cours de fin de mois
    mensuel = data.resample("ME").last().dropna(how="all")
    return mensuel

# ─── BACKTEST DUAL MOMENTUM ───────────────────────────────────────────────────

def backtest_dual_momentum(prix, buffer=0.0):
    risk_cols = list(RISK_ASSETS.values())
    safe_col  = list(SAFE_ASSET.values())[0]
    tous = risk_cols + [safe_col]
    prix = prix[tous].dropna()

    rendements_mens = prix.pct_change()
    momentum = prix.pct_change(LOOKBACK_MOIS)   # perf glissante 12 mois

    valeur = CAPITAL_DEPART
    courbe = {}
    position_actuelle = None
    nb_trades = 0
    journal = []

    dates = prix.index[LOOKBACK_MOIS:]
    for i, date in enumerate(dates):
        # Décision basée sur le momentum à la date précédente (pas de look-ahead)
        date_prec = dates[i-1] if i > 0 else date
        mom = momentum.loc[date_prec, risk_cols]

        # Momentum relatif : meilleur actif risqué
        meilleur = mom.idxmax()
        mom_meilleur = mom[meilleur]

        # Momentum absolu : positif ? sinon refuge
        if mom_meilleur <= 0:
            cible = safe_col
        elif (buffer > 0 and position_actuelle in risk_cols
              and mom[position_actuelle] > 0
              and mom_meilleur < mom[position_actuelle] + buffer):
            # Anti-whipsaw : on garde la position si le challenger ne la bat pas assez
            cible = position_actuelle
        else:
            cible = meilleur

        # Applique le rendement du mois courant à la position détenue
        if position_actuelle is not None:
            r = rendements_mens.loc[date, position_actuelle]
            if not np.isnan(r):
                valeur *= (1 + r)

        # Changement de position = frais
        if cible != position_actuelle:
            valeur *= (1 - FRAIS_PAR_TRADE)
            nb_trades += 1
            position_actuelle = cible
            journal.append((str(date.date()), cible, round(float(mom_meilleur)*100, 1)))

        courbe[str(date.date())] = round(valeur, 2)

    return courbe, nb_trades, journal

# ─── BUY & HOLD ───────────────────────────────────────────────────────────────

def backtest_buy_hold(prix, ticker):
    p = prix[ticker].dropna()
    p = p.loc[p.index[LOOKBACK_MOIS]:]   # même point de départ
    base = p.iloc[0]
    courbe = {str(d.date()): round(CAPITAL_DEPART * v / base, 2) for d, v in p.items()}
    return courbe


def backtest_world(prix):
    """Proxy World (ACWI) : panier pondéré rééquilibré mensuellement, dividendes inclus."""
    cols = list(POIDS_WORLD.keys())
    p = prix[cols].dropna()
    p = p.loc[p.index[LOOKBACK_MOIS]:]
    rends = p.pct_change().fillna(0)
    poids = np.array([POIDS_WORLD[c] for c in cols])
    valeur = CAPITAL_DEPART
    courbe = {}
    for date, row in rends.iterrows():
        r_panier = float(np.dot(poids, row[cols].values))
        valeur *= (1 + r_panier)
        courbe[str(date.date())] = round(valeur, 2)
    return courbe

# ─── MÉTRIQUES ────────────────────────────────────────────────────────────────

def metriques(courbe):
    vals = np.array(list(courbe.values()))
    dates = list(courbe.keys())
    n_annees = (pd.to_datetime(dates[-1]) - pd.to_datetime(dates[0])).days / 365.25
    cagr = (vals[-1] / vals[0]) ** (1/n_annees) - 1

    # Max drawdown
    pic = np.maximum.accumulate(vals)
    dd = (vals - pic) / pic
    max_dd = dd.min()

    # Volatilité annualisée (sur rendements mensuels)
    rends = np.diff(vals) / vals[:-1]
    vol = rends.std() * np.sqrt(12)
    sharpe = (cagr - 0.02) / vol if vol > 0 else 0   # taux sans risque ~2%

    return {
        "valeur_finale": round(float(vals[-1]), 0),
        "cagr_pct":      round(float(cagr)*100, 2),
        "max_drawdown_pct": round(float(max_dd)*100, 1),
        "volatilite_pct": round(float(vol)*100, 1),
        "sharpe":        round(float(sharpe), 2),
        "n_annees":      round(n_annees, 1),
    }

# ─── MAIN ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tous_tickers = list(RISK_ASSETS.values()) + list(SAFE_ASSET.values())
    prix = telecharger(tous_tickers)
    print(f"Données : {prix.index[0].date()} → {prix.index[-1].date()} ({len(prix)} mois)\n")

    print("Backtest Dual Momentum (base)...")
    courbe_dm, nb_trades, journal = backtest_dual_momentum(prix, buffer=0.0)

    print("Backtest Dual Momentum (anti-whipsaw)...")
    courbe_dmb, nb_trades_b, journal_b = backtest_dual_momentum(prix, buffer=BUFFER_SWITCH)

    print("Backtest Buy & Hold World...")
    courbe_world = backtest_world(prix)

    print("Backtest Buy & Hold (S&P 500)...")
    courbe_bh = backtest_buy_hold(prix, BENCHMARK)

    m_dm    = metriques(courbe_dm)
    m_dmb   = metriques(courbe_dmb)
    m_world = metriques(courbe_world)
    m_bh    = metriques(courbe_bh)

    def ligne(label, champ, unite, fmt="{:>13.2f}"):
        vals = [m_dmb[champ], m_dm[champ], m_world[champ], m_bh[champ]]
        cells = " ".join(fmt.format(v) + unite for v in vals)
        print(f"{label:26} {cells}")

    print("\n" + "="*84)
    print(f"{'RÉSULTAT sur ' + str(m_dm['n_annees']) + ' ans':^84}")
    print("="*84)
    print(f"{'':26} {'DM anti-whip':>14} {'DM base':>14} {'World B&H':>14} {'S&P B&H':>14}")
    print("-"*84)
    ligne("Valeur finale (10k)",   "valeur_finale",    " ", "{:>13.0f}")
    ligne("Rendement annuel",      "cagr_pct",         "%")
    ligne("Pire chute (drawdown)", "max_drawdown_pct", "%", "{:>13.1f}")
    ligne("Volatilité",            "volatilite_pct",   "%", "{:>13.1f}")
    ligne("Sharpe",                "sharpe",           " ")
    print("-"*84)
    print(f"Trades : DM anti-whip {nb_trades_b} ({nb_trades_b/m_dm['n_annees']:.1f}/an)"
          f"  |  DM base {nb_trades} ({nb_trades/m_dm['n_annees']:.1f}/an)")
    print("="*84)

    print("\nDerniers changements de position (anti-whipsaw) :")
    for date, actif, mom in journal_b[-8:]:
        nom = {v: k for k, v in {**RISK_ASSETS, **SAFE_ASSET}.items()}.get(actif, actif)
        print(f"  {date} → {nom} (momentum {mom:+.1f}%)")

    resultats = {
        "periode": f"{prix.index[0].date()} → {prix.index[-1].date()}",
        "dual_momentum_antiwhip": m_dmb,
        "dual_momentum_base": m_dm,
        "buy_hold_world": m_world,
        "buy_hold_sp500": m_bh,
        "nb_trades_antiwhip": nb_trades_b,
        "nb_trades_base": nb_trades,
        "courbe_dm": courbe_dmb,
        "courbe_world": courbe_world,
        "courbe_bh": courbe_bh,
    }
    with open("backtest_resultats.json", "w", encoding="utf-8") as f:
        json.dump(resultats, f, ensure_ascii=False, indent=2)
    print("\nRésultats détaillés sauvegardés dans backtest_resultats.json")
