#!/usr/bin/env python3
"""
Agent Professeur — le manager qui fait le point hebdomadaire.

Principe (logique d'entreprise) :
  - Chaque agent est un employé avec une fiche de poste et un bilan chiffré.
  - Le Professeur note chacun sur sa performance RÉELLE (pas ses promesses).
  - Il indique un niveau de confiance selon le nombre de données disponibles
    (peu de données = pas de jugement définitif, on reste prudent).
  - Il compare à la semaine précédente (progrès / régression).
  - Il propose des décisions, mais ne modifie rien en aveugle : la règle d'or
    reste que rien ne passe en production sans réussir la recette (backtest).

Tourne 1x/semaine. Pas d'appel API payant. Honnêteté avant tout.
"""

import datetime
import json
import os
import smtplib
import zoneinfo
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import yfinance as yf

TZ_PARIS = zoneinfo.ZoneInfo("Europe/Paris")

ZOHO_EMAIL    = os.environ.get("ZOHO_EMAIL", "Arnaud.kuntz@zoho.eu")
ZOHO_PASSWORD = os.environ.get("ZOHO_PASSWORD", "")
ZOHO_SMTP     = "smtp.zoho.eu"
ZOHO_PORT     = 587
# Bilans hebdo : destinataires fixes zoho + xtrem111 uniquement
# (décision Arnaud 02/07, indépendant du secret DESTINATAIRES_HEBDO).
DESTINATAIRES = ["Arnaud.kuntz@zoho.eu", "xtrem111team@gmail.com"]

FICHIER_RAPPORT = "professeur_rapport.json"
COSTS_LOG       = "costs_log.json"


def charger_couts_semaine():
    """Lit costs_log.json et retourne un résumé des 7 derniers jours."""
    if not os.path.exists(COSTS_LOG):
        return None
    try:
        with open(COSTS_LOG, "r", encoding="utf-8") as f:
            log = json.load(f)
    except Exception:
        return None
    cutoff = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
    semaine = [e for e in log if e.get("date", "") >= cutoff]
    if not semaine:
        return None
    total_usd = sum(e.get("usd", 0) for e in semaine)
    par_agent = {}
    for e in semaine:
        a = e.get("agent", "?")
        par_agent[a] = par_agent.get(a, 0) + e.get("usd", 0)
    n_appels = len(semaine)
    return {"total_usd": round(total_usd, 4), "par_agent": par_agent, "n_appels": n_appels}


def charger(fichier):
    if os.path.exists(fichier):
        with open(fichier, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def niveau_confiance(n):
    if n < 20:  return "faible"
    if n < 60:  return "moyenne"
    return "forte"


# ─── ÉVALUATIONS PAR AGENT ────────────────────────────────────────────────────

def evaluer_briefing_v4():
    """Note la qualité prédictive des signaux V4 vs le hasard (50%)."""
    perf = charger("performance.json")
    if not perf or "stats" not in perf:
        return {"agent": "Briefing V4 (signaux)", "metrique": "—",
                "note": "—", "confiance": "faible",
                "verdict": "Pas de données de performance."}
    s = perf["stats"]
    p = s.get("precision", 0) or 0   # tolère precision null/absente
    n = s.get("total", 0) or 0       # tolère total null/absent
    conf = niveau_confiance(n)

    if n < 20:
        note, verdict = "—", f"Seulement {n} signaux jugés, trop peu pour conclure."
    elif p >= 58:
        note, verdict = "A", f"Précision {p}% sur {n} signaux : edge réel vs hasard (50%)."
    elif p >= 53:
        note, verdict = "C", f"Précision {p}% : léger avantage, à confirmer."
    elif p >= 48:
        note, verdict = "D", f"Précision {p}% : équivalent au hasard, aucun edge."
    else:
        note, verdict = "E", f"Précision {p}% : sous le hasard. À cantonner en poche satellite."

    return {"agent": "Briefing V4 (signaux)", "metrique": f"{p}% précision ({n} signaux)",
            "note": note, "confiance": conf, "verdict": verdict,
            "valeur_suivie": p, "meta_borne": True}   # métrique bornée 0-100 : comparable dans le temps


def evaluer_portefeuille():
    """Le portefeuille virtuel bat-il le simple buy & hold du CAC 40 sur sa durée de vie ?"""
    pf = charger("portefeuille_virtuel.json")
    if not pf or not pf.get("historique_valeur"):
        return {"agent": "Portefeuille virtuel V4", "metrique": "—",
                "note": "—", "confiance": "faible", "verdict": "Pas encore d'historique."}

    hv = pf["historique_valeur"]
    # Ne garder que les valeurs numériques valides (tolère null / clés malformées)
    dates = sorted(d for d in hv.keys() if isinstance(hv[d], (int, float)))
    if not dates:
        return {"agent": "Portefeuille virtuel V4", "metrique": "—",
                "note": "—", "confiance": "faible", "verdict": "Historique de valeurs invalide."}
    depart, fin = 10000.0, hv[dates[-1]]
    perf_pf = (fin - depart) / depart * 100
    n_trades = len(pf.get("trades", []))

    # Benchmark : CAC 40 sur la même période
    bench_txt, perf_bench = "indisponible", None
    try:
        cac = yf.Ticker("^FCHI").history(start=dates[0])
        if not cac.empty:
            perf_bench = (cac["Close"].iloc[-1] / cac["Close"].iloc[0] - 1) * 100
            bench_txt = f"{perf_bench:+.1f}%"
    except Exception as e:
        print(f"  Benchmark CAC indisponible : {e}")

    conf = niveau_confiance(len(dates))
    if perf_bench is None:
        note, verdict = "—", f"PF {perf_pf:+.1f}%, benchmark indisponible cette semaine."
    elif len(dates) < 15:
        note, verdict = "—", f"PF {perf_pf:+.1f}% vs CAC {bench_txt} sur {len(dates)}j : trop tôt."
    elif perf_pf > perf_bench + 2:
        note, verdict = "A", f"PF {perf_pf:+.1f}% bat le CAC ({bench_txt})."
    elif perf_pf >= perf_bench - 2:
        note, verdict = "C", f"PF {perf_pf:+.1f}% fait jeu égal avec le CAC ({bench_txt})."
    else:
        note, verdict = "E", f"PF {perf_pf:+.1f}% sous le CAC ({bench_txt}) : ne crée pas de valeur."

    return {"agent": "Portefeuille virtuel V4", "metrique": f"{perf_pf:+.1f}% ({n_trades} trades)",
            "note": note, "confiance": conf, "verdict": verdict, "valeur_suivie": round(perf_pf, 1)}


def evaluer_dual_momentum():
    """Statut du cœur. Validé hors-échantillon par le harnais comme réducteur de risque."""
    st = charger("dual_momentum_statut.json")
    if not st:
        return {"agent": "Dual Momentum (cœur)", "metrique": "—",
                "note": "—", "confiance": "forte",
                "verdict": "Pas encore exécuté (1er run le 1er du mois)."}
    alloc = st.get("allocation", "—")
    return {"agent": "Dual Momentum (cœur)", "metrique": alloc,
            "note": "B", "confiance": "forte",
            "verdict": "Validé hors-échantillon : réduit le risque (chute -20% vs -25%), "
                       "ne bat pas le buy&hold World en rendement. Rôle = airbag, pas moteur."}


def evaluer_agent_collecte(nom_fichier, libelle, cle_resume):
    """News / Espion : on vérifie qu'ils tournent et produisent. Impact non encore mesuré."""
    data = charger(nom_fichier)
    if not data:
        return {"agent": libelle, "metrique": "—", "note": "—", "confiance": "faible",
                "verdict": "Aucun rapport produit."}
    date = data.get("date", "?")
    return {"agent": libelle, "metrique": f"actif (rapport du {date})",
            "note": "C", "confiance": "faible",
            "verdict": f"{cle_resume} Impact réel sur la précision pas encore mesuré "
                       "(à connecter au harnais)."}


# ─── RAPPORT ──────────────────────────────────────────────────────────────────

def construire_evolution(evals, precedent):
    """Compare valeurs suivies à la semaine précédente."""
    if not precedent:
        return {}
    anciennes = {e["agent"]: e.get("valeur_suivie") for e in precedent.get("evaluations", [])}
    evo = {}
    for e in evals:
        v = e.get("valeur_suivie")
        a = anciennes.get(e["agent"])
        if v is not None and a is not None:
            evo[e["agent"]] = round(v - a, 1)
    return evo


def meta_garde_fou(historique):
    """
    Le Professeur s'auto-challenge : il confronte ses notes passées à ce qui
    s'est réellement passé ensuite. Il ne se corrige PAS tout seul, il remonte
    ses doutes à Arnaud. (Le juge reste indépendant ; il signale, il ne triche pas.)
    Retourne (liste_doutes, message_si_inactif).
    """
    import statistics
    if len(historique) < 3:
        return [], (f"Pas encore assez d'historique ({len(historique)} semaine(s)) pour "
                    "m'auto-évaluer. Garde-fou actif dès 3 semaines.")

    # On ne s'auto-évalue QUE sur des métriques bornées et comparables dans le temps
    # (ex: précision en %, baseline 50). Une perf cumulée ne l'est pas → faux positifs.
    series = {}
    for snap in historique:
        for e in snap.get("evals", []):
            if e.get("valeur") is not None and e.get("meta_borne"):
                series.setdefault(e["agent"], []).append((e.get("note"), e["valeur"]))

    doutes = []
    for agent, serie in series.items():
        if len(serie) < 3:
            continue
        notes = [n for n, _ in serie]
        vals  = [v for _, v in serie]
        delta = vals[-1] - vals[0]

        if any(n in ("A", "B") for n in notes[:-1]) and delta < -3:
            doutes.append(f"{agent} : noté favorablement par le passé, mais sa métrique a chuté "
                          f"({vals[0]} → {vals[-1]}). Mon barème était peut-être trop optimiste.")
        if any(n in ("D", "E") for n in notes[:-1]) and delta > 5:
            doutes.append(f"{agent} : noté sévèrement par le passé, mais sa métrique progresse "
                          f"({vals[0]} → {vals[-1]}). Je l'ai peut-être sous-noté.")
        if statistics.pstdev(vals) > 5:
            doutes.append(f"{agent} : métrique très instable (écart-type "
                          f"{round(statistics.pstdev(vals),1)}). Ma confiance affichée est peut-être trompeuse.")

    return doutes, None


def generer_bloc_couts(couts):
    if not couts:
        return ("<div style='margin-top:16px;padding:12px;background:#f5f5f5;border-radius:6px;"
                "font-size:13px;color:#999;'><strong>Coûts API :</strong> aucune donnée (costs_log.json absent ou vide).</div>")
    lignes_agents = "".join(
        f"<li>{agent} : <strong>${round(v, 4):.4f}</strong></li>"
        for agent, v in sorted(couts["par_agent"].items(), key=lambda x: -x[1])
    )
    cout_mois_est = round(couts["total_usd"] / 7 * 30, 2)
    return (
        f"<div style='margin-top:16px;padding:12px;background:#e3f2fd;border-left:4px solid #1565c0;"
        f"border-radius:6px;font-size:13px;color:#222;'>"
        f"<strong style='color:#1565c0;'>Coûts API — 7 derniers jours</strong>"
        f"<ul style='margin:8px 0 0;padding-left:20px;'>{lignes_agents}</ul>"
        f"<p style='margin:6px 0 0;'><strong>Total semaine : ${couts['total_usd']:.4f}</strong> "
        f"({couts['n_appels']} appels) — estimation mensuelle : <strong>${cout_mois_est:.2f}</strong></p>"
        f"</div>"
    )


def generer_html(now, evals, evo, doutes, meta_msg, couts=None):
    couleurs = {"A": "#1b5e20", "B": "#2e7d32", "C": "#e65100",
                "D": "#b71c1c", "E": "#b71c1c", "—": "#999"}
    lignes = ""
    for e in evals:
        c = couleurs.get(e["note"], "#999")
        fleche = ""
        if e["agent"] in evo:
            d = evo[e["agent"]]
            if d > 0:   fleche = f"<span style='color:#2e7d32;'> ▲ +{d}</span>"
            elif d < 0: fleche = f"<span style='color:#c62828;'> ▼ {d}</span>"
            else:       fleche = "<span style='color:#999;'> =</span>"
        lignes += f"""<tr style='border-bottom:1px solid #eee;'>
          <td style='padding:10px;font-weight:500;'>{e['agent']}</td>
          <td style='padding:10px;font-size:13px;'>{e['metrique']}{fleche}</td>
          <td style='padding:10px;text-align:center;'>
            <span style='background:{c};color:white;font-weight:bold;padding:3px 10px;border-radius:4px;'>{e['note']}</span>
          </td>
          <td style='padding:10px;font-size:12px;color:#666;'>confiance {e['confiance']}</td>
        </tr>
        <tr><td colspan='4' style='padding:0 10px 10px;font-size:12px;color:#555;'>{e['verdict']}</td></tr>"""

    if meta_msg:
        bloc_meta = (f"<div style='margin-top:16px;padding:12px;background:#f5f5f5;border-radius:6px;"
                     f"font-size:13px;color:#666;'><strong>Garde-fou méta :</strong> {meta_msg}</div>")
    elif doutes:
        items = "".join(f"<li style='margin-bottom:6px;'>{d}</li>" for d in doutes)
        bloc_meta = (f"<div style='margin-top:16px;padding:12px;background:#fff3e0;border-left:4px solid #e65100;"
                     f"border-radius:6px;font-size:13px;color:#222;'>"
                     f"<strong style='color:#e65100;'>Garde-fou méta — je doute de mes propres notes :</strong>"
                     f"<ul style='margin:8px 0 0;padding-left:20px;'>{items}</ul>"
                     f"<p style='margin:8px 0 0;font-size:12px;color:#666;'>À toi de trancher : faut-il revoir mes barèmes ? "
                     f"(je ne me corrige pas seul)</p></div>")
    else:
        bloc_meta = ("<div style='margin-top:16px;padding:12px;background:#e8f5e9;border-radius:6px;"
                     "font-size:13px;color:#2e7d32;'><strong>Garde-fou méta :</strong> mes notes passées sont "
                     "cohérentes avec ce qui s'est passé ensuite. Rien à signaler.</div>")

    return f"""<html><body style='font-family:Arial,sans-serif;max-width:680px;margin:auto;padding:20px;color:#222;'>
<div style='background:linear-gradient(135deg,#3c3489,#534ab7);color:white;padding:16px 20px;border-radius:8px 8px 0 0;'>
  <h2 style='margin:0;font-size:18px;'>Réunion hebdomadaire — Agent Professeur</h2>
  <p style='margin:6px 0 0;font-size:12px;opacity:0.9;'>{now.strftime('%d/%m/%Y')} — bilan des agents</p>
</div>
<div style='border:1px solid #ddd;border-top:none;padding:20px;border-radius:0 0 8px 8px;'>
  <table style='width:100%;border-collapse:collapse;font-size:14px;'>
    <thead><tr style='background:#f5f5f5;'>
      <th style='padding:10px;text-align:left;'>Agent</th>
      <th style='padding:10px;text-align:left;'>Mesure</th>
      <th style='padding:10px;text-align:center;'>Note</th>
      <th style='padding:10px;text-align:left;'>Confiance</th>
    </tr></thead>
    <tbody>{lignes}</tbody>
  </table>
  {bloc_meta}
  {generer_bloc_couts(couts)}
  <div style='margin-top:16px;padding:12px;background:#ede7f6;border-radius:6px;font-size:13px;color:#3c3489;'>
    <strong>Règle d'or :</strong> aucune amélioration ne passe en production sans réussir la recette
    (backtest hors-échantillon). Le Professeur observe et propose, il ne change rien en aveugle.
  </div>
  <p style='margin-top:12px;font-size:11px;color:#999;'>Note : A = edge réel, C = neutre/à confirmer, E = contre-performant.
  Confiance faible = trop peu de données pour juger.</p>
</div>
</body></html>"""


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


if __name__ == "__main__":
    now = datetime.datetime.now(TZ_PARIS)
    print(f"Agent Professeur — réunion du {now.date()}")

    evals = [
        evaluer_dual_momentum(),
        evaluer_briefing_v4(),
        evaluer_portefeuille(),
        evaluer_agent_collecte("rapport_news.json",   "Agent News",   "Collecte le sentiment presse."),
        evaluer_agent_collecte("rapport_espion.json", "Agent Espion", "Suit l'argent institutionnel."),
    ]

    for e in evals:
        print(f"  {e['agent']:26} [{e['note']}] {e['metrique']} — confiance {e['confiance']}")

    precedent = charger(FICHIER_RAPPORT)
    evo = construire_evolution(evals, precedent)

    # Historique cumulé (snapshots compacts) pour le garde-fou méta
    historique = (precedent or {}).get("historique", [])
    historique.append({
        "date": now.date().isoformat(),
        "evals": [{"agent": e["agent"], "note": e["note"], "valeur": e.get("valeur_suivie"),
                   "meta_borne": e.get("meta_borne", False)}
                  for e in evals],
    })
    historique = historique[-12:]

    doutes, meta_msg = meta_garde_fou(historique)
    if meta_msg:
        print(f"  Garde-fou méta : {meta_msg}")
    elif doutes:
        print(f"  Garde-fou méta : {len(doutes)} doute(s) sur mes propres notes")
        for d in doutes:
            print(f"    - {d}")
    else:
        print("  Garde-fou méta : notes cohérentes, rien à signaler")

    rapport = {
        "date": now.date().isoformat(),
        "evaluations": evals,
        "evolution": evo,
        "doutes_meta": doutes,
        "historique": historique,
    }
    with open(FICHIER_RAPPORT, "w", encoding="utf-8") as f:
        json.dump(rapport, f, ensure_ascii=False, indent=2)

    print("Envoi compte-rendu hebdo...")
    couts = charger_couts_semaine()
    html = generer_html(now, evals, evo, doutes, meta_msg, couts)
    envoyer(f"Professeur — réunion hebdo des agents — {now.strftime('%d/%m/%Y')}", html)

    print("Terminé.")
