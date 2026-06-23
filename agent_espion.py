#!/usr/bin/env python3
"""
Agent Espion — suit ce que fait l'argent institutionnel.
Tourne 1x/semaine (lundi matin) et produit rapport_espion.json.
Sources gratuites :
  - ETF sectoriels européens (iShares sur Yahoo Finance) → rotations sectorielles
  - Institutional holders via Yahoo Finance → accumulation/distribution
  - % insiders et institutions par valeur → conviction des initiés
Pas d'appel API Claude — 100% gratuit.
"""

import datetime
import json
import os
import yfinance as yf
import pandas as pd

FICHIER_RAPPORT = "rapport_espion.json"

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

# ETF sectoriels iShares (cotés Xetra, accessibles via Yahoo Finance)
ETF_SECTORIELS = {
    "Banques":          "EXV1.DE",
    "Energie":          "EXV2.DE",
    "Tech":             "EXV4.DE",
    "Santé":            "EXV6.DE",
    "Industrie":        "EXH8.DE",
    "Luxe/Conso":       "EXV5.DE",
    "Utilities":        "EXH7.DE",
    "Matériaux":        "EXV3.DE",
    "Telecom":          "EXV7.DE",
    "Immobilier":       "EXI3.DE",
}

# Correspondance secteur CAC40 → ETF
SECTEUR_CAC_VERS_ETF = {
    "Luxe & Cosmétiques": "Luxe/Conso",
    "Énergie":            "Energie",
    "Aéronautique":       "Industrie",
    "Industrie":          "Industrie",
    "Technologie":        "Tech",
    "Santé":              "Santé",
    "Banques":            "Banques",
    "Chimie & Gaz":       "Matériaux",
    "Agroalimentaire":    "Luxe/Conso",
    "BTP & Concessions":  "Industrie",
    "Auto":               "Industrie",
    "Médias & Pub":       "Tech",
    "Telecom":            "Telecom",
    "Utilities":          "Utilities",
}


def analyser_etf_sectoriels():
    """
    Analyse la performance et les flux des ETF sectoriels européens.
    Détecte les rotations : quels secteurs reçoivent de l'argent frais.
    """
    print("  Analyse ETF sectoriels...")
    resultats = {}
    for secteur, ticker in ETF_SECTORIELS.items():
        try:
            h = yf.Ticker(ticker).history(period="1mo")
            if h.empty or len(h) < 5:
                continue
            perf_1s  = round((h["Close"].iloc[-1] / h["Close"].iloc[-5]  - 1) * 100, 2)
            perf_1m  = round((h["Close"].iloc[-1] / h["Close"].iloc[0]   - 1) * 100, 2)
            vol_rec  = h["Volume"].tail(5).mean()
            vol_moy  = h["Volume"].mean()
            flux     = round(vol_rec / vol_moy, 2) if vol_moy > 0 else 1.0

            # Signal : secteur en force = perf positive + volume élevé
            signal = "ENTREE"  if perf_1s > 1 and flux > 1.2 else \
                     "SORTIE"  if perf_1s < -1 and flux > 1.2 else \
                     "NEUTRE"

            resultats[secteur] = {
                "perf_1s":  perf_1s,
                "perf_1m":  perf_1m,
                "flux_vol": flux,
                "signal":   signal,
            }
            print(f"    {secteur:15} {perf_1s:+.2f}% (1s) | flux x{flux:.1f} | {signal}")
        except Exception as e:
            print(f"    {secteur}: erreur {e}")

    # Classement : secteurs en force vs faiblesse
    en_force   = sorted([(s, d) for s, d in resultats.items() if d["signal"] == "ENTREE"],
                        key=lambda x: x[1]["perf_1s"], reverse=True)
    en_sortie  = sorted([(s, d) for s, d in resultats.items() if d["signal"] == "SORTIE"],
                        key=lambda x: x[1]["perf_1s"])

    return {
        "detail":    resultats,
        "en_force":  [s for s, _ in en_force],
        "en_sortie": [s for s, _ in en_sortie],
    }


def analyser_institutionnels(nom, ticker):
    """
    Analyse les données institutionnelles d'une action :
    - % détenu par les insiders (dirigeants)
    - % détenu par les institutions
    - Variation récente des positions institutionnelles (pctChange)
    Retourne un bonus -10 à +10 et les données brutes.
    """
    try:
        stock = yf.Ticker(ticker)
        info  = stock.info

        pct_insiders = info.get("heldPercentInsiders", 0) or 0
        pct_instit   = info.get("heldPercentInstitutions", 0) or 0
        nb_instit    = info.get("institutionsCount", 0) or 0

        # Variation positions institutionnelles récentes
        ih = stock.institutional_holders
        variation_moy = 0
        top_holders   = []
        if ih is not None and not ih.empty and "pctChange" in ih.columns:
            variations = ih["pctChange"].dropna()
            if not variations.empty:
                variation_moy = round(float(variations.mean()), 3)
            # Top 3 holders avec variation positive
            acheteurs = ih[ih["pctChange"] > 0.05].sort_values("pctChange", ascending=False)
            for _, row in acheteurs.head(3).iterrows():
                top_holders.append({
                    "fonds":  str(row.get("Holder", "?")),
                    "change": round(float(row["pctChange"]) * 100, 1),
                })

        # Score
        bonus = 0
        if pct_insiders > 0.10:  bonus += 5   # insiders très impliqués
        elif pct_insiders > 0.05: bonus += 3
        if variation_moy > 0.05:  bonus += 5   # institutions qui achètent
        elif variation_moy > 0.01: bonus += 2
        elif variation_moy < -0.05: bonus -= 5  # institutions qui vendent
        elif variation_moy < -0.01: bonus -= 2
        if pct_instit < 0.05:     bonus -= 3   # peu d'intérêt institutionnel

        return {
            "pct_insiders":   round(pct_insiders * 100, 1),
            "pct_institutions": round(pct_instit * 100, 1),
            "nb_institutions": int(nb_instit),
            "variation_instit": variation_moy,
            "top_acheteurs":  top_holders,
            "bonus_espion":   max(-10, min(10, bonus)),
        }
    except Exception as e:
        return {"bonus_espion": 0, "erreur": str(e)}


def calculer_bonus_sectoriel(nom, etf_data):
    """
    Bonus/malus selon que le secteur de la valeur est en flux entrant ou sortant.
    """
    # Trouver le secteur de la valeur (approximation par nom)
    secteurs_valeur = {
        "LVMH": "Luxe/Conso", "Hermès": "Luxe/Conso", "Kering": "Luxe/Conso",
        "L'Oréal": "Luxe/Conso", "Pernod Ricard": "Luxe/Conso",
        "TotalEnergies": "Energie", "Engie": "Utilities", "Veolia": "Utilities",
        "Orange": "Telecom", "Vivendi": "Telecom", "Bouygues": "Telecom",
        "BNP Paribas": "Banques", "Société Générale": "Banques",
        "Airbus": "Industrie", "Safran": "Industrie", "Thales": "Industrie",
        "Schneider Electric": "Industrie", "Legrand": "Industrie",
        "Vinci": "Industrie", "Saint-Gobain": "Matériaux",
        "ArcelorMittal": "Matériaux",
        "Capgemini": "Tech", "Dassault Systèmes": "Tech",
        "STMicroelectronics": "Tech", "Worldline": "Tech",
        "Teleperformance": "Tech",
        "Sanofi": "Santé", "Eurofins Scientific": "Santé",
        "Air Liquide": "Matériaux",
        "Danone": "Luxe/Conso", "Michelin": "Industrie",
        "Renault": "Industrie", "Stellantis": "Industrie",
        "Publicis": "Tech", "Accor": "Luxe/Conso",
        "Alstom": "Industrie", "Edenred": "Tech",
        "Eurazeo": "Banques", "Forvia": "Industrie",
    }
    secteur = secteurs_valeur.get(nom)
    if not secteur:
        return 0
    detail = etf_data.get("detail", {}).get(secteur, {})
    signal = detail.get("signal", "NEUTRE")
    perf   = detail.get("perf_1s", 0)
    if signal == "ENTREE":  return min(8, int(perf * 2))
    if signal == "SORTIE":  return max(-8, int(perf * 2))
    return 0


def main():
    today = datetime.date.today().isoformat()
    heure = datetime.datetime.now().strftime("%H:%M")
    print(f"Agent Espion — {today} {heure}")

    # 1. Rotations sectorielles via ETF
    print("\n[1/2] Rotations sectorielles (ETF iShares)...")
    etf_data = analyser_etf_sectoriels()

    # 2. Données institutionnelles par valeur
    print("\n[2/2] Analyse institutionnelle par valeur...")
    rapport_valeurs = {}
    for nom, ticker in CAC40.items():
        print(f"  {nom}...")
        data_instit = analyser_institutionnels(nom, ticker)
        bonus_sect  = calculer_bonus_sectoriel(nom, etf_data)
        bonus_total = data_instit.get("bonus_espion", 0) + bonus_sect
        rapport_valeurs[nom] = {
            **data_instit,
            "bonus_sectoriel": bonus_sect,
            "bonus_total":     max(-15, min(15, bonus_total)),
        }

    # Valeurs avec signal fort
    signaux = sorted(
        [(n, d) for n, d in rapport_valeurs.items() if abs(d.get("bonus_total", 0)) >= 5],
        key=lambda x: x[1]["bonus_total"], reverse=True
    )

    rapport = {
        "date":          today,
        "heure":         heure,
        "etf_sectoriels": etf_data,
        "valeurs":       rapport_valeurs,
        "signaux_forts": [(n, d["bonus_total"]) for n, d in signaux],
        "resume": {
            "secteurs_en_force":  etf_data["en_force"],
            "secteurs_en_sortie": etf_data["en_sortie"],
            "top_achats_instit":  [n for n, d in signaux if d["bonus_total"] > 0][:5],
            "top_ventes_instit":  [n for n, d in signaux if d["bonus_total"] < 0][:5],
        }
    }

    with open(FICHIER_RAPPORT, "w", encoding="utf-8") as f:
        json.dump(rapport, f, ensure_ascii=False, indent=2, default=str)

    print(f"\nRapport sauvegardé : {FICHIER_RAPPORT}")
    print(f"Secteurs en force : {etf_data['en_force']}")
    print(f"Secteurs en sortie : {etf_data['en_sortie']}")
    print(f"Signaux forts : {len(signaux)} valeurs")
    for n, d in signaux[:5]:
        print(f"  {n:25} bonus {d['bonus_total']:+d}")


if __name__ == "__main__":
    main()
