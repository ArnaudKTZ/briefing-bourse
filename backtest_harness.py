#!/usr/bin/env python3
"""
Harnais de mesure rigoureux — le "sol dur" du projet.

Objectif : prouver (ou réfuter) qu'une stratégie marche sur des données que
ses réglages n'ont JAMAIS vues. C'est la seule chose que quasi aucune étude
d'IA-trading ne fait correctement, et c'est ce qui sépare un vrai edge d'une
illusion de backtest.

Méthode : walk-forward.
  1. On découpe l'histoire en fenêtres successives.
  2. Sur chaque fenêtre d'apprentissage (train), on choisit les meilleurs
     réglages (lookback, buffer) — le modèle "apprend".
  3. On applique ces réglages à la fenêtre SUIVANTE (test), jamais vue.
  4. On recolle tous les bouts de test = la performance honnête hors-échantillon.

Frais inclus. Refuge = cash (réalité PEA). Aucun look-ahead.
Réutilisable plus tard par l'Agent Professeur pour noter les agents.
"""

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import yfinance as yf

# ─── PARAMÈTRES ───────────────────────────────────────────────────────────────

POIDS_WORLD     = {"SPY": 0.60, "EFA": 0.30, "EEM": 0.10}  # proxy World (type ACWI)
TICKER_USA      = "SPY"
FRAIS_PAR_TRADE = 0.001        # 0,1% par changement de poche rotative
PART_SOCLE      = 0.50         # 50% toujours World (buy & hold)
TAUX_CASH_MENS  = 0.0          # refuge cash PEA ~0% (hypothèse conservatrice)

GRILLE_LOOKBACK = [6, 9, 12]
GRILLE_BUFFER   = [0.0, 0.02, 0.03, 0.05]

TRAIN_MOIS = 60   # 5 ans d'apprentissage
TEST_MOIS  = 12   # 1 an de test hors-échantillon
PAS_MOIS   = 12

# ─── DONNÉES ──────────────────────────────────────────────────────────────────

def charger_donnees():
    tickers = list(set(list(POIDS_WORLD) + [TICKER_USA]))
    data = yf.download(tickers, start="2003-01-01", auto_adjust=True, progress=False)["Close"]
    mensuel = data.resample("ME").last().dropna()

    # Rendements mensuels
    rends = mensuel.pct_change()
    # Rendement World = panier pondéré rééquilibré
    world_ret = sum(POIDS_WORLD[t] * rends[t] for t in POIDS_WORLD)
    usa_ret   = rends[TICKER_USA]

    # Indices de prix reconstruits (base 100) pour calculer le momentum
    world_px = (1 + world_ret.fillna(0)).cumprod() * 100
    usa_px   = (1 + usa_ret.fillna(0)).cumprod() * 100

    df = pd.DataFrame({
        "world_ret": world_ret, "usa_ret": usa_ret,
        "world_px": world_px,   "usa_px": usa_px,
    }).dropna()
    return df

# ─── STRATÉGIE HYBRIDE ────────────────────────────────────────────────────────

def momentum(px, i, lookback):
    if i - lookback < 0:
        return None
    return px.iloc[i] / px.iloc[i - lookback] - 1


def rendements_hybride(df, lookback, buffer, i_debut, i_fin, position_init=None):
    """
    Rendements mensuels de la stratégie hybride sur [i_debut, i_fin].
    Décision prise sur le momentum du mois PRÉCÉDENT (aucun look-ahead).
    Retourne (liste_rendements, position_finale, nb_trades).
    """
    rends = []
    position = position_init   # "World" / "USA" / "Cash" / None
    trades = 0

    for i in range(i_debut, i_fin):
        # Décision basée sur les données disponibles à i-1
        mom_w = momentum(df["world_px"], i - 1, lookback)
        mom_u = momentum(df["usa_px"],   i - 1, lookback)
        if mom_w is None or mom_u is None:
            cible = "Cash"
        else:
            meilleur, mom_best = ("USA", mom_u) if mom_u >= mom_w else ("World", mom_w)
            if mom_best <= 0:
                cible = "Cash"
            elif position in ("World", "USA"):
                mom_pos = mom_u if position == "USA" else mom_w
                cible = position if (mom_pos > 0 and mom_best < mom_pos + buffer) else meilleur
            else:
                cible = meilleur

        # Rendement de la poche rotative ce mois
        if cible == "USA":
            r_rot = df["usa_ret"].iloc[i]
        elif cible == "World":
            r_rot = df["world_ret"].iloc[i]
        else:
            r_rot = TAUX_CASH_MENS

        cout = 0.0
        if cible != position:
            cout = FRAIS_PAR_TRADE
            trades += 1
            position = cible

        # Socle 50% World (buy & hold) + 50% rotative, frais sur la part rotative
        r_total = PART_SOCLE * df["world_ret"].iloc[i] + (1 - PART_SOCLE) * (r_rot - cout)
        rends.append(r_total)

    return rends, position, trades

# ─── MÉTRIQUES ────────────────────────────────────────────────────────────────

def metriques(rends):
    r = np.array(rends)
    if len(r) == 0:
        return {}
    courbe = np.cumprod(1 + r)
    n_annees = len(r) / 12
    cagr = courbe[-1] ** (1 / n_annees) - 1
    pic = np.maximum.accumulate(courbe)
    max_dd = ((courbe - pic) / pic).min()
    vol = r.std() * np.sqrt(12)
    sharpe = (cagr - 0.02) / vol if vol > 0 else 0
    return {"cagr": cagr, "max_dd": max_dd, "vol": vol, "sharpe": sharpe,
            "mult": courbe[-1], "n_mois": len(r)}


def sharpe_train(df, lookback, buffer, i_debut, i_fin):
    rends, _, _ = rendements_hybride(df, lookback, buffer, i_debut, i_fin)
    m = metriques(rends)
    return m.get("sharpe", -99)

# ─── WALK-FORWARD ─────────────────────────────────────────────────────────────

def walk_forward(df):
    n = len(df)
    i = max(GRILLE_LOOKBACK) + TRAIN_MOIS
    oos_rends = []
    oos_dates = []
    folds = []
    position = None

    while i + TEST_MOIS <= n:
        i_train_debut = i - TRAIN_MOIS
        # 1. Choix des meilleurs réglages sur la fenêtre d'apprentissage
        meilleur = None
        for lb in GRILLE_LOOKBACK:
            for bf in GRILLE_BUFFER:
                s = sharpe_train(df, lb, bf, i_train_debut, i)
                if meilleur is None or s > meilleur[0]:
                    meilleur = (s, lb, bf)
        _, lb, bf = meilleur

        # 2. Application aux 12 mois SUIVANTS (jamais vus)
        rends, position, trades = rendements_hybride(df, lb, bf, i, i + TEST_MOIS, position)
        oos_rends.extend(rends)
        oos_dates.extend(df.index[i:i + TEST_MOIS])
        folds.append({
            "test": f"{df.index[i].date()} → {df.index[i+TEST_MOIS-1].date()}",
            "lookback": lb, "buffer": bf,
            "perf_test": round((np.prod([1+r for r in rends]) - 1) * 100, 1),
        })
        i += PAS_MOIS

    return oos_rends, oos_dates, folds


def buy_hold_world(df, dates):
    sous = df.loc[dates[0]:dates[-1]]
    return list(sous["world_ret"].iloc[1:])

# ─── MAIN ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Chargement des données...")
    df = charger_donnees()
    print(f"Période disponible : {df.index[0].date()} → {df.index[-1].date()} ({len(df)} mois)\n")

    print("Walk-forward (réglages choisis sur le passé, testés sur l'avenir jamais vu)...")
    oos_rends, oos_dates, folds = walk_forward(df)

    print("\nFenêtres de test hors-échantillon :")
    print(f"{'Période test':>26} {'Lookback':>9} {'Buffer':>7} {'Perf test':>10}")
    print("-" * 58)
    for f in folds:
        print(f"{f['test']:>26} {f['lookback']:>8}m {int(f['buffer']*100):>6}% {f['perf_test']:>9}%")

    m_oos = metriques(oos_rends)
    bh = buy_hold_world(df, oos_dates)
    m_bh = metriques(bh)

    print("\n" + "=" * 58)
    print(f"{'RÉSULTAT HORS-ÉCHANTILLON (honnête)':^58}")
    print("=" * 58)
    print(f"{'':30} {'Stratégie':>12} {'World B&H':>12}")
    print("-" * 58)
    print(f"{'Rendement annuel (CAGR)':30} {m_oos['cagr']*100:>11.2f}% {m_bh['cagr']*100:>11.2f}%")
    print(f"{'Pire chute (max drawdown)':30} {m_oos['max_dd']*100:>11.1f}% {m_bh['max_dd']*100:>11.1f}%")
    print(f"{'Volatilité':30} {m_oos['vol']*100:>11.1f}% {m_bh['vol']*100:>11.1f}%")
    print(f"{'Sharpe (rendement/risque)':30} {m_oos['sharpe']:>12.2f} {m_bh['sharpe']:>12.2f}")
    print("-" * 58)
    print(f"Test réalisé sur {m_oos['n_mois']} mois jamais vus par les réglages.")
    print("=" * 58)
    print("\nLecture : si la stratégie bat le World en HORS-ÉCHANTILLON, l'edge")
    print("est réel (pas du sur-ajustement). Sinon, on simplifie. C'est ça,")
    print("la rigueur que 0 étude sur 77 ne respecte.")
