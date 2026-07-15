#!/usr/bin/env python3
"""
Agent Stratège ("Loup de Wall Street") — l'adjoint d'Arnaud.

Créé le 15/07/2026 (décision Arnaud) après la recherche sur les méthodes des
grands traders (context/import/methodes_grands_traders.md). Une fois par mois :

  1. Lit l'état de TOUS les agents de la flotte (rapports JSON en local, zéro
     appel marché).
  2. Calcule en Python des FAITS déterministes (drawdowns, concentration du
     satellite, edge net, IC, coûts API...) : le LLM reçoit des faits, il n'en
     invente pas.
  3. Confronte le système aux 20 principes codifiés des grands traders
     (bibliothèque embarquée ci-dessous, source = le dossier de recherche).
  4. Produit une page de conseil + UNE SEULE proposition d'évolution priorisée,
     avec son protocole de test dans le harnais.

Gouvernance (non négociable) :
  - Le Stratège CONSEILLE, il ne modifie rien et ne prédit pas les marchés.
  - Il ne remplace pas le Professeur : le Professeur juge les résultats mesurés
    (juge à règles fixes), le Stratège conseille sur l'architecture (conseiller
    LLM). Les deux rapportent, Arnaud décide.
  - Rien de ce qu'il propose n'entre en prod sans passer la recette
    (backtest_harness.py). Le Stratège a le droit de rêver, la recette a le
    droit de veto.
  - Leçon CLQT (veille 04/07) : un LLM raconte bien et décide mal. Ici le LLM
    ne décide rien : il synthétise des faits calculés et cite des principes
    sourcés.

Coût : 1 appel Sonnet par mois (~1 centime). Tourne le 4 du mois à 18h Paris
(après les revues mensuelles DM et Crypto DM du 1er, pour les commenter).
"""

import datetime
import json
import os
import smtplib
import zoneinfo
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import anthropic

TZ_PARIS = zoneinfo.ZoneInfo("Europe/Paris")

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ZOHO_EMAIL    = os.environ.get("ZOHO_EMAIL", "Arnaud.kuntz@zoho.eu")
ZOHO_PASSWORD = os.environ.get("ZOHO_PASSWORD", "")
ZOHO_SMTP     = "smtp.zoho.eu"
ZOHO_PORT     = 587
# Rapport de gouvernance : destinataires fixes (décision Arnaud 02/07).
DESTINATAIRES = ["Arnaud.kuntz@zoho.eu", "xtrem111team@gmail.com"]

MODEL = "claude-sonnet-4-6"   # même modèle que le briefing (décision coûts 06/07)
FICHIER_RAPPORT = "stratege_rapport.json"

# ─── LA BIBLIOTHÈQUE : 20 principes des grands traders ────────────────────────
# Source complète et sourcée : context/import/methodes_grands_traders.md
# Le champ "statut" est l'audit du 15/07 ; le Stratège le réévalue à chaque
# réunion à partir des faits calculés et signale tout changement.

PRINCIPES = [
    {"id": "P1",  "titre": "Risque max 1-2% du capital par position (Turtles, PTJ, Kovner)", "statut_initial": "ABSENT"},
    {"id": "P2",  "titre": "Taille inversement proportionnelle à la volatilité (Turtles, unité N)", "statut_initial": "ABSENT"},
    {"id": "P3",  "titre": "Stop décidé AVANT l'entrée, jamais déplacé contre soi (Kovner)", "statut_initial": "PARTIEL"},
    {"id": "P4",  "titre": "Ne jamais moyenner une position perdante (PTJ : losers average losers)", "statut_initial": "OK"},
    {"id": "P5",  "titre": "Asymétrie gain/risque exigée à l'entrée, ratio >= 2 (PTJ 5:1, Minervini)", "statut_initial": "ABSENT"},
    {"id": "P6",  "titre": "Couper vite les pertes, laisser courir les gains (Seykota)", "statut_initial": "PARTIEL"},
    {"id": "P7",  "titre": "Filtre de régime : agressif seulement en marché confirmé (PTJ MM200, O'Neil)", "statut_initial": "PARTIEL"},
    {"id": "P8",  "titre": "Le cash est une position (PTJ)", "statut_initial": "OK"},
    {"id": "P9",  "titre": "Taille selon la conviction (Soros/Druckenmiller : courage d'être un cochon)", "statut_initial": "ABSENT"},
    {"id": "P10", "titre": "Pyramider les gagnants, jamais les perdants (Turtles, Livermore)", "statut_initial": "ABSENT"},
    {"id": "P11", "titre": "Limites d'exposition corrélée par secteur/direction (Turtles)", "statut_initial": "ABSENT"},
    {"id": "P12", "titre": "Frein après drawdown : réduire la voilure quand on perd (Druckenmiller)", "statut_initial": "ABSENT"},
    {"id": "P13", "titre": "Journal de bord + revue à froid systématique (tous)", "statut_initial": "OK"},
    {"id": "P14", "titre": "Système écrit, exécution mécanique, zéro discrétion (Turtles, leçon Livermore)", "statut_initial": "OK"},
    {"id": "P15", "titre": "Edge mesuré NET de frais avant de risquer (Simons : 50,75% suffisent)", "statut_initial": "OK"},
    {"id": "P16", "titre": "Edge lent = fréquence basse (AQR 1880-2016, Bouchaud)", "statut_initial": "OK"},
    {"id": "P17", "titre": "La méthode colle à la personnalité et aux contraintes (Schwager)", "statut_initial": "OK"},
    {"id": "P18", "titre": "Préservation du capital avant le rendement (Soros, Buffett règle n°1)", "statut_initial": "OK"},
    {"id": "P19", "titre": "Poche spéculative étanche, jamais le patrimoine entier (tous les survivants)", "statut_initial": "OK"},
    {"id": "P20", "titre": "Mesurer, pas raconter (Simons ; CLQT)", "statut_initial": "OK"},
]

# ─── COLLECTE DES FAITS (Python, déterministe) ────────────────────────────────

def charger(fichier):
    try:
        with open(fichier, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _valide(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and x == x


def drawdown_max(historique_valeur):
    """Pire chute % depuis un pic, sur un dict date -> valeur (NaN ignorés)."""
    if not historique_valeur:
        return None
    vals = [historique_valeur[d] for d in sorted(historique_valeur)
            if _valide(historique_valeur[d])]
    if not vals:
        return None
    pic, pire = vals[0], 0.0
    for v in vals:
        pic = max(pic, v)
        pire = min(pire, (v - pic) / pic * 100)
    return round(pire, 2)


def collecter_faits(now):
    """Tous les chiffres que le Stratège a le droit de citer. Rien d'autre."""
    faits = {
        "date_reunion": now.date().isoformat(),
        # Précision indispensable (le conseil du 15/07 avait cru à de l'argent
        # réel) : TOUS les portefeuilles du système sont VIRTUELS. Aucun euro
        # réel n'est engagé par les agents ; Arnaud passe ses ordres lui-même.
        "nature_portefeuilles": "TOUS VIRTUELS (paper trading). Aucun argent réel engagé par les agents.",
    }

    dm_st = charger("dual_momentum_statut.json") or {}
    dm_pf = charger("dual_momentum_portefeuille.json") or {}
    faits["coeur_dm"] = {
        "allocation":   dm_st.get("allocation"),
        "valeur":       dm_pf.get("valeur_actuelle"),
        "perf_pct":     dm_pf.get("perf_actuelle"),
        "drawdown_max": drawdown_max(dm_pf.get("historique_valeur")),
    }

    cr_etat = charger("crypto_dm_etat.json") or {}
    cr_pf   = charger("crypto_dm_portefeuille.json") or {}
    faits["crypto_dm"] = {
        "position":      cr_etat.get("position"),
        "valeur_usd":    cr_pf.get("valeur_actuelle"),
        "bh_btc_usd":    cr_pf.get("btc_bh_valeur"),
        "n_rotations":   cr_pf.get("n_rotations"),
        "drawdown_max":  drawdown_max(cr_pf.get("historique_valeur")),
    }

    pv = charger("portefeuille_virtuel.json") or {}
    positions = pv.get("positions", {})
    trades    = [t for t in pv.get("trades", []) if t.get("pnl_pct") is not None]
    gagnants  = [t for t in trades if t["pnl_pct"] > 0]
    hist      = pv.get("historique_valeur", {})
    dates_ok  = [d for d in hist if _valide(hist[d])]
    valeur_sat = hist[max(dates_ok)] if dates_ok else None
    faits["satellite_v4"] = {
        "valeur":            valeur_sat,
        "drawdown_max":      drawdown_max(hist),
        "positions_ouvertes": [
            {"nom": nom, "cout_eur": p.get("cout_total"), "date": p.get("date_entree")}
            for nom, p in positions.items()],
        "n_trades_clos":     len(trades),
        "pct_gagnants":      round(100 * len(gagnants) / len(trades)) if trades else None,
        "gain_moyen_pct":    round(sum(t["pnl_pct"] for t in gagnants) / len(gagnants), 2) if gagnants else None,
        "perte_moyenne_pct": round(sum(t["pnl_pct"] for t in trades if t["pnl_pct"] <= 0)
                                   / max(1, len(trades) - len(gagnants)), 2) if trades else None,
        "frais_cumules_eur": round(sum(t.get("frais_total", 0) for t in trades), 2),
        "taille_position":   "2000 EUR fixes, quelle que soit la volatilite (constat code)",
    }

    ev = charger("evaluateur_rapport.json") or {}
    j5 = (ev.get("horizons") or {}).get("J+5") or {}
    faits["evaluateur"] = {
        "date":            ev.get("date"),
        "n_obs":           ev.get("n_obs"),
        "edge_brut_j5":    (j5.get("acheter") or {}).get("edge"),
        "edge_net_j5":     (j5.get("acheter") or {}).get("edge_net"),
        "ic_j5":           (ev.get("ic_j5") or {}).get("ic_moyen"),
        "verdict":         ev.get("verdict"),
    }

    sh = charger("shadow_rapport.json") or {}
    faits["shadow"] = {"date": sh.get("date"), "verdict": sh.get("verdict"),
                       "edge_j5": ((sh.get("stats") or {}).get("J+5") or {}).get("edge")}

    pr = charger("professeur_rapport.json") or {}
    faits["professeur"] = [
        {"agent": e.get("agent"), "note": e.get("note"), "verdict": e.get("verdict")}
        for e in (pr.get("evaluations") or [])]

    dq = charger("data_quality_log.json") or []
    faits["data_quality_7_derniers"] = [
        {"date": e.get("date"), "nb_erreurs": e.get("nb_erreurs")} for e in dq[-7:]]

    cl = charger("costs_log.json") or []
    date_limite = (now.date() - datetime.timedelta(days=30)).isoformat()
    faits["cout_api_30j_usd"] = round(
        sum(e.get("usd", 0) for e in cl if e.get("date", "") >= date_limite), 3)

    return faits

# ─── L'APPEL AU CONSEILLER ────────────────────────────────────────────────────

SYSTEM_PROMPT = """Tu es l'Agent Stratège, l'adjoint d'Arnaud dans son système multi-agents
de gestion de portefeuille (cœur Dual Momentum actions, poche Crypto DM, satellite V4 en
observation, agents de mesure Shadow/Évaluateur/Professeur).

Ta mission mensuelle : confronter l'état RÉEL du système (les faits chiffrés fournis,
calculés en Python, tu ne peux en citer aucun autre) aux 20 principes codifiés des grands
traders (fournis avec leur statut au dernier audit).

Règles absolues :
- Tu CONSEILLES, tu ne prédis JAMAIS les marchés et tu ne recommandes JAMAIS d'acheter ou
  vendre quoi que ce soit. Ton domaine : l'architecture et la discipline du système.
- UNE SEULE proposition d'évolution par réunion, la plus rentable en réduction de risque
  ou en lucidité. Elle doit inclure son protocole de test (harnais backtest, walk-forward,
  frais inclus, ou mesure rétroactive sur les données existantes). Rien n'entre en prod
  sans passer la recette.
- Si un statut de principe a changé depuis l'audit (amélioration ou régression), signale-le.
- Honnêteté totale, zéro flatterie : Arnaud préfère une vérité dure à un compliment creux.
- Tutoie Arnaud. Français. Pas de tirets longs.

Format de sortie : UNIQUEMENT un fragment HTML (pas de balise html/head/body), avec cette
structure exacte :
<h3>Lecture du mois</h3> (un paragraphe : l'état du système en 4-5 phrases, les faits saillants)
<h3>Conformité aux principes des maîtres</h3> (une liste <ul> courte : uniquement les principes
dont le statut mérite commentaire ce mois-ci, avec le fait chiffré qui le justifie)
<h3>La proposition du mois</h3> (un paragraphe : LA proposition, pourquoi maintenant, et son
protocole de test précis)
<h3>Ce que dirait un maître</h3> (2-3 phrases : le regard qu'un des grands traders du dossier
porterait sur le mois écoulé, cité nommément, sans invention de citation)
Balises autorisées : h3, p, ul, li, strong, em. Aucune autre."""


def consulter_stratege(faits):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    contenu = (
        "FAITS DU MOIS (calculés en Python, seuls chiffres citables) :\n"
        + json.dumps(faits, ensure_ascii=False, indent=1)
        + "\n\nLES 20 PRINCIPES (statut au dernier audit du 15/07/2026) :\n"
        + json.dumps(PRINCIPES, ensure_ascii=False, indent=1)
        + "\n\nRédige ta page de conseil mensuelle."
    )
    message = client.messages.create(
        model=MODEL,
        max_tokens=2500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": contenu}],
    )
    _loguer_cout("stratege", MODEL, message.usage.input_tokens, message.usage.output_tokens)
    return message.content[0].text.strip()

# ─── COST LOGGING (même format que le briefing) ───────────────────────────────

COSTS_LOG = "costs_log.json"
TARIFS = {"claude-sonnet-4-6": {"input": 3.0, "output": 15.0}}

def _loguer_cout(agent, model, input_tokens, output_tokens):
    tarif = TARIFS.get(model, {"input": 5.0, "output": 25.0})
    cout_usd = (input_tokens * tarif["input"] + output_tokens * tarif["output"]) / 1_000_000
    log = []
    if os.path.exists(COSTS_LOG):
        try:
            with open(COSTS_LOG, "r", encoding="utf-8") as f:
                log = json.load(f)
        except Exception:
            log = []
    log.append({
        "date":   datetime.date.today().isoformat(),
        "heure":  datetime.datetime.now(TZ_PARIS).strftime("%H:%M"),
        "agent":  agent, "model": model,
        "input":  input_tokens, "output": output_tokens,
        "usd":    round(cout_usd, 6),
    })
    with open(COSTS_LOG, "w", encoding="utf-8") as f:
        json.dump(log[-500:], f, ensure_ascii=False, indent=2)
    print(f"  Coût API [{agent}] : {input_tokens} input / {output_tokens} output = ${cout_usd:.4f}")

# ─── EMAIL ────────────────────────────────────────────────────────────────────

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


def generer_html(now, conseil_html):
    return f"""<html><body style='font-family:Arial,sans-serif;max-width:680px;margin:auto;padding:20px;color:#222;'>
<div style='background:linear-gradient(135deg,#1a237e,#b8860b);color:white;padding:16px 20px;border-radius:8px 8px 0 0;'>
  <h2 style='margin:0;font-size:18px;'>Agent Stratège — conseil mensuel</h2>
  <p style='margin:6px 0 0;font-size:12px;opacity:0.9;'>{now.strftime('%d/%m/%Y')} — la flotte face aux principes des grands traders</p>
</div>
<div style='border:1px solid #ddd;border-top:none;padding:20px;border-radius:0 0 8px 8px;font-size:14px;line-height:1.55;'>
{conseil_html}
  <p style='margin-top:20px;font-size:11px;color:#999;'>
    Le Stratège conseille sur l'architecture et la discipline, il ne prédit pas les marchés
    et ne donne aucun signal d'achat/vente. Une proposition par mois, rien en prod sans
    passer la recette (harnais). Bibliothèque : context/import/methodes_grands_traders.md
    (20 principes sourcés : Schwager, Tudor Jones, Turtles, Soros/Druckenmiller, Simons, AQR).
    Le Professeur reste le juge des résultats ; le Stratège est le conseiller. Arnaud décide.
  </p>
</div>
</body></html>"""

# ─── MAIN ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    now = datetime.datetime.now(TZ_PARIS)
    print(f"Agent Stratège — réunion du {now.date()} {now.strftime('%H:%M')} (Paris)")

    print("Collecte des faits sur la flotte...")
    faits = collecter_faits(now)
    print(f"  Coût API 30j : ${faits['cout_api_30j_usd']}")

    if not ANTHROPIC_API_KEY:
        print("Pas de clé API — dry-run : faits collectés, pas de conseil généré.")
        print(json.dumps(faits, ensure_ascii=False, indent=1))
        raise SystemExit(0)

    print("Consultation du Stratège (1 appel Sonnet)...")
    try:
        conseil_html = consulter_stratege(faits)
    except anthropic.APIError as e:
        # Même philosophie que le briefing : échec visible, pas de crash CI.
        print(f"Échec API : {e}")
        envoyer(f"Stratège — ÉCHEC API — {now.strftime('%m/%Y')}",
                f"<p>La réunion mensuelle du Stratège a échoué : {e}</p>"
                "<p>Vérifier le crédit sur console.anthropic.com puis relancer le workflow stratege.yml.</p>")
        raise SystemExit(0)

    rapport = {
        "date":    now.date().isoformat(),
        "faits":   faits,
        "conseil": conseil_html,
    }
    with open(FICHIER_RAPPORT, "w", encoding="utf-8") as f:
        json.dump(rapport, f, ensure_ascii=False, indent=2)

    print("Envoi du conseil mensuel...")
    envoyer(f"Stratège — conseil mensuel — {now.strftime('%m/%Y')}",
            generer_html(now, conseil_html))
    print("Terminé.")
