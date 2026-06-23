#!/usr/bin/env python3
"""
Agent News — collecte les actualités financières pour les 39 valeurs CAC40.
Tourne avant le briefing du matin et produit rapport_news.json.
Pas d'appel API Claude — 100% gratuit.
"""

import datetime
import json
import os
import urllib.request
import xml.etree.ElementTree as ET
import re

FICHIER_RAPPORT = "rapport_news.json"

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

# Mots-clés positifs et négatifs pour le sentiment
MOTS_POSITIFS = [
    "hausse", "progression", "croissance", "bénéfice", "profit", "record",
    "supérieur", "dépasse", "relève", "objectif", "acquisition", "contrat",
    "partenariat", "innovation", "dividende", "rachat", "achat", "recommande",
    "surperformance", "optimiste", "rebond", "accord", "succès", "fort",
    "upgrade", "buy", "outperform", "beat", "strong",
]
MOTS_NEGATIFS = [
    "baisse", "recul", "perte", "déficit", "chute", "avertissement", "risque",
    "inférieur", "déçoit", "abaisse", "restructuration", "suppression", "dette",
    "enquête", "amende", "procès", "fraude", "grève", "crise", "alerte",
    "downgrade", "sell", "underperform", "miss", "weak", "warn",
]

# Noms alternatifs pour la détection dans les titres
NOMS_ALTERNATIFS = {
    "LVMH":               ["lvmh", "louis vuitton", "moët", "hennessy"],
    "TotalEnergies":      ["total", "totalenergies"],
    "Hermès":             ["hermès", "hermes"],
    "Airbus":             ["airbus"],
    "Schneider Electric": ["schneider"],
    "L'Oréal":            ["l'oréal", "loreal", "l'oreal"],
    "Sanofi":             ["sanofi"],
    "BNP Paribas":        ["bnp", "paribas"],
    "Air Liquide":        ["air liquide"],
    "Safran":             ["safran"],
    "Danone":             ["danone"],
    "Vinci":              ["vinci"],
    "Kering":             ["kering", "gucci", "saint laurent", "bottega"],
    "Société Générale":   ["société générale", "socgen", "sogenal"],
    "Stellantis":         ["stellantis", "peugeot", "citroën", "opel", "fiat", "jeep"],
    "Saint-Gobain":       ["saint-gobain", "saint gobain"],
    "ArcelorMittal":      ["arcelor", "mittal"],
    "Pernod Ricard":      ["pernod", "ricard"],
    "Michelin":           ["michelin"],
    "Capgemini":          ["capgemini"],
    "Renault":            ["renault", "dacia"],
    "Legrand":            ["legrand"],
    "Publicis":           ["publicis"],
    "Bouygues":           ["bouygues"],
    "Engie":              ["engie", "gdf"],
    "Orange":             ["orange telecom", "orange sa"],
    "Vivendi":            ["vivendi", "canal+"],
    "Eurofins Scientific":["eurofins"],
    "Teleperformance":    ["teleperformance"],
    "Alstom":             ["alstom"],
    "Worldline":          ["worldline"],
    "Veolia":             ["veolia"],
    "STMicroelectronics": ["stmicro", "stm"],
    "Dassault Systèmes":  ["dassault systèmes", "dassault systemes", "3ds"],
    "Edenred":            ["edenred", "ticket restaurant"],
    "Accor":              ["accor", "novotel", "ibis", "sofitel"],
    "Eurazeo":            ["eurazeo"],
    "Thales":             ["thales"],
    "Forvia":             ["forvia", "faurecia"],
}


def scorer_sentiment(titre):
    """Retourne un score de sentiment entre -3 et +3."""
    t = titre.lower()
    pos = sum(1 for m in MOTS_POSITIFS if m in t)
    neg = sum(1 for m in MOTS_NEGATIFS if m in t)
    return max(-3, min(3, pos - neg))


def mention_valeur(titre, nom):
    """Vérifie si un titre mentionne une valeur CAC40."""
    t = titre.lower()
    mots = NOMS_ALTERNATIFS.get(nom, [nom.lower()])
    return any(m in t for m in mots)


def fetch_rss(url, timeout=8):
    """Récupère et parse un flux RSS. Retourne une liste de titres."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            content = r.read().decode("utf-8", errors="ignore")
        root = ET.fromstring(content)
        items = root.findall(".//item")
        titres = []
        for item in items:
            t = item.find("title")
            if t is not None and t.text:
                titres.append(t.text.strip())
        return titres
    except Exception as e:
        print(f"  Erreur RSS {url[:50]} : {e}")
        return []


def collecter_news_valeur(nom, ticker):
    """Collecte les news d'une valeur via Yahoo Finance RSS."""
    url = f"https://fr.finance.yahoo.com/rss/headline?s={ticker}"
    titres = fetch_rss(url)
    news_valeur = []
    for t in titres:
        news_valeur.append({
            "titre":     t,
            "sentiment": scorer_sentiment(t),
            "source":    "Yahoo Finance",
        })
    return news_valeur


def collecter_news_marche():
    """Collecte les news générales du marché (CAC40, macro, Europe)."""
    sources = [
        ("Yahoo Finance CAC40", "https://fr.finance.yahoo.com/rss/headline?s=^FCHI"),
        ("Yahoo Finance Europe", "https://fr.finance.yahoo.com/rss/headline?s=^STOXX50E"),
    ]
    titres_marche = []
    for nom_src, url in sources:
        titres = fetch_rss(url)
        for t in titres:
            titres_marche.append({
                "titre":     t,
                "sentiment": scorer_sentiment(t),
                "source":    nom_src,
            })
    # Déduplique
    vus = set()
    uniques = []
    for n in titres_marche:
        if n["titre"] not in vus:
            vus.add(n["titre"])
            uniques.append(n)
    return uniques[:20]


def attribuer_news_aux_valeurs(news_marche):
    """
    Parcourt les news de marché générales et les attribue aux valeurs
    si leur nom est mentionné dans le titre.
    """
    attribution = {nom: [] for nom in CAC40}
    for article in news_marche:
        for nom in CAC40:
            if mention_valeur(article["titre"], nom):
                attribution[nom].append(article)
    return attribution


def calculer_sentiment_final(news_directes, news_attribuees):
    """Calcule le sentiment consolidé (-3 à +3) et retourne les titres clés."""
    toutes = news_directes + news_attribuees
    if not toutes:
        return 0, []
    score = sum(n["sentiment"] for n in toutes) / len(toutes)
    # Titres les plus importants (sentiment fort en premier)
    tries = sorted(toutes, key=lambda x: abs(x["sentiment"]), reverse=True)
    titres_cles = [n["titre"] for n in tries[:3]]
    return round(max(-3, min(3, score)), 2), titres_cles


def main():
    today = datetime.date.today().isoformat()
    heure = datetime.datetime.now().strftime("%H:%M")
    print(f"Agent News — {today} {heure}")

    # News générales du marché
    print("Collecte news marché général...")
    news_marche = collecter_news_marche()
    print(f"  {len(news_marche)} articles collectés")

    # Attribution aux valeurs via mention dans les titres
    attribution = attribuer_news_aux_valeurs(news_marche)

    # Sentiment global du marché
    sent_global = sum(n["sentiment"] for n in news_marche) / len(news_marche) if news_marche else 0
    mots_cles_marche = [n["titre"] for n in sorted(news_marche, key=lambda x: abs(x["sentiment"]), reverse=True)[:5]]

    # News par valeur
    print("Collecte news par valeur...")
    rapport_valeurs = {}
    for nom, ticker in CAC40.items():
        print(f"  {nom}...")
        news_directes  = collecter_news_valeur(nom, ticker)
        news_attribuees = attribution.get(nom, [])
        sentiment, titres_cles = calculer_sentiment_final(news_directes, news_attribuees)
        nb_news = len(news_directes) + len(news_attribuees)
        rapport_valeurs[nom] = {
            "sentiment":    sentiment,
            "nb_news":      nb_news,
            "titres_cles":  titres_cles,
        }

    # Valeurs avec news fortes
    signaux_forts = sorted(
        [(nom, d) for nom, d in rapport_valeurs.items() if abs(d["sentiment"]) >= 1],
        key=lambda x: abs(x[1]["sentiment"]),
        reverse=True
    )

    rapport = {
        "date":            today,
        "heure":           heure,
        "marche": {
            "sentiment_global": round(sent_global, 2),
            "nb_articles":      len(news_marche),
            "titres_cles":      mots_cles_marche,
        },
        "valeurs":         rapport_valeurs,
        "signaux_forts":   [(nom, d["sentiment"], d["titres_cles"][:1]) for nom, d in signaux_forts[:10]],
    }

    with open(FICHIER_RAPPORT, "w", encoding="utf-8") as f:
        json.dump(rapport, f, ensure_ascii=False, indent=2)

    print(f"\nRapport sauvegardé : {FICHIER_RAPPORT}")
    print(f"Sentiment marché global : {sent_global:+.2f}")
    print(f"Valeurs avec news fortes : {len(signaux_forts)}")
    if signaux_forts:
        print("Top 5 :")
        for nom, d in signaux_forts[:5]:
            print(f"  {nom:25} sentiment {d['sentiment']:+.2f} | {d['titres_cles'][0][:60] if d['titres_cles'] else ''}")


if __name__ == "__main__":
    main()
