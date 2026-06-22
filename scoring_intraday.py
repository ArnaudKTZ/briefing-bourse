#!/usr/bin/env python3
"""
Scoring intraday — collecte les scores 3x/jour sans appeler Claude.
Tourne à 9h, 12h et 16h via GitHub Actions.
Sauvegarde dans intraday_scores.json pour enrichir le briefing du lendemain.
"""

import datetime
import json
import os
import yfinance as yf
import pandas as pd
import numpy as np

try:
    from ta.momentum import RSIIndicator, StochasticOscillator
    from ta.trend import MACD, SMAIndicator
    from ta.volatility import BollingerBands, AverageTrueRange
    TA_DISPONIBLE = True
except ImportError:
    TA_DISPONIBLE = False

FICHIER_INTRADAY = "intraday_scores.json"

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


def scorer_action(nom, ticker):
    try:
        stock = yf.Ticker(ticker)
        hist  = stock.history(period="60d")

        if hist.empty or len(hist) < 20:
            return None

        cours      = round(float(hist["Close"].iloc[-1]), 2)
        cours_hier = round(float(hist["Close"].iloc[-2]), 2)
        ouverture  = round(float(hist["Open"].iloc[-1]), 2)
        variation  = round((cours - cours_hier) / cours_hier * 100, 2)
        volume     = int(hist["Volume"].iloc[-1])
        vol_moy    = int(hist["Volume"].iloc[-20:].mean())

        # Gap ouverture vs clôture hier
        gap_pct = round((ouverture - cours_hier) / cours_hier * 100, 2)

        score = 50

        if TA_DISPONIBLE:
            close = hist["Close"]

            rsi = RSIIndicator(close, window=14).rsi().iloc[-1]
            if not pd.isna(rsi):
                rsi = round(rsi, 1)
                if rsi < 25:   score += 20
                elif rsi < 35: score += 12
                elif rsi < 45: score += 5
                elif rsi > 75: score -= 20
                elif rsi > 65: score -= 12
                elif rsi > 55: score -= 5

            macd_ind  = MACD(close)
            macd_line = macd_ind.macd().iloc[-1]
            macd_sig  = macd_ind.macd_signal().iloc[-1]
            macd_hist = macd_ind.macd_diff()
            if not pd.isna(macd_line) and not pd.isna(macd_sig):
                if macd_line > macd_sig: score += 10
                else:                    score -= 10
            if len(macd_hist) >= 2:
                h1 = macd_hist.iloc[-1]
                h2 = macd_hist.iloc[-2]
                if not pd.isna(h1) and not pd.isna(h2):
                    if h1 > h2 and h1 > 0: score += 5
                    elif h1 < h2 and h1 < 0: score -= 5

            ma20  = SMAIndicator(close, window=20).sma_indicator().iloc[-1]
            ma50  = SMAIndicator(close, window=50).sma_indicator().iloc[-1]
            if not pd.isna(ma20) and not pd.isna(ma50):
                if cours > ma20 and cours > ma50:  score += 10
                elif cours < ma20 and cours < ma50: score -= 10

            bb = BollingerBands(close)
            bb_low  = bb.bollinger_lband().iloc[-1]
            bb_high = bb.bollinger_hband().iloc[-1]
            if not pd.isna(bb_low) and not pd.isna(bb_high):
                if cours < bb_low:   score += 10
                elif cours > bb_high: score -= 10

        # Volume anormal
        if vol_moy > 0:
            ratio_vol = round(volume / vol_moy, 1)
            if ratio_vol > 2:
                if variation > 0: score += 8
                else:             score -= 8

        # Gap haussier avec volume fort = signal positif
        if gap_pct > 0.5 and volume > vol_moy * 1.5: score += 5
        if gap_pct < -0.5 and volume > vol_moy * 1.5: score -= 5

        # Momentum intraday (cours vs ouverture)
        momentum_intraday = round((cours - ouverture) / ouverture * 100, 2) if ouverture else 0
        if momentum_intraday > 0.5:  score += 5
        elif momentum_intraday < -0.5: score -= 5

        score = max(0, min(100, round(score)))

        if score >= 65:   signal = "ACHETER"
        elif score <= 35: signal = "ÉVITER"
        else:             signal = "SURVEILLER"

        return {
            "nom":                nom,
            "cours":              cours,
            "variation":          variation,
            "gap_ouverture":      gap_pct,
            "momentum_intraday":  momentum_intraday,
            "volume_ratio":       round(volume / vol_moy, 1) if vol_moy > 0 else 1.0,
            "score":              score,
            "signal":             signal,
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


if __name__ == "__main__":
    now   = datetime.datetime.now()
    today = datetime.date.today().isoformat()
    heure = now.strftime("%H:%M")

    print(f"Scoring intraday — {today} {heure}")

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
        result = scorer_action(nom, ticker)
        if result:
            snapshot[nom] = result
            ok += 1

    data[today][heure] = snapshot
    sauvegarder_intraday(data)

    print(f"OK : {ok}/39 snapshots sauvegardés à {heure}")
    print("Fichier intraday_scores.json mis à jour.")
