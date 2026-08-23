#!/usr/bin/env python3
"""
Recette de la sélection Qualité-Momentum (Piste 2, 23/08).

Question : en remplaçant le "voyant" (score oscillateur, perdant net -1,2 pt) par
une sélection MOMENTUM greffée sur le Risk Engine, obtient-on enfin un edge net
positif, sur un cycle complet (2020-2026, bull ET bear), et avec moins de risque
que de simplement détenir l'indice ?

Trois mondes, même univers, mêmes frais, sans look-ahead :
  A. Ancienne logique   : achète tout ce qui est "top" (momentum), taille fixe
                          2000€, aucun airbag. Le témoin "on suit le signal bêtement".
  B. Momentum+RiskEngine: selectionner() du Risk Engine (top-3 conviction, sizing
                          volatilité, plafond secteur, filtre régime, stop/TP ATR)
                          sur la sélection momentum. La nouvelle proposition.
  C. CAC 40 buy & hold  : on détient l'indice, référence passive.

La QUALITÉ n'est PAS testée ici : les fondamentaux Yahoo ne sont pas historisés,
les utiliser sur 2020 serait du look-ahead. La porte qualité se prouvera en forward
(track record virtuel live). Ce backtest isole l'apport momentum + gestion du risque.

Simulation jour par jour, rebalance hebdo (lundi), params figés a priori.
Ne touche à rien en prod. Sortie : console + selection_backtest_resultats.json.
"""

import warnings
warnings.filterwarnings("ignore")

import json
import datetime

import pandas as pd

from risk_engine import ParamsRisque, selectionner
from selection_qm import ParamsSelection, snapshot_selection
# Réutilise les briques déjà écrites et validées du stress-test krach.
from stress_test_krach import (charger_donnees, atr_pct, regime_a_date, frais,
                               EQUITY_DEPART, BUDGET_FIXE)

PSEL = ParamsSelection()
PRISK = ParamsRisque()


def cours_a_date(serie, date, defaut):
    s = serie[serie.index <= date]
    return float(s.iloc[-1]) if len(s) else defaut


def simuler(bras, data, cac, atrs, jours, secteurs):
    """Rejoue un des trois mondes. Retourne (courbe_equity, n_trades, jours_baissier)."""
    capital = EQUITY_DEPART
    positions = {}          # nom -> {nb, prix_entree, stop_pct, tp_pct, secteur}
    courbe = {}
    n_trades = 0
    jours_baissier = 0
    closes = {n: h["Close"] for n, h in data.items()}

    # Monde C : buy & hold indiciel, calcul direct.
    if bras == "C":
        base = cours_a_date(cac, jours[0], None)
        for d in jours:
            courbe[d.strftime("%Y-%m-%d")] = round(EQUITY_DEPART * cours_a_date(cac, d, base) / base, 2)
        return courbe, 0, 0

    for date in jours:
        # 1. Sorties quotidiennes sur stop/TP ATR (seulement bras B, qui pose des stops)
        if bras == "B":
            for nom in list(positions.keys()):
                pos = positions[nom]
                cours = cours_a_date(closes[nom], date, pos["prix_entree"])
                pnl = (cours - pos["prix_entree"]) / pos["prix_entree"]
                if (pos["stop_pct"] and pnl <= -pos["stop_pct"]) or (pos["tp_pct"] and pnl >= pos["tp_pct"]):
                    brut = pos["nb"] * cours
                    capital += brut - frais(brut)
                    n_trades += 1
                    del positions[nom]

        regime = regime_a_date(cac, date)
        if regime == "baissier":
            jours_baissier += 1

        # 2. Rebalance hebdo (lundi)
        if date.weekday() == 0:
            snap = snapshot_selection(closes, atrs, secteurs, date, PSEL)  # momentum, sans porte qualité
            if snap:
                acheteurs_noms = {n for n, d in snap.items() if d["signal"] == "ACHETER"}
                # Sortie : un titre qui n'est plus dans le top momentum est vendu (les deux bras)
                for nom in list(positions.keys()):
                    if nom not in acheteurs_noms:
                        cours = cours_a_date(closes[nom], date, positions[nom]["prix_entree"])
                        brut = positions[nom]["nb"] * cours
                        capital += brut - frais(brut)
                        n_trades += 1
                        del positions[nom]

                candidats = [{"nom": n, **d} for n, d in snap.items()]
                equity = capital + sum(p["nb"] * cours_a_date(closes[n], date, p["prix_entree"])
                                       for n, p in positions.items())

                if bras == "A":
                    for c in candidats:
                        if c["signal"] != "ACHETER" or c["nom"] in positions:
                            continue
                        nb = int(BUDGET_FIXE / c["prix"]) if c["prix"] else 0
                        cout = nb * c["prix"]
                        if nb <= 0 or capital < cout + frais(cout):
                            continue
                        capital -= cout + frais(cout)
                        n_trades += 1
                        positions[c["nom"]] = {"nb": nb, "prix_entree": c["prix"],
                                               "stop_pct": None, "tp_pct": None, "secteur": c["secteur"]}
                else:  # B
                    contexte = {"regime": regime, "drawdown": 0.0}
                    pos_ouvertes = {n: {"secteur": p["secteur"]} for n, p in positions.items()}
                    for dec in selectionner(candidats, pos_ouvertes, equity, contexte, PRISK):
                        cout = dec["nb"] * dec["prix"]
                        if capital < cout + frais(cout):
                            continue
                        capital -= cout + frais(cout)
                        n_trades += 1
                        positions[dec["nom"]] = {"nb": dec["nb"], "prix_entree": dec["prix"],
                                                 "stop_pct": dec["stop_pct"], "tp_pct": dec["tp_pct"],
                                                 "secteur": dec["secteur"]}

        val = capital + sum(p["nb"] * cours_a_date(closes[n], date, p["prix_entree"])
                            for n, p in positions.items())
        courbe[date.strftime("%Y-%m-%d")] = round(val, 2)

    return courbe, n_trades, jours_baissier


def simuler_rotation(data, cac, jours, secteurs, top_n=6):
    """Monde B2 : rotation momentum MENSUELLE, panier de top_n valeurs équipondéré,
    airbag régime au niveau portefeuille (100% cash quand CAC < MM200). Pas de
    stop ATR, pas de churn hebdo : la pratique standard du momentum. Params a
    priori (mensuel, top-6, filtre trend), pas d'optimisation sur ces données."""
    capital = EQUITY_DEPART
    positions = {}
    courbe = {}
    n_trades = 0
    closes = {n: h["Close"] for n, h in data.items()}
    mois_courant = None

    for date in jours:
        premier_du_mois = (date.year, date.month) != mois_courant
        if premier_du_mois:
            mois_courant = (date.year, date.month)
            snap = snapshot_selection(closes, {}, secteurs, date, PSEL)
            regime = regime_a_date(cac, date)
            # Cible : top_n momentum si régime haussier, sinon rien (cash = airbag)
            if snap and regime == "haussier":
                classes = sorted((d for d in snap.values()), key=lambda d: d["score"], reverse=True)
                cibles = {n for n, d in snap.items()
                          if d["signal"] == "ACHETER"}
                cibles = set(sorted(cibles, key=lambda n: snap[n]["score"], reverse=True)[:top_n])
            else:
                cibles = set()
            # Vendre tout ce qui n'est pas dans la cible
            for nom in list(positions.keys()):
                if nom not in cibles:
                    cours = cours_a_date(closes[nom], date, positions[nom]["prix_entree"])
                    brut = positions[nom]["nb"] * cours
                    capital += brut - frais(brut)
                    n_trades += 1
                    del positions[nom]
            # Acheter/renforcer vers l'équipondération
            if cibles:
                equity = capital + sum(p["nb"] * cours_a_date(closes[n], date, p["prix_entree"])
                                       for n, p in positions.items())
                cible_eur = equity / len(cibles)
                for nom in cibles:
                    if nom in positions:
                        continue
                    prix = snap[nom]["prix"]
                    nb = int(cible_eur / prix) if prix else 0
                    cout = nb * prix
                    if nb <= 0 or capital < cout + frais(cout):
                        continue
                    capital -= cout + frais(cout)
                    n_trades += 1
                    positions[nom] = {"nb": nb, "prix_entree": prix, "secteur": snap[nom]["secteur"]}

        val = capital + sum(p["nb"] * cours_a_date(closes[n], date, p["prix_entree"])
                            for n, p in positions.items())
        courbe[date.strftime("%Y-%m-%d")] = round(val, 2)

    return courbe, n_trades, 0


def stats(courbe):
    vals = list(courbe.values())
    if not vals:
        return {"n": 0}
    pic, maxdd = -1e18, 0.0
    for v in vals:
        pic = max(pic, v)
        maxdd = min(maxdd, v / pic - 1)
    return {"perf_pct": round((vals[-1] / EQUITY_DEPART - 1) * 100, 2),
            "drawdown_max_pct": round(maxdd * 100, 2),
            "valeur_finale": round(vals[-1], 2)}


def perf_par_an(courbe):
    """Rendement civil par année, pour voir le comportement bull vs bear."""
    par_an = {}
    for d, v in courbe.items():
        par_an.setdefault(d[:4], []).append(v)
    out = {}
    annees = sorted(par_an)
    for i, a in enumerate(annees):
        debut = par_an[annees[i - 1]][-1] if i > 0 else EQUITY_DEPART
        out[a] = round((par_an[a][-1] / debut - 1) * 100, 1)
    return out


if __name__ == "__main__":
    START, END = "2020-01-02", "2026-08-22"
    print(f"Recette Qualité-Momentum sur {START} -> {END} (téléchargement Yahoo, ~1-2 min)...")
    data, cac = charger_donnees(__import__("marche_config").CAC40, START, END)
    secteurs = __import__("marche_config").SECTEUR_PAR_VALEUR
    print(f"  {len(data)} valeurs, {len(cac)} jours CAC")
    atrs = {n: atr_pct(h) for n, h in data.items()}
    jours = [d for d in cac[(cac.index >= pd.Timestamp(START)) & (cac.index <= pd.Timestamp(END))].index]

    resultats = {}
    for bras, label in [("A", "Ancienne (taille fixe)"), ("B", "Momentum+RiskEngine"), ("C", "CAC buy&hold")]:
        courbe, nt, jb = simuler(bras, data, cac, atrs, jours, secteurs)
        resultats[bras] = {"label": label, "stats": stats(courbe),
                           "n_trades": nt, "perf_par_an": perf_par_an(courbe), "courbe": courbe}
    # B2 : rotation momentum mensuelle + airbag régime (la correction de principe)
    courbe, nt, _ = simuler_rotation(data, cac, jours, secteurs, top_n=6)
    resultats["B2"] = {"label": "Momentum rotation mensuelle", "stats": stats(courbe),
                       "n_trades": nt, "perf_par_an": perf_par_an(courbe), "courbe": courbe}

    L = 70
    print("\n" + "=" * L)
    print(f"{'RECETTE QUALITÉ-MOMENTUM — cycle complet 2020→2026':^{L}}")
    print("=" * L)
    ordre = ["A", "B", "B2", "C"]
    print(f"{'':26}{'A.Ancien':>11}{'B.M+Risk':>11}{'B2.Rotat':>11}{'C.CAC':>11}")
    print("-" * L)
    for cle, lab, suf in [("perf_pct", "Performance totale", "%"),
                          ("drawdown_max_pct", "Drawdown max", "%"),
                          ("valeur_finale", "Valeur finale", "€")]:
        row = f"{lab:26}"
        for b in ordre:
            row += f"{str(resultats[b]['stats'][cle]) + suf:>11}"
        print(row)
    row = f"{'Nb de trades':26}"
    for b in ordre:
        row += f"{resultats[b]['n_trades']:>11}"
    print(row)
    print("-" * L)
    print("Rendement par année (%) :")
    annees = sorted(resultats["A"]["perf_par_an"])
    print(f"{'':26}" + "".join(f"{a:>11}" for a in annees[-7:]))
    for b in ordre:
        row = f"{resultats[b]['label']:26}"
        for a in annees[-7:]:
            row += f"{str(resultats[b]['perf_par_an'].get(a, '-')):>11}"
        print(row)
    print("-" * L)
    print("Momentum seul (porte qualité NON backtestée — se prouve en forward).")

    with open("selection_backtest_resultats.json", "w", encoding="utf-8") as f:
        json.dump({"date_test": datetime.date.today().isoformat(),
                   "fenetre": [START, END],
                   "params_selection": PSEL.__dict__, "params_risque": PRISK.__dict__,
                   "note": "Momentum seul (qualité non backtestable sans look-ahead). "
                           "3 mondes: ancienne taille fixe / momentum+RiskEngine / CAC B&H.",
                   "resultats": {b: {k: v for k, v in r.items() if k != "courbe"} for b, r in resultats.items()},
                   "courbes": {b: r["courbe"] for b, r in resultats.items()}},
                  f, ensure_ascii=False, indent=2)
    print("\nRésultats sauvegardés dans selection_backtest_resultats.json")
