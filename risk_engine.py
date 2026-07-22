#!/usr/bin/env python3
"""
Risk Engine — le moteur de gestion du risque (Phase 1 V5).

Origine : la recherche sur les grands traders (15/07) a montré que le trou
béant du système n'était pas la sélection (39 valeurs scorées 4x/jour) mais la
GESTION : taille, sortie, défense. Les maîtres parlent de ça, jamais de
prédiction. Le bilan du 22/07 l'a confirmé chiffres en main : le score V4 a
enfin un pouvoir de classement (IC +0,077, exploitable avant frais) mais l'edge
brut (~+0,1 pt) est dévoré par le péage de ~1%. Conclusion : ne pas reconstruire
le score, mais prendre MOINS de trades, plus CIBLÉS, mieux DIMENSIONNÉS.

Ce module est une FONCTION PURE (pas d'I/O, pas d'appel marché). Il prend des
signaux candidats + l'état du portefeuille + le contexte de marché, et rend des
décisions de position filtrées et dimensionnées, en appliquant les 6 principes
que le système n'avait pas (P1, P2, P5, P9, P11, P12 du dossier des maîtres) :

  P1  risque max par position   : perte au stop <= RISK_PCT % de l'équité
  P2  taille par volatilité     : position € = budget_risque / distance_au_stop
                                   (petite si la valeur est nerveuse, l'unité "N"
                                    des Turtles)
  P5  asymétrie exigée          : take-profit / stop >= MIN_RR (défaut 2:1)
  P9  concentration conviction  : ne garder que les TOP_K meilleurs scores du
                                   jour (moins de trades = moins de frais, et on
                                   ne prend que les plus fortes convictions)
  P11 limite sectorielle        : au plus MAX_PAR_SECTEUR positions par secteur
                                   (pas 3 banques corrélées en même temps)
  P12 frein après drawdown      : si le drawdown du portefeuille dépasse un seuil,
                                   les tailles sont réduites (facteur < 1)

RIEN N'EST FIGÉ EN PROD PAR CE FICHIER. Il est d'abord passé à la recette
(risk_engine_backtest.py) avant toute intégration au scoring live. Les
paramètres ci-dessous sont des standards de la LITTÉRATURE (Turtles, Minervini,
PTJ), choisis A PRIORI, jamais optimisés sur nos données.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ParamsRisque:
    risk_pct: float        = 0.01   # P1 : 1% de l'équité risqué par position (Turtles : 2% max, on est prudent)
    stop_atr_mult: float   = 2.0    # stop placé à 2×ATR sous l'entrée (standard trend-following)
    min_rr: float          = 2.0    # P5 : ratio take-profit / stop minimal (Minervini/PTJ)
    top_k: int             = 3      # P9 : nombre max de nouvelles positions par jour, les meilleures
    max_par_secteur: int   = 2      # P11 : positions simultanées max par secteur
    dd_seuil: float        = -0.10  # P12 : au-delà de -10% de drawdown, on réduit
    dd_facteur: float      = 0.5    # ... les tailles sont divisées par 2
    poids_max: float       = 0.25   # garde-fou : une position ne dépasse jamais 25% de l'équité
    score_min: int         = 80     # seuil d'éligibilité (inchangé vs le scoring actuel)


def stop_et_cible(prix, atr_pct, p: ParamsRisque):
    """Distances de stop et de take-profit (en fraction du prix), depuis l'ATR%.
    Retourne (stop_pct, tp_pct) ou (None, None) si l'ATR est inexploitable."""
    if atr_pct is None or atr_pct <= 0:
        return None, None
    stop_pct = p.stop_atr_mult * atr_pct
    tp_pct   = p.min_rr * stop_pct       # asymétrie garantie par construction (P5)
    return stop_pct, tp_pct


def taille_position(equity, prix, stop_pct, en_drawdown, p: ParamsRisque):
    """P1 + P2 : montant € tel que la perte au stop = risk_pct de l'équité,
    plafonné à poids_max de l'équité, réduit si le portefeuille est en drawdown
    profond (P12). Retourne (montant_eur, nb_actions)."""
    if stop_pct is None or stop_pct <= 0 or prix <= 0:
        return 0.0, 0
    budget_risque = equity * p.risk_pct
    if en_drawdown:
        budget_risque *= p.dd_facteur          # P12 : frein
    montant = budget_risque / stop_pct          # P2 : plus l'actif est volatil, plus la position est petite
    montant = min(montant, equity * p.poids_max)  # garde-fou concentration
    nb = int(montant / prix)
    return round(nb * prix, 2), nb


def selectionner(candidats, positions_ouvertes, equity, contexte, p: ParamsRisque):
    """Cœur du Risk Engine. Rend la liste des décisions d'ouverture du jour.

    candidats : liste de dicts {nom, score, prix, secteur, signal, atr_pct}
    positions_ouvertes : dict {nom: {secteur: ...}} des positions déjà tenues
    equity : valeur totale du portefeuille (capital + positions)
    contexte : {regime: "haussier"|"baissier"|None, drawdown: float<=0}
    Retourne une liste de décisions dimensionnées, potentiellement vide.
    """
    # P7 (filtre de régime) : en marché baissier confirmé, on n'ouvre RIEN.
    # Le cash est une position (principe P8). C'est la protection qu'on n'a
    # jamais eue et qui compte le jour de la tempête.
    if contexte.get("regime") == "baissier":
        return []

    en_drawdown = contexte.get("drawdown", 0.0) <= p.dd_seuil

    # Éligibles : signal ACHETER, score suffisant, pas déjà en portefeuille,
    # ATR exploitable, et asymétrie réalisable.
    eligibles = []
    for c in candidats:
        if c.get("signal") != "ACHETER" or c.get("score", 0) < p.score_min:
            continue
        if c["nom"] in positions_ouvertes:
            continue
        stop_pct, tp_pct = stop_et_cible(c["prix"], c.get("atr_pct"), p)
        if stop_pct is None:
            continue
        eligibles.append({**c, "stop_pct": stop_pct, "tp_pct": tp_pct})

    # P9 : concentration sur les plus fortes convictions (tri par score décroissant).
    eligibles.sort(key=lambda c: c["score"], reverse=True)

    # P11 : compteur d'exposition sectorielle, initialisé avec les positions tenues.
    par_secteur = {}
    for pos in positions_ouvertes.values():
        s = pos.get("secteur", "?")
        par_secteur[s] = par_secteur.get(s, 0) + 1

    decisions = []
    for c in eligibles:
        if len(decisions) >= p.top_k:                 # P9 : au plus top_k par jour
            break
        s = c.get("secteur", "?")
        if par_secteur.get(s, 0) >= p.max_par_secteur:  # P11 : plafond secteur
            continue
        montant, nb = taille_position(equity, c["prix"], c["stop_pct"], en_drawdown, p)
        if nb <= 0:
            continue
        par_secteur[s] = par_secteur.get(s, 0) + 1
        decisions.append({
            "nom":       c["nom"],
            "secteur":   s,
            "score":     c["score"],
            "prix":      c["prix"],
            "nb":        nb,
            "montant":   montant,
            "stop_pct":  round(c["stop_pct"], 4),
            "tp_pct":    round(c["tp_pct"], 4),
            "en_drawdown": en_drawdown,
        })
    return decisions
