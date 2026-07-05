#!/usr/bin/env python3
"""
Scoring intraday — collecte les scores 3x/jour.
Tourne à 9h, 12h et 16h via GitHub Actions.
Sauvegarde dans intraday_scores.json pour enrichir le briefing du lendemain.
"""

import datetime
import zoneinfo

TZ_PARIS = zoneinfo.ZoneInfo("Europe/Paris")
import json
import os
import smtplib
import urllib.request
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import yfinance as yf
import pandas as pd
import numpy as np
import anthropic

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

ZOHO_EMAIL    = os.environ.get("ZOHO_EMAIL", "Arnaud.kuntz@zoho.eu")
ZOHO_PASSWORD = os.environ.get("ZOHO_PASSWORD", "")
ZOHO_SMTP     = "smtp.zoho.eu"
ZOHO_PORT     = 587

_dest_env = os.environ.get("DESTINATAIRES", "")
DESTINATAIRES = [d.strip() for d in _dest_env.split(",") if d.strip()] if _dest_env else []

# Décision Arnaud 02/07/2026 : alertes achat/vente suspendues ~1 mois (modèle
# non validé, précision ACHETER < 50%). Le scoring, le portefeuille virtuel et
# la mesure de performance continuent de tourner normalement — seul l'email
# d'alerte est coupé. À revoir ensemble vers le 02/08/2026.
ALERTES_EMAIL_ACTIVES = False

SEUIL_ALERTE         = 85
# Poids News neutralisé le 02/07/2026 (même audit que le briefing : le sentiment
# News n'a pas d'edge positif prouvé). Réactivation = remettre POIDS_NEWS à 4.
# À retester vers le 02/08 avec un mois de données propres.
POIDS_NEWS           = 0   # était 4
FICHIER_ALERTES_VUE  = "alertes_envoyees.json"
FICHIER_PORTEFEUILLE = "portefeuille_virtuel.json"
FRAIS_TAUX           = 0.005
FRAIS_MINIMUM        = 0.50
BUDGET_PAR_POSITION  = 2000.0
MAX_POSITIONS        = 5
SEUIL_ACHAT_INTRADAY = 80   # score pour ouvrir une position intraday
SEUIL_STOP_LOSS      = -5.0
SEUIL_TAKE_PROFIT    = 8.0

try:
    from ta.momentum import RSIIndicator, StochasticOscillator
    from ta.trend import MACD, SMAIndicator
    from ta.volatility import BollingerBands, AverageTrueRange
    TA_DISPONIBLE = True
except ImportError:
    TA_DISPONIBLE = False

FICHIER_INTRADAY    = "intraday_scores.json"
FICHIER_PERFORMANCE = "performance.json"
FICHIER_RAPPORT_NEWS = "rapport_news.json"
COSTS_LOG = "costs_log.json"

_TARIFS_INTRADAY = {
    "claude-haiku-4-5-20251001": {"input": 1.0, "output": 5.0},
    "claude-opus-4-8":           {"input": 5.0, "output": 25.0},
}

def _loguer_cout_intraday(agent, model, input_tokens, output_tokens):
    tarif = _TARIFS_INTRADAY.get(model, {"input": 1.0, "output": 5.0})
    cout_usd = (input_tokens * tarif["input"] + output_tokens * tarif["output"]) / 1_000_000
    entree = {
        "date":   datetime.date.today().isoformat(),
        "heure":  datetime.datetime.now(TZ_PARIS).strftime("%H:%M"),
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
    log = log[-500:]
    with open(COSTS_LOG, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)

DATES_BANQUES_CENTRALES = [
    "2026-01-30","2026-03-06","2026-04-17","2026-06-05",
    "2026-07-23","2026-09-10","2026-10-29","2026-12-17",
    "2026-01-28","2026-03-18","2026-05-06","2026-06-17",
    "2026-07-29","2026-09-16","2026-11-04","2026-12-16",
]

ETF_SECTORIELS = {
    "Banques":    "EXV1.DE",
    "Energie":    "EXV2.DE",
    "Tech":       "EXV4.DE",
    "Santé":      "EXV6.DE",
    "Industrie":  "EXH8.DE",
    "Luxe/Conso": "EXV5.DE",
    "Utilities":  "EXH7.DE",
    "Matériaux":  "EXV3.DE",
}

SECTEUR_VALEUR = {
    "LVMH": "Luxe/Conso", "Hermès": "Luxe/Conso", "Kering": "Luxe/Conso",
    "L'Oréal": "Luxe/Conso", "Pernod Ricard": "Luxe/Conso", "Danone": "Luxe/Conso",
    "Accor": "Luxe/Conso",
    "TotalEnergies": "Energie",
    "Engie": "Utilities", "Veolia": "Utilities",
    "Orange": "Telecom", "Vivendi": "Telecom", "Bouygues": "Telecom",
    "BNP Paribas": "Banques", "Société Générale": "Banques", "Eurazeo": "Banques",
    "Airbus": "Industrie", "Safran": "Industrie", "Thales": "Industrie",
    "Schneider Electric": "Industrie", "Legrand": "Industrie", "Vinci": "Industrie",
    "Michelin": "Industrie", "Renault": "Industrie", "Stellantis": "Industrie",
    "Alstom": "Industrie", "Forvia": "Industrie",
    "Saint-Gobain": "Matériaux", "ArcelorMittal": "Matériaux", "Air Liquide": "Matériaux",
    "Capgemini": "Tech", "Dassault Systèmes": "Tech", "STMicroelectronics": "Tech",
    "Worldline": "Tech", "Teleperformance": "Tech", "Publicis": "Tech",
    "Edenred": "Tech",
    "Sanofi": "Santé", "Eurofins Scientific": "Santé",
}


def analyser_etf_intraday():
    """Lecture rapide des ETF sectoriels pour détecter les rotations du jour."""
    signaux = {}
    try:
        for secteur, ticker in ETF_SECTORIELS.items():
            h = yf.Ticker(ticker).history(period="5d")
            if h.empty or len(h) < 2:
                continue
            perf_1j = round((float(h["Close"].iloc[-1]) / float(h["Close"].iloc[-2]) - 1) * 100, 2)
            vol     = float(h["Volume"].iloc[-1])
            vol_moy = float(h["Volume"].mean())
            flux    = round(vol / vol_moy, 2) if vol_moy > 0 else 1.0
            if perf_1j > 0.5 and flux > 1.1:
                signaux[secteur] = ("ENTREE", perf_1j, flux)
            elif perf_1j < -0.5 and flux > 1.1:
                signaux[secteur] = ("SORTIE", perf_1j, flux)
    except Exception:
        pass
    return signaux


def bonus_etf_sectoriel(nom, signaux_etf):
    """Bonus/malus selon la rotation sectorielle du jour."""
    secteur = SECTEUR_VALEUR.get(nom)
    if not secteur or secteur not in signaux_etf:
        return 0
    signal, perf, _ = signaux_etf[secteur]
    if signal == "ENTREE":  return min(8, int(abs(perf) * 2))
    if signal == "SORTIE":  return max(-8, -int(abs(perf) * 2))
    return 0


def charger_rapport_news():
    if os.path.exists(FICHIER_RAPPORT_NEWS):
        with open(FICHIER_RAPPORT_NEWS, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def recuperer_contexte_global():
    """VIX + Fear&Greed + BCE/Fed → malus global unique à appliquer à tous les scores."""
    malus = 0
    infos = []
    vix_val = None
    fg_score = None
    fg_label = ""
    cac_cours = None
    cac_var   = None
    try:
        vix = yf.Ticker("^VIX").history(period="2d")
        if not vix.empty:
            vix_val = round(float(vix["Close"].iloc[-1]), 1)
            # Malus VIX retiré le 05/07 suite à l'audit (audit_malus_vix.py, 6590 jours
            # 2000-2026) : un VIX élevé précède des rendements CAC SUPÉRIEURS à J+5
            # (+0.29% vs +0.08%), et le ratio rendement/volatilité reste meilleur en
            # VIX > 25. Le malus pénalisait pile les fenêtres de rebond, comme le F&G.
            # VIX conservé comme info contextuelle et pour la détection de régime.
            if vix_val > 35:    infos.append(f"VIX EXTRÊME {vix_val} (info, sans malus)")
            elif vix_val > 25:  infos.append(f"VIX élevé {vix_val} (info, sans malus)")
    except Exception: pass
    try:
        url = "https://api.alternative.me/fng/?limit=1"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=6) as r:
            fg = json.loads(r.read())
        fg_score = int(fg["data"][0]["value"])
        fg_label = fg["data"][0]["value_classification"]
        # Malus F&G retiré le 26/06 suite à l'audit (aucun edge prouvé, indice crypto
        # sans lien avec le CAC). F&G conservé comme info contextuelle uniquement.
    except Exception: pass
    try:
        cac = yf.Ticker("^FCHI").history(period="2d")
        if not cac.empty and len(cac) >= 2:
            cac_cours = round(float(cac["Close"].iloc[-1]), 0)
            cac_var   = round((cac["Close"].iloc[-1] / cac["Close"].iloc[-2] - 1) * 100, 2)
        elif not cac.empty:
            cac_cours = round(float(cac["Close"].iloc[-1]), 0)
    except Exception: pass
    today = datetime.datetime.now(TZ_PARIS).date()
    for d_str in DATES_BANQUES_CENTRALES:
        d = datetime.date.fromisoformat(d_str)
        if 0 <= (d - today).days <= 2:
            malus -= 15; infos.append(f"Annonce BCE/Fed {d_str}")
            break
    return malus, infos, vix_val, fg_score, fg_label, cac_cours, cac_var

from marche_config import CAC40

POIDS_DEFAUT = {
    "rsi":        1.0,
    "macd":       1.0,
    "momentum":   1.0,
    "volume":     1.0,
    "bollinger":  1.0,
}


def detecter_regime_macro(vix_val, cac_var, fg_score, signaux_etf):
    """
    Appelle Claude une seule fois par run pour classifier le régime de marché
    et retourner des pondérations de facteurs adaptées.
    Utilise uniquement les données disponibles au moment du signal (pas de leakage).
    """
    if not ANTHROPIC_API_KEY:
        return POIDS_DEFAUT, "inconnu"

    nb_entrees = sum(1 for s, _, _ in signaux_etf.values() if s == "ENTREE")
    nb_sorties = sum(1 for s, _, _ in signaux_etf.values() if s == "SORTIE")

    prompt = f"""Tu es un classificateur de régime de marché boursier. Analyse ces données macro et retourne UNIQUEMENT un JSON.

Données du moment (pas de données futures) :
- VIX : {vix_val if vix_val else 'indisponible'}
- CAC 40 variation J-1 : {cac_var if cac_var is not None else 'indisponible'}%
- Fear & Greed index : {fg_score if fg_score else 'indisponible'}/100
- Rotations sectorielles ETF : {nb_entrees} secteurs en entrée, {nb_sorties} en sortie

Classifie le régime parmi : "tendance_haussiere", "tendance_baissiere", "volatile", "lateral", "crise"

Règles de pondération :
- tendance_haussiere : momentum fort, RSI modéré, MACD fort
- tendance_baissiere : momentum faible, RSI fort (survente), MACD faible
- volatile : RSI fort (rebonds), momentum faible, bollinger fort, volume fort
- lateral : RSI fort, bollinger fort, momentum faible, MACD faible
- crise : RSI fort (survente extrême), volume fort, tout le reste réduit

Retourne UNIQUEMENT ce JSON, sans texte autour :
{{"regime": "<label>", "rsi": <0.5-2.0>, "macd": <0.5-2.0>, "momentum": <0.5-2.0>, "volume": <0.5-2.0>, "bollinger": <0.5-2.0>}}"""

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        _loguer_cout_intraday("scoring_intraday", "claude-haiku-4-5-20251001",
                              response.usage.input_tokens, response.usage.output_tokens)
        data = json.loads(raw)
        regime = data.get("regime", "inconnu")
        poids = {
            "rsi":       float(data.get("rsi", 1.0)),
            "macd":      float(data.get("macd", 1.0)),
            "momentum":  float(data.get("momentum", 1.0)),
            "volume":    float(data.get("volume", 1.0)),
            "bollinger": float(data.get("bollinger", 1.0)),
        }
        # Sécurité : on clamp les poids entre 0.3 et 2.0
        poids = {k: max(0.3, min(2.0, v)) for k, v in poids.items()}
        print(f"  Régime détecté : {regime} | poids : {poids}")
        return poids, regime
    except Exception as e:
        print(f"  Régime macro : erreur ({e}), poids par défaut")
        return POIDS_DEFAUT, "inconnu"


def scorer_action(nom, ticker, malus_global=0, rapport_news=None, signaux_etf=None, poids_macro=None):
    try:
        stock = yf.Ticker(ticker)
        hist  = stock.history(period="1y")

        if hist.empty or len(hist) < 20:
            return None

        cours      = round(float(hist["Close"].iloc[-1]), 2)
        cours_hier = round(float(hist["Close"].iloc[-2]), 2)
        ouverture  = round(float(hist["Open"].iloc[-1]), 2)
        variation  = round((cours - cours_hier) / cours_hier * 100, 2)
        volume     = int(hist["Volume"].iloc[-1])
        vol_moy    = int(hist["Volume"].iloc[-20:].mean())
        gap_pct    = round((ouverture - cours_hier) / cours_hier * 100, 2)

        score = 50
        rsi_val = None
        p = poids_macro if poids_macro else POIDS_DEFAUT
        f = {}  # contributions par facteur

        if TA_DISPONIBLE:
            close = hist["Close"]
            high  = hist["High"]
            low   = hist["Low"]

            # RSI
            rsi_series = RSIIndicator(close, window=14).rsi()
            rsi_val    = rsi_series.iloc[-1]
            d_rsi = 0
            if not pd.isna(rsi_val):
                rsi_val = round(float(rsi_val), 1)
                w = p["rsi"]
                if rsi_val < 25:   d_rsi = round(20 * w)
                elif rsi_val < 35: d_rsi = round(12 * w)
                elif rsi_val < 45: d_rsi = round(5 * w)
                elif rsi_val > 75: d_rsi = -round(20 * w)
                elif rsi_val > 65: d_rsi = -round(12 * w)
                elif rsi_val > 55: d_rsi = -round(5 * w)
            score += d_rsi
            f["rsi"] = d_rsi

            # Divergence RSI/prix
            d_div = 0
            if len(hist) >= 20 and len(rsi_series) >= 20:
                try:
                    c20   = hist["Close"].tail(20).values
                    r20   = rsi_series.tail(20).values
                    i_min = c20.argmin()
                    i_max = c20.argmax()
                    if i_min < len(c20) - 3 and c20[-1] <= c20[i_min] and r20[-1] > r20[i_min] + 3:
                        d_div = round(12 * p["rsi"])
                    elif i_max < len(c20) - 3 and c20[-1] >= c20[i_max] and r20[-1] < r20[i_max] - 3:
                        d_div = -round(12 * p["rsi"])
                except Exception: pass
            score += d_div
            f["divergence_rsi"] = d_div

            # MACD
            macd_ind  = MACD(close)
            macd_line = macd_ind.macd().iloc[-1]
            macd_sig  = macd_ind.macd_signal().iloc[-1]
            macd_hist = macd_ind.macd_diff()
            d_macd = 0
            if not pd.isna(macd_line) and not pd.isna(macd_sig):
                d_macd += round(10 * p["macd"]) if macd_line > macd_sig else -round(10 * p["macd"])
            if len(macd_hist) >= 2:
                h1, h2 = macd_hist.iloc[-1], macd_hist.iloc[-2]
                if not pd.isna(h1) and not pd.isna(h2):
                    if h1 > h2 and h1 > 0:   d_macd += round(5 * p["macd"])
                    elif h1 < h2 and h1 < 0:  d_macd -= round(5 * p["macd"])
            score += d_macd
            f["macd"] = d_macd

            # Moyennes mobiles (poids fixe)
            ma20 = SMAIndicator(close, window=20).sma_indicator()
            ma50 = SMAIndicator(close, window=50).sma_indicator() if len(hist) >= 50 else None
            v20  = float(ma20.iloc[-1]) if not pd.isna(ma20.iloc[-1]) else None
            v50  = float(ma50.iloc[-1]) if ma50 is not None and not pd.isna(ma50.iloc[-1]) else None
            d_ma = 0
            if v20 and v50:
                if cours > v20 and cours > v50:    d_ma = 10
                elif cours < v20 and cours < v50:  d_ma = -10
            score += d_ma
            f["moyennes_mobiles"] = d_ma

            # Pente MA200 (poids fixe)
            d_ma200 = 0
            if len(hist) >= 220:
                try:
                    ma200 = SMAIndicator(close, window=200).sma_indicator()
                    pente = (float(ma200.iloc[-1]) - float(ma200.iloc[-20])) / float(ma200.iloc[-20]) * 100
                    if pente > 0.5:    d_ma200 = 6
                    elif pente < -0.5: d_ma200 = -6
                except Exception: pass
            score += d_ma200
            f["ma200"] = d_ma200

            # Bollinger
            bb      = BollingerBands(close)
            bb_low  = bb.bollinger_lband().iloc[-1]
            bb_high = bb.bollinger_hband().iloc[-1]
            d_boll = 0
            if not pd.isna(bb_low) and not pd.isna(bb_high):
                if cours < float(bb_low):    d_boll = round(10 * p["bollinger"])
                elif cours > float(bb_high): d_boll = -round(10 * p["bollinger"])
            score += d_boll
            f["bollinger"] = d_boll

        # Momentum multi-timeframe
        n = len(hist)
        perfs = []
        for nb_j in [5, 20, 60]:
            if n > nb_j:
                perfs.append(float(hist["Close"].iloc[-1]) / float(hist["Close"].iloc[-nb_j]) - 1)
        d_mom = 0
        if perfs:
            haussiers = sum(1 for p2 in perfs if p2 > 0)
            baissiers = sum(1 for p2 in perfs if p2 < 0)
            if haussiers == len(perfs):   d_mom = round(10 * p["momentum"])
            elif haussiers >= 2:          d_mom = round(5 * p["momentum"])
            elif baissiers == len(perfs): d_mom = -round(10 * p["momentum"])
            elif baissiers >= 2:          d_mom = -round(5 * p["momentum"])
        score += d_mom
        f["momentum"] = d_mom

        # Volume anormal
        ratio_vol = round(volume / vol_moy, 1) if vol_moy > 0 else 1.0
        d_vol = 0
        if ratio_vol > 2:
            d_vol = round(8 * p["volume"]) if variation > 0 else -round(8 * p["volume"])
        score += d_vol
        f["volume"] = d_vol

        # Gap + momentum intraday (poids fixe)
        d_gap = 0
        if gap_pct > 0.5 and volume > vol_moy * 1.5:   d_gap += 5
        if gap_pct < -0.5 and volume > vol_moy * 1.5:  d_gap -= 5
        momentum_intraday = round((cours - ouverture) / ouverture * 100, 2) if ouverture else 0
        d_intraday = 5 if momentum_intraday > 0.5 else (-5 if momentum_intraday < -0.5 else 0)
        score += d_gap + d_intraday
        f["gap"] = d_gap
        f["momentum_intraday"] = d_intraday

        # Consensus analystes
        d_analystes = 0
        try:
            info = stock.info
            rec  = info.get("recommendationMean")
            nb_a = info.get("numberOfAnalystOpinions", 0)
            cible = info.get("targetMeanPrice")
            if rec and nb_a and nb_a >= 3:
                if rec <= 1.5:   d_analystes += 8
                elif rec <= 2.2: d_analystes += 5
                elif rec <= 2.8: d_analystes += 2
                elif rec >= 4.0: d_analystes -= 8
                elif rec >= 3.5: d_analystes -= 4
                if cible and cours:
                    upside = (cible - cours) / cours * 100
                    if upside > 25:    d_analystes += 5
                    elif upside > 15:  d_analystes += 3
                    elif upside < -10: d_analystes -= 4
        except Exception: pass
        score += d_analystes
        f["analystes"] = d_analystes

        # Rotation sectorielle intraday (ETF)
        d_etf = bonus_etf_sectoriel(nom, signaux_etf) if signaux_etf else 0
        score += d_etf
        f["etf_sectoriel"] = d_etf

        # Sentiment news (POIDS_NEWS=0 depuis l'audit du 02/07)
        d_news = 0
        if rapport_news:
            nd = rapport_news.get("valeurs", {}).get(nom, {})
            sentiment = nd.get("sentiment", 0)
            d_news = int(sentiment * POIDS_NEWS)
        score += d_news
        f["news"] = d_news

        # Malus global (VIX + BCE/Fed)
        score += malus_global
        f["malus_macro"] = malus_global

        score = max(0, min(100, round(score)))
        if score >= 65:   signal = "ACHETER"
        elif score <= 35: signal = "ÉVITER"
        else:             signal = "SURVEILLER"

        return {
            "nom":               nom,
            "cours":             cours,
            "variation":         variation,
            "gap_ouverture":     gap_pct,
            "momentum_intraday": momentum_intraday,
            "volume_ratio":      ratio_vol,
            "score":             score,
            "signal":            signal,
            "facteurs":          f,
        }

    except Exception as e:
        print(f"  Erreur {nom} : {e}")
        return None


def charger_intraday():
    if os.path.exists(FICHIER_INTRADAY):
        with open(FICHIER_INTRADAY, "r") as f:
            return json.load(f)
    return {}


def sauvegarder_intraday(data):
    with open(FICHIER_INTRADAY, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def charger_alertes_envoyees():
    if os.path.exists(FICHIER_ALERTES_VUE):
        with open(FICHIER_ALERTES_VUE, "r") as f:
            return json.load(f)
    return {}


def sauvegarder_alertes_envoyees(data):
    with open(FICHIER_ALERTES_VUE, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def envoyer_alerte(alertes):
    if not alertes or not ZOHO_PASSWORD:
        return

    today = datetime.datetime.now(TZ_PARIS).date().strftime("%d/%m/%Y")
    heure = datetime.datetime.now(TZ_PARIS).strftime("%H:%M")
    sujet = f"ALERTE BOURSE — {len(alertes)} signal(s) exceptionnel(s) — {today} {heure}"

    lignes_html = ""
    for a in alertes:
        couleur = "#1b5e20" if a["signal"] == "ACHETER" else "#b71c1c"
        lignes_html += f"""
        <tr style='border-bottom:1px solid #eee;'>
          <td style='padding:10px;font-weight:bold;font-size:15px;'>{a['nom']}</td>
          <td style='padding:10px;text-align:center;'>
            <span style='background:{couleur};color:white;padding:4px 10px;border-radius:4px;font-weight:bold;'>
              {a['signal']} {a['score']}/100
            </span>
          </td>
          <td style='padding:10px;'>{a['cours']} € ({'+' if a['variation'] >= 0 else ''}{a['variation']}%)</td>
          <td style='padding:10px;color:#555;font-size:13px;'>{a['raison']}</td>
        </tr>"""

    html = f"""<html><body style='font-family:Arial,sans-serif;max-width:800px;margin:auto;padding:20px;'>
<div style='background:#b71c1c;color:white;padding:16px 20px;border-radius:8px 8px 0 0;'>
  <h2 style='margin:0;font-size:18px;'>ALERTE — Signal(s) exceptionnel(s) detecte(s)</h2>
  <p style='margin:6px 0 0;font-size:12px;opacity:0.9;'>{today} a {heure} — Score seuil : {SEUIL_ALERTE}/100</p>
</div>
<div style='border:1px solid #ddd;border-top:none;padding:20px;border-radius:0 0 8px 8px;'>
  <table style='width:100%;border-collapse:collapse;font-size:14px;'>
    <thead>
      <tr style='background:#f5f5f5;'>
        <th style='padding:10px;text-align:left;'>Valeur</th>
        <th style='padding:10px;text-align:center;'>Signal</th>
        <th style='padding:10px;text-align:left;'>Cours</th>
        <th style='padding:10px;text-align:left;'>Pourquoi</th>
      </tr>
    </thead>
    <tbody>{lignes_html}</tbody>
  </table>
  <p style='margin-top:16px;font-size:12px;color:#999;'>
    Ce briefing est informatif. Tu prends tes propres decisions d investissement.
  </p>
</div>
</body></html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = sujet
    msg["From"]    = ZOHO_EMAIL
    msg["To"]      = ", ".join(DESTINATAIRES)
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        with smtplib.SMTP(ZOHO_SMTP, ZOHO_PORT) as serveur:
            serveur.starttls()
            serveur.login(ZOHO_EMAIL, ZOHO_PASSWORD)
            serveur.sendmail(ZOHO_EMAIL, DESTINATAIRES, msg.as_string())
        print(f"Alerte envoyee : {[a['nom'] for a in alertes]}")
    except Exception as e:
        print(f"Erreur envoi alerte : {e}")


def detecter_alertes(snapshot, alertes_envoyees, today, heure):
    alertes = []
    for nom, d in snapshot.items():
        score  = d["score"]
        signal = d["signal"]
        cle    = f"{today}_{nom}"

        if cle in alertes_envoyees:
            continue

        raisons = []

        if score >= SEUIL_ALERTE and signal == "ACHETER":
            raisons.append(f"Score exceptionnel {score}/100")

        if d.get("gap_ouverture", 0) > 2 and d.get("volume_ratio", 1) > 2:
            raisons.append(f"Gap haussier +{d['gap_ouverture']}% avec volume x{d['volume_ratio']}")

        if d.get("momentum_intraday", 0) > 2 and score >= 70:
            raisons.append(f"Momentum intraday fort +{d['momentum_intraday']}%")

        if raisons:
            alertes.append({
                "nom":       nom,
                "cours":     d["cours"],
                "variation": d["variation"],
                "score":     score,
                "signal":    signal,
                "raison":    " | ".join(raisons),
            })
            alertes_envoyees[cle] = heure

    return alertes, alertes_envoyees


def calculer_frais(montant):
    return round(max(FRAIS_MINIMUM, montant * FRAIS_TAUX), 2)


FICHIER_SHADOW = "shadow_alertes.json"

def logger_alertes_shadow(alertes, today, heure, envoyees):
    """Journal permanent de toutes les alertes détectées (envoyées ou non).
    Jamais purgé, contrairement à alertes_envoyees.json (7 jours) et
    intraday_scores.json (5 jours). L'agent Shadow l'évalue chaque semaine
    pour mesurer ce que les alertes auraient rapporté, frais inclus."""
    if not alertes:
        return
    log = []
    if os.path.exists(FICHIER_SHADOW):
        try:
            with open(FICHIER_SHADOW, "r", encoding="utf-8") as f:
                log = json.load(f)
        except Exception:
            log = []
    for a in alertes:
        log.append({
            "date":     today,
            "heure":    heure,
            "nom":      a.get("nom"),
            "cours":    a.get("cours"),
            "score":    a.get("score"),
            "signal":   a.get("signal"),
            "raison":   a.get("raison", ""),
            "envoyee":  envoyees,
        })
    with open(FICHIER_SHADOW, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)
    print(f"  {len(alertes)} alerte(s) journalisée(s) dans {FICHIER_SHADOW}")


def gerer_portefeuille_intraday(snapshot, heure):
    """Ouvre/ferme des positions en cours de journée selon les signaux intraday."""
    if not os.path.exists(FICHIER_PORTEFEUILLE):
        return [], []

    with open(FICHIER_PORTEFEUILLE, "r") as f:
        pf = json.load(f)

    today    = datetime.datetime.now(TZ_PARIS).date().isoformat()
    fermes   = []
    ouverts  = []

    # Fermeture des positions si signal ÉVITER, stop-loss ou take-profit
    positions_a_fermer = []
    for nom, pos in pf["positions"].items():
        d = snapshot.get(nom)
        if not d:
            continue
        signal       = d["signal"]
        cours_actuel = d["cours"]
        pnl_pct      = (cours_actuel - pos["prix_entree"]) / pos["prix_entree"] * 100

        if signal == "ÉVITER" or pnl_pct <= SEUIL_STOP_LOSS or pnl_pct >= SEUIL_TAKE_PROFIT:
            positions_a_fermer.append((nom, cours_actuel, pnl_pct, signal))

    for nom, cours_sortie, pnl_pct, raison_signal in positions_a_fermer:
        pos           = pf["positions"][nom]
        valeur_sortie = pos["nb_actions"] * cours_sortie
        frais_vente   = calculer_frais(valeur_sortie)
        net_sortie    = valeur_sortie - frais_vente
        frais_total   = round(pos.get("frais_achat", 0) + frais_vente, 2)
        pnl_net       = round((net_sortie - pos["cout_total"]) / pos["cout_total"] * 100, 2)
        pf["capital"] += net_sortie

        raison = "ÉVITER intraday" if raison_signal == "ÉVITER" else (
            f"Stop-loss {pnl_pct:.1f}%" if pnl_pct <= SEUIL_STOP_LOSS else f"Take-profit {pnl_pct:.1f}%"
        )

        pf["trades"].append({
            "nom":           nom,
            "entree":        pos["prix_entree"],
            "sortie":        cours_sortie,
            "date_entree":   pos["date_entree"],
            "heure_entree":  pos.get("heure_entree", "07:00"),
            "source_entree": pos.get("source_entree", "Briefing"),
            "date_sortie":   today,
            "heure_sortie":  heure,
            "source_sortie": "Intraday",
            "pnl_pct":       pnl_net,
            "frais_total":   frais_total,
            "raison_sortie": raison,
        })
        del pf["positions"][nom]
        fermes.append({"nom": nom, "cours": cours_sortie, "pnl": pnl_net, "raison": raison})

    # Ouverture de nouvelles positions si score >= seuil intraday
    for nom, d in snapshot.items():
        if (d["score"] >= SEUIL_ACHAT_INTRADAY and
                d["signal"] == "ACHETER" and
                nom not in pf["positions"] and
                len(pf["positions"]) < MAX_POSITIONS and
                pf["capital"] >= BUDGET_PAR_POSITION):
            cours       = d["cours"]
            nb          = int(BUDGET_PAR_POSITION / cours)
            if nb > 0:
                cout        = nb * cours
                frais_achat = calculer_frais(cout)
                pf["capital"] -= (cout + frais_achat)
                pf["positions"][nom] = {
                    "nb_actions":   nb,
                    "prix_entree":  cours,
                    "date_entree":  today,
                    "heure_entree": heure,
                    "source_entree":"Intraday",
                    "cout_total":   cout,
                    "frais_achat":  frais_achat,
                }
                ouverts.append({"nom": nom, "cours": cours, "score": d["score"]})

    # Mise à jour valeur totale
    valeur_positions = sum(
        pos["nb_actions"] * snapshot.get(nom, {}).get("cours", pos["prix_entree"])
        for nom, pos in pf["positions"].items()
    )
    valeur_totale = round(pf["capital"] + valeur_positions, 2)
    pf["historique_valeur"][today] = valeur_totale

    with open(FICHIER_PORTEFEUILLE, "w") as f:
        json.dump(pf, f, ensure_ascii=False, indent=2)

    return fermes, ouverts


if __name__ == "__main__":
    now   = datetime.datetime.now(TZ_PARIS)
    today = datetime.datetime.now(TZ_PARIS).date().isoformat()
    heure = now.strftime("%H:%M")

    print(f"Scoring intraday — {today} {heure}")

    print("Chargement rapport agent news...")
    rapport_news = charger_rapport_news()
    if rapport_news:
        sg = rapport_news.get("marche", {}).get("sentiment_global", 0)
        print(f"  Rapport du {rapport_news.get('date','?')} {rapport_news.get('heure','?')} — sentiment global {sg:+.2f}")
    else:
        print("  Pas de rapport news disponible")

    print("Analyse rotations sectorielles ETF...")
    signaux_etf = analyser_etf_intraday()
    if signaux_etf:
        for s, (sig, perf, flux) in signaux_etf.items():
            print(f"  {s}: {sig} {perf:+.2f}% flux x{flux:.1f}")
    else:
        print("  Aucune rotation sectorielle significative")

    print("Contexte global (VIX, Fear&Greed, BCE/Fed)...")
    malus_global, infos_macro, vix_val, fg_score, fg_label, cac_cours, cac_var = recuperer_contexte_global()
    if infos_macro:
        print(f"  Alertes : {' | '.join(infos_macro)} → malus {malus_global} pts")
    else:
        print(f"  Marché calme, malus : {malus_global} pts")
    print(f"  CAC 40 : {cac_cours} ({cac_var:+.2f}%) | VIX : {vix_val} | F&G : {fg_score} {fg_label}")

    print("Détection régime macro (Claude)...")
    poids_macro, regime_macro = detecter_regime_macro(vix_val, cac_var, fg_score, signaux_etf)

    data = charger_intraday()

    # Garde seulement les 5 derniers jours
    jours = sorted(data.keys())
    while len(jours) > 5:
        del data[jours.pop(0)]

    if today not in data:
        data[today] = {}

    snapshot = {}
    ok = 0
    for nom, ticker in CAC40.items():
        print(f"  {nom}...")
        result = scorer_action(nom, ticker, malus_global=malus_global, rapport_news=rapport_news, signaux_etf=signaux_etf, poids_macro=poids_macro)
        if result:
            snapshot[nom] = result
            ok += 1

    data[today][heure] = {
        "_meta": {
            "cac_cours":        cac_cours,
            "cac_var":          cac_var,
            "vix":              vix_val,
            "fear_greed_score": fg_score,
            "fear_greed_label": fg_label,
            "malus_global":     malus_global,
            "regime_macro":     regime_macro,
            "poids_macro":      poids_macro,
        },
        **snapshot,
    }
    sauvegarder_intraday(data)
    print(f"OK : {ok}/39 snapshots sauvegardés à {heure}")

    print("Détection alertes exceptionnelles...")
    alertes_envoyees = charger_alertes_envoyees()
    sept_jours = (datetime.datetime.now(TZ_PARIS).date() - datetime.timedelta(days=7)).isoformat()
    alertes_envoyees = {k: v for k, v in alertes_envoyees.items() if k[:10] >= sept_jours}

    alertes, alertes_envoyees = detecter_alertes(snapshot, alertes_envoyees, today, heure)
    sauvegarder_alertes_envoyees(alertes_envoyees)

    print("Gestion portefeuille intraday...")
    fermes, ouverts = gerer_portefeuille_intraday(snapshot, heure)
    if fermes:
        print(f"  Positions fermées : {[f['nom'] for f in fermes]}")
    if ouverts:
        print(f"  Positions ouvertes : {[o['nom'] for o in ouverts]}")

    # Fusionne les mouvements de portefeuille dans les alertes si pertinent
    for o in ouverts:
        cle = f"{today}_{o['nom']}_achat"
        if cle not in alertes_envoyees:
            alertes.append({
                "nom":       o["nom"],
                "cours":     o["cours"],
                "variation": snapshot.get(o["nom"], {}).get("variation", 0),
                "score":     o["score"],
                "signal":    "ACHETER",
                "raison":    f"Position ouverte en portefeuille virtuel (score {o['score']}/100)",
            })
            alertes_envoyees[cle] = heure

    for f in fermes:
        cle = f"{today}_{f['nom']}_vente"
        if cle not in alertes_envoyees:
            alertes.append({
                "nom":       f["nom"],
                "cours":     f["cours"],
                "variation": snapshot.get(f["nom"], {}).get("variation", 0),
                "score":     snapshot.get(f["nom"], {}).get("score", 0),
                "signal":    "VENTE",
                "raison":    f"Position fermée — {f['raison']} | P&L : {'+' if f['pnl'] >= 0 else ''}{f['pnl']:.2f}%",
            })
            alertes_envoyees[cle] = heure

    sauvegarder_alertes_envoyees(alertes_envoyees)

    logger_alertes_shadow(alertes, today, heure, envoyees=ALERTES_EMAIL_ACTIVES)

    if alertes and ALERTES_EMAIL_ACTIVES:
        print(f"  {len(alertes)} alerte(s) — envoi email...")
        envoyer_alerte(alertes)
    elif alertes:
        print(f"  {len(alertes)} alerte(s) détectée(s) mais email suspendu (décision 02/07, revoir ~02/08).")
    else:
        print("  Aucune alerte.")

    print("Scoring intraday terminé.")
