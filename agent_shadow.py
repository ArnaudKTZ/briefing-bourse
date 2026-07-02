#!/usr/bin/env python3
"""
Agent Shadow — le contrefactuel honnête.

Principe : depuis le 02/07/2026, les alertes email achat/vente sont suspendues
(modèle non validé). Mais elles continuent d'être détectées et journalisées
dans shadow_alertes.json. Cet agent rejoue chaque semaine ce qu'elles auraient
donné si on les avait suivies : achat 2000€ au cours de l'alerte, frais
Boursobank inclus (0,5% min 0,50€ à l'achat ET à la vente), sortie mesurée à
J+1, J+3 et J+5 jours de bourse, comparée au CAC 40 sur la même fenêtre.

Le verdict est factuel, pas une opinion : "les alertes auraient rapporté X%
net de frais, contre Y% pour le CAC". C'est la base de la décision du 02/08
(réactiver, prolonger la suspension, ou ajuster le modèle).

Tourne 1x/semaine (vendredi soir, après clôture). Pas d'appel API payant.
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
ZOHO_SMTP     = "smtp.zoho.eu"
ZOHO_PORT     = 587
# Rapports de mesure : destinataires fixes zoho + xtrem111 uniquement
# (décision Arnaud 02/07, indépendant du secret DESTINATAIRES_HEBDO).
DESTINATAIRES = ["Arnaud.kuntz@zoho.eu", "xtrem111team@gmail.com"]

FICHIER_SHADOW  = "shadow_alertes.json"
FICHIER_RAPPORT = "shadow_rapport.json"

BUDGET   = 2000.0   # même hypothèse que le portefeuille virtuel
FRAIS_TAUX    = 0.005
FRAIS_MINIMUM = 0.50
HORIZONS = [1, 3, 5]   # jours de bourse après l'alerte


def calculer_frais(montant):
    return round(max(FRAIS_MINIMUM, montant * FRAIS_TAUX), 2)


def prix_ok(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and x == x  # x==x filtre NaN


def charger_alertes():
    if not os.path.exists(FICHIER_SHADOW):
        return []
    with open(FICHIER_SHADOW, "r", encoding="utf-8") as f:
        return json.load(f)


def dedupe_achats(alertes):
    """Garde une seule alerte ACHETER par valeur et par jour (la première :
    c'est celle sur laquelle on aurait agi)."""
    vues = set()
    achats = []
    for a in sorted(alertes, key=lambda x: (x.get("date", ""), x.get("heure", ""))):
        if a.get("signal") != "ACHETER" or not prix_ok(a.get("cours")):
            continue
        cle = (a["date"], a["nom"])
        if cle in vues:
            continue
        vues.add(cle)
        achats.append(a)
    return achats


def closes_apres(hist_close, date_str, n):
    """Clôture du n-ième jour de bourse strictement après date_str, ou None."""
    dates = [d.strftime("%Y-%m-%d") for d in hist_close.index]
    apres = [i for i, d in enumerate(dates) if d > date_str]
    if len(apres) < n:
        return None
    return float(hist_close.iloc[apres[n - 1]])


def evaluer_alerte(a, hist_close, cac_close):
    """Simule l'achat de BUDGET€ au cours de l'alerte, sortie à chaque horizon.
    Retourne {horizon: {"pnl_net": %, "cac": %}} + "encours" (dernier cours)."""
    cours_entree = a["cours"]
    nb = int(BUDGET / cours_entree)
    if nb <= 0:
        return None
    cout        = nb * cours_entree
    frais_achat = calculer_frais(cout)
    invest      = cout + frais_achat

    # Référence CAC au jour de l'alerte : dernière clôture <= date d'alerte
    dates_cac = [d.strftime("%Y-%m-%d") for d in cac_close.index]
    avant = [i for i, d in enumerate(dates_cac) if d <= a["date"]]
    cac_ref = float(cac_close.iloc[avant[-1]]) if avant else None

    res = {}
    for h in HORIZONS:
        px = closes_apres(hist_close, a["date"], h)
        if px is None or not prix_ok(px):
            res[f"J+{h}"] = None
            continue
        valeur      = nb * px
        frais_vente = calculer_frais(valeur)
        pnl_net     = round((valeur - frais_vente - invest) / invest * 100, 2)
        cac_h = closes_apres(cac_close, a["date"], h)
        cac_pct = round((cac_h / cac_ref - 1) * 100, 2) if (cac_h and cac_ref) else None
        res[f"J+{h}"] = {"pnl_net": pnl_net, "cac": cac_pct}

    # Valorisation au dernier cours connu (position toujours "ouverte")
    px_dernier = float(hist_close.iloc[-1])
    if prix_ok(px_dernier):
        valeur      = nb * px_dernier
        frais_vente = calculer_frais(valeur)
        res["encours"] = round((valeur - frais_vente - invest) / invest * 100, 2)
    return res


def agreger(evaluations):
    """Stats par horizon : n, % gagnants, moyenne nette, moyenne CAC, edge."""
    stats = {}
    for h in [f"J+{n}" for n in HORIZONS]:
        pnls = [e["res"][h]["pnl_net"] for e in evaluations
                if e["res"].get(h) and e["res"][h]["pnl_net"] is not None]
        cacs = [e["res"][h]["cac"] for e in evaluations
                if e["res"].get(h) and e["res"][h].get("cac") is not None]
        if not pnls:
            stats[h] = None
            continue
        moy  = round(sum(pnls) / len(pnls), 2)
        moyc = round(sum(cacs) / len(cacs), 2) if cacs else None
        stats[h] = {
            "n":         len(pnls),
            "gagnants_pct": round(sum(1 for p in pnls if p > 0) / len(pnls) * 100, 1),
            "moyenne_nette": moy,
            "cac_moyen":  moyc,
            "edge":       round(moy - moyc, 2) if moyc is not None else None,
        }
    return stats


def verdict(stats):
    """Verdict factuel basé sur J+5 (l'horizon le plus proche de la durée de
    détention réelle du satellite), avec garde-fou sur la taille d'échantillon."""
    s = stats.get("J+5") or stats.get("J+3") or stats.get("J+1")
    if not s:
        return "—", "Aucune alerte évaluable pour l'instant (il faut au moins 1 jour de bourse après l'alerte)."
    if s["n"] < 10:
        return "—", f"Seulement {s['n']} alertes évaluables : trop peu pour conclure, on continue d'accumuler."
    if s["edge"] is not None and s["edge"] > 0.3 and s["gagnants_pct"] > 55:
        return "UTILES", (f"Les alertes battent le CAC de {s['edge']:+.2f} pts net de frais "
                          f"({s['gagnants_pct']}% gagnantes sur {s['n']}). Réactivation défendable.")
    if s["edge"] is not None and s["edge"] < -0.3:
        return "NUISIBLES", (f"Les alertes font {s['edge']:+.2f} pts SOUS le CAC net de frais "
                             f"sur {s['n']} cas. Les suivre aurait détruit de la valeur.")
    return "NEUTRES", (f"Ni edge ni contre-performance nets ({s['edge']:+.2f} pts vs CAC, "
                       f"{s['gagnants_pct']}% gagnantes sur {s['n']}). La suspension ne coûte rien.")


def generer_html(now, achats, evaluations, stats, verdict_label, verdict_txt, en_attente):
    couleur = {"UTILES": "#2e7d32", "NUISIBLES": "#b71c1c", "NEUTRES": "#e65100", "—": "#757575"}[verdict_label]

    lignes_stats = ""
    for h, s in stats.items():
        if not s:
            lignes_stats += f"""<tr style='border-bottom:1px solid #eee;'>
              <td style='padding:8px 10px;font-weight:600;'>{h}</td>
              <td colspan='4' style='padding:8px 10px;color:#999;'>pas encore de données</td></tr>"""
            continue
        c = "#2e7d32" if s["moyenne_nette"] > 0 else "#c62828"
        ce = "#2e7d32" if (s["edge"] or 0) > 0 else "#c62828"
        lignes_stats += f"""<tr style='border-bottom:1px solid #eee;'>
          <td style='padding:8px 10px;font-weight:600;'>{h}</td>
          <td style='padding:8px 10px;text-align:center;'>{s['n']}</td>
          <td style='padding:8px 10px;text-align:center;'>{s['gagnants_pct']}%</td>
          <td style='padding:8px 10px;text-align:right;color:{c};font-weight:600;'>{s['moyenne_nette']:+.2f}%</td>
          <td style='padding:8px 10px;text-align:right;color:{ce};font-weight:600;'>{'' if s['edge'] is None else format(s['edge'], '+.2f') + ' pts'}</td>
        </tr>"""

    lignes_detail = ""
    for e in sorted(evaluations, key=lambda x: x["alerte"]["date"], reverse=True)[:15]:
        a, r = e["alerte"], e["res"]
        j5 = r.get("J+5")
        val = f"{j5['pnl_net']:+.2f}%" if j5 else (f"{r.get('encours', 0):+.2f}% (en cours)" if "encours" in r else "—")
        c = "#2e7d32" if (j5 and j5["pnl_net"] > 0) or (not j5 and r.get("encours", 0) > 0) else "#c62828"
        lignes_detail += f"""<tr style='border-bottom:1px solid #f0f0f0;'>
          <td style='padding:6px 10px;font-size:12px;'>{a['date']}</td>
          <td style='padding:6px 10px;font-size:12px;font-weight:500;'>{a['nom']}</td>
          <td style='padding:6px 10px;font-size:12px;text-align:center;'>{a.get('score', '—')}</td>
          <td style='padding:6px 10px;font-size:12px;text-align:right;'>{a['cours']}€</td>
          <td style='padding:6px 10px;font-size:12px;text-align:right;color:{c};font-weight:600;'>{val}</td>
        </tr>"""

    return f"""<html><body style='font-family:Arial,sans-serif;max-width:680px;margin:auto;padding:20px;color:#222;'>
<div style='background:linear-gradient(135deg,#37474f,#546e7a);color:white;padding:16px 20px;border-radius:8px 8px 0 0;'>
  <h2 style='margin:0;font-size:18px;'>Agent Shadow — le contrefactuel des alertes</h2>
  <p style='margin:6px 0 0;font-size:12px;opacity:0.9;'>{now.strftime('%d/%m/%Y')} — alertes suspendues depuis le 02/07, mesurées quand même</p>
</div>
<div style='border:1px solid #ddd;border-top:none;padding:20px;border-radius:0 0 8px 8px;'>
  <div style='background:{couleur}11;border-left:4px solid {couleur};padding:14px 16px;border-radius:6px;'>
    <p style='margin:0;font-weight:700;color:{couleur};'>Verdict : {verdict_label}</p>
    <p style='margin:8px 0 0;font-size:14px;'>{verdict_txt}</p>
  </div>
  <h3 style='font-size:14px;margin:20px 0 8px;'>Si on avait suivi chaque alerte ACHETER (2000€, frais Boursobank inclus)</h3>
  <table style='width:100%;border-collapse:collapse;font-size:13px;'>
    <thead><tr style='background:#f5f5f5;'>
      <th style='padding:8px 10px;text-align:left;'>Sortie</th>
      <th style='padding:8px 10px;'>N</th>
      <th style='padding:8px 10px;'>Gagnantes</th>
      <th style='padding:8px 10px;text-align:right;'>Moy. nette</th>
      <th style='padding:8px 10px;text-align:right;'>vs CAC</th>
    </tr></thead>
    <tbody>{lignes_stats}</tbody>
  </table>
  <h3 style='font-size:14px;margin:20px 0 8px;'>Dernières alertes ({len(achats)} au total, {en_attente} trop récentes pour J+5)</h3>
  <table style='width:100%;border-collapse:collapse;'>
    <thead><tr style='background:#f5f5f5;font-size:12px;'>
      <th style='padding:6px 10px;text-align:left;'>Date</th>
      <th style='padding:6px 10px;text-align:left;'>Valeur</th>
      <th style='padding:6px 10px;'>Score</th>
      <th style='padding:6px 10px;text-align:right;'>Entrée</th>
      <th style='padding:6px 10px;text-align:right;'>P&L J+5 net</th>
    </tr></thead>
    <tbody>{lignes_detail}</tbody>
  </table>
  <p style='margin-top:16px;font-size:12px;color:#999;'>
    Hypothèse : achat 2000€ au cours de l'alerte, revente à la clôture de J+N, frais 0,5% min 0,50€
    à l'achat et à la vente. Une alerte par valeur et par jour (la première). Décision de réactivation : ~02/08.
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
    with smtplib.SMTP(ZOHO_SMTP, ZOHO_PORT) as s:
        s.starttls()
        s.login(ZOHO_EMAIL, ZOHO_PASSWORD)
        s.sendmail(ZOHO_EMAIL, DESTINATAIRES, msg.as_string())
    print(f"  Email envoyé à {', '.join(DESTINATAIRES)}")


if __name__ == "__main__":
    now = datetime.datetime.now(TZ_PARIS)
    print(f"Agent Shadow — {now.date()} {now.strftime('%H:%M')} (Paris)")

    alertes = charger_alertes()
    achats  = dedupe_achats(alertes)
    print(f"{len(alertes)} alertes journalisées, {len(achats)} achats uniques à évaluer")

    # Un seul fetch par valeur distincte + le CAC
    print("Récupération des cours...")
    noms = sorted({a["nom"] for a in achats if a["nom"] in CAC40})
    hists = {}
    for nom in noms:
        try:
            h = yf.Ticker(CAC40[nom]).history(period="3mo")["Close"].dropna()
            if not h.empty:
                hists[nom] = h
        except Exception as e:
            print(f"  {nom} : données indisponibles ({e})")
    cac_close = yf.Ticker("^FCHI").history(period="3mo")["Close"].dropna()

    evaluations = []
    en_attente  = 0
    for a in achats:
        h = hists.get(a["nom"])
        if h is None:
            continue
        res = evaluer_alerte(a, h, cac_close)
        if res is None:
            continue
        if all(res.get(f"J+{n}") is None for n in HORIZONS):
            en_attente += 1
        evaluations.append({"alerte": a, "res": res})

    stats = agreger(evaluations)
    verdict_label, verdict_txt = verdict(stats)

    print(f"Verdict : {verdict_label} — {verdict_txt}")
    for h, s in stats.items():
        if s:
            print(f"  {h} : n={s['n']}, {s['gagnants_pct']}% gagnantes, "
                  f"moy {s['moyenne_nette']:+.2f}%, edge vs CAC {s['edge']}")

    rapport = {
        "date":         now.date().isoformat(),
        "n_alertes":    len(alertes),
        "n_achats":     len(achats),
        "en_attente":   en_attente,
        "stats":        stats,
        "verdict":      verdict_label,
        "verdict_txt":  verdict_txt,
    }
    with open(FICHIER_RAPPORT, "w", encoding="utf-8") as f:
        json.dump(rapport, f, ensure_ascii=False, indent=2)

    print("Envoi rapport hebdo...")
    html = generer_html(now, achats, evaluations, stats, verdict_label, verdict_txt, en_attente)
    envoyer(f"Shadow — les alertes suspendues auraient été {verdict_label} — {now.strftime('%d/%m/%Y')}", html)

    print("Terminé.")
