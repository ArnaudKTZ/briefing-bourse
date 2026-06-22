#!/usr/bin/env python3
"""
Agent Bourse V3 — Le meilleur agent trader IA
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

DESTINATAIRES = [
    "xtrem111team@gmail.com",
    "ferrey83400@gmail.com",
    "Arnaud.kuntz@zoho.eu",
]

FICHIER_PERFORMANCE  = "performance.json"
FICHIER_PORTEFEUILLE = "portefeuille_virtuel.json"
FICHIER_INTRADAY     = "intraday_scores.json"

_persistance_cache        = {}  # chargé une fois au démarrage du main
_poids_indicateurs_cache  = {}  # poids appris par indicateur/secteur


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

CAC40 = {
    "LVMH":               "MC.PA",
    "TotalEnergies":      "TTE.PA",
    "Hermès":             "RMS.PA",
    "Airbus":             "AIR.PA",
    "Schneider Electric": "SU.PA",
    "L'Oréal":            "OR.PA",
    "Sanofi":             "SAN.PA",
    "BNP Paribas":        "BNP.PA",
    "Air Liquide":        "AI.PA",
    "Safran":             "SAF.PA",
    "Danone":             "BN.PA",
    "Vinci":              "DG.PA",
    "Kering":             "KER.PA",
    "Société Générale":   "GLE.PA",
    "Stellantis":         "STLAM.MI",
    "Saint-Gobain":       "SGO.PA",
    "ArcelorMittal":      "MT",
    "Pernod Ricard":      "RI.PA",
    "Michelin":           "ML.PA",
    "Capgemini":          "CAP.PA",
    "Renault":            "RNO.PA",
    "Legrand":            "LR.PA",
    "Publicis":           "PUB.PA",
    "Bouygues":           "EN.PA",
    "Engie":              "ENGI.PA",
    "Orange":             "ORA.PA",
    "Vivendi":            "VIV.PA",
    "Eurofins Scientific":"ERF.PA",
    "Teleperformance":    "TEP.PA",
    "Alstom":             "ALO.PA",
    "Worldline":          "WLN.PA",
    "Veolia":             "VIE.PA",
    "STMicroelectronics": "STM",
    "Dassault Systèmes":  "DSY.PA",
    "Edenred":            "EDEN.PA",
    "Accor":              "AC.PA",
    "Eurazeo":            "RF.PA",
    "Thales":             "HO.PA",
    "Forvia":             "FRVIA.PA",
}

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
    """Récupère PER, croissance CA, dette/fonds propres, marge nette via yfinance."""
    try:
        info = ticker_obj.info
        per         = info.get("trailingPE") or info.get("forwardPE")
        rev_growth  = info.get("revenueGrowth")      # ex: 0.12 = +12%
        debt_equity = info.get("debtToEquity")        # ex: 45.2 = 45.2%
        marge_nette = info.get("profitMargins")       # ex: 0.18 = 18%
        per         = round(per, 1) if per else None
        rev_growth  = round(rev_growth * 100, 1) if rev_growth else None
        debt_equity = round(debt_equity, 1) if debt_equity else None
        marge_nette = round(marge_nette * 100, 1) if marge_nette else None
        return {"per": per, "rev_growth": rev_growth, "debt_equity": debt_equity, "marge_nette": marge_nette}
    except:
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

    return max(-15, min(15, bonus))


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
    except:
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
    except:
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
    except:
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

    # Bonus/malus sentiment news
    sentiment = d.get("sentiment_news", 0)
    score += sentiment * 4

    # Malus si résultats dans les 3 jours (risque élevé)
    if d.get("resultats_proches"):
        score = max(35, min(score, 64))  # force SURVEILLER
        d["alerte_resultats"] = True

    # Bonus indicateurs appris par secteur
    score += d.get("bonus_indicateurs_appris", 0)

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
            except:
                pass

        # Patterns bougies
        patterns = detecter_patterns(hist.tail(3))

        # Fondamentaux
        fond = recuperer_fondamentaux(stock)
        bonus_fond = scorer_fondamentaux(fond)

        # News + sentiment
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
        if not hist.empty:
            cours    = round(hist["Close"].iloc[-1], 0)
            hier     = round(hist["Close"].iloc[-2], 0)
            variation = round((cours - hier) / hier * 100, 2)
            return cours, variation, hist
    except:
        pass
    return None, None, None


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

        if signal not in ["ACHETER", "ÉVITER"] or not prix_hier:
            continue

        d_auj = donnees_dict.get(nom)
        if not d_auj:
            continue

        prix_auj = d_auj.get("cours")
        if not prix_auj:
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
        if signal not in ["ACHETER", "ÉVITER"] or not prix_hier:
            continue
        d_auj = donnees_dict.get(nom)
        if not d_auj:
            continue
        prix_auj = d_auj.get("cours")
        if not prix_auj:
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

    return resume_pf, pf, donnees_dict


def generer_html_portefeuille(pf, donnees_dict):
    """Génère le bloc HTML du tableau portefeuille virtuel pour l'email."""
    valeur_totale = list(pf["historique_valeur"].values())[-1] if pf["historique_valeur"] else 10000.0
    perf_pf = round((valeur_totale - 10000) / 10000 * 100, 2)
    signe_global = "+" if perf_pf >= 0 else ""
    gain_total = round(valeur_totale - 10000, 2)
    signe_gain = "+" if gain_total >= 0 else ""
    couleur_global = "#2e7d32" if perf_pf >= 0 else "#c62828"

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
        lignes_trades += f"""<tr style='border-bottom:1px solid #eee;background:#f9f9f9;'>
          <td style='padding:7px 10px;font-weight:500;'>{nom}</td>
          <td style='padding:7px 10px;'><div style='color:#333;'>{fmt_date(pos['date_entree'])} {heure_e}</div><div style='margin-top:3px;'>{src_e}</div></td>
          <td style='padding:7px 10px;color:#999;font-style:italic;'>en cours</td>
          <td style='padding:7px 10px;text-align:right;'>{pos['prix_entree']:.2f} €</td>
          <td style='padding:7px 10px;text-align:right;color:#999;'>—</td>
          <td style='padding:7px 10px;text-align:right;color:#999;font-size:12px;'>{frais_achat:.2f} €</td>
          <td style='padding:7px 10px;text-align:right;font-weight:600;color:{couleur};'>{signe}{pnl:.2f} %</td>
        </tr>"""

    if not lignes_trades:
        lignes_trades = "<tr><td colspan='7' style='padding:12px;text-align:center;color:#999;'>Aucun trade pour l'instant</td></tr>"

    return f"""
<div style='margin:20px 0;'>
  <h3 style='margin:0 0 12px;font-size:15px;color:#1a1a2e;'>Portefeuille virtuel</h3>
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
        <td colspan='6' style='padding:8px 10px;font-weight:600;'>Gain/Perte total (frais inclus)</td>
        <td style='padding:8px 10px;text-align:right;font-weight:700;font-size:14px;color:{couleur_global};'>{signe_gain}{gain_total:.0f} € ({signe_global}{perf_pf:.2f} %)</td>
      </tr>
    </tfoot>
  </table>
  <div style='display:flex;gap:10px;margin-top:10px;flex-wrap:wrap;align-items:center;'>
    <span style='font-size:11px;color:#999;'>Capital libre : {capital_libre:.0f} € | Frais Boursobank : 0,5% min 0,50 €</span>
    <span style='font-size:10px;background:#e3f0fb;color:#1565c0;padding:2px 7px;border-radius:3px;'>Briefing = signal 7h</span>
    <span style='font-size:10px;background:#fff8e1;color:#e65100;padding:2px 7px;border-radius:3px;'>Intraday = signal 9h/12h/16h</span>
    <span style='font-size:10px;background:#fce4ec;color:#b71c1c;padding:2px 7px;border-radius:3px;'>Alerte = score 85+</span>
  </div>
</div>"""


# ─── CONSTRUCTION DU PROMPT ───────────────────────────────────────────────────

def construire_prompt(donnees, cac_cours, cac_var, perf_resume, perf_stats, momentum, pf_resume, est_lundi):
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

    return f"""Tu es l'agent trader IA le plus avancé au monde.
Tu analyses le marché français pour Arnaud, investisseur PEA débutant.
Nous sommes le {jour} {today.strftime('%d/%m/%Y')}.

## Données marché temps réel

{indice_txt}

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

## Format de sortie STRICT

---

**BRIEFING BOURSE V3 — {jour.capitalize()} {today.strftime('%d/%m/%Y')}**

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


def envoyer_email(briefing, perf_stats, html_portefeuille=""):
    today     = datetime.date.today()
    precision = perf_stats.get("precision", 0)
    sujet     = f"Agent Bourse V3 — {today.strftime('%d/%m/%Y')} | Precision : {precision}%"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = sujet
    msg["From"]    = ZOHO_EMAIL
    msg["To"]      = ", ".join(DESTINATAIRES)

    msg.attach(MIMEText(briefing, "plain", "utf-8"))

    contenu = markdown_vers_html(briefing)
    html = f"""<html><body style='font-family:Arial,sans-serif;font-size:13px;
color:#222;max-width:1000px;margin:auto;padding:20px;'>
<div style='background:linear-gradient(135deg,#1a1a2e,#16213e);color:white;padding:16px 20px;border-radius:8px 8px 0 0;'>
  <h2 style='margin:0;font-size:18px;'>Agent Bourse V3 — {today.strftime('%d/%m/%Y')}</h2>
  <p style='margin:6px 0 0;font-size:12px;opacity:0.8;'>
    RSI + Stochastique + MACD + Bollinger + ATR + Bougies + Pivot Points + Beta + Auto-apprentissage
    | Precision : <strong>{precision}%</strong>
  </p>
</div>
<div style='border:1px solid #ddd;border-top:none;padding:20px;border-radius:0 0 8px 8px;'>
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

    print("Chargement historique performance...")
    perf = charger_performance()

    print("Récupération CAC 40...")
    cac_cours, cac_var, hist_cac = recuperer_indice_cac()

    print("Récupération données temps réel (1 an d'historique)...")
    donnees = []
    for nom, ticker in CAC40.items():
        print(f"  {nom}...")
        d = recuperer_donnees_action(nom, ticker, hist_cac)
        if d:
            donnees.append(d)

    ok      = [d for d in donnees if "erreur" not in d]
    erreurs = [d for d in donnees if "erreur" in d]
    print(f"OK : {len(ok)}/39 | Erreurs : {len(erreurs)}")

    print("Évaluation performance hier...")
    perf, perf_resume = evaluer_performance_hier(perf, donnees)

    print("Calcul momentum sectoriel...")
    donnees_dict = {d["nom"]: d for d in ok}
    momentum     = calculer_momentum_sectoriel(donnees_dict)

    print("Gestion portefeuille virtuel...")
    pf_resume, pf_data, pf_donnees_dict = gerer_portefeuille_virtuel(donnees, perf)

    print("Génération briefing par Claude...")
    prompt  = construire_prompt(donnees, cac_cours, cac_var, perf_resume, perf["stats"], momentum, pf_resume, est_lundi)
    client  = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    message = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=6000,
        messages=[{"role": "user", "content": prompt}]
    )
    briefing = message.content[0].text

    print("Sauvegarde recommandations...")
    sauvegarder_recommandations(perf, donnees)

    print("Envoi email...")
    html_pf = generer_html_portefeuille(pf_data, pf_donnees_dict)
    envoyer_email(briefing, perf["stats"], html_pf)

    print("Terminé.")
