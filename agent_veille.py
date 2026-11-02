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
import html
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
# Bilans hebdo : destinataires fixes zoho uniquement
# (décision Arnaud 02/07, indépendant du secret DESTINATAIRES_HEBDO).
DESTINATAIRES = ["Arnaud.kuntz@zoho.eu"]

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
    """Récupère les papiers arXiv. Renvoie [] (et le signale) en cas de panne réseau/parse."""
    try:
        req = urllib.request.Request(ARXIV_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            contenu = r.read().decode("utf-8", errors="ignore")
        root = ET.fromstring(contenu)
    except Exception as e:
        print(f"  WARN arXiv indisponible : {e}")
        return []
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


# Registre des hypothèses déjà tranchées par ce projet (ajout du 01/11). Avant
# ça, rien n'empêchait de ré-explorer deux fois la même idée déjà réfutée (le
# VIX et le Fear & Greed ont chacun été proposés puis rejetés à deux reprises
# dans l'historique). Ne bloque rien : annote seulement, pour que le digest
# dise "déjà tranché, voir HISTORY.md" au lieu de refaire semblant de découvrir.
DEJA_TRANCHE = {
    "vix": "Malus VIX testé et retiré le 05/07/2026 : un VIX élevé précède des rendements CAC SUPÉRIEURS, pas inférieurs (26 ans de données).",
    "fear and greed": "Indice Fear & Greed testé et retiré le 26/06/2026 : contre-productif, même conclusion que le VIX.",
    "fear & greed": "Indice Fear & Greed testé et retiré le 26/06/2026 : contre-productif, même conclusion que le VIX.",
    "canary": "Signal canari (DAA, Keller & Keuning) testé sur le cœur Dual Momentum le 11/10/2026 : rejeté (CAGR -2,51 pts/an pour seulement +0,6 pt de drawdown en moins).",
    "breadth momentum": "Breadth momentum façon VAA/PAA écarté le 11/10/2026 : aucune publication ne le valide sur un univers investi à seulement 2 actifs (World/USA).",
    "emerging market": "Les marchés émergents comme 3e classe d'actif DÉTENUE ont été rejetés deux fois (dual_momentum_backtest puis piste1_bridage_pea du 08/09/2026) : ils aggravent la pire chute du cœur.",
    "rsi": "Famille RSI/MACD/Bollinger retail réfutée par 'Retail Trader's Ruin' (arXiv 2607.20093, lu le 29/07/2026) : Sharpe-gap et CAGR-gap significativement négatifs sur NASDAQ-100 et réplique UE.",
}


def verifier_deja_tranche(article):
    """Articles qui recoupent une hypothèse déjà testée et tranchée ici.
    N'exclut rien (un nouvel angle sur un vieux sujet peut rester utile),
    annote seulement pour éviter de perdre du temps à redécouvrir."""
    texte = (article["titre"] + " " + article["resume"]).lower()
    return [v for cle, v in DEJA_TRANCHE.items() if cle in texte]


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


def extrait_resume(resume, n_phrases=2, max_chars=420):
    """Les premières phrases de l'abstract arXiv (déjà récupéré, jamais affiché
    avant le 18/07 : le digest ne montrait qu'une étiquette générique par
    mots-clés, ce qui obligeait à trier à la main). Découpage simple sur '. '."""
    if not resume:
        return ""
    phrases = [p.strip() for p in resume.split(". ") if p.strip()]
    texte = ". ".join(phrases[:n_phrases])
    if texte and not texte.endswith("."):
        texte += "."
    if len(texte) > max_chars:
        texte = texte[:max_chars].rsplit(" ", 1)[0] + "…"
    return texte


# ─── SUIVI 13F — version modeste du "Loup de Wall Street" (ajout du 02/11) ────
# Idée d'Arnaud (01-02/11) : un agent qui étudie ce que font les meilleurs
# traders chaque jour. Version honnête plutôt que la promesse intenable d'un
# agent qui "apprend et devient le meilleur" : les grands gérants américains
# publient leurs positions (formulaire 13F, SEC) avec un RETARD STRUCTUREL de
# 45 jours après la fin du trimestre — pas du temps réel, et leur échelle
# (des centaines de millions de dollars, souvent du trading institutionnel)
# ne se transpose pas à un portefeuille retail. Ce n'est donc jamais un
# signal à suivre, seulement une source d'idées à vérifier soi-même, dans le
# même esprit que les papiers arXiv ci-dessus.
GERANTS_SUIVIS = {
    "Berkshire Hathaway (Buffett)": "0001067983",
    "Pershing Square (Ackman)":     "0001336528",
    "Himalaya Capital (Li Lu)":     "0001709323",
}
FICHIER_13F = "veille_13f_historique.json"
SEC_HEADERS = {"User-Agent": "JarvisAgentBourse/1.0 (recherche personnelle; arnaud.kuntz@zoho.eu)"}
NS_13F = "{http://www.sec.gov/edgar/document/thirteenf/informationtable}"


def _requete_sec(url):
    req = urllib.request.Request(url, headers=SEC_HEADERS)
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read()


def dernier_13f(cik):
    """Dernier dépôt 13F-HR connu : (accession, date_dépôt, date_des_positions)."""
    try:
        data = json.loads(_requete_sec(f"https://data.sec.gov/submissions/CIK{cik}.json"))
        recent = data["filings"]["recent"]
        for i, forme in enumerate(recent["form"]):
            if forme == "13F-HR":
                return recent["accessionNumber"][i], recent["filingDate"][i], recent["reportDate"][i]
    except Exception as e:
        print(f"  SEC indisponible pour {cik} : {e}")
    return None


def holdings_13f(cik, accession):
    """Positions agrégées par CUSIP (un même titre peut apparaître plusieurs
    fois dans le dépôt, une ligne par filiale ayant une discrétion de vote
    séparée — il faut sommer, pas prendre la première ligne)."""
    acc_nodash = accession.replace("-", "")
    base = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc_nodash}"
    try:
        index = json.loads(_requete_sec(f"{base}/index.json"))
        fichiers_xml = [it["name"] for it in index["directory"]["item"] if it["name"].endswith(".xml")]
        candidats = [f for f in fichiers_xml if f != "primary_doc.xml"]
        if not candidats:
            return {}
        table_xml = _requete_sec(f"{base}/{candidats[0]}")
    except Exception as e:
        print(f"  Table de positions indisponible ({cik}, {accession}) : {e}")
        return {}

    try:
        root = ET.fromstring(table_xml)
    except Exception as e:
        print(f"  XML illisible ({cik}, {accession}) : {e}")
        return {}

    positions = {}
    for entry in root.findall(f"{NS_13F}infoTable"):
        cusip = entry.findtext(f"{NS_13F}cusip")
        nom   = entry.findtext(f"{NS_13F}nameOfIssuer")
        valeur = entry.findtext(f"{NS_13F}value")
        if not cusip:
            continue
        p = positions.setdefault(cusip, {"nom": nom, "valeur": 0})
        p["valeur"] += int(valeur or 0)
    return positions


def comparer_13f(actuel, precedent):
    """Nouvelles positions, sorties, plus fortes variations de valeur (%)."""
    cusips_actuels, cusips_precedents = set(actuel), set(precedent)
    nouvelles = [actuel[c]["nom"] for c in cusips_actuels - cusips_precedents]
    sorties   = [precedent[c]["nom"] for c in cusips_precedents - cusips_actuels]
    variations = []
    for c in cusips_actuels & cusips_precedents:
        v0, v1 = precedent[c]["valeur"], actuel[c]["valeur"]
        if v0 > 0:
            variations.append((actuel[c]["nom"], round((v1 - v0) / v0 * 100, 1)))
    variations.sort(key=lambda x: abs(x[1]), reverse=True)
    return nouvelles[:10], sorties[:10], variations[:8]


def suivre_gerants():
    """Pour chaque gérant suivi, vérifie s'il y a un dépôt 13F plus récent que
    la dernière fois vérifiée, et si oui compare les positions. Les 13F ne
    changent que ~4x/an par gérant : la plupart des semaines, rien de neuf."""
    historique = {}
    if os.path.exists(FICHIER_13F):
        with open(FICHIER_13F, "r", encoding="utf-8") as f:
            historique = json.load(f)

    comptes_rendus = []
    for nom_gerant, cik in GERANTS_SUIVIS.items():
        info = dernier_13f(cik)
        if not info:
            continue
        accession, date_depot, date_position = info
        connu = historique.get(cik, {})
        if connu.get("date_position") == date_position:
            continue  # déjà vu

        positions = holdings_13f(cik, accession)
        if not positions:
            continue
        nouvelles, sorties, variations = comparer_13f(positions, connu.get("positions", {}))
        retard_jours = (datetime.date.today() - datetime.date.fromisoformat(date_position)).days

        comptes_rendus.append({
            "gerant": nom_gerant, "date_position": date_position, "date_depot": date_depot,
            "retard_jours": retard_jours, "nouvelles": nouvelles, "sorties": sorties,
            "variations": variations, "premier_releve": not connu,
        })
        historique[cik] = {"date_position": date_position, "positions": positions}

    with open(FICHIER_13F, "w", encoding="utf-8") as f:
        json.dump(historique, f, ensure_ascii=False, indent=2)
    return comptes_rendus


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


def bloc_html_13f(comptes_rendus):
    if not comptes_rendus:
        return ""
    cartes = ""
    for cr in comptes_rendus:
        if cr["premier_releve"]:
            detail = (f"<p style='margin:6px 0 0;font-size:12px;color:#666;'>Premier relevé : "
                      f"{len(cr['variations']) + len(cr['nouvelles'])} positions enregistrées comme référence, "
                      f"rien à comparer encore.</p>")
        else:
            lignes = []
            if cr["nouvelles"]:
                lignes.append("<strong>Nouvelles :</strong> " + ", ".join(cr["nouvelles"][:6]))
            if cr["sorties"]:
                lignes.append("<strong>Sorties :</strong> " + ", ".join(cr["sorties"][:6]))
            if cr["variations"]:
                var_txt = ", ".join(f"{nom} ({v:+.0f}%)" for nom, v in cr["variations"][:5])
                lignes.append("<strong>Plus fortes variations :</strong> " + var_txt)
            detail = "".join(f"<p style='margin:4px 0 0;font-size:12px;color:#444;'>{l}</p>" for l in lignes)
        cartes += f"""<div style='border:1px solid #e0e0e0;border-radius:8px;padding:12px 16px;margin-bottom:10px;'>
          <p style='margin:0;font-weight:600;font-size:13px;'>{cr['gerant']}</p>
          <p style='margin:2px 0 0;font-size:11px;color:#b71c1c;'>Positions au {cr['date_position']},
            dépôt publié le {cr['date_depot']} — déjà {cr['retard_jours']} jours de retard structurel.</p>
          {detail}
        </div>"""
    return f"""
  <h3 style='font-size:14px;margin:20px 0 8px;'>Dépôts 13F — ce que font quelques gérants réputés (avec retard)</h3>
  <div style='background:#fff3e0;border-left:4px solid #e65100;padding:10px 14px;border-radius:6px;font-size:12px;color:#8a4b00;margin-bottom:10px;'>
    Pas un signal à suivre : ces positions datent d'il y a 1,5 à 3 mois (délai légal de 45 jours après
    la fin du trimestre), et l'échelle de ces gérants ne se transpose pas à un portefeuille retail.
    Une idée à vérifier soi-même, jamais un ordre à copier.
  </div>
  {cartes}"""


def generer_html(now, top, comptes_rendus_13f=None):
    cartes = ""
    for a in top:
        h = set(a["hits"])
        titre_safe = html.escape(a["titre"])
        lien_safe  = html.escape(a["lien"], quote=True)
        extrait_safe = html.escape(extrait_resume(a.get("resume", "")))
        bloc_extrait = (f"<p style='margin:6px 0 0;font-size:13px;color:#444;line-height:1.45;'>{extrait_safe}</p>"
                        if extrait_safe else "")
        deja = a.get("deja_tranche") or []
        bloc_deja = ""
        if deja:
            verdicts_safe = "".join(f"<li>{html.escape(v)}</li>" for v in deja)
            bloc_deja = (f"<div style='margin:8px 0 0;padding:8px 10px;background:#fff3e0;border-left:3px solid #e65100;"
                         f"border-radius:4px;font-size:11px;color:#8a4b00;'>"
                         f"<strong>Déjà tranché ici :</strong><ul style='margin:4px 0 0;padding-left:16px;'>{verdicts_safe}</ul></div>")
        cartes += f"""<div style='border:1px solid #e0e0e0;border-radius:8px;padding:14px 16px;margin-bottom:12px;'>
          <a href='{lien_safe}' style='font-size:15px;font-weight:600;color:#185fa5;text-decoration:none;'>{titre_safe}</a>
          {bloc_extrait}
          <p style='margin:6px 0 0;font-size:12px;color:#0f6e56;'>{pourquoi(h)}</p>
          <p style='margin:4px 0 0;font-size:12px;color:#999;'>{a['date']} · mots-clés : {', '.join(a['hits'][:5])}</p>
          {bloc_deja}
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
  {bloc_html_13f(comptes_rendus_13f)}
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
        a["deja_tranche"] = verifier_deja_tranche(a)
        if a["deja_tranche"]:
            a["score"] = max(0, a["score"] - 5)   # ne disparaît pas, mais cède la place aux idées neuves

    pertinents = [a for a in articles if a["score"] >= 3]
    pertinents.sort(key=lambda x: x["score"], reverse=True)
    top = pertinents[:8]

    print(f"  {len(pertinents)} pertinents, top {len(top)} retenus :")
    for a in top:
        print(f"    [{a['score']:>2}] {a['titre'][:70]}")

    print("Vérification des dépôts 13F (gérants suivis)...")
    comptes_rendus_13f = suivre_gerants()
    for cr in comptes_rendus_13f:
        print(f"  {cr['gerant']} : nouveau dépôt du {cr['date_depot']} "
              f"(positions au {cr['date_position']}, {cr['retard_jours']} j de retard)")
    if not comptes_rendus_13f:
        print("  Rien de neuf (13F inchangés depuis la dernière vérification)")

    rapport = {
        "date": now.date().isoformat(),
        "nb_articles": len(articles),
        "top": [{"titre": a["titre"], "lien": a["lien"], "date": a["date"],
                 "score": a["score"], "hits": a["hits"],
                 "deja_tranche": a.get("deja_tranche") or [],
                 "extrait": extrait_resume(a.get("resume", ""))} for a in top],
        "depots_13f": comptes_rendus_13f,
    }
    with open(FICHIER_RAPPORT, "w", encoding="utf-8") as f:
        json.dump(rapport, f, ensure_ascii=False, indent=2)

    if top or comptes_rendus_13f:
        print("Envoi digest veille...")
        html = generer_html(now, top, comptes_rendus_13f)
        sujet = f"Veille — {len(top)} idées"
        if comptes_rendus_13f:
            sujet += f" + {len(comptes_rendus_13f)} dépôt(s) 13F"
        envoyer(f"{sujet} — {now.strftime('%d/%m/%Y')}", html)
    else:
        print("  Rien à signaler cette semaine, pas d'email.")

    print("Terminé.")
