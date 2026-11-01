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
import zoneinfo
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from lookahead_guard import auditer_usage_fondamentaux

TZ_PARIS = zoneinfo.ZoneInfo("Europe/Paris")

ZOHO_EMAIL    = os.environ.get("ZOHO_EMAIL", "Arnaud.kuntz@zoho.eu")
ZOHO_PASSWORD = os.environ.get("ZOHO_PASSWORD", "")
ZOHO_SMTP     = "smtp.zoho.eu"
ZOHO_PORT     = 587
DESTINATAIRE  = os.environ.get("DESTINATAIRE_PRINCIPAL", "")

FICHIER_RAPPORT_NEWS    = "rapport_news.json"
FICHIER_INTRADAY        = "intraday_scores.json"
FICHIER_PERFORMANCE     = "performance.json"
FICHIER_WATCHDOG_LOG    = "watchdog_log.json"
FICHIER_PORTEFEUILLE    = "portefeuille_virtuel.json"
FICHIER_DERNIER_BRIEFING = "dernier_briefing.json"


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
    today = datetime.datetime.now(TZ_PARIS).date().isoformat()
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
    Vérifie que le briefing a tourné aujourd'hui en lisant dernier_briefing.json.
    """
    today = datetime.datetime.now(TZ_PARIS).date().isoformat()
    data  = charger_json(FICHIER_DERNIER_BRIEFING)
    if not data:
        return False, "dernier_briefing.json introuvable"
    date_briefing = data.get("date", "")
    if date_briefing == today:
        heure = data.get("heure", "?")
        return True, f"OK — briefing du jour envoyé à {heure}"
    return False, f"Aucune trace du briefing pour {today} (dernier : {date_briefing})"


def verifier_intraday_hier():
    """
    Vérifie que le scoring intraday a bien tourné hier
    (utile si le watchdog tourne le matin avant le premier intraday).
    """
    hier  = (datetime.datetime.now(TZ_PARIS).date() - datetime.timedelta(days=1)).isoformat()
    data  = charger_json(FICHIER_INTRADAY)
    if not data:
        return None, "intraday_scores.json introuvable"
    if hier in data:
        nb_heures = len(data[hier])
        return True, f"OK hier — {nb_heures} snapshot(s) enregistré(s)"
    # Vendredi = pas de données le week-end, on ignore
    if datetime.datetime.now(TZ_PARIS).date().weekday() == 0:
        return None, "Lundi — pas de données intraday attendues hier"
    return False, f"Aucun scoring intraday pour hier ({hier})"


# Vérification d'invariant (ajout du 01/11) : le Watchdog ne surveillait que
# la PLOMBERIE (agents silencieux), jamais la LOGIQUE. Le bug du circuit-
# breaker (câblé dans scoring_intraday.py le 11/10, oublié dans
# briefing_bourse_v3.py, 4 positions pleine taille ouvertes sous -25% de
# drawdown entre le 12 et le 16/10, découvert seulement le 29/10 par audit
# manuel) est resté invisible 18 jours parce que rien ne vérifiait en continu
# que la règle elle-même était respectée. Ce check rejoue, pour chaque trade
# ouvert depuis le déploiement du circuit-breaker, le calcul de drawdown qui
# AURAIT DÛ s'appliquer, et compare à la taille réellement observée (déduite
# des frais, 0,5%/côté). Il ne corrige rien, il alerte.
DATE_DEPLOIEMENT_CIRCUIT_BREAKER = "2026-10-11"
FENETRE_VERIFICATION_JOURS = 3   # ne re-signale pas indéfiniment un incident déjà vu et corrigé
SEUIL_REDUCTION_DD = -15.0
SEUIL_STOP_DD       = -25.0


def _taille_approx(frais_total):
    """Reconstruit la taille de position à partir des frais (achat + vente,
    0,5%/côté) : frais_total / 0.01 ≈ taille d'origine, à ±quelques % près
    (arrondi au nombre entier d'actions)."""
    if not frais_total:
        return None
    return frais_total / 0.01


def verifier_circuit_breaker_satellite():
    """Pour chaque trade satellite ouvert depuis le 11/10, vérifie que la
    taille réellement utilisée correspond au palier de drawdown attendu à la
    date d'ouverture (plein tarif / réduit à 1000€ / aucune ouverture)."""
    pf = charger_json(FICHIER_PORTEFEUILLE)
    if not pf:
        return None, "portefeuille_virtuel.json introuvable"

    hv = pf.get("historique_valeur", {})
    hv_valides = {k: v for k, v in hv.items() if isinstance(v, (int, float)) and v == v}
    if not hv_valides:
        return None, "historique_valeur vide, rien à vérifier"
    dates_triees = sorted(hv_valides)

    def drawdown_avant(date_cible):
        """Drawdown connu à la veille de date_cible (dernier point < date_cible)."""
        anterieurs = [d for d in dates_triees if d < date_cible]
        if not anterieurs:
            return None
        pic = max(hv_valides[d] for d in dates_triees if d <= anterieurs[-1])
        valeur = hv_valides[anterieurs[-1]]
        return (valeur - pic) / pic * 100 if pic > 0 else 0.0

    today = datetime.datetime.now(TZ_PARIS).date()
    borne_recente = max(
        DATE_DEPLOIEMENT_CIRCUIT_BREAKER,
        (today - datetime.timedelta(days=FENETRE_VERIFICATION_JOURS)).isoformat(),
    )

    violations = []
    trades_verifies = 0
    for t in pf.get("trades", []):
        # Fenêtre glissante récente seulement : un incident déjà détecté et
        # corrigé ne doit pas re-déclencher une alerte à chaque run, pour
        # toujours. Passé la fenêtre, il appartient à l'historique (HISTORY.md).
        if t.get("date_entree", "") < borne_recente:
            continue
        dd = drawdown_avant(t["date_entree"])
        if dd is None:
            continue
        trades_verifies += 1
        taille = _taille_approx(t.get("frais_total"))

        if dd <= SEUIL_STOP_DD:
            violations.append(
                f"{t['nom']} ouvert le {t['date_entree']} à {taille:.0f}€ "
                f"alors que le drawdown était {dd:.1f}% (<= {SEUIL_STOP_DD}%, "
                f"AUCUNE ouverture attendue)")
        elif dd <= SEUIL_REDUCTION_DD and taille and taille > 1300:
            violations.append(
                f"{t['nom']} ouvert le {t['date_entree']} à {taille:.0f}€ "
                f"(taille pleine) alors que le drawdown était {dd:.1f}% "
                f"(<= {SEUIL_REDUCTION_DD}%, taille réduite ~1000€ attendue)")

    if violations:
        return False, f"{len(violations)} violation(s) sur {trades_verifies} trade(s) vérifié(s) : " + " | ".join(violations[:3])
    return True, f"OK — {trades_verifies} trade(s) vérifié(s) depuis le {DATE_DEPLOIEMENT_CIRCUIT_BREAKER}, aucune violation"


def verifier_lookahead():
    """Sentinelle Look-Ahead (ajout du 01/11) : un nouveau script qui touche
    des données fondamentales/consensus sans être recensé dans le registre
    de lookahead_guard.py est signalé, plutôt que silencieusement considéré
    sûr. Ne bloque rien, alerte seulement."""
    resultats = auditer_usage_fondamentaux()
    non_verifies = [f for f, v in resultats.items() if v.startswith("À VÉRIFIER")]
    if non_verifies:
        return False, f"{len(non_verifies)} fichier(s) non audité(s) touchent des données fondamentales/consensus : {non_verifies}"
    return True, f"OK — {len(resultats)} fichier(s) utilisant des données fondamentales/consensus, tous vérifiés sûrs"


# Agents hebdo et mensuels (ajout du 18/07 : la panne du cron Dividendes était
# passée inaperçue une semaine, découverte par hasard le 13/07). Hebdo : alerte
# si le dernier rapport a plus de max_age_jours. Mensuel : alerte si aucun run
# ce mois-ci une fois le jour attendu passé (+ tolérance en jours).
SURVEILLANCE_PERIODIQUE = [
    ("Dividendes (lundi 8h05)",   "dividendes_rapport.json",   {"max_age_jours": 8}),
    ("Shadow (vendredi 18h35)",   "shadow_rapport.json",       {"max_age_jours": 8}),
    ("Évaluateur (samedi 7h35)",  "evaluateur_rapport.json",   {"max_age_jours": 8}),
    ("Veille (samedi 9h)",        "veille_rapport.json",       {"max_age_jours": 8}),
    ("Professeur (dimanche 18h)", "professeur_rapport.json",   {"max_age_jours": 8}),
    ("Dual Momentum (1er, 8h)",   "dual_momentum_statut.json", {"jour_du_mois": 1, "tolerance": 2}),
    ("Crypto DM (1er, 8h15)",     "crypto_dm_etat.json",       {"jour_du_mois": 1, "tolerance": 2}),
    ("Stratège (le 4, 18h)",      "stratege_rapport.json",     {"jour_du_mois": 4, "tolerance": 2}),
]


def verifier_periodique(fichier, cadence):
    """Statut (ok, msg) d'un agent hebdo/mensuel d'après la date de son rapport.
    ok=None = pas encore exigible (affiché sans alerte)."""
    data = charger_json(fichier)
    if not data:
        return False, f"{fichier} introuvable"
    date_str = data.get("date", "")
    try:
        d = datetime.date.fromisoformat(date_str)
    except (ValueError, TypeError):
        return False, f"date illisible dans {fichier} : '{date_str}'"
    today = datetime.datetime.now(TZ_PARIS).date()
    age = (today - d).days

    if "max_age_jours" in cadence:
        if age <= cadence["max_age_jours"]:
            return True, f"OK — dernier rapport le {date_str} (il y a {age} j)"
        return False, f"dernier rapport le {date_str} (il y a {age} j, cadence hebdo dépassée)"

    jour_attendu = cadence["jour_du_mois"]
    if today.day < jour_attendu + cadence.get("tolerance", 2):
        return None, f"pas encore exigible ce mois-ci (dernier : {date_str})"
    if (d.year, d.month) == (today.year, today.month):
        return True, f"OK — run mensuel du {date_str}"
    return False, f"aucun run ce mois-ci (attendu le {jour_attendu}, dernier : {date_str})"


def envoyer_alerte_watchdog(problemes, statuts):
    if not ZOHO_PASSWORD:
        print("  Pas de mot de passe ZOHO — alerte non envoyée")
        return

    now   = datetime.datetime.now(TZ_PARIS)
    today = now.strftime("%d/%m/%Y")
    heure = now.strftime("%H:%M")

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
    now   = datetime.datetime.now(TZ_PARIS)
    today = now.date().isoformat()
    heure = now.strftime("%H:%M")
    print(f"Watchdog — {today} {heure} (heure Paris)")

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

    print("Vérification cohérence circuit-breaker satellite...")
    ok, msg = verifier_circuit_breaker_satellite()
    statuts["Circuit-breaker satellite"] = (ok, msg)
    print(f"  {'OK' if ok else ('IGNORÉ' if ok is None else 'ECHEC')} : {msg}")

    print("Vérification Sentinelle Look-Ahead...")
    ok, msg = verifier_lookahead()
    statuts["Sentinelle Look-Ahead"] = (ok, msg)
    print(f"  {'OK' if ok else 'ECHEC'} : {msg}")

    print("Vérification agents hebdo/mensuels...")
    for libelle, fichier, cadence in SURVEILLANCE_PERIODIQUE:
        ok, msg = verifier_periodique(fichier, cadence)
        statuts[libelle] = (ok, msg)
        print(f"  {'OK' if ok else ('IGNORÉ' if ok is None else 'ECHEC')} [{libelle}] : {msg}")

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
