#!/usr/bin/env python3
"""
Agent Bourse V5 — Le meilleur agent trader IA
- Données temps réel Yahoo Finance
- RSI, MACD, Stochastique, ATR, Bollinger, MA20/50/200
- Patterns de bougies japonaises
- Score de confiance algorithmique
- Volumes anormaux
- Supports / Résistances (Pivot Points)
- Proximité 52 semaines haut/bas
- Momentum sectoriel
- Beta vs CAC 40
- Calendrier économique
- Auto-amélioration avec mémoire longue
- Simulation portefeuille virtuel
"""

import smtplib
import datetime
import os
import json
import re
import math
import urllib.request
import zoneinfo

TZ_PARIS = zoneinfo.ZoneInfo("Europe/Paris")
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import anthropic
import yfinance as yf
import pandas as pd
import numpy as np

try:
    from ta.momentum import RSIIndicator, StochasticOscillator
    from ta.trend import MACD, SMAIndicator, EMAIndicator
    from ta.volatility import BollingerBands, AverageTrueRange
    TA_DISPONIBLE = True
except ImportError:
    TA_DISPONIBLE = False

# ─── CONFIGURATION ────────────────────────────────────────────────────────────

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "COLLE_TA_CLE_ICI")
ZOHO_EMAIL        = os.environ.get("ZOHO_EMAIL", "Arnaud.kuntz@zoho.eu")
ZOHO_PASSWORD     = os.environ.get("ZOHO_PASSWORD", "")
ZOHO_SMTP         = "smtp.zoho.eu"
ZOHO_PORT         = 587

_dest_env = os.environ.get("DESTINATAIRES", "")
DESTINATAIRES = [d.strip() for d in _dest_env.split(",") if d.strip()] if _dest_env else []

FICHIER_PERFORMANCE  = "performance.json"
FICHIER_PORTEFEUILLE = "portefeuille_virtuel.json"
FICHIER_INTRADAY     = "intraday_scores.json"

_persistance_cache        = {}  # chargé une fois au démarrage du main
_poids_indicateurs_cache  = {}  # poids appris par indicateur/secteur
_rapport_news_cache       = {}  # rapport de l'agent news (rapport_news.json)
_rapport_espion_cache     = {}  # rapport de l'agent espion (rapport_espion.json)


def charger_persistance_intraday():
    """
    Lit intraday_scores.json et calcule pour chaque valeur :
    - combien de snapshots hier étaient ACHETER / ÉVITER
    - si le score montait ou descendait en cours de journée
    - le gap d'ouverture moyen
    Retourne un dict {nom: {bonus: int, label: str}}
    """
    if not os.path.exists(FICHIER_INTRADAY):
        return {}

    with open(FICHIER_INTRADAY, "r") as f:
        data = json.load(f)

    hier = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    # Remonte jusqu'à 3 jours en arrière pour trouver le dernier jour de bourse
    for delta in range(1, 5):
        candidate = (datetime.date.today() - datetime.timedelta(days=delta)).isoformat()
        if candidate in data:
            hier = candidate
            break
    else:
        return {}

    snapshots = data.get(hier, {})
    if not snapshots:
        return {}

    heures = sorted(snapshots.keys())
    persistance = {}

    for nom in CAC40:
        scores_jour = []
        signaux     = []
        for h in heures:
            d = snapshots[h].get(nom)
            if d:
                scores_jour.append(d["score"])
                signaux.append(d["signal"])

        if not scores_jour:
            continue

        nb_acheter = signaux.count("ACHETER")
        nb_eviter  = signaux.count("ÉVITER")
        total      = len(signaux)

        # Momentum du score (montée ou descente en journée)
        tendance_score = scores_jour[-1] - scores_jour[0] if len(scores_jour) > 1 else 0

        bonus = 0
        label = ""

        # Signal persistant toute la journée = fort
        if nb_acheter == total:
            bonus += 12
            label = "Signal ACHETER persistant toute la journée"
        elif nb_acheter >= total * 0.66:
            bonus += 6
            label = f"Signal ACHETER majoritaire ({nb_acheter}/{total} snapshots)"
        elif nb_eviter == total:
            bonus -= 12
            label = "Signal ÉVITER persistant toute la journée"
        elif nb_eviter >= total * 0.66:
            bonus -= 6
            label = f"Signal ÉVITER majoritaire ({nb_eviter}/{total} snapshots)"

        # Momentum du score en hausse = confirmation
        if tendance_score > 10:
            bonus += 5
            label += " | Score en hausse hier"
        elif tendance_score < -10:
            bonus -= 5
            label += " | Score en baisse hier"

        persistance[nom] = {"bonus": bonus, "label": label.strip(" |"), "scores_hier": scores_jour}

    return persistance

# ─── CAC 40 TICKERS ───────────────────────────────────────────────────────────

from marche_config import CAC40

SECTEURS = {
    "Luxe":              ["LVMH", "Hermès", "Kering", "L'Oréal", "Pernod Ricard"],
    "Énergie":           ["TotalEnergies", "Engie"],
    "Industrie/Défense": ["Airbus", "Schneider Electric", "Safran", "Vinci", "Saint-Gobain",
                          "Legrand", "ArcelorMittal", "Alstom", "Forvia", "Bouygues", "Thales"],
    "Banques/Finance":   ["BNP Paribas", "Société Générale", "Eurazeo"],
    "Santé":             ["Sanofi", "Air Liquide", "Eurofins Scientific"],
    "Tech":              ["Capgemini", "Dassault Systèmes", "STMicroelectronics", "Worldline"],
    "Télécom/Média":     ["Orange", "Vivendi", "Publicis", "Teleperformance"],
    "Conso/Autre":       ["Danone", "Michelin", "Renault", "Stellantis", "Accor", "Edenred", "Veolia"],
}


# ─── FONDAMENTAUX ─────────────────────────────────────────────────────────────

def recuperer_fondamentaux(ticker_obj):
    """Récupère PER, P/B, croissance CA, dette/fonds propres, marge nette via yfinance."""
    try:
        info = ticker_obj.info
        per         = info.get("trailingPE") or info.get("forwardPE")
        pb          = info.get("priceToBook")
        rev_growth  = info.get("revenueGrowth")
        debt_equity = info.get("debtToEquity")
        marge_nette = info.get("profitMargins")
        per         = round(per, 1) if per else None
        pb          = round(pb, 2) if pb else None
        rev_growth  = round(rev_growth * 100, 1) if rev_growth else None
        debt_equity = round(debt_equity, 1) if debt_equity else None
        marge_nette = round(marge_nette * 100, 1) if marge_nette else None
        return {"per": per, "pb": pb, "rev_growth": rev_growth, "debt_equity": debt_equity, "marge_nette": marge_nette}
    except Exception:
        return {}


def scorer_fondamentaux(fond):
    """Retourne un bonus/malus (-15 à +15) basé sur les fondamentaux."""
    bonus = 0
    per = fond.get("per")
    if per:
        if per < 12:   bonus += 8
        elif per < 20: bonus += 4
        elif per > 40: bonus -= 8
        elif per > 30: bonus -= 4

    rev = fond.get("rev_growth")
    if rev is not None:
        if rev > 15:   bonus += 6
        elif rev > 5:  bonus += 3
        elif rev < -5: bonus -= 6
        elif rev < 0:  bonus -= 3

    de = fond.get("debt_equity")
    if de is not None:
        if de < 30:    bonus += 4
        elif de > 150: bonus -= 6
        elif de > 100: bonus -= 3

    marge = fond.get("marge_nette")
    if marge is not None:
        if marge > 20:  bonus += 4
        elif marge > 10: bonus += 2
        elif marge < 0: bonus -= 6

    pb = fond.get("pb")
    if pb is not None:
        if pb < 1.0:   bonus += 5   # sous la valeur comptable = décote
        elif pb < 2.0: bonus += 2
        elif pb > 8.0: bonus -= 4   # trop cher par rapport aux actifs

    return max(-20, min(20, bonus))


# ─── FEAR & GREED + CONSENSUS ANALYSTES ───────────────────────────────────────

def recuperer_fear_greed():
    """
    Fear & Greed Index via alternative.me (gratuit, pas de clé API).
    0-24 = Extreme Fear, 25-44 = Fear, 45-55 = Neutral,
    56-75 = Greed, 76-100 = Extreme Greed.
    Retourne un dict avec score, label et malus (toujours 0 depuis l'audit du 26/06).
    Affiché comme info contextuelle, mais N'IMPACTE PLUS le scoring : l'audit sur 8 ans
    (audit_malus_macro.py) a montré que ce F&G (indice crypto) n'a aucun pouvoir prédictif
    sur le CAC et que la peur extrême précède des rendements légèrement supérieurs à la
    moyenne — le malus défensif était injustifié, voire à contre-sens.
    """
    try:
        url = "https://api.alternative.me/fng/?limit=1"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read())
        score = int(data["data"][0]["value"])
        label = data["data"][0]["value_classification"]
        malus = 0   # retiré suite à l'audit : aucun edge prouvé
        return {"score": score, "label": label, "malus": malus}
    except Exception:
        return {"score": None, "label": "N/A", "malus": 0}


def scorer_consensus_analystes(ticker_obj, cours):
    """
    Analyse le consensus des analystes via yfinance.
    recommendationMean : 1=Strong Buy, 3=Hold, 5=Strong Sell
    upside potentiel = (targetMeanPrice - cours) / cours * 100
    Retourne bonus -12 à +12.
    """
    try:
        info = ticker_obj.info
        rec  = info.get("recommendationMean")
        nb   = info.get("numberOfAnalystOpinions", 0)
        cible = info.get("targetMeanPrice")

        if not rec or not nb or nb < 3:
            return 0, {}

        bonus = 0
        if rec <= 1.5:   bonus += 8    # Strong Buy unanime
        elif rec <= 2.2: bonus += 5    # Buy
        elif rec <= 2.8: bonus += 2    # Buy modéré
        elif rec >= 4.0: bonus -= 8    # Sell
        elif rec >= 3.5: bonus -= 4    # Underperform

        if cible and cours:
            upside = (cible - cours) / cours * 100
            if upside > 25:    bonus += 5
            elif upside > 15:  bonus += 3
            elif upside > 5:   bonus += 1
            elif upside < -10: bonus -= 4
            elif upside < 0:   bonus -= 2

        return max(-12, min(12, bonus)), {
            "rec_score": round(float(rec), 2),
            "nb_analystes": int(nb),
            "cible_moy": round(float(cible), 2) if cible else None,
            "upside_pct": round(float(upside), 1) if cible and cours else None,
        }
    except Exception:
        return 0, {}


# ─── ACTUALITÉS EN TEMPS RÉEL ─────────────────────────────────────────────────

def recuperer_news_sentiment(ticker_obj, nom):
    """Récupère les titres de news via yfinance et calcule un sentiment simple."""
    try:
        news_raw = ticker_obj.news or []
        titres = []
        for n in news_raw[:5]:
            t = n.get("content", {}).get("title", "") or n.get("title", "")
            if t:
                titres.append(t)

        if not titres:
            return {"news": [], "sentiment": 0}

        mots_positifs = ["hausse", "croissance", "record", "contrat", "acquisition", "bénéfice",
                         "surpasse", "relève", "dividende", "accord", "partenariat", "commande",
                         "beat", "profit", "gain", "rise", "up", "growth", "wins", "strong"]
        mots_negatifs = ["baisse", "perte", "avertissement", "profit warning", "recul", "abandon",
                         "enquête", "fraude", "sanction", "licenciement", "coupe", "chute",
                         "miss", "loss", "down", "cut", "weak", "fall", "slump", "warning"]

        score_sent = 0
        for titre in titres:
            t_low = titre.lower()
            for m in mots_positifs:
                if m in t_low: score_sent += 1
            for m in mots_negatifs:
                if m in t_low: score_sent -= 1

        sentiment = max(-3, min(3, score_sent))
        return {"news": titres[:3], "sentiment": sentiment}
    except Exception:
        return {"news": [], "sentiment": 0}


# ─── CALENDRIER RÉSULTATS ─────────────────────────────────────────────────────

def verifier_resultats_proches(ticker_obj):
    """Retourne True si des résultats sont attendus dans les 3 prochains jours."""
    try:
        cal = ticker_obj.calendar
        if cal is None:
            return False
        today = datetime.date.today()
        if hasattr(cal, 'get'):
            date_res = cal.get("Earnings Date")
            if date_res is None:
                return False
            if hasattr(date_res, '__iter__') and not isinstance(date_res, str):
                date_res = list(date_res)[0] if date_res else None
            if date_res:
                if hasattr(date_res, 'date'):
                    date_res = date_res.date()
                delta = (date_res - today).days
                return 0 <= delta <= 3
    except Exception:
        pass
    return False


# ─── AUTO-APPRENTISSAGE PAR INDICATEUR ────────────────────────────────────────

def charger_poids_indicateurs():
    """Charge les poids appris par indicateur et par secteur depuis performance.json."""
    if not os.path.exists(FICHIER_PERFORMANCE):
        return {}
    try:
        with open(FICHIER_PERFORMANCE, "r", encoding="utf-8") as f:
            perf = json.load(f)
        return perf.get("poids_indicateurs", {})
    except Exception:
        return {}


def calculer_bonus_indicateurs_appris(d, poids):
    """Applique les poids appris par secteur pour ajuster le score."""
    if not poids:
        return 0
    secteur = d.get("secteur_nom", "")
    poids_secteur = poids.get(secteur, {})
    if not poids_secteur:
        return 0

    bonus = 0
    # RSI : si historiquement fiable dans ce secteur, on l'amplifie
    fiab_rsi = poids_secteur.get("rsi_fiabilite", 0.5)
    if d.get("rsi") and fiab_rsi > 0.6:
        rsi = d["rsi"]
        if rsi < 35:   bonus += round((fiab_rsi - 0.5) * 20)
        elif rsi > 65: bonus -= round((fiab_rsi - 0.5) * 20)

    # MACD : idem
    fiab_macd = poids_secteur.get("macd_fiabilite", 0.5)
    if d.get("macd") and fiab_macd > 0.6:
        if d["macd"] == "haussier":   bonus += round((fiab_macd - 0.5) * 10)
        elif d["macd"] == "baissier": bonus -= round((fiab_macd - 0.5) * 10)

    return max(-10, min(10, bonus))


def mettre_a_jour_poids_indicateurs(perf, historique_indicateurs):
    """Met à jour la fiabilité de chaque indicateur par secteur dans performance.json."""
    if "poids_indicateurs" not in perf:
        perf["poids_indicateurs"] = {}

    for secteur, indicateurs in historique_indicateurs.items():
        if secteur not in perf["poids_indicateurs"]:
            perf["poids_indicateurs"][secteur] = {}

        for ind_nom, stats in indicateurs.items():
            total   = stats.get("total", 0)
            corrects = stats.get("corrects", 0)
            if total >= 5:
                fiabilite = round(corrects / total, 3)
                perf["poids_indicateurs"][secteur][f"{ind_nom}_fiabilite"] = fiabilite

    return perf


# ─── CALENDRIER BCE/FED ───────────────────────────────────────────────────────

# Dates des annonces de taux BCE et Fed 2026 (J à 0h = jour de l'annonce)
DATES_BANQUES_CENTRALES = [
    # BCE 2026
    "2026-01-30", "2026-03-06", "2026-04-17", "2026-06-05",
    "2026-07-23", "2026-09-10", "2026-10-29", "2026-12-17",
    # Fed (FOMC) 2026
    "2026-01-28", "2026-03-18", "2026-05-06", "2026-06-17",
    "2026-07-29", "2026-09-16", "2026-11-04", "2026-12-16",
]

def verifier_annonce_banque_centrale():
    """
    Retourne (True, label) si une annonce BCE ou Fed est dans les 48h.
    Applique un malus de -15 sur tous les scores : volatilité imprévisible.
    """
    today = datetime.date.today()
    for d_str in DATES_BANQUES_CENTRALES:
        d = datetime.date.fromisoformat(d_str)
        delta = (d - today).days
        if 0 <= delta <= 2:
            label = "BCE" if int(d_str[5:7]) in [1,3,4,6,7,9,10,12] else "Fed"
            return True, f"Annonce {label} dans {delta}j ({d_str})"
    return False, ""


# ─── INDICATEURS AVANCÉS ──────────────────────────────────────────────────────

def detecter_divergence_rsi(hist, rsi_series):
    """
    Divergence haussière : prix fait un nouveau bas mais RSI ne confirme pas (= retournement haussier).
    Divergence baissière : prix fait un nouveau haut mais RSI ne confirme pas (= retournement baissier).
    Regarde les 20 dernières séances.
    Retourne : "haussiere", "baissiere" ou None
    """
    try:
        if len(hist) < 20 or len(rsi_series) < 20:
            return None
        close = hist["Close"].tail(20).values
        rsi   = rsi_series.tail(20).values

        prix_min_idx = close.argmin()
        prix_max_idx = close.argmax()

        # Divergence haussière : dernier prix < prix min précédent, mais RSI dernier > RSI au min précédent
        if prix_min_idx < len(close) - 3:
            if close[-1] <= close[prix_min_idx] and rsi[-1] > rsi[prix_min_idx] + 3:
                return "haussiere"

        # Divergence baissière : dernier prix >= prix max précédent, mais RSI dernier < RSI au max précédent
        if prix_max_idx < len(close) - 3:
            if close[-1] >= close[prix_max_idx] and rsi[-1] < rsi[prix_max_idx] - 3:
                return "baissiere"
    except Exception:
        pass
    return None


def detecter_compression_bollinger(hist):
    """
    Compression Bollinger : largeur des bandes < 5% du prix moyen sur 20j.
    Signale une explosion de volatilité imminente (direction inconnue).
    Retourne True si compression détectée.
    """
    try:
        close = hist["Close"]
        boll  = BollingerBands(close=close, window=20, window_dev=2)
        haut  = boll.bollinger_hband().iloc[-1]
        bas   = boll.bollinger_lband().iloc[-1]
        mid   = boll.bollinger_mavg().iloc[-1]
        largeur_pct = (haut - bas) / mid * 100 if mid > 0 else 100
        return largeur_pct < 4.0
    except Exception:
        return False


def calculer_pente_ma200(hist):
    """
    Pente de la MA200 sur les 20 derniers jours.
    Retourne "haussiere", "baissiere" ou "neutre".
    Une MA200 qui monte = tendance de fond haussière (signal de qualité).
    """
    try:
        if len(hist) < 220:
            return "neutre"
        close = hist["Close"]
        ma200 = SMAIndicator(close=close, window=200).sma_indicator()
        val_actuelle = ma200.iloc[-1]
        val_20j      = ma200.iloc[-20]
        pente_pct    = (val_actuelle - val_20j) / val_20j * 100
        if pente_pct > 0.5:   return "haussiere"
        elif pente_pct < -0.5: return "baissiere"
        else:                  return "neutre"
    except Exception:
        return "neutre"


def calculer_momentum_multitimeframe(hist):
    """
    Performance sur 1j, 5j, 20j, 60j.
    Convergence = tous les timeframes dans le même sens = signal fort.
    Retourne dict + bonus_convergence (-10 à +10).
    """
    try:
        close = hist["Close"]
        n = len(close)
        p1j  = round((close.iloc[-1] / close.iloc[-2]  - 1) * 100, 2) if n >= 2  else None
        p5j  = round((close.iloc[-1] / close.iloc[-5]  - 1) * 100, 2) if n >= 5  else None
        p20j = round((close.iloc[-1] / close.iloc[-20] - 1) * 100, 2) if n >= 20 else None
        p60j = round((close.iloc[-1] / close.iloc[-60] - 1) * 100, 2) if n >= 60 else None

        perfs = [p for p in [p1j, p5j, p20j, p60j] if p is not None]
        haussieres = sum(1 for p in perfs if p > 0)
        baissiers  = sum(1 for p in perfs if p < 0)

        bonus = 0
        if haussieres == len(perfs) and len(perfs) >= 3:
            bonus = 10   # tous les timeframes haussiers = conviction maximale
        elif haussieres >= 3:
            bonus = 5
        elif baissiers == len(perfs) and len(perfs) >= 3:
            bonus = -10
        elif baissiers >= 3:
            bonus = -5

        return {"p1j": p1j, "p5j": p5j, "p20j": p20j, "p60j": p60j, "bonus_convergence": bonus}
    except Exception:
        return {"bonus_convergence": 0}


# ─── PATTERNS BOUGIES JAPONAISES ─────────────────────────────────────────────

def detecter_patterns(hist):
    """Détecte les patterns de bougies japonaises sur les 3 dernières bougies."""
    if len(hist) < 3:
        return []

    patterns = []
    o  = hist["Open"].values
    h  = hist["High"].values
    l  = hist["Low"].values
    c  = hist["Close"].values

    # Dernière bougie
    body     = abs(c[-1] - o[-1])
    range_   = h[-1] - l[-1]
    upper_sh = h[-1] - max(c[-1], o[-1])
    lower_sh = min(c[-1], o[-1]) - l[-1]
    bullish  = c[-1] > o[-1]

    if range_ == 0:
        return patterns

    # Doji : corps très petit
    if body / range_ < 0.1:
        patterns.append("Doji (indécision)")

    # Marteau (bullish) : longue mèche basse, petit corps en haut
    if lower_sh > 2 * body and upper_sh < body * 0.5 and bullish:
        patterns.append("Marteau (bullish)")

    # Shooting Star (bearish) : longue mèche haute, petit corps en bas
    if upper_sh > 2 * body and lower_sh < body * 0.5 and not bullish:
        patterns.append("Shooting Star (bearish)")

    # Englobante haussière : bougie verte qui englobe la rouge précédente
    if (c[-1] > o[-1] and c[-2] < o[-2] and
            c[-1] > o[-2] and o[-1] < c[-2]):
        patterns.append("Englobante haussière (bullish)")

    # Englobante baissière
    if (c[-1] < o[-1] and c[-2] > o[-2] and
            c[-1] < o[-2] and o[-1] > c[-2]):
        patterns.append("Englobante baissière (bearish)")

    # Étoile du matin (Morning Star) : 3 bougies
    if (c[-3] < o[-3] and
            abs(c[-2] - o[-2]) < (h[-2] - l[-2]) * 0.3 and
            c[-1] > o[-1] and c[-1] > (o[-3] + c[-3]) / 2):
        patterns.append("Étoile du matin (bullish fort)")

    # Étoile du soir (Evening Star)
    if (c[-3] > o[-3] and
            abs(c[-2] - o[-2]) < (h[-2] - l[-2]) * 0.3 and
            c[-1] < o[-1] and c[-1] < (o[-3] + c[-3]) / 2):
        patterns.append("Étoile du soir (bearish fort)")

    # Trois soldats blancs
    if (c[-3] > o[-3] and c[-2] > o[-2] and c[-1] > o[-1] and
            c[-1] > c[-2] > c[-3]):
        patterns.append("3 soldats blancs (bullish fort)")

    # Trois corbeaux noirs
    if (c[-3] < o[-3] and c[-2] < o[-2] and c[-1] < o[-1] and
            c[-1] < c[-2] < c[-3]):
        patterns.append("3 corbeaux noirs (bearish fort)")

    return patterns


# ─── SCORE DE CONFIANCE ───────────────────────────────────────────────────────

# Poids News et Espion NEUTRALISÉS le 02/07/2026 après audit de contribution.
# L'audit rétroactif (312 obs News, 117 Espion) a montré que le sentiment News
# tel que pondéré n'a aucun edge positif (les valeurs "bonne nouvelle" sous-
# performent légèrement l'univers, le signal penche même à l'envers) et que le
# bonus Espion n'est pas mesurable (données institutionnelles Yahoo vides sur
# les .PA). On arrête de polluer le score avec du non-prouvé.
# À RETESTER vers le 02/08 avec un mois de données propres avant toute décision
# définitive (supprimer, réduire, ou inverser le signe News). Réactivation =
# remettre POIDS_NEWS à 4 et POIDS_ESPION à 1.
POIDS_NEWS   = 0   # était 4 (score += sentiment_news * POIDS_NEWS)
POIDS_ESPION = 0   # était 1 (score += bonus_espion * POIDS_ESPION)


def calculer_score_confiance(d, persistance_intraday=None):
    """
    Score de 0 à 100 basé sur la convergence des indicateurs.
    > 65 = ACHETER, < 35 = ÉVITER, sinon SURVEILLER
    Bonus/malus supplémentaire si le signal a été persistant la veille (intraday).
    """
    score = 50

    # RSI
    if d.get("rsi") is not None:
        rsi = d["rsi"]
        if rsi < 25:   score += 20
        elif rsi < 35: score += 12
        elif rsi < 45: score += 5
        elif rsi > 75: score -= 20
        elif rsi > 65: score -= 12
        elif rsi > 55: score -= 5

    # Stochastique
    if d.get("stoch_k") is not None:
        sk = d["stoch_k"]
        if sk < 20:   score += 10
        elif sk > 80: score -= 10

    # MACD
    if d.get("macd") == "haussier":   score += 10
    elif d.get("macd") == "baissier": score -= 10

    # Histogramme MACD (accélération)
    if d.get("macd_hist_accelere") == "positif":  score += 5
    elif d.get("macd_hist_accelere") == "negatif": score -= 5

    # Moyennes mobiles
    cours = d.get("cours", 0)
    ma20  = d.get("ma20")
    ma50  = d.get("ma50")
    ma200 = d.get("ma200")

    if ma20 and ma50:
        if cours > ma20 and cours > ma50:  score += 10
        elif cours < ma20 and cours < ma50: score -= 10

    if ma200:
        if cours > ma200:  score += 5
        elif cours < ma200: score -= 5

    # Golden/Death cross
    if d.get("golden_cross"): score += 15
    if d.get("death_cross"):  score -= 15

    # Bollinger
    boll = d.get("boll_zone", "")
    if "SOUS" in boll:       score += 10
    elif "AU-DESSUS" in boll: score -= 10

    # Volume anormal
    if d.get("volume_anormal") == "fort_hausse": score += 8
    elif d.get("volume_anormal") == "fort_baisse": score -= 8

    # Patterns bougies
    patterns = d.get("patterns", [])
    for p in patterns:
        if "bullish fort" in p: score += 12
        elif "bullish" in p:    score += 7
        elif "bearish fort" in p: score -= 12
        elif "bearish" in p:    score -= 7

    # Proximité 52 semaines
    if d.get("pct_52w_bas") is not None and d["pct_52w_bas"] < 10:  score += 8
    if d.get("pct_52w_haut") is not None and d["pct_52w_haut"] < 5: score -= 8

    # Bonus persistance intraday (signaux confirmés la veille)
    nom = d.get("nom", "")
    if persistance_intraday and nom in persistance_intraday:
        p = persistance_intraday[nom]
        score += p["bonus"]
        d["persistance_label"] = p["label"]
        d["scores_hier"]       = p["scores_hier"]

    # Bonus fondamentaux
    score += d.get("bonus_fondamentaux", 0)

    # Bonus/malus sentiment news (POIDS_NEWS=0 depuis l'audit du 02/07, cf. plus haut)
    sentiment = d.get("sentiment_news", 0)
    score += sentiment * POIDS_NEWS

    # Malus si résultats dans les 3 jours (risque élevé)
    if d.get("resultats_proches"):
        score = max(35, min(score, 64))  # force SURVEILLER
        d["alerte_resultats"] = True

    # Bonus indicateurs appris par secteur
    score += d.get("bonus_indicateurs_appris", 0)

    # Malus macro global (VIX, EUR/USD, pétrole)
    score += d.get("malus_macro", 0)

    # Malus annonce BCE/Fed dans les 48h
    score += d.get("malus_banque_centrale", 0)

    # Bonus momentum relatif vs CAC40
    score += d.get("bonus_momentum_rel", 0)

    # Consensus analystes (cible prix + recommandation)
    score += d.get("bonus_analystes", 0)

    # Bonus argent institutionnel (agent espion) — POIDS_ESPION=0 depuis l'audit du 02/07
    score += d.get("bonus_espion", 0) * POIDS_ESPION

    # Fear & Greed (malus global injecté via d["malus_fear_greed"])
    score += d.get("malus_fear_greed", 0)

    # Bonus convergence multi-timeframe
    score += d.get("bonus_convergence_tf", 0)

    # Divergence RSI/prix
    div = d.get("divergence_rsi")
    if div == "haussiere":  score += 12
    elif div == "baissiere": score -= 12

    # Pente MA200
    pente = d.get("pente_ma200")
    if pente == "haussiere":  score += 6
    elif pente == "baissiere": score -= 6

    score = max(0, min(100, round(score)))

    if score >= 65:   signal = "ACHETER"
    elif score <= 35: signal = "ÉVITER"
    else:             signal = "SURVEILLER"

    return score, signal


# ─── RÉCUPÉRATION DES DONNÉES ─────────────────────────────────────────────────

def recuperer_donnees_action(nom, ticker, hist_cac=None):
    try:
        stock = yf.Ticker(ticker)
        hist  = stock.history(period="1y")

        if hist.empty or len(hist) < 20:
            return {"nom": nom, "ticker": ticker, "erreur": "Pas de données"}

        # Yahoo peut renvoyer une dernière bougie incomplète (Close = NaN) quand la
        # bourse n'a pas encore ouvert ou que le flux n'est pas finalisé (fréquent sur
        # les valeurs Euronext Paris tôt le matin). On l'ignore pour retomber sur le
        # dernier cours réellement connu, plutôt que de propager des NaN en aval.
        hist = hist[hist["Close"].notna()]
        if hist.empty or len(hist) < 20:
            return {"nom": nom, "ticker": ticker, "erreur": "Pas de données"}

        cours      = round(hist["Close"].iloc[-1], 2)
        cours_hier = round(hist["Close"].iloc[-2], 2)
        variation  = round((cours - cours_hier) / cours_hier * 100, 2)
        volume     = int(hist["Volume"].iloc[-1])

        # 52 semaines
        w52_haut = round(hist["High"].max(), 2)
        w52_bas  = round(hist["Low"].min(), 2)
        pct_52w_haut = round((w52_haut - cours) / w52_haut * 100, 1)
        pct_52w_bas  = round((cours - w52_bas) / w52_bas * 100, 1)

        rsi = stoch_k = stoch_d = macd_sig = macd_hist_acc = None
        ma20 = ma50 = ma200 = boll_zone = atr = None
        golden_cross = death_cross = False

        if TA_DISPONIBLE:
            close  = hist["Close"]
            high   = hist["High"]
            low    = hist["Low"]

            # RSI
            rsi = round(RSIIndicator(close=close, window=14).rsi().iloc[-1], 1)

            # Stochastique
            stoch = StochasticOscillator(high=high, low=low, close=close, window=14, smooth_window=3)
            stoch_k = round(stoch.stoch().iloc[-1], 1)
            stoch_d = round(stoch.stoch_signal().iloc[-1], 1)

            # MACD
            macd_ind  = MACD(close=close)
            macd_val  = macd_ind.macd().iloc[-1]
            macd_sig_val = macd_ind.macd_signal().iloc[-1]
            macd_sig  = "haussier" if macd_val > macd_sig_val else "baissier"
            hist_vals = macd_ind.macd_diff()
            if len(hist_vals) >= 2:
                macd_hist_acc = "positif" if hist_vals.iloc[-1] > hist_vals.iloc[-2] else "negatif"

            # Moyennes mobiles
            ma20 = round(SMAIndicator(close=close, window=20).sma_indicator().iloc[-1], 2)
            if len(hist) >= 50:
                ma50 = round(SMAIndicator(close=close, window=50).sma_indicator().iloc[-1], 2)
            if len(hist) >= 200:
                ma200 = round(SMAIndicator(close=close, window=200).sma_indicator().iloc[-1], 2)

            # Golden / Death cross
            if ma20 and ma50:
                ma20_prev = SMAIndicator(close=close, window=20).sma_indicator().iloc[-2]
                ma50_prev = SMAIndicator(close=close, window=50).sma_indicator().iloc[-2]
                if ma20_prev < ma50_prev and ma20 > ma50:
                    golden_cross = True
                elif ma20_prev > ma50_prev and ma20 < ma50:
                    death_cross = True

            # Bollinger
            boll  = BollingerBands(close=close, window=20, window_dev=2)
            b_inf = boll.bollinger_lband().iloc[-1]
            b_sup = boll.bollinger_hband().iloc[-1]
            b_mid = boll.bollinger_mavg().iloc[-1]
            boll_pct = round((cours - b_inf) / (b_sup - b_inf) * 100, 0) if b_sup != b_inf else 50
            if cours < b_inf:
                boll_zone = f"SOUS bande inf (survendu, {boll_pct}%)"
            elif cours > b_sup:
                boll_zone = f"AU-DESSUS bande sup (suracheté, {boll_pct}%)"
            else:
                boll_zone = f"dans les bandes ({boll_pct}%)"

            # ATR (volatilité)
            atr = round(AverageTrueRange(high=high, low=low, close=close, window=14).average_true_range().iloc[-1], 2)

        # Volume anormal
        vol_moy20 = hist["Volume"].tail(20).mean()
        ratio_vol  = volume / vol_moy20 if vol_moy20 > 0 else 1
        if ratio_vol > 2:
            vol_anormal = "fort_hausse" if variation > 0 else "fort_baisse"
        elif ratio_vol > 1.5:
            vol_anormal = "elevé"
        else:
            vol_anormal = "normal"

        # Pivot Points (support/résistance)
        h_hier = hist["High"].iloc[-2]
        l_hier = hist["Low"].iloc[-2]
        c_hier = cours_hier
        pivot  = round((h_hier + l_hier + c_hier) / 3, 2)
        r1     = round(2 * pivot - l_hier, 2)
        s1     = round(2 * pivot - h_hier, 2)
        r2     = round(pivot + (h_hier - l_hier), 2)
        s2     = round(pivot - (h_hier - l_hier), 2)

        # Beta vs CAC 40
        beta = None
        if hist_cac is not None and len(hist_cac) >= 50:
            try:
                ret_stock = hist["Close"].pct_change().dropna()
                ret_cac   = hist_cac["Close"].pct_change().dropna()
                common    = ret_stock.index.intersection(ret_cac.index)
                if len(common) >= 30:
                    rs = ret_stock.loc[common].tail(60)
                    rc = ret_cac.loc[common].tail(60)
                    cov  = rs.cov(rc)
                    var  = rc.var()
                    beta = round(cov / var, 2) if var != 0 else None
            except Exception:
                pass

        # Patterns bougies
        patterns = detecter_patterns(hist.tail(3))

        # Fondamentaux
        fond = recuperer_fondamentaux(stock)
        bonus_fond = scorer_fondamentaux(fond)

        # Bonus agent espion (institutionnels + rotations sectorielles)
        if _rapport_espion_cache and nom in _rapport_espion_cache.get("valeurs", {}):
            data_esp = _rapport_espion_cache["valeurs"][nom]
            bonus_esp = data_esp.get("bonus_total", 0)
        else:
            bonus_esp = 0

        # News + sentiment : priorité au rapport agent_news, fallback Yahoo Finance
        if _rapport_news_cache and nom in _rapport_news_cache.get("valeurs", {}):
            nd = _rapport_news_cache["valeurs"][nom]
            news_data = {"sentiment": nd["sentiment"], "news": nd["titres_cles"]}
        else:
            news_data = recuperer_news_sentiment(stock, nom)

        # Calendrier résultats
        resultats_proches = verifier_resultats_proches(stock)

        # Secteur
        valeur_secteur = {}
        for sec, vals in SECTEURS.items():
            for v in vals:
                valeur_secteur[v] = sec
        secteur_nom = valeur_secteur.get(nom, "Autre")

        # Poids indicateurs appris
        bonus_ind = calculer_bonus_indicateurs_appris(
            {"rsi": rsi, "macd": macd_sig, "secteur_nom": secteur_nom},
            _poids_indicateurs_cache
        )

        # Consensus analystes
        bonus_analystes, data_analystes = scorer_consensus_analystes(stock, cours)

        # Divergence RSI/prix
        rsi_series   = RSIIndicator(close=hist["Close"], window=14).rsi() if TA_DISPONIBLE else None
        div_rsi      = detecter_divergence_rsi(hist, rsi_series) if rsi_series is not None else None

        # Compression Bollinger
        compression_boll = detecter_compression_bollinger(hist) if TA_DISPONIBLE else False

        # Pente MA200
        pente_ma200 = calculer_pente_ma200(hist) if TA_DISPONIBLE else "neutre"

        # Momentum multi-timeframe
        mtf = calculer_momentum_multitimeframe(hist)

        data = {
            "nom":          nom,
            "ticker":       ticker,
            "cours":        cours,
            "cours_hier":   cours_hier,
            "variation":    variation,
            "volume":       volume,
            "ratio_vol":    round(ratio_vol, 1),
            "volume_anormal": vol_anormal,
            "rsi":          rsi,
            "stoch_k":      stoch_k,
            "stoch_d":      stoch_d,
            "macd":         macd_sig,
            "macd_hist_accelere": macd_hist_acc,
            "ma20":         ma20,
            "ma50":         ma50,
            "ma200":        ma200,
            "golden_cross": golden_cross,
            "death_cross":  death_cross,
            "boll_zone":    boll_zone,
            "atr":          atr,
            "w52_haut":     w52_haut,
            "w52_bas":      w52_bas,
            "pct_52w_haut": pct_52w_haut,
            "pct_52w_bas":  pct_52w_bas,
            "pivot":        pivot,
            "r1": r1, "r2": r2,
            "s1": s1, "s2": s2,
            "beta":         beta,
            "patterns":     patterns,
            "news":         news_data["news"],
            "sentiment_news":          news_data["sentiment"],
            "bonus_fondamentaux":      bonus_fond,
            "fondamentaux":            fond,
            "resultats_proches":       resultats_proches,
            "bonus_indicateurs_appris":bonus_ind,
            "secteur_nom":             secteur_nom,
            "divergence_rsi":          div_rsi,
            "compression_bollinger":   compression_boll,
            "pente_ma200":             pente_ma200,
            "momentum_tf":             mtf,
            "bonus_convergence_tf":    mtf.get("bonus_convergence", 0),
            "bonus_analystes":         bonus_analystes,
            "analystes":               data_analystes,
            "bonus_espion":            bonus_esp,
        }

        score, signal = calculer_score_confiance(data, persistance_intraday=_persistance_cache)
        data["score"]  = score
        data["signal"] = signal

        return data

    except Exception as e:
        return {"nom": nom, "ticker": ticker, "erreur": str(e)}


def recuperer_indice_cac():
    try:
        ticker = yf.Ticker("^FCHI")
        hist   = ticker.history(period="1y")
        hist   = hist[hist["Close"].notna()]
        if not hist.empty:
            cours    = round(hist["Close"].iloc[-1], 0)
            hier     = round(hist["Close"].iloc[-2], 0)
            variation = round((cours - hier) / hier * 100, 2)
            return cours, variation, hist
    except Exception:
        pass
    return None, None, None


def recuperer_contexte_macro():
    """
    Récupère VIX, EUR/USD et pétrole (Brent).
    Retourne un dict avec les valeurs et un malus_global (-20 à 0)
    appliqué uniformément à tous les scores quand le marché est sous stress.
    """
    ctx = {"vix": None, "eurusd": None, "brent": None, "malus_global": 0, "alerte_macro": []}
    try:
        vix = yf.Ticker("^VIX").history(period="2d")
        if not vix.empty:
            ctx["vix"] = round(vix["Close"].iloc[-1], 1)
    except Exception:
        pass
    try:
        eurusd = yf.Ticker("EURUSD=X").history(period="2d")
        if not eurusd.empty:
            cours_eu = eurusd["Close"].iloc[-1]
            hier_eu  = eurusd["Close"].iloc[-2]
            ctx["eurusd"] = round(cours_eu, 4)
            ctx["eurusd_var"] = round((cours_eu - hier_eu) / hier_eu * 100, 2)
    except Exception:
        pass
    try:
        brent = yf.Ticker("BZ=F").history(period="2d")
        if not brent.empty:
            cours_br = brent["Close"].iloc[-1]
            hier_br  = brent["Close"].iloc[-2]
            ctx["brent"] = round(cours_br, 1)
            ctx["brent_var"] = round((cours_br - hier_br) / hier_br * 100, 2)
    except Exception:
        pass

    malus = 0
    vix = ctx["vix"]
    if vix is not None:
        if vix > 35:
            malus -= 20
            ctx["alerte_macro"].append(f"VIX EXTRÊME ({vix}) — marché en panique")
        elif vix > 25:
            malus -= 12
            ctx["alerte_macro"].append(f"VIX élevé ({vix}) — stress de marché")
        elif vix > 20:
            malus -= 5
            ctx["alerte_macro"].append(f"VIX modéré ({vix})")

    eurusd_var = ctx.get("eurusd_var")
    if eurusd_var is not None and abs(eurusd_var) > 0.8:
        malus -= 5
        ctx["alerte_macro"].append(f"EUR/USD instable ({eurusd_var:+.2f}%)")

    brent_var = ctx.get("brent_var")
    if brent_var is not None and brent_var > 3:
        malus -= 5
        ctx["alerte_macro"].append(f"Pétrole en forte hausse ({brent_var:+.1f}%) — pression sur marges")
    elif brent_var is not None and brent_var < -3:
        malus -= 3
        ctx["alerte_macro"].append(f"Pétrole en forte baisse ({brent_var:+.1f}%)")

    ctx["malus_global"] = malus
    return ctx


def calculer_momentum_relatif_cac(donnees_dict, cac_var):
    """
    Pour chaque action, calcule la surperformance vs CAC40 sur 5 et 20 jours.
    Une action qui surperforme son indice = signal de force relative.
    Retourne un dict {nom: {"perf_relative_5j": x, "bonus_momentum_rel": y}}
    """
    result = {}
    for nom, d in donnees_dict.items():
        if "erreur" in d:
            continue
        try:
            stock = yf.Ticker(d["ticker"])
            hist  = stock.history(period="1mo")
            if len(hist) < 20:
                continue
            perf_5j  = round((hist["Close"].iloc[-1] / hist["Close"].iloc[-5]  - 1) * 100, 2)
            perf_20j = round((hist["Close"].iloc[-1] / hist["Close"].iloc[-20] - 1) * 100, 2)
            # Approx CAC sur 5j à partir de la variation connue du jour
            rel_5j = perf_5j - (cac_var or 0)
            bonus = 0
            if rel_5j > 3:    bonus += 8
            elif rel_5j > 1:  bonus += 4
            elif rel_5j < -3: bonus -= 8
            elif rel_5j < -1: bonus -= 4
            result[nom] = {
                "perf_5j":  perf_5j,
                "perf_20j": perf_20j,
                "rel_5j":   round(rel_5j, 2),
                "bonus_momentum_rel": bonus,
            }
        except Exception:
            pass
    return result


# ─── MOMENTUM SECTORIEL ───────────────────────────────────────────────────────

def calculer_momentum_sectoriel(donnees_dict):
    momentum = {}
    for secteur, valeurs in SECTEURS.items():
        variations = []
        scores     = []
        for nom in valeurs:
            d = donnees_dict.get(nom)
            if d and "erreur" not in d:
                variations.append(d.get("variation", 0))
                scores.append(d.get("score", 50))
        if variations:
            momentum[secteur] = {
                "variation_moy": round(sum(variations) / len(variations), 2),
                "score_moy":     round(sum(scores) / len(scores), 0),
            }
    return momentum


# ─── PERFORMANCE TRACKING ─────────────────────────────────────────────────────

def charger_performance():
    stats_defaut = {
        "total": 0, "corrects": 0, "precision": 0.0,
        "acheter_total": 0, "acheter_corrects": 0,
        "eviter_total": 0,  "eviter_corrects": 0,
        "par_secteur": {}
    }
    if os.path.exists(FICHIER_PERFORMANCE):
        with open(FICHIER_PERFORMANCE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Complète les champs manquants si fichier V2
        for k, v in stats_defaut.items():
            if k not in data.get("stats", {}):
                data.setdefault("stats", {})[k] = v
        return data
    return {"historique": {}, "stats": stats_defaut}


def _prix_valide(x):
    """Un prix exploitable : numérique et pas NaN. `not x` ne suffit pas car
    NaN est truthy en Python — c'est ce qui a pollué les stats le 01/07/2026."""
    return isinstance(x, (int, float)) and not isinstance(x, bool) and not math.isnan(x)


def evaluer_performance_hier(perf, donnees_actuelles):
    if not perf["historique"]:
        return perf, "Première session. L'auto-évaluation commence dès demain."

    date_hier = None
    for i in range(1, 8):
        d = (datetime.date.today() - datetime.timedelta(days=i)).isoformat()
        if d in perf["historique"]:
            date_hier = d
            break

    if not date_hier:
        return perf, "Pas d'historique récent."

    reco_hier    = perf["historique"][date_hier]
    donnees_dict = {d["nom"]: d for d in donnees_actuelles if "erreur" not in d}

    bons    = []
    mauvais = []
    total   = 0
    corrects = 0

    for nom, data in reco_hier.items():
        signal    = data.get("signal")
        prix_hier = data.get("prix")
        score_hier = data.get("score")
        secteur   = data.get("secteur", "Autre")

        if signal not in ["ACHETER", "ÉVITER"] or not _prix_valide(prix_hier):
            continue

        d_auj = donnees_dict.get(nom)
        if not d_auj:
            continue

        prix_auj = d_auj.get("cours")
        if not _prix_valide(prix_auj):
            continue

        hausse   = prix_auj > prix_hier
        correct  = (signal == "ACHETER" and hausse) or (signal == "ÉVITER" and not hausse)
        variation = round((prix_auj - prix_hier) / prix_hier * 100, 2)

        total    += 1
        corrects += int(correct)

        # Stats par type
        if signal == "ACHETER":
            perf["stats"]["acheter_total"] += 1
            if correct: perf["stats"]["acheter_corrects"] += 1
        else:
            perf["stats"]["eviter_total"] += 1
            if correct: perf["stats"]["eviter_corrects"] += 1

        # Stats par secteur
        if secteur not in perf["stats"]["par_secteur"]:
            perf["stats"]["par_secteur"][secteur] = {"total": 0, "corrects": 0}
        perf["stats"]["par_secteur"][secteur]["total"]    += 1
        perf["stats"]["par_secteur"][secteur]["corrects"] += int(correct)

        signe = "+" if variation > 0 else ""
        if correct:
            bons.append(f"{nom} ({signal}, score {score_hier}) -> {signe}{variation}%")
        else:
            mauvais.append(f"{nom} ({signal}, score {score_hier}) -> {signe}{variation}%")

    if total > 0:
        perf["stats"]["total"]    += total
        perf["stats"]["corrects"] += corrects
        perf["stats"]["precision"] = round(perf["stats"]["corrects"] / perf["stats"]["total"] * 100, 1)

    prec_ach = round(perf["stats"]["acheter_corrects"] / perf["stats"]["acheter_total"] * 100, 1) \
               if perf["stats"]["acheter_total"] > 0 else 0
    prec_ev  = round(perf["stats"]["eviter_corrects"] / perf["stats"]["eviter_total"] * 100, 1) \
               if perf["stats"]["eviter_total"] > 0 else 0

    resume = f"J-1 ({date_hier}) : {corrects}/{total} corrects\n"
    resume += f"Precision ACHETER : {prec_ach}% | EVITER : {prec_ev}%\n"
    if bons:
        resume += f"Bons : {', '.join(bons[:5])}\n"
    if mauvais:
        resume += f"Erreurs : {', '.join(mauvais[:5])}"

    # Meilleur/pire secteur
    meilleur_secteur = max(
        perf["stats"]["par_secteur"].items(),
        key=lambda x: x[1]["corrects"] / max(x[1]["total"], 1),
        default=(None, None)
    )
    pire_secteur = min(
        perf["stats"]["par_secteur"].items(),
        key=lambda x: x[1]["corrects"] / max(x[1]["total"], 1),
        default=(None, None)
    )

    if meilleur_secteur[0]:
        ms = meilleur_secteur
        ps = pire_secteur
        ms_pct = round(ms[1]["corrects"] / max(ms[1]["total"], 1) * 100, 0)
        ps_pct = round(ps[1]["corrects"] / max(ps[1]["total"], 1) * 100, 0)
        resume += f"\nMeilleur secteur : {ms[0]} ({ms_pct}%) | Pire : {ps[0]} ({ps_pct}%)"

    # Auto-apprentissage par indicateur et secteur
    hist_ind = {}
    for nom, data in reco_hier.items():
        signal    = data.get("signal")
        prix_hier = data.get("prix")
        secteur   = data.get("secteur", "Autre")
        if signal not in ["ACHETER", "ÉVITER"] or not _prix_valide(prix_hier):
            continue
        d_auj = donnees_dict.get(nom)
        if not d_auj:
            continue
        prix_auj = d_auj.get("cours")
        if not _prix_valide(prix_auj):
            continue
        hausse  = prix_auj > prix_hier
        correct = (signal == "ACHETER" and hausse) or (signal == "ÉVITER" and not hausse)

        if secteur not in hist_ind:
            hist_ind[secteur] = {}

        # RSI
        rsi = data.get("rsi")
        if rsi is not None:
            rsi_signal = "acheter" if rsi < 40 else ("eviter" if rsi > 60 else None)
            if rsi_signal:
                k = "rsi"
                hist_ind[secteur].setdefault(k, {"total": 0, "corrects": 0})
                hist_ind[secteur][k]["total"] += 1
                if (rsi_signal == "acheter" and hausse) or (rsi_signal == "eviter" and not hausse):
                    hist_ind[secteur][k]["corrects"] += 1

        # MACD
        macd = data.get("macd")
        if macd in ["haussier", "baissier"]:
            k = "macd"
            hist_ind[secteur].setdefault(k, {"total": 0, "corrects": 0})
            hist_ind[secteur][k]["total"] += 1
            if (macd == "haussier" and hausse) or (macd == "baissier" and not hausse):
                hist_ind[secteur][k]["corrects"] += 1

    perf = mettre_a_jour_poids_indicateurs(perf, hist_ind)

    return perf, resume


def sauvegarder_recommandations(perf, donnees_actuelles):
    today        = datetime.date.today().isoformat()
    donnees_dict = {d["nom"]: d for d in donnees_actuelles if "erreur" not in d}

    # Trouve le secteur de chaque valeur
    valeur_secteur = {}
    for secteur, valeurs in SECTEURS.items():
        for v in valeurs:
            valeur_secteur[v] = secteur

    perf["historique"][today] = {}
    for nom, d in donnees_dict.items():
        perf["historique"][today][nom] = {
            "signal":       d.get("signal", "SURVEILLER"),
            "score":        d.get("score", 50),
            "prix":         d.get("cours"),
            "secteur":      valeur_secteur.get(nom, "Autre"),
            "rsi":          d.get("rsi"),
            "macd":         d.get("macd"),
            "boll_zone":    d.get("boll_zone", ""),
            "golden_cross": d.get("golden_cross", False),
            "death_cross":  d.get("death_cross", False),
        }

    # Garde 90 jours
    dates = sorted(perf["historique"].keys())
    for vieille in dates[:-90]:
        del perf["historique"][vieille]

    with open(FICHIER_PERFORMANCE, "w", encoding="utf-8") as f:
        json.dump(perf, f, ensure_ascii=False, indent=2)


# ─── PORTEFEUILLE VIRTUEL ─────────────────────────────────────────────────────

FRAIS_TAUX    = 0.005
FRAIS_MINIMUM = 0.50

def calculer_frais(montant):
    return round(max(FRAIS_MINIMUM, montant * FRAIS_TAUX), 2)

def gerer_portefeuille_virtuel(donnees_actuelles, perf):
    """Simule un portefeuille virtuel basé sur les signaux ACHETER."""
    if not os.path.exists(FICHIER_PORTEFEUILLE):
        pf = {"capital": 10000.0, "positions": {}, "historique_valeur": {}, "trades": []}
    else:
        with open(FICHIER_PORTEFEUILLE, "r") as f:
            pf = json.load(f)

    today        = datetime.date.today().isoformat()
    donnees_dict = {d["nom"]: d for d in donnees_actuelles if "erreur" not in d}

    # Ferme les positions ÉVITER ou qui ont plus de 10 jours
    positions_a_fermer = []
    for nom, pos in pf["positions"].items():
        d = donnees_dict.get(nom)
        if not d:
            continue
        signal       = d.get("signal")
        jours_tenu   = (datetime.date.today() - datetime.date.fromisoformat(pos["date_entree"])).days
        cours_actuel = d.get("cours", pos["prix_entree"])
        pnl_pct      = (cours_actuel - pos["prix_entree"]) / pos["prix_entree"] * 100

        if signal == "ÉVITER" or jours_tenu >= 10 or pnl_pct <= -5 or pnl_pct >= 8:
            positions_a_fermer.append((nom, cours_actuel, pnl_pct))

    for nom, cours_sortie, pnl_pct in positions_a_fermer:
        pos          = pf["positions"][nom]
        valeur_sortie = pos["nb_actions"] * cours_sortie
        frais_vente  = calculer_frais(valeur_sortie)
        net_sortie   = valeur_sortie - frais_vente
        frais_total  = round(pos.get("frais_achat", 0) + frais_vente, 2)
        pnl_net      = round((net_sortie - pos["cout_total"]) / pos["cout_total"] * 100, 2)
        pf["capital"] += net_sortie
        pf["trades"].append({
            "nom":          nom,
            "entree":       pos["prix_entree"],
            "sortie":       cours_sortie,
            "date_entree":  pos["date_entree"],
            "heure_entree": pos.get("heure_entree", "07:00"),
            "source_entree":pos.get("source_entree", "Briefing"),
            "date_sortie":  today,
            "heure_sortie": datetime.datetime.now().strftime("%H:%M"),
            "source_sortie":"Briefing",
            "pnl_pct":      pnl_net,
            "frais_total":  frais_total,
        })
        del pf["positions"][nom]

    # Ouvre des positions sur signaux ACHETER (max 5 positions, 2000€ chacune)
    max_positions = 5
    budget_par_position = 2000.0

    for nom, d in donnees_dict.items():
        if (d.get("signal") == "ACHETER" and
                nom not in pf["positions"] and
                len(pf["positions"]) < max_positions and
                pf["capital"] >= budget_par_position and
                d.get("score", 0) >= 70):
            cours       = d["cours"]
            nb          = int(budget_par_position / cours)
            if nb > 0:
                cout        = nb * cours
                frais_achat = calculer_frais(cout)
                pf["capital"] -= (cout + frais_achat)
                pf["positions"][nom] = {
                    "nb_actions":   nb,
                    "prix_entree":  cours,
                    "date_entree":  today,
                    "heure_entree": datetime.datetime.now().strftime("%H:%M"),
                    "source_entree":"Briefing",
                    "cout_total":   cout,
                    "frais_achat":  frais_achat,
                }

    # Calcul valeur totale
    valeur_positions = sum(
        pos["nb_actions"] * donnees_dict.get(nom, {}).get("cours", pos["prix_entree"])
        for nom, pos in pf["positions"].items()
    )
    valeur_totale = round(pf["capital"] + valeur_positions, 2)

    # Garde-fou : si une donnée de marché manquante a fait fuiter un NaN jusqu'ici,
    # on ne pollue pas l'historique avec une valeur fausse et on le signale à l'appelant.
    donnees_invalides = math.isnan(valeur_totale)

    if donnees_invalides:
        with open(FICHIER_PORTEFEUILLE, "w") as f:
            json.dump(pf, f, ensure_ascii=False, indent=2)
        resume_pf = ("Portefeuille virtuel : données de marché indisponibles aujourd'hui, "
                     "valeur non recalculée (dernière valeur connue conservée).\n")
        return resume_pf, pf, donnees_dict, donnees_invalides

    pf["historique_valeur"][today] = valeur_totale

    # Perf vs CAC 40 (base 10000€ au départ)
    perf_pf = round((valeur_totale - 10000) / 10000 * 100, 2)

    resume_pf = f"Portefeuille virtuel : {valeur_totale}€ (départ 10 000€, {'+' if perf_pf > 0 else ''}{perf_pf}%)\n"
    resume_pf += f"Capital libre : {round(pf['capital'], 2)}€ | Positions ouvertes : {len(pf['positions'])}\n"

    if pf["positions"]:
        resume_pf += "Positions : "
        for nom, pos in pf["positions"].items():
            cours_actuel = donnees_dict.get(nom, {}).get("cours", pos["prix_entree"])
            pnl = round((cours_actuel - pos["prix_entree"]) / pos["prix_entree"] * 100, 2)
            resume_pf += f"{nom} ({'+' if pnl > 0 else ''}{pnl}%) | "

    # Derniers trades
    if pf["trades"]:
        derniers = pf["trades"][-5:]
        resume_pf += "\nDerniers trades : "
        for t in derniers:
            resume_pf += f"{t['nom']} ({'+' if t['pnl_pct'] > 0 else ''}{t['pnl_pct']}%) | "

    with open(FICHIER_PORTEFEUILLE, "w") as f:
        json.dump(pf, f, ensure_ascii=False, indent=2)

    return resume_pf, pf, donnees_dict, donnees_invalides


def generer_html_portefeuille(pf, donnees_dict, perf_cac=None, date_debut=None):
    """Génère le bloc HTML du tableau portefeuille virtuel pour l'email.
    perf_cac : performance du CAC 40 depuis le départ du portefeuille (comparaison)."""
    valeur_totale = list(pf["historique_valeur"].values())[-1] if pf["historique_valeur"] else 10000.0
    perf_pf = round((valeur_totale - 10000) / 10000 * 100, 2)
    signe_global = "+" if perf_pf >= 0 else ""
    gain_total = round(valeur_totale - 10000, 2)
    signe_gain = "+" if gain_total >= 0 else ""
    couleur_global = "#2e7d32" if perf_pf >= 0 else "#c62828"

    # Comparaison au CAC 40 sur la même période (le chiffre brut ne veut rien dire sans référence)
    bloc_vs_cac = ""
    if perf_cac is not None:
        ecart = round(perf_pf - perf_cac, 2)
        bat = ecart >= 0
        coul = "#2e7d32" if bat else "#c62828"
        verdict = "surperforme" if bat else "sous-performe"
        depuis = f" depuis le {date_debut[8:10]}/{date_debut[5:7]}" if date_debut else ""
        bloc_vs_cac = f"""
  <div style='margin-bottom:16px;padding:10px 14px;background:{'#e8f5e9' if bat else '#ffebee'};border-radius:8px;font-size:13px;'>
    <strong style='color:{coul};'>Le portefeuille {verdict} le CAC 40{depuis}</strong> :
    {signe_global}{perf_pf:.2f}% contre {'+' if perf_cac >= 0 else ''}{perf_cac:.2f}% pour le CAC 40
    (<span style='color:{coul};font-weight:600;'>{'+' if ecart >= 0 else ''}{ecart:.2f} pts</span>)
  </div>"""

    nb_positions = len(pf["positions"])
    capital_libre = round(pf["capital"], 2)

    def badge_source(source):
        styles = {
            "Briefing":  "background:#e3f0fb;color:#1565c0;",
            "Intraday":  "background:#fff8e1;color:#e65100;",
            "Alerte":    "background:#fce4ec;color:#b71c1c;",
        }
        st = styles.get(source, "background:#eee;color:#333;")
        return f"<span style='font-size:10px;{st}padding:2px 6px;border-radius:3px;'>{source}</span>"

    def fmt_date(iso):
        return iso[8:10] + "/" + iso[5:7] + "/" + iso[2:4]

    lignes_trades = ""
    derniers_trades = pf["trades"][-10:] if pf["trades"] else []
    for t in reversed(derniers_trades):
        pnl = t["pnl_pct"]
        signe = "+" if pnl >= 0 else ""
        couleur = "#2e7d32" if pnl >= 0 else "#c62828"
        frais = t.get("frais_total", 0)
        heure_e  = t.get("heure_entree", "07:00")
        heure_s  = t.get("heure_sortie", "")
        src_e    = badge_source(t.get("source_entree", "Briefing"))
        src_s    = badge_source(t.get("source_sortie", "Briefing"))
        lignes_trades += f"""<tr style='border-bottom:1px solid #eee;'>
          <td style='padding:7px 10px;font-weight:500;'>{t['nom']}</td>
          <td style='padding:7px 10px;text-align:right;color:#999;'>—</td>
          <td style='padding:7px 10px;'><div style='color:#333;'>{fmt_date(t['date_entree'])} {heure_e}</div><div style='margin-top:3px;'>{src_e}</div></td>
          <td style='padding:7px 10px;'><div style='color:#333;'>{fmt_date(t['date_sortie'])} {heure_s}</div><div style='margin-top:3px;'>{src_s}</div></td>
          <td style='padding:7px 10px;text-align:right;'>{t['entree']:.2f} €</td>
          <td style='padding:7px 10px;text-align:right;'>{t['sortie']:.2f} €</td>
          <td style='padding:7px 10px;text-align:right;color:#999;font-size:12px;'>{frais:.2f} €</td>
          <td style='padding:7px 10px;text-align:right;font-weight:600;color:{couleur};'>{signe}{pnl:.2f} %</td>
        </tr>"""

    for nom, pos in pf["positions"].items():
        cours_actuel = donnees_dict.get(nom, {}).get("cours", pos["prix_entree"])
        pnl = round((cours_actuel - pos["prix_entree"]) / pos["prix_entree"] * 100, 2)
        signe = "+" if pnl >= 0 else ""
        couleur = "#2e7d32" if pnl >= 0 else "#c62828"
        frais_achat = pos.get("frais_achat", 0)
        heure_e = pos.get("heure_entree", "07:00")
        src_e   = badge_source(pos.get("source_entree", "Briefing"))
        nb_act = pos.get("nb_actions", "—")
        lignes_trades += f"""<tr style='border-bottom:1px solid #eee;background:#f9f9f9;'>
          <td style='padding:7px 10px;font-weight:500;'>{nom}</td>
          <td style='padding:7px 10px;text-align:right;font-weight:600;'>{nb_act}</td>
          <td style='padding:7px 10px;'><div style='color:#333;'>{fmt_date(pos['date_entree'])} {heure_e}</div><div style='margin-top:3px;'>{src_e}</div></td>
          <td style='padding:7px 10px;color:#999;font-style:italic;'>en cours</td>
          <td style='padding:7px 10px;text-align:right;'>{pos['prix_entree']:.2f} €</td>
          <td style='padding:7px 10px;text-align:right;color:#999;'>—</td>
          <td style='padding:7px 10px;text-align:right;color:#999;font-size:12px;'>{frais_achat:.2f} €</td>
          <td style='padding:7px 10px;text-align:right;font-weight:600;color:{couleur};'>{signe}{pnl:.2f} %</td>
        </tr>"""

    if not lignes_trades:
        lignes_trades = "<tr><td colspan='8' style='padding:12px;text-align:center;color:#999;'>Aucun trade pour l'instant</td></tr>"

    return f"""
<div style='margin:20px 0;'>
  <h3 style='margin:0 0 12px;font-size:15px;color:#1a1a2e;'>Portefeuille virtuel</h3>
  {bloc_vs_cac}
  <div style='display:flex;gap:12px;margin-bottom:16px;flex-wrap:wrap;'>
    <div style='flex:1;min-width:120px;background:#f5f5f5;border-radius:8px;padding:12px 16px;'>
      <div style='font-size:11px;color:#666;margin-bottom:4px;'>Capital de départ</div>
      <div style='font-size:18px;font-weight:600;'>10 000 €</div>
    </div>
    <div style='flex:1;min-width:120px;background:#f5f5f5;border-radius:8px;padding:12px 16px;'>
      <div style='font-size:11px;color:#666;margin-bottom:4px;'>Valeur actuelle</div>
      <div style='font-size:18px;font-weight:600;'>{valeur_totale:.0f} €</div>
    </div>
    <div style='flex:1;min-width:120px;background:#f5f5f5;border-radius:8px;padding:12px 16px;'>
      <div style='font-size:11px;color:#666;margin-bottom:4px;'>Performance</div>
      <div style='font-size:18px;font-weight:600;color:{couleur_global};'>{signe_global}{perf_pf:.2f} %</div>
    </div>
    <div style='flex:1;min-width:120px;background:#f5f5f5;border-radius:8px;padding:12px 16px;'>
      <div style='font-size:11px;color:#666;margin-bottom:4px;'>Positions ouvertes</div>
      <div style='font-size:18px;font-weight:600;'>{nb_positions}</div>
    </div>
  </div>
  <table style='width:100%;border-collapse:collapse;font-size:13px;'>
    <thead>
      <tr style='background:#1a1a2e;color:white;'>
        <th style='padding:8px 10px;text-align:left;font-weight:500;'>Action</th>
        <th style='padding:8px 10px;text-align:right;font-weight:500;'>Qté</th>
        <th style='padding:8px 10px;text-align:left;font-weight:500;'>Date achat</th>
        <th style='padding:8px 10px;text-align:left;font-weight:500;'>Date vente</th>
        <th style='padding:8px 10px;text-align:right;font-weight:500;'>Prix achat</th>
        <th style='padding:8px 10px;text-align:right;font-weight:500;'>Prix vente</th>
        <th style='padding:8px 10px;text-align:right;font-weight:500;'>Frais</th>
        <th style='padding:8px 10px;text-align:right;font-weight:500;'>Gain/Perte</th>
      </tr>
    </thead>
    <tbody>
      {lignes_trades}
    </tbody>
    <tfoot>
      <tr style='background:#f0f0f0;border-top:2px solid #ddd;'>
        <td colspan='7' style='padding:8px 10px;font-weight:600;'>Gain/Perte total (frais inclus)</td>
        <td style='padding:8px 10px;text-align:right;font-weight:700;font-size:14px;color:{couleur_global};'>{signe_gain}{gain_total:.0f} € ({signe_global}{perf_pf:.2f} %)</td>
      </tr>
    </tfoot>
  </table>
  <div style='display:flex;gap:10px;margin-top:10px;flex-wrap:wrap;align-items:center;'>
    <span style='font-size:11px;color:#999;'>Capital libre : {capital_libre:.0f} € | Frais Boursobank : 0,5% min 0,50 €</span>
    <span style='font-size:10px;background:#e3f0fb;color:#1565c0;padding:2px 7px;border-radius:3px;'>Briefing = signal 7h</span>
    <span style='font-size:10px;background:#fff8e1;color:#e65100;padding:2px 7px;border-radius:3px;'>Intraday = signal 9h/12h/16h</span>
    <span style='font-size:10px;background:#eeeeee;color:#757575;padding:2px 7px;border-radius:3px;'>Alertes email suspendues jusqu'au ~02/08 (modèle en observation)</span>
  </div>
</div>"""


# ─── CONSTRUCTION DU PROMPT ───────────────────────────────────────────────────

def construire_prompt(donnees, cac_cours, cac_var, perf_resume, perf_stats, momentum, pf_resume, est_lundi, macro=None):
    today = datetime.date.today()
    jours = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
    jour  = jours[today.weekday()]

    donnees_dict = {d["nom"]: d for d in donnees if "erreur" not in d}

    # Bloc données par secteur
    bloc = ""
    for secteur, valeurs in SECTEURS.items():
        mom = momentum.get(secteur, {})
        bloc += f"\n### {secteur} | Momentum : {mom.get('variation_moy', 0):+.2f}% | Score moy : {mom.get('score_moy', 50)}/100\n"
        for nom in valeurs:
            d = donnees_dict.get(nom)
            if not d:
                continue

            score  = d.get("score", 50)
            signal = d.get("signal", "SURVEILLER")
            emoji  = "ACHETER" if signal == "ACHETER" else ("ÉVITER" if signal == "ÉVITER" else "SURVEILLER")

            ligne  = f"- **{nom}** [{emoji} {score}/100] : {d['cours']}€ ({'+' if d['variation'] > 0 else ''}{d['variation']}%)"
            if d.get("rsi"):
                ligne += f" | RSI={d['rsi']}"
            if d.get("stoch_k"):
                ligne += f" | Stoch={d['stoch_k']}"
            if d.get("macd"):
                ligne += f" | MACD {d['macd']}"
            if d.get("ma200"):
                pos200 = ">" if d["cours"] > d["ma200"] else "<"
                ligne += f" | {pos200}MA200"
            if d.get("golden_cross"):
                ligne += " | *** GOLDEN CROSS ***"
            if d.get("death_cross"):
                ligne += " | *** DEATH CROSS ***"
            if d.get("volume_anormal") in ["fort_hausse", "fort_baisse"]:
                ligne += f" | VOL x{d['ratio_vol']} !"
            if d.get("pct_52w_bas", 100) < 15:
                ligne += f" | Proche 52s bas (+{d['pct_52w_bas']}%)"
            if d.get("pct_52w_haut", 100) < 5:
                ligne += f" | Proche 52s HAUT (-{d['pct_52w_haut']}%)"
            if d.get("beta"):
                ligne += f" | Beta={d['beta']}"
            if d.get("patterns"):
                ligne += f" | Bougies: {', '.join(d['patterns'])}"
            if d.get("atr"):
                ligne += f" | ATR={d['atr']}"
            if d.get("news"):
                ligne += f"\n  News: {' // '.join(d['news'][:2])}"
            bloc += ligne + "\n"

    prec_ach = round(perf_stats["acheter_corrects"] / max(perf_stats["acheter_total"], 1) * 100, 1)
    prec_ev  = round(perf_stats["eviter_corrects"] / max(perf_stats["eviter_total"], 1) * 100, 1)

    perf_txt = ""
    if perf_stats["total"] > 0:
        perf_txt = f"""
## Performance agent (auto-amélioration)
- Precision globale : {perf_stats['precision']}% ({perf_stats['total']} signaux)
- Precision ACHETER : {prec_ach}% | Precision EVITER : {prec_ev}%
- {perf_resume}

Adapte tes recommandations selon tes forces et faiblesses identifiées.
Si un secteur te pose problème, sois plus conservateur dessus.
"""

    section_lundi = ""
    if est_lundi:
        section_lundi = """
**Dividendes de la semaine** (lundi uniquement)
| Valeur | Date détachement | Montant estimé | Rendement |
|--------|-----------------|----------------|-----------|
"""

    indice_txt = f"CAC 40 : {cac_cours:.0f} pts ({'+' if cac_var > 0 else ''}{cac_var}%)" if cac_cours else ""

    macro_txt = ""
    if macro:
        vix_str   = f"VIX : {macro['vix']}" if macro.get("vix") else ""
        eurusd_str = f"EUR/USD : {macro.get('eurusd','N/A')} ({macro.get('eurusd_var', 0):+.2f}%)" if macro.get("eurusd") else ""
        brent_str  = f"Brent : {macro.get('brent','N/A')}$ ({macro.get('brent_var', 0):+.1f}%)" if macro.get("brent") else ""
        alertes    = " | ".join(macro.get("alerte_macro", []))
        macro_txt  = f"**Contexte macro :** {' | '.join(filter(None, [vix_str, eurusd_str, brent_str]))}"
        fg = macro.get("fear_greed", {})
        if fg.get("score") is not None:
            macro_txt += f" | Fear&Greed : {fg['score']}/100 ({fg['label']})"
        if _rapport_espion_cache:
            res = _rapport_espion_cache.get("resume", {})
            macro_txt += f"\n**Argent institutionnel (hebdo) :** secteurs en force : {res.get('secteurs_en_force',[])} | en sortie : {res.get('secteurs_en_sortie',[])}"
            if res.get("top_achats_instit"):
                macro_txt += f"\n**Accumulation institutions :** {', '.join(res['top_achats_instit'][:5])}"
        if _rapport_news_cache:
            sm = _rapport_news_cache.get("marche", {})
            macro_txt += f"\n**Sentiment presse financière :** {sm.get('sentiment_global', 0):+.2f} | {sm.get('nb_articles', 0)} articles analysés"
            titres = sm.get("titres_cles", [])[:3]
            if titres:
                macro_txt += "\n" + "\n".join(f"- {t}" for t in titres)
        if alertes:
            macro_txt += f"\n**ALERTES MACRO :** {alertes}"
        malus_total = macro.get("malus_global", 0) + fg.get("malus", 0)
        if malus_total < 0:
            macro_txt += f"\n**Malus global appliqué sur tous les scores : {malus_total} pts**"

    return f"""Tu es l'agent trader IA le plus avancé au monde.
Tu analyses le marché français pour Arnaud, investisseur PEA débutant.
Nous sommes le {jour} {today.strftime('%d/%m/%Y')}.

## Données marché temps réel

{indice_txt}
{macro_txt}

{bloc}

{perf_txt}

## Portefeuille virtuel (simulation)
{pf_resume}

## Tes règles d'analyse

1. Le score de confiance (0-100) est calculé algorithmiquement. Il t'est donné, utilise-le.
2. Croise TOUJOURS au moins 3 indicateurs avant de valider un signal fort.
3. Un Golden Cross ou Death Cross est un signal majeur prioritaire.
4. Un volume x2 ou plus confirme la direction du mouvement.
5. Les patterns de bougies renforcent ou contredisent les indicateurs.
6. Adapte-toi à ta performance passée par secteur.
7. Sois honnête sur l'incertitude. Ne force pas un signal si les indicateurs divergent.
8. Intègre le momentum sectoriel dans ton analyse.
9. Si VIX > 25 ou alerte macro, signale-le en début de briefing et renforce le biais défensif.
10. Une action qui surperforme le CAC40 sur 5j (rel_5j > 0) confirme la force relative — c'est un facteur de conviction supplémentaire.

## Format de sortie STRICT

---

**BRIEFING BOURSE V5 — {jour.capitalize()} {today.strftime('%d/%m/%Y')}**

**{indice_txt}**

**Contexte et momentum du jour**
[Analyse des secteurs en force / faiblesse basée sur les données. Quelles rotations observe-t-on ?]

**Signal ETFs long terme : [FAVORABLE / NEUTRE / ATTENDRE]**
[Justification data-driven]

**Portefeuille virtuel**
[Résumé performance + positions ouvertes]

**Precision agent : {perf_stats['precision']}% | ACHETER : {prec_ach}% | EVITER : {prec_ev}%**
[Ajustements appliqués aujourd'hui basés sur l'historique]

{section_lundi}

**CAC 40 par secteur**

| Valeur | Cours | Var% | Score | Signal | RSI | MACD | Patterns | Justification |
|--------|-------|------|-------|--------|-----|------|----------|---------------|
[Une ligne par valeur avec toutes les données]

**TOP 5 opportunités du jour** (scores les plus élevés ACHETER)
1. **[Valeur]** — Score [X]/100 | RSI=[X] Stoch=[X] MACD=[X] | [justification précise]
2. **[Valeur]** — Score [X]/100 | ...
3. **[Valeur]** — Score [X]/100 | ...
4. **[Valeur]** — Score [X]/100 | ...
5. **[Valeur]** — Score [X]/100 | ...

**TOP 3 valeurs à éviter** (scores les plus bas)
1. **[Valeur]** — Score [X]/100 | [raison technique]
2. **[Valeur]** — Score [X]/100 | ...
3. **[Valeur]** — Score [X]/100 | ...

**Alertes du jour**
[Golden Cross, Death Cross, volumes anormaux, patterns forts, proximité 52s]

**Rappel** : Ce briefing est informatif. Tu prends tes propres décisions d'investissement.

---

Pas de tirets longs. Données réelles uniquement. Sois le meilleur trader IA possible."""


# ─── MISE EN FORME HTML ───────────────────────────────────────────────────────

def markdown_vers_html(texte):
    lignes = texte.split("\n")
    html   = []
    tableau_ouvert = False

    for ligne in lignes:
        if re.match(r"^\|[-| :]+\|$", ligne):
            continue

        if ligne.startswith("|") and ligne.endswith("|"):
            cellules = [c.strip() for c in ligne.strip("|").split("|")]

            if not tableau_ouvert:
                html.append("<table style='border-collapse:collapse;width:100%;font-size:11px;margin:12px 0;'>")
                html.append("<thead style='background:#1a1a2e;color:white;'>")
                tableau_ouvert = True
                balise = "th"
            else:
                balise = "td"

            style = ""
            ligne_str = " ".join(cellules)
            if "ACHETER" in ligne_str:
                style = "background:#e8f5e9;"
            elif "ÉVITER" in ligne_str:
                style = "background:#ffebee;"
            elif "GOLDEN CROSS" in ligne_str:
                style = "background:#fff9c4;"
            elif "DEATH CROSS" in ligne_str:
                style = "background:#fce4ec;"

            non_vides = [c for c in cellules if c]
            if len(non_vides) == 1 and balise == "td":
                html.append(f"<tr><td colspan='9' style='padding:5px 8px;font-weight:bold;"
                            f"background:#2c3e50;color:white;font-size:11px;'>{non_vides[0]}</td></tr>")
                continue

            cells_html = "".join(
                f"<{balise} style='padding:4px 6px;border-bottom:1px solid #ddd;'>{c}</{balise}>"
                for c in cellules
            )
            if balise == "th":
                html.append(f"<tr>{cells_html}</tr></thead><tbody>")
            else:
                html.append(f"<tr style='{style}'>{cells_html}</tr>")
            continue

        if tableau_ouvert:
            html.append("</tbody></table>")
            tableau_ouvert = False

        ligne = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", ligne)

        if ligne.strip() == "":
            html.append("<br>")
        elif ligne.strip() == "---":
            html.append("<hr style='border:1px solid #ddd;margin:8px 0;'>")
        elif ligne.startswith("**Alertes"):
            html.append(f"<p style='margin:3px 0;background:#fff3cd;padding:6px;border-radius:4px;'>{ligne}</p>")
        else:
            html.append(f"<p style='margin:3px 0;'>{ligne}</p>")

    if tableau_ouvert:
        html.append("</tbody></table>")

    return "\n".join(html)


def valoriser_portefeuille_dm():
    """Valorise au prix du jour le portefeuille virtuel V5 (cœur). Renvoie une ligne HTML ou ''."""
    fichier = "dual_momentum_portefeuille.json"
    if not os.path.exists(fichier):
        return ""
    try:
        with open(fichier, "r", encoding="utf-8") as f:
            pf = json.load(f)
        uw, uu, cash = pf.get("units_world", 0), pf.get("units_usa", 0), pf.get("cash", 0)
        date_init = pf.get("date_init", "")
        cw8 = float(yf.Ticker("CW8.PA").history(period="5d")["Close"].dropna().iloc[-1])
        ese = float(yf.Ticker("ESE.PA").history(period="5d")["Close"].dropna().iloc[-1])
        valeur = uw * cw8 + uu * ese + cash
        perf = (valeur - 10000) / 10000 * 100
        # Référence : World buy & hold depuis le départ
        hist = yf.Ticker("CW8.PA").history(start=date_init)["Close"].dropna()
        perf_world = (cw8 / float(hist.iloc[0]) - 1) * 100 if len(hist) else None
        coul = "#2e7d32" if perf >= 0 else "#c62828"
        ref = ""
        if perf_world is not None:
            ecart = perf - perf_world
            cref = "#2e7d32" if ecart >= 0 else "#c62828"
            ref = (f" · vs World buy &amp; hold {'+' if perf_world >= 0 else ''}{perf_world:.2f}% "
                   f"(<span style='color:{cref};'>{'+' if ecart >= 0 else ''}{ecart:.2f} pts</span>)")
        val_world = uw * cw8
        val_usa   = uu * ese
        px_world  = pf.get("dernier_cours", {}).get("World")
        px_usa    = pf.get("dernier_cours", {}).get("USA")

        def delta_cours(cours_actuel, prix_achat):
            if prix_achat is None or prix_achat == 0:
                return ""
            d = cours_actuel - prix_achat
            c = "#2e7d32" if d >= 0 else "#c62828"
            return f"<span style='color:{c};font-size:11px;'>({'+' if d >= 0 else ''}{d:.2f}€)</span>"

        tableau_pf = (
            f"<table style='margin-top:8px;width:100%;border-collapse:collapse;font-size:13px;'>"
            f"<thead><tr style='background:#f1f8f4;'>"
            f"<th style='padding:5px 8px;text-align:left;color:#555;font-weight:600;'>ETF</th>"
            f"<th style='padding:5px 8px;text-align:right;color:#555;font-weight:600;'>Parts</th>"
            f"<th style='padding:5px 8px;text-align:right;color:#555;font-weight:600;'>Prix achat</th>"
            f"<th style='padding:5px 8px;text-align:right;color:#555;font-weight:600;'>Cours actuel</th>"
            f"<th style='padding:5px 8px;text-align:right;color:#555;font-weight:600;'>Valeur</th>"
            f"</tr></thead><tbody>"
            f"<tr style='border-top:1px solid #ddd;'>"
            f"<td style='padding:5px 8px;'>World (CW8.PA)</td>"
            f"<td style='padding:5px 8px;text-align:right;'>{uw:.4f}</td>"
            f"<td style='padding:5px 8px;text-align:right;color:#888;'>{f'{px_world:.2f}€' if px_world else '—'}</td>"
            f"<td style='padding:5px 8px;text-align:right;'>{cw8:.2f}€ {delta_cours(cw8, px_world)}</td>"
            f"<td style='padding:5px 8px;text-align:right;'>{val_world:.0f}€</td>"
            f"</tr>"
            f"<tr style='border-top:1px solid #ddd;'>"
            f"<td style='padding:5px 8px;'>USA (ESE.PA)</td>"
            f"<td style='padding:5px 8px;text-align:right;'>{uu:.4f}</td>"
            f"<td style='padding:5px 8px;text-align:right;color:#888;'>{f'{px_usa:.2f}€' if px_usa else '—'}</td>"
            f"<td style='padding:5px 8px;text-align:right;'>{ese:.2f}€ {delta_cours(ese, px_usa)}</td>"
            f"<td style='padding:5px 8px;text-align:right;'>{val_usa:.0f}€</td>"
            f"</tr>"
            f"<tr style='border-top:2px solid #1d9e75;background:#f1f8f4;font-weight:600;'>"
            f"<td style='padding:5px 8px;' colspan='4'>Total</td>"
            f"<td style='padding:5px 8px;text-align:right;'>"
            f"<span style='color:{coul};'>{'+' if perf >= 0 else ''}{perf:.2f}%</span>"
            f" — <strong>{valeur:.0f}€</strong>"
            f"</td></tr>"
            f"</tbody></table>"
        )
        # Mise à jour du JSON pour la PWA
        pf["cours_actuel"] = {"World": round(cw8, 4), "USA": round(ese, 4)}
        pf["valeur_actuelle"] = round(valeur, 2)
        pf["perf_actuelle"] = round(perf, 4)
        pf["historique_valeur"][datetime.date.today().isoformat()] = round(valeur, 2)
        with open(fichier, "w", encoding="utf-8") as f:
            json.dump(pf, f, ensure_ascii=False, indent=2)

        resume_pf = (
            f"<p style='margin:6px 0 0;font-size:13px;color:#555;'>Portefeuille virtuel V5 "
            f"depuis le {date_init[8:10]}/{date_init[5:7]}{ref}</p>"
        )
        return tableau_pf + resume_pf
    except Exception as e:
        print(f"  WARN valorisation portefeuille V5 : {e}")
        return ""


def generer_html_dual_momentum():
    """Bandeau 'position sérieuse' alimenté par l'agent Dual Momentum (cœur du patrimoine)."""
    fichier = "dual_momentum_statut.json"
    if not os.path.exists(fichier):
        return ""
    try:
        with open(fichier, "r", encoding="utf-8") as f:
            s = json.load(f)
    except Exception:
        return ""
    alloc = s.get("allocation", "")
    if not alloc:
        return ""
    moms = s.get("momentums", {})
    maj = s.get("date", "")
    ligne_pf = valoriser_portefeuille_dm()

    # Tableau explicatif : une ligne par poche active
    NOMS_ETF = {"World": "Amundi MSCI World Screened (CW8)", "USA": "Amundi MSCI USA Screened (ESE)"}
    ALLOC = {"World": 50, "USA": 50}  # allocation fixe 50/50 tant que les deux sont positifs
    lignes_tableau = ""
    for poche, mom in moms.items():
        nom = NOMS_ETF.get(poche, poche)
        alloc_pct = ALLOC.get(poche, "—")
        coul_mom = "#2e7d32" if mom >= 0 else "#c62828"
        lignes_tableau += (
            f"<tr style='border-top:1px solid #c8e6c9;'>"
            f"<td style='padding:5px 8px;'>{nom}</td>"
            f"<td style='padding:5px 8px;text-align:center;font-weight:600;'>{alloc_pct}%</td>"
            f"<td style='padding:5px 8px;text-align:right;color:{coul_mom};font-weight:600;'>{mom:+.1f}%</td>"
            f"<td style='padding:5px 8px;font-size:12px;color:#666;'>Conserver</td>"
            f"</tr>"
        )

    tableau = (
        f"<table style='margin-top:10px;width:100%;border-collapse:collapse;font-size:13px;'>"
        f"<thead><tr style='background:#c8e6c9;'>"
        f"<th style='padding:5px 8px;text-align:left;color:#0f6e56;'>ETF</th>"
        f"<th style='padding:5px 8px;text-align:center;color:#0f6e56;'>Alloc.</th>"
        f"<th style='padding:5px 8px;text-align:right;color:#0f6e56;'>Momentum 12m</th>"
        f"<th style='padding:5px 8px;text-align:left;color:#0f6e56;'>Action</th>"
        f"</tr></thead><tbody>{lignes_tableau}</tbody></table>"
    )

    return f"""
<div style='margin:0 0 16px;padding:14px 16px;background:#e8f5ee;border-left:4px solid #1d9e75;border-radius:6px;'>
  <p style='margin:0;font-size:13px;font-weight:bold;color:#0f6e56;'>Cœur du patrimoine (Dual Momentum) — rien à faire au quotidien</p>
  {tableau}
  {ligne_pf}
  <p style='margin:8px 0 0;font-size:12px;color:#888;'>Revue mensuelle le 1er · MAJ {maj}</p>
</div>"""


FICHIER_QUALITE_DONNEES = "data_quality_log.json"

def logger_qualite_donnees(donnees):
    """Journalise le nombre de valeurs sans données de marché exploitables par jour,
    pour distinguer un incident isolé (Yahoo) d'un pattern récurrent à traiter
    (voir roadmap V5 : diversification des sources de données)."""
    erreurs = [d for d in donnees if "erreur" in d]
    entree = {
        "date":           datetime.date.today().isoformat(),
        "heure":          datetime.datetime.now(TZ_PARIS).strftime("%H:%M"),
        "total":          len(donnees),
        "nb_erreurs":     len(erreurs),
        "tickers_erreur": [{"nom": d["nom"], "raison": d.get("erreur", "")} for d in erreurs],
    }
    if os.path.exists(FICHIER_QUALITE_DONNEES):
        with open(FICHIER_QUALITE_DONNEES, "r", encoding="utf-8") as f:
            log = json.load(f)
    else:
        log = []
    log.append(entree)
    log = log[-90:]  # ~3 mois glissants, suffisant pour repérer un pattern
    with open(FICHIER_QUALITE_DONNEES, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)
    if erreurs:
        print(f"  Qualité données journalisée : {len(erreurs)}/{len(donnees)} en erreur")
    return entree


def envoyer_email_alerte(raison):
    """Email court envoyé à la place du briefing normal quand les données de marché
    sont invalides (NaN) — évite d'envoyer des chiffres faux plutôt que de se taire."""
    today = datetime.date.today()
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Agent Bourse V5 — Alerte données — {today.strftime('%d/%m/%Y')}"
    msg["From"]    = ZOHO_EMAIL
    msg["To"]      = ", ".join(DESTINATAIRES)

    texte = (f"Le briefing du {today.strftime('%d/%m/%Y')} n'a pas pu être calculé correctement.\n\n"
             f"Raison : {raison}\n\n"
             "Aucune valeur n'a été mise à jour (portefeuille, performance) pour éviter "
             "d'afficher des chiffres faux. La dernière valeur connue reste affichée dans la PWA.")
    msg.attach(MIMEText(texte, "plain", "utf-8"))
    html = f"""<html><body style='font-family:Arial,sans-serif;font-size:13px;color:#222;'>
<p><strong>Le briefing du {today.strftime('%d/%m/%Y')} n'a pas pu être calculé correctement.</strong></p>
<p>Raison : {raison}</p>
<p>Aucune valeur n'a été mise à jour (portefeuille, performance) pour éviter d'afficher des
chiffres faux. La dernière valeur connue reste affichée dans la PWA.</p>
</body></html>"""
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP(ZOHO_SMTP, ZOHO_PORT) as serveur:
        serveur.starttls()
        serveur.login(ZOHO_EMAIL, ZOHO_PASSWORD)
        serveur.sendmail(ZOHO_EMAIL, DESTINATAIRES, msg.as_string())

    print(f"Email d'alerte envoyé à : {', '.join(DESTINATAIRES)} — raison : {raison}")


def envoyer_email(briefing, perf_stats, html_portefeuille="", html_dual_momentum=""):
    today     = datetime.date.today()
    precision = perf_stats.get("precision", 0)
    sujet     = f"Agent Bourse V5 — {today.strftime('%d/%m/%Y')} | Precision : {precision}%"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = sujet
    msg["From"]    = ZOHO_EMAIL
    msg["To"]      = ", ".join(DESTINATAIRES)

    msg.attach(MIMEText(briefing, "plain", "utf-8"))

    contenu = markdown_vers_html(briefing)
    html = f"""<html><body style='font-family:Arial,sans-serif;font-size:13px;
color:#222;max-width:1000px;margin:auto;padding:20px;'>
<div style='background:linear-gradient(135deg,#1a1a2e,#16213e);color:white;padding:16px 20px;border-radius:8px 8px 0 0;'>
  <h2 style='margin:0;font-size:18px;'>Agent Bourse V5 — {today.strftime('%d/%m/%Y')}</h2>
  <p style='margin:6px 0 0;font-size:12px;opacity:0.8;'>
    RSI + Stochastique + MACD + Bollinger + ATR + Bougies + Pivot Points + Beta + Auto-apprentissage
    | Precision : <strong>{precision}%</strong>
  </p>
</div>
<div style='border:1px solid #ddd;border-top:none;padding:20px;border-radius:0 0 8px 8px;'>
{html_dual_momentum}
{contenu}
<hr style='border:1px solid #ddd;margin:20px 0;'>
{html_portefeuille}
</div>
</body></html>"""

    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP(ZOHO_SMTP, ZOHO_PORT) as serveur:
        serveur.starttls()
        serveur.login(ZOHO_EMAIL, ZOHO_PASSWORD)
        serveur.sendmail(ZOHO_EMAIL, DESTINATAIRES, msg.as_string())

    print(f"Email envoyé à : {', '.join(DESTINATAIRES)}")


# ─── COST LOGGING ─────────────────────────────────────────────────────────────

COSTS_LOG = "costs_log.json"
TARIFS = {
    "claude-opus-4-8":        {"input": 5.0,  "output": 25.0},
    "claude-haiku-4-5-20251001": {"input": 1.0, "output": 5.0},
    "claude-haiku-4-5":       {"input": 1.0,  "output": 5.0},
}

def _loguer_cout(agent, model, input_tokens, output_tokens):
    """Ajoute une entrée dans costs_log.json (tokens + coût en USD)."""
    tarif = TARIFS.get(model, {"input": 5.0, "output": 25.0})
    cout_usd = (input_tokens * tarif["input"] + output_tokens * tarif["output"]) / 1_000_000
    entree = {
        "date":   datetime.date.today().isoformat(),
        "heure":  datetime.datetime.now().strftime("%H:%M"),
        "agent":  agent,
        "model":  model,
        "input":  input_tokens,
        "output": output_tokens,
        "usd":    round(cout_usd, 6),
    }
    log = []
    if os.path.exists(COSTS_LOG):
        try:
            with open(COSTS_LOG, "r", encoding="utf-8") as f:
                log = json.load(f)
        except Exception:
            log = []
    log.append(entree)
    log = log[-500:]  # garde les 500 dernières entrées
    with open(COSTS_LOG, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)
    print(f"  Coût API [{agent}] : {input_tokens} input / {output_tokens} output = ${cout_usd:.4f}")


# ─── MAIN ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    today     = datetime.date.today()
    est_lundi = today.weekday() == 0

    print("Chargement persistance intraday...")
    _persistance_cache = charger_persistance_intraday()
    print(f"  {len(_persistance_cache)} valeurs avec historique intraday")

    print("Chargement poids indicateurs appris...")
    _poids_indicateurs_cache = charger_poids_indicateurs()
    print(f"  {len(_poids_indicateurs_cache)} secteurs avec poids appris")

    print("Chargement rapport agent espion...")
    FICHIER_RAPPORT_ESPION = "rapport_espion.json"
    if os.path.exists(FICHIER_RAPPORT_ESPION):
        with open(FICHIER_RAPPORT_ESPION, "r", encoding="utf-8") as f:
            _rapport_espion_cache = json.load(f)
        resume = _rapport_espion_cache.get("resume", {})
        print(f"  Rapport du {_rapport_espion_cache.get('date','?')} chargé")
        print(f"  Secteurs en force : {resume.get('secteurs_en_force', [])}")
    else:
        print("  Pas de rapport espion disponible")

    print("Chargement rapport agent news...")
    FICHIER_RAPPORT_NEWS = "rapport_news.json"
    if os.path.exists(FICHIER_RAPPORT_NEWS):
        with open(FICHIER_RAPPORT_NEWS, "r", encoding="utf-8") as f:
            _rapport_news_cache = json.load(f)
        print(f"  Rapport du {_rapport_news_cache.get('date','?')} chargé — sentiment global {_rapport_news_cache.get('marche',{}).get('sentiment_global',0):+.2f}")
    else:
        print("  Pas de rapport news disponible, fallback Yahoo Finance")

    print("Chargement historique performance...")
    perf = charger_performance()

    print("Récupération CAC 40...")
    cac_cours, cac_var, hist_cac = recuperer_indice_cac()

    print("Récupération contexte macro (VIX, EUR/USD, Brent)...")
    macro = recuperer_contexte_macro()
    malus_macro = macro["malus_global"]
    if macro["alerte_macro"]:
        print(f"  Alertes macro : {' | '.join(macro['alerte_macro'])}")
    print(f"  Malus global appliqué : {malus_macro} pts")

    print("Vérification annonces BCE/Fed...")
    annonce_bc, annonce_bc_label = verifier_annonce_banque_centrale()
    malus_bc = -15 if annonce_bc else 0
    if annonce_bc:
        print(f"  ALERTE : {annonce_bc_label} → malus {malus_bc} pts")
        macro["alerte_macro"].append(annonce_bc_label)
    malus_total = malus_macro + malus_bc

    print("Récupération Fear & Greed Index...")
    fg = recuperer_fear_greed()
    malus_fg = fg["malus"]
    macro["fear_greed"] = fg
    if fg["score"] is not None:
        print(f"  Fear & Greed : {fg['score']}/100 ({fg['label']}) → malus {malus_fg} pts")
        if malus_fg != 0:
            macro["alerte_macro"].append(f"Fear&Greed {fg['score']}/100 ({fg['label']})")

    print("Récupération données temps réel (1 an d'historique)...")
    donnees = []
    for nom, ticker in CAC40.items():
        print(f"  {nom}...")
        d = recuperer_donnees_action(nom, ticker, hist_cac)
        if d and "erreur" not in d:
            d["malus_macro"] = malus_macro
            d["malus_banque_centrale"] = malus_bc
            d["malus_fear_greed"] = malus_fg
            # recalculer le score avec les malus globaux
            score, signal = calculer_score_confiance(d, persistance_intraday=_persistance_cache)
            d["score"]  = score
            d["signal"] = signal
            donnees.append(d)
        elif d:
            donnees.append(d)

    ok      = [d for d in donnees if "erreur" not in d]
    erreurs = [d for d in donnees if "erreur" in d]
    print(f"OK : {len(ok)}/39 | Erreurs : {len(erreurs)}")
    logger_qualite_donnees(donnees)

    print("Calcul momentum relatif vs CAC40...")
    donnees_dict = {d["nom"]: d for d in ok}
    momentum_rel = calculer_momentum_relatif_cac(donnees_dict, cac_var)
    for nom, mr in momentum_rel.items():
        if nom in donnees_dict:
            donnees_dict[nom]["bonus_momentum_rel"] = mr["bonus_momentum_rel"]
            donnees_dict[nom]["perf_5j"]  = mr["perf_5j"]
            donnees_dict[nom]["perf_20j"] = mr["perf_20j"]
            donnees_dict[nom]["rel_5j"]   = mr["rel_5j"]
            # recalculer le score avec les nouveaux bonus
            score, signal = calculer_score_confiance(donnees_dict[nom], persistance_intraday=_persistance_cache)
            donnees_dict[nom]["score"]  = score
            donnees_dict[nom]["signal"] = signal
    donnees = list(donnees_dict.values()) + [d for d in donnees if "erreur" in d]

    print("Évaluation performance hier...")
    perf, perf_resume = evaluer_performance_hier(perf, donnees)

    print("Calcul momentum sectoriel...")
    donnees_dict = {d["nom"]: d for d in ok}
    momentum     = calculer_momentum_sectoriel(donnees_dict)

    print("Gestion portefeuille virtuel...")
    pf_resume, pf_data, pf_donnees_dict, pf_invalide = gerer_portefeuille_virtuel(donnees, perf)

    if pf_invalide:
        print("Données de marché invalides (NaN) : envoi d'une alerte à la place du briefing normal.")
        n_erreurs = len([d for d in donnees if "erreur" in d])
        envoyer_email_alerte(f"{n_erreurs}/{len(donnees)} valeurs sans données de marché exploitables aujourd'hui.")
        raise SystemExit(0)

    print("Génération briefing par Claude...")
    prompt  = construire_prompt(donnees, cac_cours, cac_var, perf_resume, perf["stats"], momentum, pf_resume, est_lundi, macro=macro)
    client  = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    message = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=6000,
        messages=[{"role": "user", "content": prompt}]
    )
    briefing = message.content[0].text
    _loguer_cout("briefing", "claude-opus-4-8",
                 message.usage.input_tokens, message.usage.output_tokens)

    print("Sauvegarde recommandations...")
    sauvegarder_recommandations(perf, donnees)

    print("Sauvegarde briefing pour PWA...")
    briefing_pwa = {
        "date":      datetime.datetime.now(TZ_PARIS).date().isoformat(),
        "heure":     datetime.datetime.now(TZ_PARIS).strftime("%H:%M"),
        "texte":     briefing,
        "cac_cours": cac_cours,
        "cac_var":   cac_var,
        "precision": perf["stats"].get("precision", 0),
    }
    with open("dernier_briefing.json", "w", encoding="utf-8") as f:
        json.dump(briefing_pwa, f, ensure_ascii=False, indent=2)

    print("Envoi email...")
    # Performance du CAC 40 depuis le départ du portefeuille (comparaison)
    perf_cac_pf = None
    date_debut_pf = None
    try:
        dates_pf = sorted(pf_data.get("historique_valeur", {}).keys())
        if dates_pf and hist_cac is not None and not hist_cac.empty:
            date_debut_pf = dates_pf[0]
            cac_close = hist_cac["Close"]
            apres = cac_close[cac_close.index.strftime("%Y-%m-%d") >= date_debut_pf]
            if len(apres) >= 1:
                perf_cac_pf = round((cac_close.iloc[-1] / apres.iloc[0] - 1) * 100, 2)
    except Exception as e:
        print(f"  Comparaison CAC indisponible : {e}")

    html_pf = generer_html_portefeuille(pf_data, pf_donnees_dict, perf_cac_pf, date_debut_pf)
    html_dm = generer_html_dual_momentum()
    envoyer_email(briefing, perf["stats"], html_pf, html_dm)

    print("Terminé.")
