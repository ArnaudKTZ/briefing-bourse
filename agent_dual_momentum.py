#!/usr/bin/env python3
"""
Agent Dual Momentum — le conseiller patrimonial mensuel.

Stratégie (hybride 50/50, validée par backtest sur 22 ans) :
  - 50% du capital reste TOUJOURS sur le World (buy & hold, le socle).
  - 50% tourne chaque mois selon le momentum :
      * compare World vs USA sur 12 mois
      * garde le meilleur s'il est en hausse (momentum absolu positif)
      * sinon, se met à l'abri en cash
      * ne change que si le challenger bat la position en cours de +3% (anti-whipsaw)

Tourne 1x par mois (1er du mois). Pas d'appel API payant.
Le cerveau calcule sur des données fiables longue histoire (CW8, ESE).
L'utilisateur achète les ETF équivalents de sa liste Boursobank PEA.
"""

import datetime
import json
import os
import smtplib
import sys
import zoneinfo
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import yfinance as yf

TZ_PARIS = zoneinfo.ZoneInfo("Europe/Paris")

ZOHO_EMAIL    = os.environ.get("ZOHO_EMAIL", "Arnaud.kuntz@zoho.eu")
ZOHO_PASSWORD = os.environ.get("ZOHO_PASSWORD", "")
ZOHO_SMTP     = "smtp.zoho.eu"
ZOHO_PORT     = 587
_dest_env     = os.environ.get("DESTINATAIRES", "")
DESTINATAIRES = [d.strip() for d in _dest_env.split(",") if d.strip()] if _dest_env else []

FICHIER_ETAT   = "dual_momentum_etat.json"
FICHIER_STATUT = "dual_momentum_statut.json"   # lu par le briefing V4 quotidien

LOOKBACK_MOIS = 12
BUFFER_SWITCH = 0.03   # +3% requis pour changer la poche rotative

# Univers de rotation. proxy = ticker fiable pour le CALCUL du momentum.
# etf_achat = ce que l'utilisateur achète réellement dans son PEA Boursobank.
UNIVERS = {
    "World": {"proxy": "CW8.PA",  "etf_achat": "Amundi MSCI World Screened"},
    "USA":   {"proxy": "ESE.PA",  "etf_achat": "Amundi MSCI USA Screened"},
}
SOCLE = "World"   # la moitié buy & hold permanente


def momentum_12m(ticker):
    """Rendement sur 12 mois (cours de fin de mois). Lève une exception si données absentes."""
    hist = yf.Ticker(ticker).history(period="14mo")
    if hist.empty or len(hist) < 200:
        raise RuntimeError(f"Données insuffisantes pour {ticker} ({len(hist)} lignes)")
    mensuel = hist["Close"].resample("ME").last().dropna()
    if len(mensuel) < LOOKBACK_MOIS + 1:
        raise RuntimeError(f"Pas assez de mois pour {ticker} ({len(mensuel)})")
    actuel = float(mensuel.iloc[-1])
    ref    = float(mensuel.iloc[-(LOOKBACK_MOIS + 1)])
    return round((actuel / ref - 1) * 100, 1), round(actuel, 2)


def charger_etat():
    if os.path.exists(FICHIER_ETAT):
        with open(FICHIER_ETAT, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"poche_rotative": None, "date": None, "historique": []}


def sauvegarder_etat(etat):
    with open(FICHIER_ETAT, "w", encoding="utf-8") as f:
        json.dump(etat, f, ensure_ascii=False, indent=2)


def decider_poche_rotative(momentums, position_actuelle):
    """
    momentums : {"World": (mom, cours), "USA": (mom, cours)}
    Retourne la cible de la poche rotative : "World", "USA" ou "Cash".
    """
    classement = sorted(momentums.items(), key=lambda x: x[1][0], reverse=True)
    meilleur, (mom_meilleur, _) = classement[0]

    # Momentum absolu : si le meilleur est négatif, on se met à l'abri
    if mom_meilleur <= 0:
        return "Cash"

    # Anti-whipsaw : on garde la position en cours si elle est encore positive
    # et que le challenger ne la bat pas d'au moins BUFFER_SWITCH
    if position_actuelle in momentums:
        mom_actuel = momentums[position_actuelle][0]
        if mom_actuel > 0 and mom_meilleur < mom_actuel + BUFFER_SWITCH * 100:
            return position_actuelle

    return meilleur


def construire_allocation(poche_rotative):
    """Combine le socle (50% World) et la poche rotative (50%) en allocation finale."""
    alloc = {SOCLE: 50.0}
    if poche_rotative == "Cash":
        alloc["Cash"] = alloc.get("Cash", 0) + 50.0
    else:
        alloc[poche_rotative] = alloc.get(poche_rotative, 0) + 50.0
    return alloc


def formater_alloc(alloc):
    parts = []
    for actif, pct in alloc.items():
        if actif == "Cash":
            parts.append(f"{pct:.0f}% liquidités")
        else:
            parts.append(f"{pct:.0f}% {UNIVERS[actif]['etf_achat']}")
    return " + ".join(parts)


def envoyer_email(sujet, html):
    if not ZOHO_PASSWORD or not DESTINATAIRES:
        print("  Pas de mot de passe / destinataire — email non envoyé")
        return
    msg = MIMEMultipart("alternative")
    msg["Subject"] = sujet
    msg["From"]    = ZOHO_EMAIL
    msg["To"]      = ", ".join(DESTINATAIRES)
    msg.attach(MIMEText(html, "html", "utf-8"))
    with smtplib.SMTP(ZOHO_SMTP, ZOHO_PORT) as serveur:
        serveur.starttls()
        serveur.login(ZOHO_EMAIL, ZOHO_PASSWORD)
        serveur.sendmail(ZOHO_EMAIL, DESTINATAIRES, msg.as_string())
    print(f"  Email envoyé à {', '.join(DESTINATAIRES)}")


def generer_html(now, momentums, ancienne, nouvelle, alloc_av, alloc_ap, action):
    couleur_action = "#b71c1c" if action == "BASCULE" else "#2e7d32"
    lignes_mom = ""
    for actif, (mom, cours) in momentums.items():
        c = "#2e7d32" if mom > 0 else "#c62828"
        lignes_mom += f"""<tr style='border-bottom:1px solid #eee;'>
          <td style='padding:8px 10px;font-weight:500;'>{UNIVERS[actif]['etf_achat']}</td>
          <td style='padding:8px 10px;text-align:right;color:{c};font-weight:600;'>{mom:+.1f}%</td>
        </tr>"""

    if action == "BASCULE":
        bloc_action = f"""<div style='background:#fff3e0;border-left:4px solid #e65100;padding:14px 16px;border-radius:6px;'>
          <p style='margin:0;font-weight:600;color:#e65100;'>Action ce mois-ci : bascule de la poche rotative</p>
          <p style='margin:8px 0 0;font-size:14px;'>Vends <strong>{ancienne}</strong>, achète <strong>{nouvelle}</strong>.</p>
        </div>"""
    else:
        bloc_action = f"""<div style='background:#e8f5e9;border-left:4px solid #2e7d32;padding:14px 16px;border-radius:6px;'>
          <p style='margin:0;font-weight:600;color:#2e7d32;'>Rien à faire ce mois-ci.</p>
          <p style='margin:8px 0 0;font-size:14px;'>La poche rotative reste sur <strong>{nouvelle}</strong>.</p>
        </div>"""

    return f"""<html><body style='font-family:Arial,sans-serif;max-width:640px;margin:auto;padding:20px;color:#222;'>
<div style='background:linear-gradient(135deg,#0f6e56,#1d9e75);color:white;padding:16px 20px;border-radius:8px 8px 0 0;'>
  <h2 style='margin:0;font-size:18px;'>Conseiller Dual Momentum — revue mensuelle</h2>
  <p style='margin:6px 0 0;font-size:12px;opacity:0.9;'>{now.strftime('%d/%m/%Y')} — cœur du patrimoine (hybride 50/50)</p>
</div>
<div style='border:1px solid #ddd;border-top:none;padding:20px;border-radius:0 0 8px 8px;'>
  {bloc_action}
  <h3 style='font-size:14px;margin:20px 0 8px;'>Allocation cible</h3>
  <p style='font-size:15px;margin:0;padding:10px 12px;background:#f5f5f5;border-radius:6px;'>{formater_alloc(alloc_ap)}</p>
  <h3 style='font-size:14px;margin:20px 0 8px;'>Momentum 12 mois</h3>
  <table style='width:100%;border-collapse:collapse;font-size:14px;'>
    <thead><tr style='background:#f5f5f5;'>
      <th style='padding:8px 10px;text-align:left;'>Actif</th>
      <th style='padding:8px 10px;text-align:right;'>Perf 12 mois</th>
    </tr></thead>
    <tbody>{lignes_mom}</tbody>
  </table>
  <p style='margin-top:16px;font-size:12px;color:#999;'>
    Règle : 50% toujours sur le World, 50% sur le meilleur momentum (ou cash si tout baisse).
    Revue le 1er de chaque mois. Ceci est une aide à la décision, tu restes maître de tes ordres.
  </p>
</div>
</body></html>"""


if __name__ == "__main__":
    now = datetime.datetime.now(TZ_PARIS)
    print(f"Agent Dual Momentum — {now.date()} {now.strftime('%H:%M')} (Paris)")

    print("Calcul des momentums 12 mois...")
    momentums = {}
    for actif, cfg in UNIVERS.items():
        mom, cours = momentum_12m(cfg["proxy"])
        momentums[actif] = (mom, cours)
        print(f"  {actif:6} ({cfg['proxy']}) : {mom:+.1f}% sur 12 mois")

    etat = charger_etat()
    ancienne_poche = etat.get("poche_rotative")

    nouvelle_poche = decider_poche_rotative(momentums, ancienne_poche)
    print(f"Poche rotative : {ancienne_poche} -> {nouvelle_poche}")

    action = "BASCULE" if (ancienne_poche is not None and nouvelle_poche != ancienne_poche) else "RIEN"

    alloc_avant = construire_allocation(ancienne_poche) if ancienne_poche else {}
    alloc_apres = construire_allocation(nouvelle_poche)

    def libelle(poche):
        if poche is None:   return "—"
        if poche == "Cash": return "liquidités"
        return UNIVERS[poche]["etf_achat"]

    # Mise à jour de l'état
    etat["poche_rotative"] = nouvelle_poche
    etat["date"] = now.date().isoformat()
    etat.setdefault("historique", []).append({
        "date": now.date().isoformat(),
        "poche": nouvelle_poche,
        "momentums": {k: v[0] for k, v in momentums.items()},
    })
    etat["historique"] = etat["historique"][-36:]
    sauvegarder_etat(etat)

    # Statut court pour le briefing quotidien V4
    statut = {
        "date": now.date().isoformat(),
        "allocation": formater_alloc(alloc_apres),
        "poche_rotative": nouvelle_poche,
        "momentums": {k: v[0] for k, v in momentums.items()},
        "derniere_action": action,
    }
    with open(FICHIER_STATUT, "w", encoding="utf-8") as f:
        json.dump(statut, f, ensure_ascii=False, indent=2)

    print(f"Allocation cible : {formater_alloc(alloc_apres)}")

    print("Envoi email mensuel...")
    sujet = (f"Dual Momentum — {'BASCULE ' + libelle(ancienne_poche) + ' vers ' + libelle(nouvelle_poche) if action == 'BASCULE' else 'rien a faire'} "
             f"— {now.strftime('%m/%Y')}")
    html = generer_html(now, momentums, libelle(ancienne_poche), libelle(nouvelle_poche),
                        alloc_avant, alloc_apres, action)
    envoyer_email(sujet, html)

    print("Terminé.")
