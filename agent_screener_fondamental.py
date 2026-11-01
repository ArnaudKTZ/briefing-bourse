#!/usr/bin/env python3
"""
Agent Screener Fondamental CAC40 — automatise le quality-screen du 01/11
sur les 39 valeurs, au lieu de le refaire à la main valeur par valeur.

Origine (recherche "Super agents et compétences bourse", 01/11) : la
recherche fondamentale manuelle du 01/11 (skills quality-screen +
investment-checklist, façon Buffett/Munger) sur 3 valeurs (L'Oréal, Air
Liquide, LVMH) a pris une session de travail pour 3 titres sur 39. Aucun
outil open source trouvé ne combine univers CAC40 + indicateurs fondamentaux
de qualité + exécution automatisée régulière. Celui-ci le fait, en version
SIMPLIFIÉE et explicitement documentée comme telle.

SIMPLIFICATION ASSUMÉE : le quality-screen manuel du 01/11 utilisait des
moyennes sur 5-10 ans (ROE, FCF cumulé) obtenues par recherche web poste par
poste. yfinance ne donne qu'un instantané TTM (douze derniers mois) par
simple appel .info — pas d'historique profond en un seul appel. Ce screener
est donc un filtre de premier passage sur les douze derniers mois, pas un
remplacement du quality-screen approfondi. Un score élevé ici est un
candidat à approfondir à la main (comme on l'a fait pour les 3 valeurs du
01/11), pas une décision d'achat.

SÉCURITÉ ANTI-LOOK-AHEAD (Sentinelle, voir lookahead_guard.py) : ce script
ne fait JAMAIS tourner son score sur une date passée — il calcule le score
d'AUJOURD'HUI avec les données d'AUJOURD'HUI, pour une décision qui ne
regarde que vers l'avant (prospective, comme etf_facteur_portefeuille.json
ou dual_momentum_portefeuille.json). Aucune simulation historique, donc
aucun risque de biais temporel par construction. Si un jour ce script
sert à BACKTESTER le score sur des dates passées, utiliser
lookahead_guard.verifier_lag_publication() avant d'utiliser une donnée
fondamentale comme "connue" à une date donnée (lag minimum 45 jours après
publication réelle des comptes).

6 critères (5 utilisables dès le premier mois, la dilution s'évalue à partir
du 2e mois faute d'historique) :
  1. ROE >= 15%
  2. Free cash-flow positif (TTM)
  3. Marge brute >= 15% (pouvoir de fixation des prix)
  4. Marge nette >= 5%
  5. Couverture de dette (EBITDA/dette totale >= 15%) — exempté pour le
     secteur Banques/Finance (bilan structurellement différent)
  6. Pas de dilution excessive (actions en circulation stables ou en baisse,
     tolérance +2%/mois) — à partir du 2e mois

Aucun achat automatique. Sort une liste de candidats pour revue humaine,
dans l'esprit de la recherche individuelle du 01/11 (LVMH).

Tourne 1x/mois (le 2, 8h30). Pas d'appel API payant.
"""

import datetime
import json
import os
import smtplib
import zoneinfo
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import yfinance as yf

from marche_config import CAC40, SECTEUR_PAR_VALEUR

TZ_PARIS = zoneinfo.ZoneInfo("Europe/Paris")

ZOHO_EMAIL    = os.environ.get("ZOHO_EMAIL", "Arnaud.kuntz@zoho.eu")
ZOHO_PASSWORD = os.environ.get("ZOHO_PASSWORD", "")
DESTINATAIRES = ["Arnaud.kuntz@zoho.eu"]

FICHIER_RAPPORT = "screener_fondamental_cac40.json"
SECTEUR_SANS_DETTE = "Banques/Finance"


def analyser_valeur(nom, ticker):
    info = yf.Ticker(ticker).info
    secteur = SECTEUR_PAR_VALEUR.get(nom, "?")

    roe        = info.get("returnOnEquity")
    fcf        = info.get("freeCashflow")
    marge_brute = info.get("grossMargins")
    marge_nette = info.get("profitMargins")
    ebitda     = info.get("ebitda")
    dette      = info.get("totalDebt")
    prix       = info.get("currentPrice") or info.get("regularMarketPrice")
    cible      = info.get("targetMeanPrice")
    reco       = info.get("recommendationMean")
    actions    = info.get("sharesOutstanding")

    criteres = {}
    criteres["roe_15"]       = (roe is not None, roe is not None and roe >= 0.15)
    criteres["fcf_positif"]  = (fcf is not None, fcf is not None and fcf > 0)
    criteres["marge_brute_15"] = (marge_brute is not None, marge_brute is not None and marge_brute >= 0.15)
    criteres["marge_nette_5"]  = (marge_nette is not None, marge_nette is not None and marge_nette >= 0.05)

    if secteur == SECTEUR_SANS_DETTE:
        criteres["couverture_dette"] = (True, True)  # exempté, bilan différent
    elif dette is None or dette == 0:
        criteres["couverture_dette"] = (True, True)  # pas de dette = critère trivialement passé
    else:
        cov = (ebitda / dette) if (ebitda is not None and dette) else None
        criteres["couverture_dette"] = (cov is not None, cov is not None and cov >= 0.15)

    score = sum(1 for calculable, passe in criteres.values() if calculable and passe)
    sur = sum(1 for calculable, _ in criteres.values() if calculable)

    upside = round((cible / prix - 1) * 100, 1) if (cible and prix) else None

    return {
        "nom": nom, "ticker": ticker, "secteur": secteur,
        "score": score, "sur": sur, "criteres": {k: v[1] if v[0] else None for k, v in criteres.items()},
        "roe_pct": round(roe * 100, 1) if roe is not None else None,
        "fcf": fcf,
        "marge_brute_pct": round(marge_brute * 100, 1) if marge_brute is not None else None,
        "marge_nette_pct": round(marge_nette * 100, 1) if marge_nette is not None else None,
        "prix": prix, "cible_analystes": cible, "upside_cible_pct": upside,
        "recommandation_moy": reco, "actions_circulation": actions,
    }


def ajouter_dilution(valeurs, precedent):
    """Compare les actions en circulation à celles du mois précédent.
    Pas de donnée au premier mois : critère non calculable, ignoré du score."""
    anciennes = {v["nom"]: v.get("actions_circulation") for v in (precedent or {}).get("valeurs", [])}
    for v in valeurs:
        ancien = anciennes.get(v["nom"])
        actuel = v.get("actions_circulation")
        if ancien and actuel:
            variation = (actuel - ancien) / ancien * 100
            pas_dilue = variation <= 2.0
            v["criteres"]["pas_de_dilution"] = pas_dilue
            v["dilution_pct_1m"] = round(variation, 2)
            if pas_dilue:
                v["score"] += 1
            v["sur"] += 1
        else:
            v["criteres"]["pas_de_dilution"] = None
            v["dilution_pct_1m"] = None
    return valeurs


def generer_html(now, valeurs, top):
    lignes = ""
    for v in top:
        c = v["criteres"]
        badges = "".join(
            f"<span style='display:inline-block;margin:0 3px 3px 0;padding:2px 6px;border-radius:3px;"
            f"font-size:10px;background:{'#e8f5e9;color:#2e7d32' if ok else ('#ffebee;color:#c62828' if ok is False else '#f5f5f5;color:#999')};'>"
            f"{label}</span>"
            for label, ok in [("ROE", c.get("roe_15")), ("FCF", c.get("fcf_positif")),
                               ("Marge brute", c.get("marge_brute_15")), ("Marge nette", c.get("marge_nette_5")),
                               ("Dette", c.get("couverture_dette")), ("Dilution", c.get("pas_de_dilution"))]
        )
        upside = f"{v['upside_cible_pct']:+.1f}%" if v.get("upside_cible_pct") is not None else "—"
        lignes += f"""<tr style='border-bottom:1px solid #eee;'>
          <td style='padding:8px 10px;font-weight:600;'>{v['nom']}</td>
          <td style='padding:8px 10px;text-align:center;font-weight:700;'>{v['score']}/{v['sur']}</td>
          <td style='padding:8px 10px;font-size:11px;'>{badges}</td>
          <td style='padding:8px 10px;text-align:right;'>{upside}</td>
        </tr>"""

    return f"""<html><body style='font-family:Arial,sans-serif;max-width:720px;margin:auto;padding:20px;color:#222;'>
<div style='background:linear-gradient(135deg,#1b5e20,#2e7d32);color:white;padding:16px 20px;border-radius:8px 8px 0 0;'>
  <h2 style='margin:0;font-size:18px;'>Screener Fondamental CAC40</h2>
  <p style='margin:6px 0 0;font-size:12px;opacity:0.9;'>{now.strftime('%d/%m/%Y')} — {len(valeurs)} valeurs analysées, filtre qualité simplifié (TTM)</p>
</div>
<div style='border:1px solid #ddd;border-top:none;padding:20px;border-radius:0 0 8px 8px;'>
  <div style='background:#e8f5e9;border-left:4px solid #2e7d32;padding:12px 16px;border-radius:6px;font-size:13px;'>
    <strong>Rappel :</strong> filtre de premier passage sur les 12 derniers mois (pas 5-10 ans comme la
    recherche manuelle du 01/11). Un score élevé = candidat à approfondir à la main, pas un signal d'achat.
    Aucun ordre automatique.
  </div>
  <h3 style='font-size:14px;margin:20px 0 8px;'>Top candidats (score qualité décroissant)</h3>
  <table style='width:100%;border-collapse:collapse;font-size:13px;'>
    <thead><tr style='background:#f5f5f5;'>
      <th style='padding:8px 10px;text-align:left;'>Valeur</th>
      <th style='padding:8px 10px;'>Score</th>
      <th style='padding:8px 10px;text-align:left;'>Détail</th>
      <th style='padding:8px 10px;text-align:right;'>Cible analystes</th>
    </tr></thead>
    <tbody>{lignes}</tbody>
  </table>
  <p style='margin-top:16px;font-size:11px;color:#999;'>
    ROE &gt;= 15%, FCF positif, marge brute &gt;= 15%, marge nette &gt;= 5%, couverture dette EBITDA/dette &gt;= 15%
    (exempté pour les banques), pas de dilution &gt;2%/mois (dès le 2e mois). "Cible analystes" = consensus
    Yahoo Finance, pas une valorisation indépendante.
  </p>
</div>
</body></html>"""


def envoyer(sujet, html):
    if not ZOHO_PASSWORD or not DESTINATAIRES:
        print("  Pas de mot de passe / destinataire — email non envoyé")
        return
    msg = MIMEMultipart("alternative")
    msg["Subject"], msg["From"], msg["To"] = sujet, ZOHO_EMAIL, ", ".join(DESTINATAIRES)
    msg.attach(MIMEText(html, "html", "utf-8"))
    with smtplib.SMTP("smtp.zoho.eu", 587) as s:
        s.starttls()
        s.login(ZOHO_EMAIL, ZOHO_PASSWORD)
        s.sendmail(ZOHO_EMAIL, DESTINATAIRES, msg.as_string())
    print(f"  Email envoyé à {', '.join(DESTINATAIRES)}")


if __name__ == "__main__":
    now = datetime.datetime.now(TZ_PARIS)
    print(f"Agent Screener Fondamental CAC40 — {now.date()} {now.strftime('%H:%M')} (Paris)")

    precedent = None
    if os.path.exists(FICHIER_RAPPORT):
        with open(FICHIER_RAPPORT, "r", encoding="utf-8") as f:
            precedent = json.load(f)

    valeurs = []
    for nom, ticker in CAC40.items():
        try:
            v = analyser_valeur(nom, ticker)
            valeurs.append(v)
        except Exception as e:
            print(f"  {nom} : indisponible ({e})")

    valeurs = ajouter_dilution(valeurs, precedent)
    valeurs.sort(key=lambda v: (v["score"], v.get("upside_cible_pct") or -999), reverse=True)
    top = [v for v in valeurs if v["sur"] >= 4][:12]

    print(f"{len(valeurs)} valeurs analysées, {len(top)} candidats retenus (score >= 4/6 ou 4/5)")
    for v in top[:5]:
        print(f"  {v['nom']:20} {v['score']}/{v['sur']}  upside analystes {v.get('upside_cible_pct')}")

    rapport = {
        "date": now.date().isoformat(),
        "n": len(valeurs),
        "top": [v["nom"] for v in top],
        "valeurs": valeurs,
    }
    with open(FICHIER_RAPPORT, "w", encoding="utf-8") as f:
        json.dump(rapport, f, ensure_ascii=False, indent=2)

    print("Envoi rapport mensuel...")
    html = generer_html(now, valeurs, top)
    envoyer(f"Screener Fondamental CAC40 — {len(top)} candidats — {now.strftime('%m/%Y')}", html)
    print("Terminé.")
