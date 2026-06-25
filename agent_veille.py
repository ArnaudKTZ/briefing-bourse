#!/usr/bin/env python3
"""
Agent Veille — l'éclaireur (le poisson pilote).

Surveille la recherche récente en finance quantitative (arXiv q-fin) et fait
remonter les idées qui pourraient améliorer le système. Filtre par pertinence
selon la stratégie d'Arnaud (momentum, facteurs, régimes, allocation, agents IA).

Principe : il PROPOSE des idées à tester. Il n'adopte rien.
Toute idée doit ensuite passer la recette (backtest_harness) avant la prod.
Source gratuite, sans clé API. Tourne 1x/semaine.
"""

import datetime
import json
import os
import smtplib
import urllib.request
import xml.etree.ElementTree as ET
import zoneinfo
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

TZ_PARIS = zoneinfo.ZoneInfo("Europe/Paris")

ZOHO_EMAIL    = os.environ.get("ZOHO_EMAIL", "Arnaud.kuntz@zoho.eu")
ZOHO_PASSWORD = os.environ.get("ZOHO_PASSWORD", "")
ZOHO_SMTP     = "smtp.zoho.eu"
ZOHO_PORT     = 587
# Bilans hebdo : destinataires restreints (override possible via secret DESTINATAIRES_HEBDO)
_dest_env     = os.environ.get("DESTINATAIRES_HEBDO", "")
DESTINATAIRES = ([d.strip() for d in _dest_env.split(",") if d.strip()]
                 or ["Arnaud.kuntz@zoho.eu", "xtrem111team@gmail.com"])

FICHIER_RAPPORT = "veille_rapport.json"
ATOM = "{http://www.w3.org/2005/Atom}"

# Catégories arXiv finance quantitative
ARXIV_URL = (
    "http://export.arxiv.org/api/query?"
    "search_query=cat:q-fin.PM+OR+cat:q-fin.TR+OR+cat:q-fin.ST+OR+cat:q-fin.CP"
    "&sortBy=submittedDate&sortOrder=descending&max_results=40"
)

# Mots-clés pondérés selon la pertinence pour le système d'Arnaud
MOTS_CLES = {
    # cœur de stratégie (poids fort)
    "momentum": 3, "trend following": 3, "trend-following": 3, "dual momentum": 4,
    "factor": 2, "cross-sectional": 3, "time series momentum": 3, "regime": 3,
    "asset allocation": 3, "portfolio allocation": 3, "risk parity": 2,
    "tactical allocation": 3, "rotation": 2,
    # rigueur / méthode (poids fort, c'est notre avantage)
    "walk-forward": 4, "out-of-sample": 4, "overfit": 3, "backtest": 2,
    "transaction cost": 2, "data snooping": 3, "robust": 1,
    # IA appliquée (poids moyen)
    "reinforcement learning": 2, "llm": 2, "language model": 2, "agent": 1,
    "ensemble": 2, "machine learning": 1, "deep learning": 1,
    # risque
    "drawdown": 2, "tail risk": 2, "volatility targeting": 3,
}


def fetch_arxiv():
    req = urllib.request.Request(ARXIV_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        contenu = r.read().decode("utf-8", errors="ignore")
    root = ET.fromstring(contenu)
    articles = []
    for entry in root.findall(f"{ATOM}entry"):
        titre = (entry.findtext(f"{ATOM}title") or "").strip().replace("\n", " ")
        resume = (entry.findtext(f"{ATOM}summary") or "").strip().replace("\n", " ")
        lien = ""
        for link in entry.findall(f"{ATOM}link"):
            if link.get("rel") == "alternate":
                lien = link.get("href", "")
        date = (entry.findtext(f"{ATOM}published") or "")[:10]
        if titre:
            articles.append({"titre": titre, "resume": resume, "lien": lien, "date": date})
    return articles


def scorer_pertinence(article):
    texte = (article["titre"] + " " + article["resume"]).lower()
    score = 0
    hits = []
    for mot, poids in MOTS_CLES.items():
        if mot in texte:
            # bonus si le mot est dans le titre
            facteur = 2 if mot in article["titre"].lower() else 1
            score += poids * facteur
            hits.append(mot)
    return score, hits


def pourquoi(hits):
    """Phrase courte expliquant l'intérêt selon les mots-clés trouvés."""
    rigueur = {"walk-forward", "out-of-sample", "overfit", "data snooping", "transaction cost"}
    coeur   = {"momentum", "dual momentum", "trend following", "trend-following",
               "regime", "asset allocation", "tactical allocation", "volatility targeting"}
    if hits & rigueur:
        return "Méthode de validation rigoureuse — pile notre avantage compétitif."
    if hits & coeur:
        return "Touche directement le cœur de ta stratégie (momentum / allocation / régime)."
    return "Piste IA/risque à explorer."


def envoyer(sujet, html):
    if not ZOHO_PASSWORD or not DESTINATAIRES:
        print("  Pas de mot de passe / destinataire — email non envoyé")
        return
    msg = MIMEMultipart("alternative")
    msg["Subject"], msg["From"], msg["To"] = sujet, ZOHO_EMAIL, ", ".join(DESTINATAIRES)
    msg.attach(MIMEText(html, "html", "utf-8"))
    with smtplib.SMTP(ZOHO_SMTP, ZOHO_PORT) as s:
        s.starttls()
        s.login(ZOHO_EMAIL, ZOHO_PASSWORD)
        s.sendmail(ZOHO_EMAIL, DESTINATAIRES, msg.as_string())
    print(f"  Email envoyé à {', '.join(DESTINATAIRES)}")


def generer_html(now, top):
    cartes = ""
    for a in top:
        h = set(a["hits"])
        cartes += f"""<div style='border:1px solid #e0e0e0;border-radius:8px;padding:14px 16px;margin-bottom:12px;'>
          <a href='{a['lien']}' style='font-size:15px;font-weight:600;color:#185fa5;text-decoration:none;'>{a['titre']}</a>
          <p style='margin:6px 0 0;font-size:13px;color:#0f6e56;'>{pourquoi(h)}</p>
          <p style='margin:4px 0 0;font-size:12px;color:#999;'>{a['date']} · mots-clés : {', '.join(a['hits'][:5])}</p>
        </div>"""

    return f"""<html><body style='font-family:Arial,sans-serif;max-width:680px;margin:auto;padding:20px;color:#222;'>
<div style='background:linear-gradient(135deg,#0c447c,#185fa5);color:white;padding:16px 20px;border-radius:8px 8px 0 0;'>
  <h2 style='margin:0;font-size:18px;'>Veille — l'éclaireur</h2>
  <p style='margin:6px 0 0;font-size:12px;opacity:0.9;'>{now.strftime('%d/%m/%Y')} — ce qui se fait de mieux en finance quantitative</p>
</div>
<div style='border:1px solid #ddd;border-top:none;padding:20px;border-radius:0 0 8px 8px;'>
  <p style='font-size:13px;color:#555;margin:0 0 16px;'>Top {len(top)} idées récentes filtrées pour ta stratégie. À évaluer, pas à adopter.</p>
  {cartes}
  <div style='margin-top:8px;padding:12px;background:#e8f0fb;border-radius:6px;font-size:13px;color:#0c447c;'>
    <strong>Rappel :</strong> aucune de ces idées ne va en production sans passer la recette (backtest hors-échantillon). On prend chez les caïds, mais on vérifie chez nous.
  </div>
</div>
</body></html>"""


if __name__ == "__main__":
    now = datetime.datetime.now(TZ_PARIS)
    print(f"Agent Veille — {now.date()}")

    print("Récupération arXiv q-fin...")
    articles = fetch_arxiv()
    print(f"  {len(articles)} articles récupérés")

    for a in articles:
        a["score"], a["hits"] = scorer_pertinence(a)

    pertinents = [a for a in articles if a["score"] >= 3]
    pertinents.sort(key=lambda x: x["score"], reverse=True)
    top = pertinents[:8]

    print(f"  {len(pertinents)} pertinents, top {len(top)} retenus :")
    for a in top:
        print(f"    [{a['score']:>2}] {a['titre'][:70]}")

    rapport = {
        "date": now.date().isoformat(),
        "nb_articles": len(articles),
        "top": [{"titre": a["titre"], "lien": a["lien"], "date": a["date"],
                 "score": a["score"], "hits": a["hits"]} for a in top],
    }
    with open(FICHIER_RAPPORT, "w", encoding="utf-8") as f:
        json.dump(rapport, f, ensure_ascii=False, indent=2)

    if top:
        print("Envoi digest veille...")
        html = generer_html(now, top)
        envoyer(f"Veille — {len(top)} idées à explorer — {now.strftime('%d/%m/%Y')}", html)
    else:
        print("  Aucun article pertinent cette semaine, pas d'email.")

    print("Terminé.")
