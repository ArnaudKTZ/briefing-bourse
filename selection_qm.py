#!/usr/bin/env python3
"""
Sélection Qualité-Momentum (Piste 2, 23/08) — le nouveau cerveau de choix.

Pourquoi ce module existe : 2 mois de mesures + un papier académique ont établi
que le score V4 (oscillateur RSI/MACD/Bollinger) ne prédit pas la direction et
perd net de frais. On arrête de jouer au voyant. On le remplace par deux choses
qui, elles, ont une vraie base : acheter ce qui MONTE DÉJÀ durablement (momentum,
effet documenté par AQR) ET seulement des entreprises SAINES (qualité value, à la
Buffett). La sélection nourrit ensuite le Risk Engine (sizing, stops, top-3), qui
lui a fait ses preuves (forward +2,15 pts + stress-test krach 2020).

Deux fonctions pures, sans I/O, testables :
  - score_momentum : rang cross-sectionnel du momentum 12-1 mois (standard : on
    saute le dernier mois pour éviter le retournement court terme). Sortie 50-100.
  - porte_qualite  : filtre DUR sur des fondamentaux (ROE, marge, dette). Un titre
    qui échoue la porte n'est jamais acheté, quel que soit son momentum.

PARAMÈTRES FIGÉS A PRIORI (standards littérature value/momentum), zéro
optimisation sur nos données. La sélection passe la recette (selection_backtest.py)
avant toute intégration au live.

Note honnêteté data : porte_qualite lit les fondamentaux COURANTS (yfinance .info).
Ils ne sont pas historisés proprement, donc la porte ne se backteste PAS sans biais
de look-ahead. Elle se prouve en FORWARD (track record virtuel), comme le Risk
Engine le 22/07. Le momentum, lui, se backteste (prix passés disponibles).
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class ParamsSelection:
    mom_lookback: int   = 252   # 12 mois de bourse
    mom_skip: int       = 21    # on ignore le dernier mois (reversal court terme)
    score_achat: int    = 80    # score >= 80 => éligible ACHETER (top du momentum)
    # Porte qualité (seuils value standard) :
    roe_min: float      = 0.10  # rentabilité des fonds propres >= 10%
    marge_min: float    = 0.0   # marge opérationnelle strictement positive
    dette_max: float    = 150.0 # debtToEquity yfinance (~150 = 1,5x fonds propres)


def momentum_brut(closes: pd.Series, date, p: ParamsSelection):
    """Momentum 12-1 mois à la date t : rendement entre t-12mois et t-1mois.
    Aucun look-ahead (données <= date). Renvoie None si historique insuffisant."""
    serie = closes[closes.index <= date]
    if len(serie) <= p.mom_lookback:
        return None
    recent = serie.iloc[-1 - p.mom_skip]          # il y a ~1 mois
    ancien = serie.iloc[-1 - p.mom_lookback]       # il y a ~12 mois
    if ancien <= 0:
        return None
    return recent / ancien - 1


def score_momentum(moms: dict, p: ParamsSelection):
    """Transforme un dict {nom: momentum_brut} en scores 50-100 par rang
    cross-sectionnel (le meilleur momentum du jour = 100)."""
    valides = {n: m for n, m in moms.items() if m is not None and m == m}
    if not valides:
        return {}
    rangs = pd.Series(valides).rank(pct=True)      # 0..1
    return {n: int(round(50 + 50 * rangs[n])) for n in valides}


def porte_qualite(info: dict, secteur: str, p: ParamsSelection):
    """Filtre dur de qualité. Renvoie (passe: bool, raisons: list).
    Les banques/finance sont exemptées du critère de dette (le debtToEquity n'a
    pas le même sens pour une banque). Un champ manquant = échec prudent, sauf
    l'exemption bancaire."""
    raisons = []
    roe = info.get("returnOnEquity")
    if roe is None or roe < p.roe_min:
        raisons.append(f"ROE {roe} < {p.roe_min}")
    marge = info.get("operatingMargins")
    if marge is None or marge <= p.marge_min:
        raisons.append(f"marge {marge} <= {p.marge_min}")
    est_banque = secteur == "Banques/Finance"
    if not est_banque:
        dte = info.get("debtToEquity")
        if dte is None or dte > p.dette_max:
            raisons.append(f"dette {dte} > {p.dette_max}")
    return (len(raisons) == 0, raisons)


def snapshot_selection(closes_par_nom: dict, atr_par_nom: dict, secteur_par_nom: dict,
                       date, p: ParamsSelection, infos_par_nom: dict = None):
    """Construit le snapshot {nom: {score, prix, secteur, signal, atr_pct}} attendu
    par le Risk Engine (selectionner()).

    - Momentum toujours appliqué (rang cross-sectionnel).
    - Porte qualité appliquée seulement si infos_par_nom est fourni (mode LIVE).
      En mode backtest (infos_par_nom=None), la porte est neutralisée : on ne peut
      pas juger la qualité passée sans look-ahead.
    - signal = ACHETER si score>=score_achat ET qualité OK ; sinon SURVEILLER.
      On ne produit pas de ÉVITER ici : la sortie est gérée par le Risk Engine
      (stop/TP ATR) et par la chute du momentum au rebalancement suivant.
    """
    moms = {n: momentum_brut(s, date, p) for n, s in closes_par_nom.items()}
    scores = score_momentum(moms, p)
    snap = {}
    for nom, score in scores.items():
        serie = closes_par_nom[nom][closes_par_nom[nom].index <= date]
        if serie.empty:
            continue
        secteur = secteur_par_nom.get(nom, "?")
        qualite_ok = True
        if infos_par_nom is not None:
            qualite_ok, _ = porte_qualite(infos_par_nom.get(nom, {}), secteur, p)
        a = atr_par_nom.get(nom)
        atr_val = None
        if a is not None and len(a[a.index <= date]):
            atr_val = float(a[a.index <= date].iloc[-1])
        snap[nom] = {
            "score": score,
            "prix": float(serie.iloc[-1]),
            "secteur": secteur,
            "signal": "ACHETER" if (score >= p.score_achat and qualite_ok) else "SURVEILLER",
            "atr_pct": atr_val,
            "momentum": round(moms[nom] * 100, 1) if moms[nom] is not None else None,
        }
    return snap
