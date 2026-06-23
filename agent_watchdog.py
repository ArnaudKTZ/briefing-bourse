#!/usr/bin/env python3
"""
Agent Watchdog — surveille que les autres agents ont bien tourné.
Tourne à 7h30 et vérifie :
- Le briefing du matin a bien été envoyé (commit Performance update du jour)
- L'agent news a bien tourné (rapport_news.json du jour)
- Les scores intraday sont bien sauvegardés
Si un agent est silencieux, envoie une alerte email immédiate.
"""

import datetime
import json
import os
import smtplib
import subprocess
import urllib.request
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

ZOHO_EMAIL    = os.environ.get("ZOHO_EMAIL", "Arnaud.kuntz@zoho.eu")
ZOHO_PASSWORD = os.environ.get("ZOHO_PASSWORD", "")
ZOHO_SMTP     = "smtp.zoho.eu"
ZOHO_PORT     = 587
DESTINATAIRE  = os.environ.get("DESTINATAIRE_PRINCIPAL", "")

FICHIER_RAPPORT_NEWS  = "rapport_news.json"
FICHIER_INTRADAY      = "intraday_scores.json"
FICHIER_PERFORMANCE   = "performance.json"
FICHIER_WATCHDOG_LOG  = "watchdog_log.json"


def charger_json(fichier):
    if os.path.exists(fichier):
        with open(fichier, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def sauvegarder_log(log):
    with open(FICHIER_WATCHDOG_LOG, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)


def verifier_agent_news():
    """Vérifie que rapport_news.json a été produit aujourd'hui."""
    today = datetime.date.today().isoformat()
    data  = charger_json(FICHIER_RAPPORT_NEWS)
    if not data:
        return False, "rapport_news.json introuvable"
    date_rapport = data.get("date", "")
    if date_rapport != today:
        return False, f"rapport_news.json date du {date_rapport} (attendu {today})"
    nb = data.get("marche", {}).get("nb_articles", 0)
    return True, f"OK — {nb} articles, sentiment {data.get('marche',{}).get('sentiment_global',0):+.2f}"


def verifier_briefing():
    """
    Vérifie que le briefing a tourné aujourd'hui en lisant performance.json.
    Le briefing écrit une entrée dans recommandations avec la date du jour.
    """
    today = datetime.date.today().isoformat()
    data  = charger_json(FICHIER_PERFORMANCE)
    if not data:
        return False, "performance.json introuvable"

    # Cherche une recommandation datée d'aujourd'hui
    recos = data.get("recommandations", {})
    recos_today = [k for k in recos if k.startswith(today)]
    if recos_today:
        return True, f"OK — {len(recos_today)} recommandations enregistrées"

    # Fallback : vérifie la date du dernier run dans stats
    derniere_date = data.get("derniere_execution", "")
    if derniere_date == today:
        return True, "OK — dernière exécution aujourd'hui"

    return False, f"Aucune trace du briefing pour {today}"


def verifier_intraday_hier():
    """
    Vérifie que le scoring intraday a bien tourné hier
    (utile si le watchdog tourne le matin avant le premier intraday).
    """
    hier  = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    data  = charger_json(FICHIER_INTRADAY)
    if not data:
        return None, "intraday_scores.json introuvable"
    if hier in data:
        nb_heures = len(data[hier])
        return True, f"OK hier — {nb_heures} snapshot(s) enregistré(s)"
    # Vendredi = pas de données le week-end, on ignore
    if datetime.date.today().weekday() == 0:
        return None, "Lundi — pas de données intraday attendues hier"
    return False, f"Aucun scoring intraday pour hier ({hier})"


def envoyer_alerte_watchdog(problemes, statuts):
    if not ZOHO_PASSWORD:
        print("  Pas de mot de passe ZOHO — alerte non envoyée")
        return

    today = datetime.date.today().strftime("%d/%m/%Y")
    heure = datetime.datetime.now().strftime("%H:%M")

    lignes_html = ""
    for agent, (ok, msg) in statuts.items():
        if ok is None:
            couleur, icone = "#757575", "—"
        elif ok:
            couleur, icone = "#2e7d32", "✓"
        else:
            couleur, icone = "#b71c1c", "✗"
        lignes_html += f"""
        <tr style='border-bottom:1px solid #eee;'>
          <td style='padding:10px;font-weight:bold;'>{agent}</td>
          <td style='padding:10px;text-align:center;'>
            <span style='color:{couleur};font-size:16px;font-weight:bold;'>{icone}</span>
          </td>
          <td style='padding:10px;font-size:13px;color:#555;'>{msg}</td>
        </tr>"""

    html = f"""<html><body style='font-family:Arial,sans-serif;max-width:700px;margin:auto;padding:20px;'>
<div style='background:#e65100;color:white;padding:16px 20px;border-radius:8px 8px 0 0;'>
  <h2 style='margin:0;font-size:17px;'>WATCHDOG — Anomalie détectée</h2>
  <p style='margin:6px 0 0;font-size:12px;opacity:0.9;'>{today} à {heure}</p>
</div>
<div style='border:1px solid #ddd;border-top:none;padding:20px;border-radius:0 0 8px 8px;'>
  <p style='color:#b71c1c;font-weight:bold;'>
    {len(problemes)} agent(s) silencieux détecté(s) : {', '.join(problemes)}
  </p>
  <table style='width:100%;border-collapse:collapse;font-size:14px;margin-top:10px;'>
    <thead>
      <tr style='background:#f5f5f5;'>
        <th style='padding:10px;text-align:left;'>Agent</th>
        <th style='padding:10px;text-align:center;'>Statut</th>
        <th style='padding:10px;text-align:left;'>Détail</th>
      </tr>
    </thead>
    <tbody>{lignes_html}</tbody>
  </table>
  <div style='margin-top:16px;padding:12px;background:#fff8e1;border-radius:6px;'>
    <p style='margin:0;font-size:13px;color:#e65100;font-weight:bold;'>Action recommandée :</p>
    <p style='margin:6px 0 0;font-size:13px;color:#555;'>
      Aller sur GitHub → Actions → relancer manuellement le workflow concerné.
    </p>
  </div>
  <p style='margin-top:12px;font-size:11px;color:#999;'>Watchdog Agent — surveillance automatique</p>
</div>
</body></html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"WATCHDOG — {len(problemes)} agent(s) en anomalie — {today}"
    msg["From"]    = ZOHO_EMAIL
    msg["To"]      = DESTINATAIRE
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        with smtplib.SMTP(ZOHO_SMTP, ZOHO_PORT) as serveur:
            serveur.starttls()
            serveur.login(ZOHO_EMAIL, ZOHO_PASSWORD)
            serveur.sendmail(ZOHO_EMAIL, [DESTINATAIRE], msg.as_string())
        print(f"  Alerte watchdog envoyée à {DESTINATAIRE}")
    except Exception as e:
        print(f"  Erreur envoi alerte : {e}")


if __name__ == "__main__":
    today = datetime.date.today().isoformat()
    heure = datetime.datetime.now().strftime("%H:%M")
    print(f"Watchdog — {today} {heure}")

    statuts = {}

    print("Vérification Agent News...")
    ok, msg = verifier_agent_news()
    statuts["Agent News"] = (ok, msg)
    print(f"  {'OK' if ok else 'ECHEC'} : {msg}")

    print("Vérification Briefing matin...")
    ok, msg = verifier_briefing()
    statuts["Briefing 7h"] = (ok, msg)
    print(f"  {'OK' if ok else 'ECHEC'} : {msg}")

    print("Vérification Scoring intraday (hier)...")
    ok, msg = verifier_intraday_hier()
    statuts["Scoring intraday"] = (ok, msg)
    print(f"  {'OK' if ok else ('IGNORÉ' if ok is None else 'ECHEC')} : {msg}")

    # Problèmes = agents qui ont échoué (ok=False, pas None)
    problemes = [agent for agent, (ok, _) in statuts.items() if ok is False]

    # Sauvegarde du log
    log = {
        "date":      today,
        "heure":     heure,
        "statuts":   {k: {"ok": v[0], "msg": v[1]} for k, v in statuts.items()},
        "problemes": problemes,
    }
    sauvegarder_log(log)

    if problemes:
        print(f"\n{len(problemes)} problème(s) détecté(s) : {problemes}")
        print("Envoi alerte email...")
        envoyer_alerte_watchdog(problemes, statuts)
    else:
        print("\nTous les agents sont OK.")

    print("Watchdog terminé.")
