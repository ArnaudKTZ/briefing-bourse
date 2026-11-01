#!/usr/bin/env python3
"""
Audit — le sentiment News a-t-il un edge, avec 4 mois de données en plus ?

Origine : POIDS_NEWS a été mis à 0 le 02/07/2026 après un premier audit sur
312 observations (sentiment penchant à l'envers, bucket négatif surperforme).
Décision prise avec un historique encore très court. On a maintenant ~4 mois
de rapports quotidiens en plus — l'occasion de refaire la mesure avant de
laisser le poids à 0 indéfiniment sans preuve récente (piste priorité moyenne
du 01/11).

Problème technique : rapport_news.json est écrasé chaque jour (pas d'historique
conservé dans le fichier lui-même). La seule trace du passé est dans git : ce
script rejoue chaque commit quotidien du rapport (~04h45, 1/jour) via
`git show`, reconstruit un historique sentiment × jour × valeur, et mesure le
rendement forward (J+5, clôture) comme le fait agent_evaluateur.py pour le
score composite.

Ne modifie rien en prod, ne touche à aucun fichier suivi. Sortie : console +
audit_news_sentiment_resultats.json.
"""

import json
import subprocess
import warnings

import numpy as np
import yfinance as yf

from marche_config import CAC40

HORIZON = 5
FICHIER_RESULTATS = "audit_news_sentiment_resultats.json"

warnings.filterwarnings("ignore")


def commits_quotidiens():
    """Un commit par jour (le run ~04h45, le plus régulier) sur l'historique
    de rapport_news.json."""
    out = subprocess.run(
        ["git", "log", "--format=%H|%ai", "--", "rapport_news.json"],
        capture_output=True, text=True, check=True,
    ).stdout.strip().splitlines()
    vus = set()
    commits = []
    for ligne in out:
        hash_, date_heure = ligne.split("|", 1)
        date = date_heure.split(" ")[0]
        heure = date_heure.split(" ")[1]
        if date in vus:
            continue
        if heure.startswith("04:4"):
            commits.append((date, hash_))
            vus.add(date)
    return sorted(commits)


def contenu_a(hash_):
    try:
        raw = subprocess.run(
            ["git", "show", f"{hash_}:rapport_news.json"],
            capture_output=True, text=True, check=True,
        ).stdout
        return json.loads(raw)
    except Exception:
        return None


def charger_closes():
    closes = {}
    for nom, ticker in CAC40.items():
        try:
            h = yf.Ticker(ticker).history(period="1y")["Close"].dropna()
            if not h.empty:
                closes[nom] = h
        except Exception as e:
            print(f"  {nom} : cours indisponibles ({e})")
    return closes


def close_apres(serie, date_str, n):
    dates = [d.strftime("%Y-%m-%d") for d in serie.index]
    apres = [i for i, d in enumerate(dates) if d > date_str]
    if len(apres) < n:
        return None
    return float(serie.iloc[apres[n - 1]])


def close_le_jour_ou_avant(serie, date_str):
    dates = [d.strftime("%Y-%m-%d") for d in serie.index]
    avant_ou_jour = [i for i, d in enumerate(dates) if d <= date_str]
    if not avant_ou_jour:
        return None
    return float(serie.iloc[avant_ou_jour[-1]])


def sentiment_bucket(s):
    if s is None:
        return None
    if s <= -0.3: return "très négatif (<=-0.3)"
    if s < -0.05: return "négatif (-0.3 à -0.05)"
    if s <= 0.05: return "neutre (-0.05 à 0.05)"
    if s < 0.3:   return "positif (0.05 à 0.3)"
    return "très positif (>=0.3)"


def moyenne(vals):
    vals = [v for v in vals if v is not None]
    return round(sum(vals) / len(vals), 3) if vals else None


if __name__ == "__main__":
    print("Reconstruction de l'historique sentiment via git (rapport_news.json)...")
    commits = commits_quotidiens()
    print(f"  {len(commits)} jours de rapport retrouvés ({commits[0][0]} -> {commits[-1][0]})")

    print("Téléchargement des clôtures (39 valeurs, 1 an)...")
    closes = charger_closes()

    obs = []
    for date, hash_ in commits:
        d = contenu_a(hash_)
        if not d:
            continue
        for nom, v in (d.get("valeurs") or {}).items():
            sentiment = v.get("sentiment")
            if sentiment is None or nom not in closes:
                continue
            prix = close_le_jour_ou_avant(closes[nom], date)
            if prix is None:
                continue
            px5 = close_apres(closes[nom], date, HORIZON)
            if px5 is None:
                continue
            rend = round((px5 / prix - 1) * 100, 2)
            obs.append({"date": date, "nom": nom, "sentiment": sentiment, "rend": rend})

    print(f"{len(obs)} observations valeur x jour reconstruites")

    univers = [o["rend"] for o in obs]
    m_uni = moyenne(univers)

    labels = ["très négatif (<=-0.3)", "négatif (-0.3 à -0.05)", "neutre (-0.05 à 0.05)",
              "positif (0.05 à 0.3)", "très positif (>=0.3)"]
    resultat = {}
    print(f"\nRendement moyen univers à J+{HORIZON} : {m_uni:+.2f}%\n")
    print(f"{'Bucket sentiment':30}{'N':>6}{'Rdt moyen':>12}{'Edge vs univers':>18}")
    print("-" * 66)
    for label in labels:
        vals = [o["rend"] for o in obs if sentiment_bucket(o["sentiment"]) == label]
        m = moyenne(vals)
        edge = round(m - m_uni, 2) if m is not None else None
        resultat[label] = {"n": len(vals), "moy": m, "edge": edge}
        print(f"{label:30}{len(vals):>6}{'' if m is None else format(m, '+.2f')+'%':>12}"
              f"{'' if edge is None else format(edge, '+.2f')+' pts':>18}")

    # Corrélation de rang simple (sentiment vs rendement), sans scipy
    import pandas as pd
    s_series = pd.Series([o["sentiment"] for o in obs])
    r_series = pd.Series([o["rend"] for o in obs])
    ic = round(float(s_series.rank().corr(r_series.rank())), 4) if len(obs) > 10 else None

    print(f"\nIC de Spearman (sentiment vs rendement J+{HORIZON}) : {ic}")
    print(f"(comparable à l'IC du score composite dans agent_evaluateur.py — "
          f"repères : ~0 aucun pouvoir, 0.03 faible, 0.05+ exploitable avant frais)")

    seuil_n = 30
    porteurs = [f"{l} ({resultat[l]['edge']:+.2f} pts, n={resultat[l]['n']})"
                for l in labels if resultat[l]["n"] >= seuil_n and resultat[l]["edge"] is not None
                and abs(resultat[l]["edge"]) >= 0.3]
    if porteurs or (ic is not None and abs(ic) >= 0.03):
        verdict = (f"Signal mesurable : IC={ic}" + (f" ; buckets porteurs : {', '.join(porteurs)}" if porteurs else "")
                   + ". À confirmer avant de remonter POIDS_NEWS (passer par scoring_intraday.py, jamais en aveugle).")
    else:
        verdict = (f"Toujours aucun edge mesurable (IC={ic}, aucun bucket au-dessus de 0,3 pt avec n>=30). "
                   f"POIDS_NEWS=0 reste justifié sur {len(obs)} observations ({commits[0][0]} -> {commits[-1][0]}).")
    print(f"\nVerdict : {verdict}")

    with open(FICHIER_RESULTATS, "w", encoding="utf-8") as f:
        json.dump({
            "periode": f"{commits[0][0]} -> {commits[-1][0]}",
            "n_jours": len(commits), "n_obs": len(obs),
            "univers_moy_j5": m_uni, "buckets": resultat,
            "ic_spearman_j5": ic, "verdict": verdict,
        }, f, ensure_ascii=False, indent=2)
    print(f"\nRésultats sauvegardés dans {FICHIER_RESULTATS}")
