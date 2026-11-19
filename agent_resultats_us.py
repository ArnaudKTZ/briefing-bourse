#!/usr/bin/env python3
"""
Agent Résultats US : suivi des publications trimestrielles du top 10 du MSCI World.

Pourquoi : l'ETF MSCI World de l'assurance vie BoursoVie pèse environ un quart
sur ces 10 géants américains. Leurs résultats trimestriels sont ce qui fait le
plus bouger l'argent réel. Ce n'est PAS un signal d'achat ou de vente.

Comment : lancé chaque matin juste avant le briefing de 7h (même workflow).
Pour chaque entreprise, lit la liste de ses dépôts à la SEC :
  - nouveau communiqué de résultats (8-K item 2.02) : annonce, chiffres à venir ;
  - nouveau rapport trimestriel ou annuel (10-Q / 10-K) : chiffres officiels
    (chiffre d'affaires, marge nette, bénéfice par action, évolution sur un an).
Si les chiffres SEC ne sont pas encore à jour le jour du dépôt, on retente le
lendemain (jusqu'à 10 jours).

Sortie : resultats_us.json
  - "vu" : dernier dépôt connu par entreprise (mémoire entre deux runs) ;
  - "nouveaux" : ce qui est apparu à ce run (lu par le briefing, affiché
    seulement s'il y a du nouveau) ;
  - "historique" : les 40 dernières détections (lu par l'appli web).

Premier lancement : mémorise l'état actuel sans rien annoncer.
Identification SEC obligatoire : variable d'environnement SEC_USER_AGENT
("Nom email"). Absente = l'agent ne fait rien, le briefing part sans ce bloc.
"""

import datetime
import json
import os
import sys

import sec_facts as sf

FICHIER = "resultats_us.json"

# Top 10 approximatif du MSCI World (le classement bouge un peu chaque trimestre).
# Modifiable ici : ticker SEC -> nom affiché.
TOP10 = {
    "NVDA": "Nvidia",
    "AAPL": "Apple",
    "MSFT": "Microsoft",
    "AMZN": "Amazon",
    "GOOGL": "Alphabet",
    "META": "Meta",
    "AVGO": "Broadcom",
    "TSLA": "Tesla",
    "BRK-B": "Berkshire Hathaway",
    "JPM": "JPMorgan",
}

MAX_RETENTE_JOURS = 10
TAILLE_HISTORIQUE = 40


def charger():
    if os.path.exists(FICHIER):
        with open(FICHIER, encoding="utf-8") as f:
            return json.load(f)
    return {}


def sauver(etat):
    with open(FICHIER, "w", encoding="utf-8") as f:
        json.dump(etat, f, ensure_ascii=False, indent=2)
        f.write("\n")


def chiffres(fetcher, cik, periode_rapport):
    """Ligne du trimestre couvert par le rapport, ou None si la SEC n'est pas encore à jour."""
    cf = fetcher.json(sf.FACTS_URL % cik, "companyfacts-CIK%s.json" % cik)
    res = sf.analyse(cf, quarters=6)
    if not res["rows"]:
        return None
    r = res["rows"][0]
    if periode_rapport and r["end"] < periode_rapport:
        return None  # faits XBRL en retard sur le dépôt
    return {
        "trimestre": r["fiscal"].strip(),
        "fin_periode": r["end"],
        "q4_deduit": bool(r["derived"]),
        "ca_mds": round(r["revenue"] / 1e9, 2) if r["revenue"] is not None else None,
        "ca_yoy": r["revenue_yoy"],
        "marge_nette": r["net_margin"],
        "benef_net_mds": round(r["net_income"] / 1e9, 2) if r["net_income"] is not None else None,
        "bpa": r["eps_diluted"],
        "bpa_yoy": r["eps_yoy"],
    }


def main():
    ua = sf.user_agent(None, config=None)
    if not ua:
        print("  WARN résultats US : SEC_USER_AGENT absent, agent sauté")
        return 0
    fetcher = sf.Fetcher(ua)
    etat = charger()
    premier = "vu" not in etat
    vu = etat.setdefault("vu", {})
    attente = etat.setdefault("en_attente", {})
    historique = etat.setdefault("historique", [])
    aujourdhui = datetime.date.today().isoformat()
    nouveaux = []

    try:
        ciks = sf.ticker_ciks(fetcher)
    except sf.FactsError as e:
        print(f"  WARN résultats US : {e}")
        return 0

    for ticker, nom in TOP10.items():
        cik = ciks.get(ticker.replace("-", "."), (None, None))[0]
        if not cik:
            print(f"  WARN résultats US : pas de CIK pour {ticker}")
            continue
        try:
            sub = fetcher.json(sf.SUBMISSIONS_URL % cik, "submissions-CIK%s.json" % cik)
            dep = sf.latest_filings(sub, cik, None)
        except sf.FactsError as e:
            print(f"  WARN résultats US {ticker} : {e}")
            continue
        connu = vu.get(ticker, {})
        rap, k8 = dep.get("report"), dep.get("earnings_8k")

        if premier:
            vu[ticker] = {"rapport": rap and rap["accession"], "8k": k8 and k8["accession"]}
            continue

        # 1) Communiqué de résultats (arrive en premier, souvent la veille au soir)
        if k8 and k8["accession"] != connu.get("8k"):
            connu["8k"] = k8["accession"]
            nouveaux.append({"ticker": ticker, "nom": nom, "type": "annonce",
                             "depose": k8["filed"], "url": k8["url"]})

        # 2) Rapport officiel 10-Q / 10-K : chiffres
        if rap and (rap["accession"] != connu.get("rapport") or ticker in attente):
            try:
                c = chiffres(fetcher, cik, rap.get("period"))
            except sf.FactsError as e:
                print(f"  WARN résultats US {ticker} chiffres : {e}")
                c = None
            if c:
                connu["rapport"] = rap["accession"]
                attente.pop(ticker, None)
                nouveaux.append({"ticker": ticker, "nom": nom, "type": "chiffres",
                                 "forme": rap["form"], "depose": rap["filed"],
                                 "url": rap["url"], **c})
            else:
                debut = attente.setdefault(ticker, aujourdhui)
                if (datetime.date.fromisoformat(aujourdhui)
                        - datetime.date.fromisoformat(debut)).days >= MAX_RETENTE_JOURS:
                    connu["rapport"] = rap["accession"]  # abandon, évite de boucler
                    attente.pop(ticker, None)
        vu[ticker] = connu

    for n in nouveaux:
        n["detecte"] = aujourdhui
    etat["nouveaux"] = nouveaux
    etat["historique"] = (nouveaux + historique)[:TAILLE_HISTORIQUE]
    etat["maj"] = aujourdhui
    etat["entreprises"] = TOP10
    sauver(etat)
    if premier:
        print(f"  Résultats US : premier lancement, état mémorisé pour {len(vu)} entreprises")
    else:
        print(f"  Résultats US : {len(nouveaux)} nouveauté(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
