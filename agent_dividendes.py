#!/usr/bin/env python3
"""
Agent Dividendes PEA — le calendrier factuel des détachements CAC 40.

Quick win 100% factuel (aucun appel API payant, aucune décision de trading) :
  - Rendement 12 mois glissants de chaque valeur du CAC 40 (dividendes réellement
    versés sur les 12 derniers mois / cours actuel)
  - Détachements à venir sous ~5 semaines : date confirmée par Yahoo quand elle
    existe, sinon estimation par anniversaire (même période l'an dernier),
    clairement étiquetée comme telle
  - Dernier détachement passé (date + montant) pour chaque valeur

Contexte PEA : les dividendes y sont réinvestissables sans frottement fiscal
(pas de flat tax tant qu'on ne retire pas). Connaître le calendrier évite
aussi les mauvaises surprises : acheter la veille d'un détachement fait
mécaniquement baisser le cours du montant du dividende.

Tourne 1x/semaine (lundi matin). Info uniquement, ne touche à aucun score.
"""

import datetime
import json
import os
import smtplib
import zoneinfo
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import yfinance as yf

from marche_config import CAC40

TZ_PARIS = zoneinfo.ZoneInfo("Europe/Paris")

ZOHO_EMAIL    = os.environ.get("ZOHO_EMAIL", "Arnaud.kuntz@zoho.eu")
ZOHO_PASSWORD = os.environ.get("ZOHO_PASSWORD", "")
# Rapports d'info : destinataires fixes zoho + xtrem111 uniquement
# (même règle que Shadow/Évaluateur, décision Arnaud 02/07).
DESTINATAIRES = ["Arnaud.kuntz@zoho.eu", "xtrem111team@gmail.com"]

FICHIER_RAPPORT = "dividendes_rapport.json"

FENETRE_JOURS = 35  # horizon "détachements à venir"


def analyser_valeur(nom, ticker, aujourd_hui):
    """Dividendes 12 mois, dernier détachement, prochain détachement (confirmé ou estimé)."""
    t = yf.Ticker(ticker)
    divs = t.dividends
    if divs is None or divs.empty:
        return None
    divs.index = divs.index.tz_localize(None)

    hist = t.history(period="5d")["Close"].dropna()
    if hist.empty:
        return None
    cours = float(hist.iloc[-1])

    un_an = aujourd_hui - datetime.timedelta(days=365)
    divs_12m = divs[divs.index >= str(un_an)]
    total_12m = round(float(divs_12m.sum()), 2)
    rendement = round(total_12m / cours * 100, 2) if cours else None

    dernier_date    = divs.index[-1].date()
    dernier_montant = round(float(divs.iloc[-1]), 2)

    # Prochain détachement : date Yahoo si publiée, sinon anniversaire N-1
    prochain = None
    try:
        cal = t.calendar
        ex_div = (cal or {}).get("Ex-Dividend Date")
        if ex_div:
            d = ex_div if isinstance(ex_div, datetime.date) else ex_div.date()
            if aujourd_hui <= d <= aujourd_hui + datetime.timedelta(days=FENETRE_JOURS):
                prochain = {"date": d.isoformat(), "montant": None, "source": "confirmé (Yahoo)"}
    except Exception:
        pass
    if prochain is None:
        # Anniversaires : les détachements des 3 dernières années projetés sur l'année en cours
        for ts in divs.index[-8:]:
            for delta_ans in (1, 2, 3):
                try:
                    d = ts.date().replace(year=ts.year + delta_ans)
                except ValueError:  # 29 février
                    d = ts.date().replace(year=ts.year + delta_ans, day=28)
                if aujourd_hui <= d <= aujourd_hui + datetime.timedelta(days=FENETRE_JOURS):
                    prochain = {"date": d.isoformat(), "montant": round(float(divs[ts]), 2),
                                "source": f"estimé (anniversaire {ts.year})"}
                    break
            if prochain:
                break

    return {
        "nom":             nom,
        "ticker":          ticker,
        "cours":           round(cours, 2),
        "div_12m":         total_12m,
        "rendement_12m":   rendement,
        "dernier_date":    dernier_date.isoformat(),
        "dernier_montant": dernier_montant,
        "prochain":        prochain,
    }


def generer_html(now, valeurs, a_venir):
    lignes_venir = ""
    for v in a_venir:
        p = v["prochain"]
        montant = f"{p['montant']:.2f}€" if p.get("montant") else "montant non publié"
        rdt_detach = (f" ({p['montant'] / v['cours'] * 100:.1f}% du cours)"
                      if p.get("montant") and v.get("cours") else "")
        lignes_venir += (
            f"<tr style='border-top:1px solid #eee;'>"
            f"<td style='padding:6px 10px;font-weight:600;'>{v['nom']}</td>"
            f"<td style='padding:6px 10px;'>{p['date'][8:10]}/{p['date'][5:7]}</td>"
            f"<td style='padding:6px 10px;text-align:right;'>{montant}{rdt_detach}</td>"
            f"<td style='padding:6px 10px;font-size:11px;color:#999;'>{p['source']}</td></tr>"
        )
    bloc_venir = (f"""
  <h3 style='font-size:14px;margin:20px 0 8px;'>Détachements sous ~5 semaines</h3>
  <table style='width:100%;border-collapse:collapse;font-size:13px;'>
    <thead><tr style='background:#f5f5f5;'>
      <th style='padding:6px 10px;text-align:left;'>Valeur</th>
      <th style='padding:6px 10px;text-align:left;'>Date</th>
      <th style='padding:6px 10px;text-align:right;'>Montant</th>
      <th style='padding:6px 10px;text-align:left;'>Fiabilité</th>
    </tr></thead><tbody>{lignes_venir}</tbody></table>
  <p style='margin:4px 0 0;font-size:11px;color:#999;'>Rappel : le cours baisse mécaniquement du montant
    du dividende le jour du détachement. Acheter juste avant ne "gagne" rien.</p>"""
                  if lignes_venir else
                  "<p style='margin:16px 0 0;font-size:13px;color:#666;'>Aucun détachement identifié sous ~5 semaines.</p>")

    lignes_rdt = ""
    for v in valeurs[:15]:
        lignes_rdt += (
            f"<tr style='border-top:1px solid #eee;'>"
            f"<td style='padding:5px 10px;font-weight:600;'>{v['nom']}</td>"
            f"<td style='padding:5px 10px;text-align:right;color:#2e7d32;font-weight:600;'>{v['rendement_12m']:.2f}%</td>"
            f"<td style='padding:5px 10px;text-align:right;'>{v['div_12m']:.2f}€</td>"
            f"<td style='padding:5px 10px;text-align:right;color:#888;'>{v['cours']:.2f}€</td>"
            f"<td style='padding:5px 10px;color:#888;'>{v['dernier_date'][8:10]}/{v['dernier_date'][5:7]}/{v['dernier_date'][2:4]} ({v['dernier_montant']:.2f}€)</td></tr>"
        )

    return f"""<html><body style='font-family:Arial,sans-serif;max-width:680px;margin:auto;padding:20px;color:#222;'>
<div style='background:linear-gradient(135deg,#4527a0,#5e35b1);color:white;padding:16px 20px;border-radius:8px 8px 0 0;'>
  <h2 style='margin:0;font-size:18px;'>Agent Dividendes PEA — calendrier CAC 40</h2>
  <p style='margin:6px 0 0;font-size:12px;opacity:0.9;'>{now.strftime('%d/%m/%Y')} — dividendes réellement versés sur 12 mois, calendrier à ~5 semaines</p>
</div>
<div style='border:1px solid #ddd;border-top:none;padding:20px;border-radius:0 0 8px 8px;'>
  {bloc_venir}
  <h3 style='font-size:14px;margin:20px 0 8px;'>Top 15 rendements 12 mois glissants</h3>
  <table style='width:100%;border-collapse:collapse;font-size:13px;'>
    <thead><tr style='background:#f5f5f5;'>
      <th style='padding:5px 10px;text-align:left;'>Valeur</th>
      <th style='padding:5px 10px;text-align:right;'>Rendement</th>
      <th style='padding:5px 10px;text-align:right;'>Div. 12m</th>
      <th style='padding:5px 10px;text-align:right;'>Cours</th>
      <th style='padding:5px 10px;text-align:left;'>Dernier détachement</th>
    </tr></thead><tbody>{lignes_rdt}</tbody></table>
  <p style='margin-top:16px;font-size:12px;color:#999;'>
    100% factuel (historique Yahoo Finance), aucun signal de trading : un gros rendement peut signaler
    une valeur en difficulté (cours effondré), pas une bonne affaire. Dans le PEA, les dividendes
    sont réinvestissables sans fiscalité tant qu'il n'y a pas de retrait.
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
    aujourd_hui = now.date()
    print(f"Agent Dividendes PEA — {aujourd_hui} {now.strftime('%H:%M')} (Paris)")

    valeurs = []
    for nom, ticker in CAC40.items():
        try:
            v = analyser_valeur(nom, ticker, aujourd_hui)
            if v and v["rendement_12m"]:
                valeurs.append(v)
        except Exception as e:
            print(f"  {nom} : indisponible ({e})")
    valeurs.sort(key=lambda v: v["rendement_12m"], reverse=True)

    a_venir = sorted([v for v in valeurs if v["prochain"]],
                     key=lambda v: v["prochain"]["date"])
    print(f"{len(valeurs)} valeurs analysées, {len(a_venir)} détachements sous {FENETRE_JOURS} jours")

    rapport = {
        "date":    aujourd_hui.isoformat(),
        "n":       len(valeurs),
        "a_venir": [{"nom": v["nom"], **v["prochain"]} for v in a_venir],
        "valeurs": valeurs,
    }
    with open(FICHIER_RAPPORT, "w", encoding="utf-8") as f:
        json.dump(rapport, f, ensure_ascii=False, indent=2)

    print("Envoi rapport hebdo...")
    html = generer_html(now, valeurs, a_venir)
    envoyer(f"Dividendes PEA — calendrier CAC 40 — {now.strftime('%d/%m/%Y')}", html)
    print("Terminé.")
