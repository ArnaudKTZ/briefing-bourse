#!/usr/bin/env python3
"""
Stress-test des airbags du Risk Engine sur de VRAIS krachs (Piste 1, 23/08).

Origine : la recette forward du 22/08 a montré que le Risk Engine bat le baseline
(+2,15 pts sur la fenêtre), mais la vérification a établi que ses DEUX freins de
crise n'ont JAMAIS joué : P7 (filtre régime, bloque toute ouverture quand le CAC
passe sous sa MM200) et P12 (frein drawdown, divise les tailles au-delà de -10%).
Le CAC est resté au-dessus de sa MM200 tout du long, drawdown max -5,7%. Donc la
capacité anti-krach, qui est le seul argument pour un jour engager du réel, reste
NON TESTÉE. On n'a pas à attendre des années qu'un bear arrive en live : on rejoue
les airbags sur 2020 (COVID) et 2022 (bear taux).

LIMITE ASSUMÉE (à ne pas cacher) : le score V4 réel n'existait pas en 2020/2022.
On utilise donc un SIGNAL PROXY transparent (momentum 60 jours, rang cross-
sectionnel), IDENTIQUE pour les deux bras. Ce test n'évalue donc PAS la qualité du
signal (Piste 2) — il isole une seule chose : à signal égal, est-ce que P7+P12
réduisent le drawdown et améliorent la traversée du krach, versus ne pas les avoir ?

Deux bras, même univers, même signal, même fenêtre :
  A. Baseline : achète les ACHETER du proxy, taille fixe 2000€, AUCUN airbag.
  B. Risk Engine : selectionner() du module risk_engine (P7 régime, P12 DD,
                   sizing volatilité P2, top-K P9, plafond secteur P11, stop/TP ATR).

Simulation de portefeuille jour par jour (pas un edge J+5 par trade) : c'est la
COURBE d'équité et le DRAWDOWN qui comptent pour juger un airbag. Rebalancement
hebdomadaire (lundi), sorties quotidiennes sur stop/TP ATR, sortie sur signal
négatif au rebalancement. Sans look-ahead : régime et momentum lus à la date t sur
les données <= t, rendements sur les clôtures postérieures.

Ne touche à rien en prod. Sortie : console + stress_test_krach_resultats.json.
"""

import warnings
warnings.filterwarnings("ignore")

import json
import datetime

import numpy as np
import pandas as pd
import yfinance as yf

from marche_config import CAC40, SECTEUR_PAR_VALEUR
from risk_engine import ParamsRisque, selectionner

# Frais alignés sur le reste du projet : 0,5% par côté.
def frais(montant):
    return round(montant * 0.005, 2)

EQUITY_DEPART = 10000.0
BUDGET_FIXE   = 2000.0     # baseline actuelle
LOOKBACK_MOM  = 60         # momentum sur ~3 mois de bourse
SEUIL_ACHAT   = 80         # score proxy >= 80 (top ~20% du momentum) => ACHETER
SEUIL_EVITER  = 40         # score proxy <= 40 => ÉVITER (sortie)


def charger_donnees(tickers, start, end):
    """Télécharge High/Low/Close pour tous les tickers, avec 300 jours de marge
    avant `start` pour calculer MM200 et momentum sans trou au début de fenêtre."""
    marge_start = (pd.Timestamp(start) - pd.Timedelta(days=430)).strftime("%Y-%m-%d")
    data = {}
    for nom, tk in tickers.items():
        try:
            h = yf.Ticker(tk).history(start=marge_start, end=end)[["High", "Low", "Close"]].dropna()
            if len(h) > 200:
                h.index = h.index.tz_localize(None)
                data[nom] = h
        except Exception:
            continue
    cac = yf.Ticker("^FCHI").history(start=marge_start, end=end)["Close"].dropna()
    cac.index = cac.index.tz_localize(None)
    return data, cac


def atr_pct(h):
    """Série ATR14 en fraction du cours (True Range lissé / clôture)."""
    prev = h["Close"].shift(1)
    tr = np.maximum(h["High"] - h["Low"],
                    np.maximum((h["High"] - prev).abs(), (h["Low"] - prev).abs()))
    return (tr.rolling(14).mean() / h["Close"]).dropna()


def score_proxy(data, atrs, date):
    """Signal proxy à la date t : momentum 60 jours, transformé en rang cross-
    sectionnel 0-100. Renvoie un snapshot {nom: {score, prix, secteur, signal,
    atr_pct}}. Aucun look-ahead : tout est lu sur les données <= date."""
    moms = {}
    for nom, h in data.items():
        clos = h["Close"][h.index <= date]
        if len(clos) <= LOOKBACK_MOM:
            continue
        m = clos.iloc[-1] / clos.iloc[-1 - LOOKBACK_MOM] - 1
        if m == m:
            moms[nom] = m
    if not moms:
        return {}
    rangs = pd.Series(moms).rank(pct=True)   # 0..1
    snap = {}
    for nom, m in moms.items():
        score = int(round(50 + 50 * rangs[nom]))       # 50..100
        a = atrs[nom][atrs[nom].index <= date]
        snap[nom] = {
            "score": score,
            "prix": float(data[nom]["Close"][data[nom].index <= date].iloc[-1]),
            "secteur": SECTEUR_PAR_VALEUR.get(nom, "?"),
            "signal": "ACHETER" if score >= SEUIL_ACHAT else ("ÉVITER" if score <= SEUIL_EVITER else "SURVEILLER"),
            "atr_pct": float(a.iloc[-1]) if len(a) else None,
        }
    return snap


def regime_a_date(cac, date):
    """'haussier' si CAC >= MM200 à la date t, 'baissier' sinon (P7)."""
    serie = cac[cac.index <= date]
    if len(serie) < 200:
        return None
    mm200 = serie.rolling(200).mean().iloc[-1]
    return "haussier" if serie.iloc[-1] >= mm200 else "baissier"


def valoriser(positions, data, date):
    """Valeur des positions à la clôture de `date` (dernier cours valide connu)."""
    tot = 0.0
    for nom, p in positions.items():
        clos = data[nom]["Close"][data[nom].index <= date]
        cours = float(clos.iloc[-1]) if len(clos) else p["prix_entree"]
        tot += p["nb"] * cours
    return tot


def simuler(bras, data, cac, atrs, jours, p):
    """Rejoue le portefeuille jour par jour. Rebalance chaque lundi. Retourne
    la courbe d'équité + des compteurs d'airbag (jours régime baissier, jours où
    P7 a bloqué des candidats, jours où P12 était actif)."""
    capital = EQUITY_DEPART
    positions = {}            # nom -> {nb, prix_entree, stop_pct, tp_pct, secteur}
    equity_curve = {}
    jours_baissier = 0
    jours_p7_bloque = 0       # bras B avait des ACHETER mais régime baissier => rien ouvert
    jours_p12_actif = 0
    pic = EQUITY_DEPART

    for date in jours:
        snap = {nom: d for nom, d in score_proxy(data, atrs, date).items()}
        if not snap:
            continue

        # 1. Sorties quotidiennes : stop / take-profit ATR (les deux bras les ont
        #    dès qu'une position a un stop ; le baseline n'en pose pas -> sortie
        #    seulement sur signal ÉVITER au rebalancement).
        for nom in list(positions.keys()):
            d = snap.get(nom)
            if not d:
                continue
            cours = d["prix"]
            pos = positions[nom]
            pnl = (cours - pos["prix_entree"]) / pos["prix_entree"]
            raison = None
            if pos["stop_pct"] and pnl <= -pos["stop_pct"]:
                raison = "stop"
            elif pos["tp_pct"] and pnl >= pos["tp_pct"]:
                raison = "tp"
            if raison:
                brut = pos["nb"] * cours
                capital += brut - frais(brut)
                del positions[nom]

        # 2. Régime + drawdown courants
        regime = regime_a_date(cac, date)
        if regime == "baissier":
            jours_baissier += 1
        equity = capital + valoriser(positions, data, date)
        pic = max(pic, equity)
        drawdown = (equity - pic) / pic if pic > 0 else 0.0
        if drawdown <= p.dd_seuil:
            jours_p12_actif += 1

        # 3. Rebalancement hebdo (lundi) : sorties sur signal + ouvertures
        if date.weekday() == 0:
            # Sorties sur signal ÉVITER (les deux bras)
            for nom in list(positions.keys()):
                if snap.get(nom, {}).get("signal") == "ÉVITER":
                    cours = snap[nom]["prix"]
                    brut = positions[nom]["nb"] * cours
                    capital += brut - frais(brut)
                    del positions[nom]

            candidats = [{"nom": n, **d} for n, d in snap.items()]
            acheteurs = [c for c in candidats if c["signal"] == "ACHETER" and c["nom"] not in positions]

            if bras == "A":
                # Baseline : toutes les ACHETER, taille fixe, aucun airbag.
                for c in acheteurs:
                    cout = int(BUDGET_FIXE / c["prix"]) * c["prix"]
                    nb = int(BUDGET_FIXE / c["prix"])
                    if nb <= 0 or capital < cout + frais(cout):
                        continue
                    capital -= cout + frais(cout)
                    positions[c["nom"]] = {"nb": nb, "prix_entree": c["prix"],
                                           "stop_pct": None, "tp_pct": None,
                                           "secteur": c["secteur"]}
            else:
                # Risk Engine : selectionner() applique P7/P9/P11/P2/P12.
                if acheteurs and regime == "baissier":
                    jours_p7_bloque += 1
                contexte = {"regime": regime, "drawdown": drawdown}
                pos_ouvertes = {n: {"secteur": pp["secteur"]} for n, pp in positions.items()}
                for dec in selectionner(candidats, pos_ouvertes, equity, contexte, p):
                    cout = dec["nb"] * dec["prix"]
                    if capital < cout + frais(cout):
                        continue
                    capital -= cout + frais(cout)
                    positions[dec["nom"]] = {"nb": dec["nb"], "prix_entree": dec["prix"],
                                             "stop_pct": dec["stop_pct"], "tp_pct": dec["tp_pct"],
                                             "secteur": dec["secteur"]}

        equity_curve[date.strftime("%Y-%m-%d")] = round(capital + valoriser(positions, data, date), 2)

    return equity_curve, {"jours_baissier": jours_baissier,
                          "jours_p7_bloque": jours_p7_bloque,
                          "jours_p12_actif": jours_p12_actif}


def stats_courbe(courbe):
    vals = list(courbe.values())
    if not vals:
        return {"n": 0}
    pic = -1e18
    maxdd = 0.0
    for v in vals:
        pic = max(pic, v)
        maxdd = min(maxdd, v / pic - 1)
    return {
        "perf_pct": round((vals[-1] / EQUITY_DEPART - 1) * 100, 2),
        "drawdown_max_pct": round(maxdd * 100, 2),
        "valeur_finale": round(vals[-1], 2),
        "n_jours": len(vals),
    }


def run_stress(nom_krach, start, end, p):
    print(f"\n### {nom_krach} ({start} -> {end}) : téléchargement...")
    data, cac = charger_donnees(CAC40, start, end)
    print(f"  {len(data)}/{len(CAC40)} valeurs avec assez d'historique")
    atrs = {nom: atr_pct(h) for nom, h in data.items()}

    # Jours de bourse dans la fenêtre (bornée après `start`)
    ref = cac[(cac.index >= pd.Timestamp(start)) & (cac.index <= pd.Timestamp(end))].index
    jours = [d for d in ref]

    ca, ma = simuler("A", data, cac, atrs, jours, p)
    cb, mb = simuler("B", data, cac, atrs, jours, p)
    sa, sb = stats_courbe(ca), stats_courbe(cb)

    print(f"  Régime baissier : {mb['jours_baissier']}/{len(jours)} jours")
    print(f"  P7 (ouvertures bloquées en baissier) : {mb['jours_p7_bloque']} rebalancement(s)")
    print(f"  P12 (frein DD actif)                 : {mb['jours_p12_actif']} jour(s)")
    print(f"  {'':22}{'A. Baseline':>15}{'B. RiskEngine':>15}")
    print(f"  {'Performance':22}{str(sa['perf_pct'])+' %':>15}{str(sb['perf_pct'])+' %':>15}")
    print(f"  {'Drawdown max':22}{str(sa['drawdown_max_pct'])+' %':>15}{str(sb['drawdown_max_pct'])+' %':>15}")

    return {"fenetre": [start, end], "n_valeurs": len(data), "n_jours": len(jours),
            "airbags": mb, "baseline_A": sa, "risk_engine_B": sb,
            "courbe_A": ca, "courbe_B": cb}


if __name__ == "__main__":
    p = ParamsRisque()
    resultats = {
        "date_test": datetime.date.today().isoformat(),
        "params": p.__dict__,
        "note_methode": "Signal PROXY momentum identique aux deux bras : ce test isole "
                        "l'effet des airbags P7/P12, PAS la qualité du signal (Piste 2). "
                        "Simulation de portefeuille jour par jour, rebalance hebdo, sans look-ahead.",
        "krachs": {},
    }
    for nom_krach, s, e in [("COVID 2020", "2020-01-02", "2020-07-31"),
                            ("Bear taux 2022", "2022-01-03", "2022-10-31")]:
        resultats["krachs"][nom_krach] = run_stress(nom_krach, s, e, p)

    with open("stress_test_krach_resultats.json", "w", encoding="utf-8") as f:
        json.dump(resultats, f, ensure_ascii=False, indent=2)
    print("\nRésultats sauvegardés dans stress_test_krach_resultats.json")
