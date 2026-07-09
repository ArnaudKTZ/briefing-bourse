#!/usr/bin/env python3
"""
Backtest Crypto Dual Momentum — passage par la recette AVANT toute prod.

Hypothèse à tester (idée du 25/06) : le momentum absolu (rotation vers le
cash quand tout est négatif) vaut plus sur crypto que sur actions, parce que
les bear markets crypto détruisent -80% et durent des mois. L'airbag y serait
un vrai moteur de rendement, pas seulement une assurance.

Méthode : le même walk-forward que backtest_harness.py (réglages choisis sur
le passé, appliqués à l'année suivante jamais vue, frais inclus, décision sur
le momentum du mois précédent = aucun look-ahead). Pas de socle buy & hold
ici : la poche crypto est entièrement rotative, le refuge est le cash/stable.

Règles anti-leakage gardées de la veille du 05/07 : données point-in-time
strictes ; si un jour le live fait +0.2 Sharpe de moins que ce backtest,
suspicion de contamination.

Limites honnêtes, à relire avant toute décision :
  - Historique court : BTC depuis 2014, ETH depuis 2017, SOL depuis 2020.
    Moins de cycles que les 22 ans du backtest actions.
  - Un régime domine l'échantillon (hausse séculaire du BTC) : le CAGR
    absolu est flatté, seule la COMPARAISON à buy & hold est instructive.
  - Frais 0,5% par rotation (exchange + slippage), hypothèse conservatrice.
  - Fiscalité hors PEA non modélisée (flat tax sur chaque arbitrage gagnant
    en France) : elle réduirait l'edge réel des rotations.

RÉSULTAT (09/07, données 2014-2026) — deux modes testés :
  1. Walk-forward avec optimisation du lookback (la recette actions) : ÉCHOUE.
     L'optimiseur choisit des lookbacks courts (3-9 mois) qui brillent en
     train puis se font hacher en test (Sharpe OOS 0.17-0.25 vs 0.46 B&H).
     C'est le papier Bouchaud (veille 04/07) rejoué : les signaux rapides
     sont morts, seuls les lents survivent.
  2. Réglages FIXES a priori (lookback 12 mois, le standard Antonacci, celui
     du DM actions ; buffer sans effet) : PASSE sur la même fenêtre 2018-2026.
     BTC/ETH : CAGR 46% vs 32% B&H BTC, drawdown -51% vs -73%, Sharpe 0.73
     vs 0.46. BTC seul : DD -41% vs -73% à CAGR supérieur (l'airbag confirmé).
     Ajouter SOL DÉTRUIT tout (DD -90% : rotation vers SOL au sommet 2021,
     -95% ensuite) — même leçon que les émergents côté actions : rejeté.
  Robustesse lookback (BTC seul, Sharpe vs 0.46 B&H) : 3 → 0.55, 6 → 0.43,
  9 → 0.57, 12 → 0.62. L'airbag (DD réduit) tient sur TOUS les lookbacks ;
  l'edge de rendement exact, lui, dépend du réglage : rester humble dessus.

Ce script ne touche à rien en prod. Sortie : console + crypto_dm_resultats.json.
"""

import warnings
warnings.filterwarnings("ignore")

import json

import numpy as np
import pandas as pd
import yfinance as yf

# ─── PARAMÈTRES ───────────────────────────────────────────────────────────────

TICKERS = {"BTC": "BTC-USD", "ETH": "ETH-USD", "SOL": "SOL-USD"}
FRAIS_PAR_TRADE = 0.005   # 0,5% par changement de position (exchange + slippage)
TAUX_CASH_MENS  = 0.0     # refuge cash/stablecoin, hypothèse conservatrice

GRILLE_LOOKBACK = [3, 6, 9, 12]
GRILLE_BUFFER   = [0.0, 0.03, 0.05, 0.10]

TRAIN_MOIS = 36   # 3 ans d'apprentissage (l'histoire crypto est courte)
TEST_MOIS  = 12   # 1 an de test hors-échantillon
PAS_MOIS   = 12

# Réglages fixes a priori (mode 2) : le standard de la littérature (Antonacci)
# et du DM actions. Choisis AVANT de voir les résultats crypto, pas optimisés.
LOOKBACK_FIXE = 12
BUFFER_FIXE   = 0.0   # sans effet mesuré : les écarts de momentum crypto sont larges

FICHIER_RESULTATS = "crypto_dm_resultats.json"

# ─── DONNÉES ──────────────────────────────────────────────────────────────────

def charger_donnees():
    """Clôtures mensuelles par actif. On garde les NaN (ETH et SOL naissent en
    cours de route) : un actif sans historique suffisant n'est simplement pas
    candidat ce mois-là."""
    data = yf.download(list(TICKERS.values()), start="2014-01-01",
                       auto_adjust=True, progress=False)["Close"]
    data = data.rename(columns={v: k for k, v in TICKERS.items()})
    mensuel = data.resample("ME").last()
    # Timeline = les mois où le BTC existe (le doyen de l'univers)
    mensuel = mensuel[mensuel["BTC"].notna()]
    rends = mensuel.pct_change()
    return mensuel, rends


def valide(x):
    return x is not None and x == x

# ─── STRATÉGIE ────────────────────────────────────────────────────────────────

def momentum(px, i, lookback):
    if i - lookback < 0:
        return None
    a, b = px.iloc[i], px.iloc[i - lookback]
    if not (valide(a) and valide(b)):
        return None
    return a / b - 1


def rendements_rotation(px, rends, lookback, buffer, i_debut, i_fin, rotation,
                        position_init=None):
    """Rendements mensuels de la rotation pure sur [i_debut, i_fin].
    Décision sur le momentum du mois PRÉCÉDENT (aucun look-ahead).
    Retourne (liste_rendements, position_finale, nb_trades)."""
    out = []
    position = position_init   # un actif / "Cash" / None
    trades = 0

    for i in range(i_debut, i_fin):
        moms = {}
        for actif in rotation:
            m = momentum(px[actif], i - 1, lookback)
            # Candidat seulement si son rendement du mois i est mesurable
            if m is not None and valide(rends[actif].iloc[i]):
                moms[actif] = m

        if not moms:
            cible = "Cash"
        else:
            meilleur = max(moms, key=moms.get)
            mom_best = moms[meilleur]
            if mom_best <= 0:
                cible = "Cash"                      # momentum absolu : refuge
            elif position in moms and moms[position] > 0 and mom_best < moms[position] + buffer:
                cible = position                    # anti-whipsaw
            else:
                cible = meilleur

        r = TAUX_CASH_MENS if cible == "Cash" else float(rends[cible].iloc[i])

        cout = 0.0
        if cible != position:
            cout = FRAIS_PAR_TRADE
            trades += 1
            position = cible

        out.append(r - cout)

    return out, position, trades

# ─── MÉTRIQUES ────────────────────────────────────────────────────────────────

def metriques(rends_liste):
    r = np.array([x for x in rends_liste if valide(x)])
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
            "mult": round(float(courbe[-1]), 2), "n_mois": len(r)}


def sharpe_train(px, rends, lookback, buffer, i_debut, i_fin, rotation):
    out, _, _ = rendements_rotation(px, rends, lookback, buffer, i_debut, i_fin, rotation)
    return metriques(out).get("sharpe", -99)

# ─── WALK-FORWARD ─────────────────────────────────────────────────────────────

def walk_forward(px, rends, rotation):
    n = len(px)
    i = max(GRILLE_LOOKBACK) + TRAIN_MOIS
    oos_rends, oos_dates, folds = [], [], []
    position = None
    total_trades = 0

    while i < n:
        i_fin_test = min(i + TEST_MOIS, n)
        i_train_debut = i - TRAIN_MOIS

        # 1. Meilleurs réglages sur la fenêtre d'apprentissage
        meilleur = None
        for lb in GRILLE_LOOKBACK:
            for bf in GRILLE_BUFFER:
                s = sharpe_train(px, rends, lb, bf, i_train_debut, i, rotation)
                if meilleur is None or s > meilleur[0]:
                    meilleur = (s, lb, bf)
        _, lb, bf = meilleur

        # 2. Application aux mois SUIVANTS (jamais vus)
        out, position, trades = rendements_rotation(
            px, rends, lb, bf, i, i_fin_test, rotation, position)
        total_trades += trades
        oos_rends.extend(out)
        oos_dates.extend(px.index[i:i_fin_test])
        folds.append({
            "test": f"{px.index[i].date()} → {px.index[i_fin_test - 1].date()}",
            "lookback": lb, "buffer": bf,
            "perf_test": round((np.prod([1 + r for r in out]) - 1) * 100, 1),
        })
        i += PAS_MOIS

    return oos_rends, oos_dates, folds, total_trades


def buy_hold(rends, actif, dates):
    sous = rends[actif].loc[dates[0]:dates[-1]]
    return [float(x) for x in sous]

# ─── MAIN ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Chargement des données crypto (Yahoo, mensuel)...")
    px, rends = charger_donnees()
    dispo = {a: str(px[a].first_valid_index().date()) for a in TICKERS}
    print(f"Période : {px.index[0].date()} → {px.index[-1].date()} ({len(px)} mois)")
    print(f"Premier mois par actif : {dispo}\n")

    configs = {
        "BTC seul (absolu)": ["BTC"],
        "BTC/ETH":           ["BTC", "ETH"],
        "BTC/ETH/SOL":       ["BTC", "ETH", "SOL"],
    }

    resultats, dates_ref = {}, None
    for nom, rotation in configs.items():
        print(f"Walk-forward — {nom}...")
        oos, dates, folds, trades = walk_forward(px, rends, rotation)
        resultats[nom] = {"metriques": metriques(oos), "folds": folds,
                          "n_trades": trades}
        dates_ref = dates

    m_bh = metriques(buy_hold(rends, "BTC", dates_ref))

    # Mode 2 : réglages fixes a priori, sur la même fenêtre hors-optimisation
    i0 = px.index.get_loc(dates_ref[0])
    fixes = {}
    for nom, rotation in configs.items():
        out, _, trades = rendements_rotation(
            px, rends, LOOKBACK_FIXE, BUFFER_FIXE, i0, len(px), rotation)
        fixes[nom] = {"metriques": metriques(out), "n_trades": trades}

    lignes = [
        ("Rendement annuel",      "cagr",   lambda v: f"{v*100:.1f}%"),
        ("Pire chute (drawdown)", "max_dd", lambda v: f"{v*100:.1f}%"),
        ("Volatilité",            "vol",    lambda v: f"{v*100:.1f}%"),
        ("Sharpe",                "sharpe", lambda v: f"{v:.2f}"),
        ("Multiple final",        "mult",   lambda v: f"x{v:.1f}"),
    ]

    def tableau(titre, res_par_config):
        largeur = 26 + 20 * (len(configs) + 1)
        print("\n" + "=" * largeur)
        print(f"{titre:^{largeur}}")
        print("=" * largeur)
        entetes = "".join(f"{n:>20}" for n in list(configs) + ["B&H BTC"])
        print(f"{'':26}{entetes}")
        print("-" * largeur)
        for label, cle, fmt in lignes:
            vals = "".join(f"{fmt(res_par_config[n]['metriques'][cle]):>20}" for n in configs)
            vals += f"{fmt(m_bh[cle]):>20}"
            print(f"{label:26}{vals}")
        print("-" * largeur)

    tableau("MODE 1 — WALK-FORWARD OPTIMISÉ (hors-échantillon)", resultats)
    n_mois = resultats[list(configs)[0]]["metriques"]["n_mois"]
    print(f"Test sur {n_mois} mois jamais vus par les réglages "
          f"({dates_ref[0].date()} → {dates_ref[-1].date()}), frais {FRAIS_PAR_TRADE*100:.1f}%/rotation.")

    tableau(f"MODE 2 — RÉGLAGES FIXES A PRIORI (lookback {LOOKBACK_FIXE} mois), même fenêtre", fixes)
    print("Réglages non optimisés (standard littérature + DM actions) : pas de")
    print("sélection sur ces données, mais fenêtre identique pour comparaison.")

    print("\nDétail des folds (BTC/ETH/SOL) :")
    for f in resultats["BTC/ETH/SOL"]["folds"]:
        print(f"  {f['test']}  lookback={f['lookback']:>2}  buffer={f['buffer']:.2f}  perf={f['perf_test']:+.1f}%")

    with open(FICHIER_RESULTATS, "w", encoding="utf-8") as f:
        json.dump({
            "date":      pd.Timestamp.now().strftime("%Y-%m-%d"),
            "periode_oos": f"{dates_ref[0].date()} → {dates_ref[-1].date()}",
            "frais_par_trade": FRAIS_PAR_TRADE,
            "walk_forward_optimise": {n: resultats[n] for n in configs},
            "reglages_fixes": {"lookback": LOOKBACK_FIXE, "buffer": BUFFER_FIXE,
                               "configs": fixes},
            "buy_hold_btc": m_bh,
        }, f, ensure_ascii=False, indent=2)
    print(f"\nRésultats sauvegardés dans {FICHIER_RESULTATS}")

    print("\nVERDICT : la rotation crypto n'est adoptable que si elle réduit le")
    print("drawdown SANS sacrifier le Sharpe vs B&H BTC. L'histoire est courte")
    print("(un seul grand régime haussier) : exiger une marge nette, pas un match nul.")
    print("Le mode optimisé échoue (lookbacks courts sélectionnés puis hachés) ;")
    print("seul le lookback 12 fixe est candidat, BTC/ETH sans SOL. Décision : Arnaud.")
