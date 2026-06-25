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
TICKER_EMERGENT = "EEM"        # proxy émergents (longue histoire, depuis 2003)
FRAIS_PAR_TRADE = 0.001        # 0,1% par changement de poche rotative
PART_SOCLE      = 0.50         # 50% toujours World (buy & hold)
TAUX_CASH_MENS  = 0.0          # refuge cash PEA ~0% (hypothèse conservatrice)

# Colonnes (prix, rendement) par actif de rotation possible
ASSET_COLS = {
    "World":     ("world_px", "world_ret"),
    "USA":       ("usa_px",   "usa_ret"),
    "Emergents": ("em_px",    "em_ret"),
}

GRILLE_LOOKBACK = [6, 9, 12]
GRILLE_BUFFER   = [0.0, 0.02, 0.03, 0.05]

TRAIN_MOIS = 60   # 5 ans d'apprentissage
TEST_MOIS  = 12   # 1 an de test hors-échantillon
PAS_MOIS   = 12

# ─── DONNÉES ──────────────────────────────────────────────────────────────────

def charger_donnees():
    tickers = list(set(list(POIDS_WORLD) + [TICKER_USA, TICKER_EMERGENT]))
    data = yf.download(tickers, start="2003-01-01", auto_adjust=True, progress=False)["Close"]
    mensuel = data.resample("ME").last().dropna()

    # Rendements mensuels
    rends = mensuel.pct_change()
    # Rendement World = panier pondéré rééquilibré
    world_ret = sum(POIDS_WORLD[t] * rends[t] for t in POIDS_WORLD)
    usa_ret   = rends[TICKER_USA]
    em_ret    = rends[TICKER_EMERGENT]

    # Indices de prix reconstruits (base 100) pour calculer le momentum
    world_px = (1 + world_ret.fillna(0)).cumprod() * 100
    usa_px   = (1 + usa_ret.fillna(0)).cumprod() * 100
    em_px    = (1 + em_ret.fillna(0)).cumprod() * 100

    df = pd.DataFrame({
        "world_ret": world_ret, "usa_ret": usa_ret, "em_ret": em_ret,
        "world_px": world_px,   "usa_px": usa_px,   "em_px": em_px,
    }).dropna()
    return df

# ─── STRATÉGIE HYBRIDE ────────────────────────────────────────────────────────

def momentum(px, i, lookback):
    if i - lookback < 0:
        return None
    return px.iloc[i] / px.iloc[i - lookback] - 1


def rendements_hybride(df, lookback, buffer, i_debut, i_fin, rotation, position_init=None):
    """
    Rendements mensuels de la stratégie hybride sur [i_debut, i_fin].
    rotation = liste d'actifs candidats pour la poche rotative (ex: ["World","USA"]).
    Décision prise sur le momentum du mois PRÉCÉDENT (aucun look-ahead).
    Retourne (liste_rendements, position_finale, nb_trades).
    """
    rends = []
    position = position_init   # un des actifs de rotation / "Cash" / None
    trades = 0

    for i in range(i_debut, i_fin):
        # Momentum de chaque candidat à i-1
        moms = {}
        for actif in rotation:
            px_col = ASSET_COLS[actif][0]
            m = momentum(df[px_col], i - 1, lookback)
            if m is not None:
                moms[actif] = m

        if not moms:
            cible = "Cash"
        else:
            meilleur = max(moms, key=moms.get)
            mom_best = moms[meilleur]
            if mom_best <= 0:
                cible = "Cash"                      # momentum absolu : tout négatif -> refuge
            elif position in moms and moms[position] > 0 and mom_best < moms[position] + buffer:
                cible = position                    # anti-whipsaw
            else:
                cible = meilleur

        # Rendement de la poche rotative ce mois
        r_rot = TAUX_CASH_MENS if cible == "Cash" else df[ASSET_COLS[cible][1]].iloc[i]

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


def sharpe_train(df, lookback, buffer, i_debut, i_fin, rotation):
    rends, _, _ = rendements_hybride(df, lookback, buffer, i_debut, i_fin, rotation)
    m = metriques(rends)
    return m.get("sharpe", -99)

# ─── WALK-FORWARD ─────────────────────────────────────────────────────────────

def walk_forward(df, rotation):
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
                s = sharpe_train(df, lb, bf, i_train_debut, i, rotation)
                if meilleur is None or s > meilleur[0]:
                    meilleur = (s, lb, bf)
        _, lb, bf = meilleur

        # 2. Application aux 12 mois SUIVANTS (jamais vus)
        rends, position, trades = rendements_hybride(df, lb, bf, i, i + TEST_MOIS, rotation, position)
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
    # Mêmes mois que la stratégie OOS (ne pas sauter le 1er mois : comparaison juste)
    sous = df.loc[dates[0]:dates[-1]]
    return list(sous["world_ret"])

# ─── MAIN ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Chargement des données...")
    df = charger_donnees()
    print(f"Période disponible : {df.index[0].date()} → {df.index[-1].date()} ({len(df)} mois)\n")

    configs = {
        "Sans émergents (World+USA)":      ["World", "USA"],
        "Avec émergents (World+USA+Émerg)": ["World", "USA", "Emergents"],
    }

    resultats = {}
    dates_ref = None
    for nom, rotation in configs.items():
        print(f"Walk-forward — {nom}...")
        oos_rends, oos_dates, folds = walk_forward(df, rotation)
        resultats[nom] = metriques(oos_rends)
        dates_ref = oos_dates

    m_bh = metriques(buy_hold_world(df, dates_ref))

    noms = list(configs.keys())
    print("\n" + "=" * 76)
    print(f"{'RECETTE — RÉSULTAT HORS-ÉCHANTILLON (honnête)':^76}")
    print("=" * 76)
    print(f"{'':26} {noms[0]:>22} {noms[1]:>22}".replace(" (World+USA)", "").replace(" (World+USA+Émerg)", ""))
    print(f"{'':26} {'World+USA':>22} {'+ Émergents':>22}")
    print("-" * 76)
    a, b = resultats[noms[0]], resultats[noms[1]]
    print(f"{'Rendement annuel':26} {a['cagr']*100:>21.2f}% {b['cagr']*100:>21.2f}%")
    print(f"{'Pire chute (drawdown)':26} {a['max_dd']*100:>21.1f}% {b['max_dd']*100:>21.1f}%")
    print(f"{'Volatilité':26} {a['vol']*100:>21.1f}% {b['vol']*100:>21.1f}%")
    print(f"{'Sharpe':26} {a['sharpe']:>22.2f} {b['sharpe']:>22.2f}")
    print("-" * 76)
    print(f"Référence : World buy & hold = {m_bh['cagr']*100:.2f}%/an, "
          f"chute {m_bh['max_dd']*100:.1f}%, Sharpe {m_bh['sharpe']:.2f}")
    print(f"Test sur {a['n_mois']} mois jamais vus par les réglages.")
    print("=" * 76)
    print("\nVERDICT : on adopte les émergents SEULEMENT si la colonne de droite")
    print("améliore le Sharpe sans dégrader le drawdown. Sinon on reste simple.")
