#!/usr/bin/env python3
"""
Backtest S&P 500 Equal Weight — passage par la recette AVANT toute décision.

Origine (16/07/2026) : Charles Gave recommande de ne pas tout mettre sur le
MSCI World (70% US, top 10 = ~25% de l'indice) et d'y adjoindre du S&P 500
équipondéré (Equal Weight). L'argument structurel est recevable (concentration
mega-tech) ; comme pour les émergents et le SOL, il passe par le harnais.

Proxy EW : RSP (Invesco S&P 500 Equal Weight ETF, avril 2003 → aujourd'hui),
le plus long historique investissable. Même fenêtre pour TOUTES les variantes
(alignement dropna), mêmes grilles, mêmes frais que backtest_harness.py.

Variantes testées (socle fixé A PRIORI, lookback/buffer optimisés en
walk-forward comme la recette l'exige) :
  A. Baseline actuelle : socle 50% World + rotation World/USA
  B. Socle coupé : 25% World + 25% EW + rotation World/USA
  C. EW dans la rotation : socle 50% World + rotation World/USA/EW
  D. B et C combinés
Références buy & hold sur les mêmes mois : World seul, EW seul,
50/50 World-EW ("Gave pur", sans momentum).

CRITÈRES D'ADOPTION, posés avant de voir les résultats (comme le 22/07) :
une variante n'est adoptable que si, en hors-échantillon, elle améliore le
Sharpe d'au moins +0.03 SANS dégrader le pire drawdown de plus de 2 points
vs la baseline A. Match nul = on reste simple (règle des émergents).

Ce script ne touche à rien en prod. Sortie : console + sp500_ew_resultats.json.
"""

import warnings
warnings.filterwarnings("ignore")

import json

import numpy as np
import pandas as pd
import yfinance as yf

# ─── PARAMÈTRES (identiques au harnais, EW ajouté) ────────────────────────────

POIDS_WORLD     = {"SPY": 0.60, "EFA": 0.30, "EEM": 0.10}  # proxy World (type ACWI)
TICKER_USA      = "SPY"
TICKER_EW       = "RSP"        # Invesco S&P 500 Equal Weight (depuis 2003)
FRAIS_PAR_TRADE = 0.001
TAUX_CASH_MENS  = 0.0

ASSET_COLS = {
    "World": ("world_px", "world_ret"),
    "USA":   ("usa_px",   "usa_ret"),
    "EW":    ("ew_px",    "ew_ret"),
}

GRILLE_LOOKBACK = [6, 9, 12]
GRILLE_BUFFER   = [0.0, 0.02, 0.03, 0.05]

TRAIN_MOIS = 60
TEST_MOIS  = 12
PAS_MOIS   = 12

FICHIER_RESULTATS = "sp500_ew_resultats.json"

# ─── DONNÉES ──────────────────────────────────────────────────────────────────

def charger_donnees():
    tickers = list(set(list(POIDS_WORLD) + [TICKER_USA, TICKER_EW]))
    data = yf.download(tickers, start="2003-01-01", auto_adjust=True, progress=False)["Close"]
    mensuel = data.resample("ME").last().dropna()

    rends = mensuel.pct_change()
    world_ret = sum(POIDS_WORLD[t] * rends[t] for t in POIDS_WORLD)
    usa_ret   = rends[TICKER_USA]
    ew_ret    = rends[TICKER_EW]

    df = pd.DataFrame({
        "world_ret": world_ret,
        "usa_ret":   usa_ret,
        "ew_ret":    ew_ret,
        "world_px":  (1 + world_ret.fillna(0)).cumprod() * 100,
        "usa_px":    (1 + usa_ret.fillna(0)).cumprod() * 100,
        "ew_px":     (1 + ew_ret.fillna(0)).cumprod() * 100,
    }).dropna()
    return df

# ─── STRATÉGIE (harnais généralisé : socle paramétrable) ──────────────────────

def momentum(px, i, lookback):
    if i - lookback < 0:
        return None
    return px.iloc[i] / px.iloc[i - lookback] - 1


def rendements_hybride(df, lookback, buffer, i_debut, i_fin, rotation, socle,
                       position_init=None):
    """socle = {"world_ret": 0.50} ou {"world_ret": 0.25, "ew_ret": 0.25}.
    La part rotative = 1 - somme(socle). Décision sur le momentum du mois
    précédent (aucun look-ahead), frais sur la part rotative uniquement."""
    part_socle = sum(socle.values())
    rends = []
    position = position_init
    trades = 0

    for i in range(i_debut, i_fin):
        moms = {}
        for actif in rotation:
            m = momentum(df[ASSET_COLS[actif][0]], i - 1, lookback)
            if m is not None:
                moms[actif] = m

        if not moms:
            cible = "Cash"
        else:
            meilleur = max(moms, key=moms.get)
            mom_best = moms[meilleur]
            if mom_best <= 0:
                cible = "Cash"
            elif position in moms and moms[position] > 0 and mom_best < moms[position] + buffer:
                cible = position
            else:
                cible = meilleur

        r_rot = TAUX_CASH_MENS if cible == "Cash" else df[ASSET_COLS[cible][1]].iloc[i]

        cout = 0.0
        if cible != position:
            cout = FRAIS_PAR_TRADE
            trades += 1
            position = cible

        r_socle = sum(poids * df[col].iloc[i] for col, poids in socle.items())
        rends.append(r_socle + (1 - part_socle) * (r_rot - cout))

    return rends, position, trades

# ─── MÉTRIQUES / WALK-FORWARD (identiques au harnais) ─────────────────────────

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
    return {"cagr": round(float(cagr), 4), "max_dd": round(float(max_dd), 4),
            "vol": round(float(vol), 4), "sharpe": round(float(sharpe), 2),
            "n_mois": len(r)}


def walk_forward(df, rotation, socle):
    n = len(df)
    i = max(GRILLE_LOOKBACK) + TRAIN_MOIS
    oos_rends, oos_dates, folds = [], [], []
    position = None

    while i + TEST_MOIS <= n:
        i_train_debut = i - TRAIN_MOIS
        meilleur = None
        for lb in GRILLE_LOOKBACK:
            for bf in GRILLE_BUFFER:
                r, _, _ = rendements_hybride(df, lb, bf, i_train_debut, i, rotation, socle)
                s = metriques(r).get("sharpe", -99)
                if meilleur is None or s > meilleur[0]:
                    meilleur = (s, lb, bf)
        _, lb, bf = meilleur

        rends, position, _ = rendements_hybride(df, lb, bf, i, i + TEST_MOIS,
                                                rotation, socle, position)
        oos_rends.extend(rends)
        oos_dates.extend(df.index[i:i + TEST_MOIS])
        folds.append({"test": f"{df.index[i].date()} → {df.index[i+TEST_MOIS-1].date()}",
                      "lookback": lb, "buffer": bf,
                      "perf_test": round((np.prod([1 + r for r in rends]) - 1) * 100, 1)})
        i += PAS_MOIS

    return oos_rends, oos_dates, folds

# ─── MAIN ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Chargement des données (SPY/EFA/EEM/RSP, mensuel depuis 2003)...")
    df = charger_donnees()
    print(f"Période alignée : {df.index[0].date()} → {df.index[-1].date()} ({len(df)} mois)\n")

    SOCLE_WORLD  = {"world_ret": 0.50}
    SOCLE_MIXTE  = {"world_ret": 0.25, "ew_ret": 0.25}

    configs = {
        "A. Baseline (socle World, rot W/USA)":   (["World", "USA"],       SOCLE_WORLD),
        "B. Socle 25W+25EW, rot W/USA":           (["World", "USA"],       SOCLE_MIXTE),
        "C. Socle World, rot W/USA/EW":           (["World", "USA", "EW"], SOCLE_WORLD),
        "D. Socle 25W+25EW, rot W/USA/EW":        (["World", "USA", "EW"], SOCLE_MIXTE),
    }

    resultats, folds_all, dates_ref = {}, {}, None
    for nom, (rotation, socle) in configs.items():
        print(f"Walk-forward — {nom}...")
        oos, dates, folds = walk_forward(df, rotation, socle)
        resultats[nom] = metriques(oos)
        folds_all[nom] = folds
        dates_ref = dates

    sous = df.loc[dates_ref[0]:dates_ref[-1]]
    refs = {
        "B&H World":          metriques(list(sous["world_ret"])),
        "B&H EW":             metriques(list(sous["ew_ret"])),
        "B&H 50 World/50 EW": metriques(list(0.5 * sous["world_ret"] + 0.5 * sous["ew_ret"])),
    }

    lignes = [("Rendement annuel", "cagr", 100, "%"), ("Pire chute", "max_dd", 100, "%"),
              ("Volatilité", "vol", 100, "%"), ("Sharpe", "sharpe", 1, "")]

    largeur = 24 + 13 * (len(configs) + len(refs))
    print("\n" + "=" * largeur)
    print(f"{'RECETTE S&P 500 EQUAL WEIGHT — HORS-ÉCHANTILLON':^{largeur}}")
    print("=" * largeur)
    entetes = [n.split(".")[0] if "." in n else n for n in list(configs)] + list(refs)
    print(f"{'':24}" + "".join(f"{e:>13}" for e in entetes))
    print("-" * largeur)
    tout = {**resultats, **refs}
    for label, cle, mult, suffixe in lignes:
        vals = "".join(f"{tout[n][cle]*mult:>12.2f}{suffixe}" if suffixe else f"{tout[n][cle]:>13.2f}"
                       for n in list(configs) + list(refs))
        print(f"{label:24}{vals}")
    print("-" * largeur)
    print(f"Test sur {resultats[list(configs)[0]]['n_mois']} mois jamais vus. "
          f"Frais {FRAIS_PAR_TRADE*100:.1f}%/rotation. Refuge cash.")

    with open(FICHIER_RESULTATS, "w", encoding="utf-8") as f:
        json.dump({"date": pd.Timestamp.now().strftime("%Y-%m-%d"),
                   "periode_oos": f"{dates_ref[0].date()} → {dates_ref[-1].date()}",
                   "criteres_adoption_a_priori": "Sharpe OOS >= baseline +0.03 ET drawdown pas dégradé de plus de 2 pts",
                   "configs": resultats, "references_buy_hold": refs,
                   "folds": folds_all}, f, ensure_ascii=False, indent=2)
    print(f"\nRésultats sauvegardés dans {FICHIER_RESULTATS}")

    print("\nVERDICT (critères posés avant de voir les chiffres) : une variante n'est")
    print("adoptable que si elle bat la baseline A d'au moins +0.03 de Sharpe OOS")
    print("sans dégrader le pire drawdown de plus de 2 points. Match nul = on reste simple.")
