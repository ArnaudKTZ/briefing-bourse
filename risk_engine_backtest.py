#!/usr/bin/env python3
"""
Recette du Risk Engine — le mesurer AVANT de l'intégrer au scoring live.

Question posée : maintenant que le score a un pouvoir de classement (bilan du
22/07, IC +0,077), est-ce que prendre MOINS de trades mais mieux ciblés
(concentration sur les top convictions, filtre de régime, plafond sectoriel) et
mieux DIMENSIONNÉS (taille par volatilité) améliore l'edge net de frais et réduit
le risque du portefeuille, par rapport au comportement actuel « tout ACHETER
>= 80, 2000€ fixe » ?

Méthode : on rejoue les recos réelles de la fenêtre propre (performance.json
depuis le 02/07, horodatées avec le prix d'entrée à 7h), on calcule le rendement
J+5 net de frais de chaque position, et on compare deux mondes :
  A. Baseline actuel : toutes les ACHETER >= 80, taille fixe.
  B. Risk Engine     : selectionner() du module risk_engine (top-K conviction,
                       plafond secteur, filtre régime, sizing volatilité, frein DD).

Paramètres du Risk Engine FIGÉS a priori (standards littérature), aucune
optimisation sur ces données. Sans look-ahead : régime lu la veille, rendement
mesuré sur les clôtures postérieures.

Ne touche à rien en prod. Sortie : console + risk_engine_resultats.json.
"""

import warnings
warnings.filterwarnings("ignore")

import json
import statistics

import numpy as np
import yfinance as yf

from marche_config import CAC40
from risk_engine import ParamsRisque, selectionner, stop_et_cible, taille_position
from agent_evaluateur import (charger_closes, close_apres, charger_contexte_cac,
                              contexte_pour, prix_ok, DATE_DONNEES_PROPRES)

FRAIS_ALLER_RETOUR = 1.0   # points de %, comme l'Évaluateur (0,5%/côté)
HORIZON = 5                 # J+5, l'horizon de référence du bilan
EQUITY_DEPART = 10000.0
BUDGET_FIXE = 2000.0        # baseline actuelle
FICHIER_RESULTATS = "risk_engine_resultats.json"


def charger_recos_propres():
    with open("performance.json", "r", encoding="utf-8") as f:
        hist = json.load(f).get("historique", {})
    return {d: recos for d, recos in sorted(hist.items()) if d >= DATE_DONNEES_PROPRES}


def atr_pct_series(ticker):
    """Série ATR14 en % du cours (True Range lissé / clôture), par date."""
    try:
        h = yf.Ticker(ticker).history(period="6mo")[["High", "Low", "Close"]].dropna()
    except Exception:
        return {}
    if h.empty:
        return {}
    prev_close = h["Close"].shift(1)
    tr = np.maximum(h["High"] - h["Low"],
                    np.maximum((h["High"] - prev_close).abs(),
                               (h["Low"] - prev_close).abs()))
    atr = tr.rolling(14).mean()
    return {d.strftime("%Y-%m-%d"): float(atr.loc[d] / h["Close"].loc[d])
            for d in h.index if atr.loc[d] == atr.loc[d] and h["Close"].loc[d] > 0}


def rendement_j5(closes, nom, date, prix):
    """Rendement % entre le prix d'entrée et la clôture J+5, ou None."""
    if nom not in closes or not prix_ok(prix):
        return None
    px = close_apres(closes[nom], date, HORIZON)
    return (px / prix - 1) * 100 if (px and prix_ok(px)) else None


def simuler(monde, recos, closes, atr_par_nom, regime_par_date, p):
    """Rejoue la fenêtre. Retourne la liste des trades pris avec leur P&L net
    (% et €) et le compte des jours où le filtre régime a bloqué."""
    trades = []
    jours_bloques = 0
    for date in sorted(recos):
        # Candidats du jour, enrichis de l'ATR% à cette date
        candidats = []
        for nom, d in recos[date].items():
            atr = atr_par_nom.get(nom, {}).get(date)
            candidats.append({"nom": nom, "score": d.get("score", 0),
                              "prix": d.get("prix"), "secteur": d.get("secteur", "?"),
                              "signal": d.get("signal", "SURVEILLER"), "atr_pct": atr})

        if monde == "A":
            picks = [{"nom": c["nom"], "secteur": c["secteur"], "score": c["score"],
                      "prix": c["prix"], "nb": int(BUDGET_FIXE / c["prix"]) if c["prix"] else 0,
                      "stop_pct": None}
                     for c in candidats
                     if c["signal"] == "ACHETER" and c["score"] >= p.score_min and prix_ok(c["prix"])]
        else:
            contexte = {"regime": regime_par_date.get(date), "drawdown": 0.0}
            if contexte["regime"] == "baissier":
                jours_bloques += 1
            picks = selectionner(candidats, {}, EQUITY_DEPART, contexte, p)

        for pk in picks:
            r = rendement_j5(closes, pk["nom"], date, pk["prix"])
            if r is None or pk["nb"] <= 0:
                continue
            r_net = r - FRAIS_ALLER_RETOUR
            montant = pk["nb"] * pk["prix"]
            trades.append({"date": date, "nom": pk["nom"], "secteur": pk["secteur"],
                           "score": pk["score"], "montant": round(montant, 2),
                           "rdt_net_pct": round(r_net, 2),
                           "pnl_eur": round(montant * r_net / 100, 2)})
    return trades, jours_bloques


def resume(trades):
    if not trades:
        return {"n": 0}
    nets = [t["rdt_net_pct"] for t in trades]
    pnls = [t["pnl_eur"] for t in trades]
    return {
        "n_trades":        len(trades),
        "edge_net_moyen":  round(statistics.mean(nets), 3),
        "pct_gagnants":    round(100 * sum(1 for x in nets if x > 0) / len(nets)),
        "pnl_total_eur":   round(sum(pnls), 2),
        "pnl_eur_ecart_type": round(statistics.pstdev(pnls), 2),   # dispersion du risque € (effet du sizing P2)
        "capital_engage_moyen": round(statistics.mean(t["montant"] for t in trades)),
    }


if __name__ == "__main__":
    print("Chargement des recos propres (depuis le 02/07)...")
    recos = charger_recos_propres()
    noms = {n for d in recos.values() for n in d}
    print(f"  {len(recos)} jours, {len(noms)} valeurs concernées")

    print("Récupération des clôtures (pour les rendements J+5)...")
    closes = charger_closes()

    print("Calcul des ATR% par valeur...")
    atr_par_nom = {nom: atr_pct_series(CAC40[nom]) for nom in noms if nom in CAC40}

    print("Contexte de régime (CAC vs MM200, lu la veille)...")
    regimes_cac, _ = charger_contexte_cac()
    regime_par_date = {d: contexte_pour(regimes_cac, d) for d in recos}
    regimes_vus = {v for v in regime_par_date.values()}
    print(f"  régimes rencontrés : {regimes_vus}")

    p = ParamsRisque()
    trades_a, _ = simuler("A", recos, closes, atr_par_nom, regime_par_date, p)
    trades_b, bloques = simuler("B", recos, closes, atr_par_nom, regime_par_date, p)
    ra, rb = resume(trades_a), resume(trades_b)

    largeur = 62
    print("\n" + "=" * largeur)
    print(f"{'RECETTE RISK ENGINE — fenêtre propre depuis le ' + DATE_DONNEES_PROPRES:^{largeur}}")
    print("=" * largeur)
    print(f"{'':32}{'A. Baseline':>15}{'B. RiskEngine':>15}")
    print("-" * largeur)
    lignes = [
        ("Nb de trades",             "n_trades",        ""),
        ("Edge net moyen / trade",   "edge_net_moyen",  " pts"),
        ("% trades gagnants",        "pct_gagnants",    " %"),
        ("Capital engagé moyen",     "capital_engage_moyen", " €"),
        ("P&L total (virtuel)",      "pnl_total_eur",   " €"),
        ("Écart-type P&L par trade", "pnl_eur_ecart_type", " €"),
    ]
    for label, cle, suf in lignes:
        va, vb = ra.get(cle, "-"), rb.get(cle, "-")
        print(f"{label:32}{str(va)+suf:>15}{str(vb)+suf:>15}")
    print("-" * largeur)
    print(f"Filtre de régime : {bloques} jour(s) bloqué(s) en marché baissier.")
    print(f"Frais {FRAIS_ALLER_RETOUR:.1f}%/aller-retour. Params figés a priori (littérature).")

    with open(FICHIER_RESULTATS, "w", encoding="utf-8") as f:
        json.dump({"date_test": __import__("datetime").date.today().isoformat(),
                   "fenetre_depuis": DATE_DONNEES_PROPRES,
                   "params": p.__dict__,
                   "baseline_A": ra, "risk_engine_B": rb,
                   "jours_bloques_regime": bloques,
                   "note": "P7 (régime) et P12 (frein DD) non exercés faute de marché baissier "
                           "et de drawdown suffisant sur la fenêtre propre — à re-mesurer en tempête."},
                  f, ensure_ascii=False, indent=2)
    print(f"\nRésultats sauvegardés dans {FICHIER_RESULTATS}")
