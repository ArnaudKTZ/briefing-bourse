#!/usr/bin/env python3
"""
Agent Évaluateur — la mesure multi-horizons honnête.

Problème résolu : la "précision" historique (hit-rate binaire à J+1 vs un
hasard supposé à 50%) juge mal des signaux techniques multi-jours. Si le CAC
monte 55% des jours, un ACHETER aveugle "réussit" 55% du temps : le vrai
benchmark n'est pas 50%, c'est le marché lui-même.

Ce que mesure cet agent, à partir de performance.json (90 jours de recos
horodatées avec prix d'entrée à 7h) :
  - Rendement moyen des ACHETER à J+1 / J+3 / J+5 / J+10 (clôtures réelles)
  - Comparé au rendement moyen de TOUT l'univers CAC 40 le même jour
    (= le edge réel, en points)
  - Idem pour les ÉVITER (on veut qu'ils fassent PIRE que l'univers)
  - Découpage par bucket de score (65-74 / 75-84 / 85+) : le score
    discrimine-t-il vraiment ?

Rétroactif : évalue tout l'historique disponible à chaque run, pas besoin
d'attendre. Tourne 1x/semaine (samedi matin). Pas d'appel API payant.
Sert de base au bilan du 22/07 et aux décisions du Professeur.
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
_dest_env     = os.environ.get("DESTINATAIRES_HEBDO", "")
DESTINATAIRES = ([d.strip() for d in _dest_env.split(",") if d.strip()]
                 or ["Arnaud.kuntz@zoho.eu", "xtrem111team@gmail.com"])

FICHIER_PERFORMANCE = "performance.json"
FICHIER_RAPPORT     = "evaluateur_rapport.json"

HORIZONS = [1, 3, 5, 10]
BUCKETS  = [(85, 100, "85+"), (75, 84, "75-84"), (65, 74, "65-74")]


def prix_ok(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and x == x


def charger_historique():
    if not os.path.exists(FICHIER_PERFORMANCE):
        return {}
    with open(FICHIER_PERFORMANCE, "r", encoding="utf-8") as f:
        return json.load(f).get("historique", {})


def charger_closes():
    """Une série de clôtures par valeur (6 mois couvre les 90 jours d'historique + J+10)."""
    closes = {}
    for nom, ticker in CAC40.items():
        try:
            h = yf.Ticker(ticker).history(period="6mo")["Close"].dropna()
            if not h.empty:
                closes[nom] = h
        except Exception as e:
            print(f"  {nom} : cours indisponibles ({e})")
    return closes


def close_apres(serie, date_str, n):
    """Clôture du n-ième jour de bourse strictement après date_str, ou None."""
    dates = [d.strftime("%Y-%m-%d") for d in serie.index]
    apres = [i for i, d in enumerate(dates) if d > date_str]
    if len(apres) < n:
        return None
    return float(serie.iloc[apres[n - 1]])


def rendements_forward(historique, closes):
    """Pour chaque reco de chaque jour : rendement % entre le prix stocké à 7h
    et la clôture de J+N. Retourne une liste plate d'observations."""
    obs = []
    for date, recos in sorted(historique.items()):
        for nom, d in recos.items():
            prix = d.get("prix")
            if not prix_ok(prix) or nom not in closes:
                continue
            rends = {}
            for h in HORIZONS:
                px = close_apres(closes[nom], date, h)
                rends[h] = round((px / prix - 1) * 100, 2) if (px and prix_ok(px)) else None
            obs.append({
                "date":   date,
                "nom":    nom,
                "signal": d.get("signal", "SURVEILLER"),
                "score":  d.get("score", 50),
                "rends":  rends,
            })
    return obs


def moyenne(vals):
    vals = [v for v in vals if v is not None]
    return round(sum(vals) / len(vals), 2) if vals else None


def stats_horizon(obs, h):
    """Edge des ACHETER et ÉVITER vs l'univers complet, à l'horizon h."""
    univers = [o["rends"][h] for o in obs]
    acheter = [o["rends"][h] for o in obs if o["signal"] == "ACHETER"]
    eviter  = [o["rends"][h] for o in obs if o["signal"] == "ÉVITER"]

    m_uni, m_ach, m_evi = moyenne(univers), moyenne(acheter), moyenne(eviter)
    n_ach = len([v for v in acheter if v is not None])
    n_evi = len([v for v in eviter if v is not None])
    if m_uni is None:
        return None
    return {
        "univers_moy":  m_uni,
        "acheter":      {"n": n_ach, "moy": m_ach,
                         "edge": round(m_ach - m_uni, 2) if m_ach is not None else None},
        # Pour ÉVITER, un edge POSITIF = les valeurs évitées font pire que l'univers = signal utile
        "eviter":       {"n": n_evi, "moy": m_evi,
                         "edge": round(m_uni - m_evi, 2) if m_evi is not None else None},
    }


def stats_buckets(obs, h):
    """Le score discrimine-t-il ? Rendement moyen par bucket de score ACHETER."""
    res = {}
    for lo, hi, label in BUCKETS:
        vals = [o["rends"][h] for o in obs
                if o["signal"] == "ACHETER" and lo <= o["score"] <= hi]
        vals = [v for v in vals if v is not None]
        res[label] = {"n": len(vals), "moy": moyenne(vals)}
    return res


def verdict(stats_h, buckets_j5):
    """Verdict factuel sur l'horizon le plus peuplé avec assez de recul (J+5, sinon J+3)."""
    for h in [5, 3, 1]:
        s = stats_h.get(h)
        if s and s["acheter"]["n"] >= 30:
            edge_a = s["acheter"]["edge"]
            edge_e = s["eviter"]["edge"]
            morceaux = []
            if edge_a is not None:
                if edge_a > 0.2:
                    morceaux.append(f"les ACHETER battent l'univers de {edge_a:+.2f} pts à J+{h}")
                elif edge_a < -0.2:
                    morceaux.append(f"les ACHETER font {edge_a:+.2f} pts SOUS l'univers à J+{h} : le signal détruit de la valeur")
                else:
                    morceaux.append(f"les ACHETER ne se distinguent pas de l'univers ({edge_a:+.2f} pts à J+{h})")
            if edge_e is not None:
                if edge_e > 0.2:
                    morceaux.append(f"les ÉVITER sont utiles ({edge_e:+.2f} pts évités)")
                elif edge_e < -0.2:
                    morceaux.append(f"les ÉVITER sont contre-productifs ({edge_e:+.2f} pts)")
                else:
                    morceaux.append("les ÉVITER sont neutres")
            # Monotonie des buckets : 85+ devrait battre 65-74
            b_haut, b_bas = buckets_j5.get("85+", {}), buckets_j5.get("65-74", {})
            if (b_haut.get("n", 0) >= 10 and b_bas.get("n", 0) >= 10
                    and b_haut.get("moy") is not None and b_bas.get("moy") is not None):
                if b_haut["moy"] > b_bas["moy"] + 0.2:
                    morceaux.append("le score discrimine (85+ bat 65-74)")
                else:
                    morceaux.append("le score ne discrimine PAS (85+ ne bat pas 65-74)")
            return f"Sur {s['acheter']['n']} ACHETER : " + " ; ".join(morceaux) + "."
    return "Pas encore assez d'observations avec recul suffisant (minimum 30 ACHETER à J+5). On accumule."


def generer_html(now, obs, stats_h, buckets_j5, verdict_txt):
    n_jours = len({o["date"] for o in obs})

    lignes = ""
    for h in HORIZONS:
        s = stats_h.get(h)
        if not s:
            lignes += f"""<tr style='border-bottom:1px solid #eee;'>
              <td style='padding:8px 10px;font-weight:600;'>J+{h}</td>
              <td colspan='5' style='padding:8px 10px;color:#999;'>pas encore de données</td></tr>"""
            continue
        ea, ee = s["acheter"]["edge"], s["eviter"]["edge"]
        ca = "#2e7d32" if (ea or 0) > 0 else "#c62828"
        ce = "#2e7d32" if (ee or 0) > 0 else "#c62828"
        lignes += f"""<tr style='border-bottom:1px solid #eee;'>
          <td style='padding:8px 10px;font-weight:600;'>J+{h}</td>
          <td style='padding:8px 10px;text-align:right;'>{s['univers_moy']:+.2f}%</td>
          <td style='padding:8px 10px;text-align:right;'>{'' if s['acheter']['moy'] is None else format(s['acheter']['moy'], '+.2f') + '%'} <span style='color:#999;font-size:11px;'>(n={s['acheter']['n']})</span></td>
          <td style='padding:8px 10px;text-align:right;color:{ca};font-weight:700;'>{'' if ea is None else format(ea, '+.2f') + ' pts'}</td>
          <td style='padding:8px 10px;text-align:right;'>{'' if s['eviter']['moy'] is None else format(s['eviter']['moy'], '+.2f') + '%'} <span style='color:#999;font-size:11px;'>(n={s['eviter']['n']})</span></td>
          <td style='padding:8px 10px;text-align:right;color:{ce};font-weight:700;'>{'' if ee is None else format(ee, '+.2f') + ' pts'}</td>
        </tr>"""

    lignes_buckets = ""
    for label in ["85+", "75-84", "65-74"]:
        b = buckets_j5.get(label, {})
        m = b.get("moy")
        c = "#2e7d32" if (m or 0) > 0 else "#c62828"
        lignes_buckets += f"""<tr style='border-bottom:1px solid #eee;'>
          <td style='padding:8px 10px;font-weight:600;'>Score {label}</td>
          <td style='padding:8px 10px;text-align:center;'>{b.get('n', 0)}</td>
          <td style='padding:8px 10px;text-align:right;color:{c};font-weight:600;'>{'—' if m is None else format(m, '+.2f') + '%'}</td>
        </tr>"""

    return f"""<html><body style='font-family:Arial,sans-serif;max-width:680px;margin:auto;padding:20px;color:#222;'>
<div style='background:linear-gradient(135deg,#00695c,#00897b);color:white;padding:16px 20px;border-radius:8px 8px 0 0;'>
  <h2 style='margin:0;font-size:18px;'>Agent Évaluateur — mesure multi-horizons</h2>
  <p style='margin:6px 0 0;font-size:12px;opacity:0.9;'>{now.strftime('%d/%m/%Y')} — {n_jours} jours de recos évalués, benchmark = l'univers CAC 40 lui-même</p>
</div>
<div style='border:1px solid #ddd;border-top:none;padding:20px;border-radius:0 0 8px 8px;'>
  <div style='background:#e0f2f1;border-left:4px solid #00695c;padding:14px 16px;border-radius:6px;'>
    <p style='margin:0;font-size:14px;'><strong>Verdict :</strong> {verdict_txt}</p>
  </div>
  <h3 style='font-size:14px;margin:20px 0 8px;'>Rendement moyen après le signal (prix d'entrée 7h → clôture J+N)</h3>
  <table style='width:100%;border-collapse:collapse;font-size:13px;'>
    <thead><tr style='background:#f5f5f5;'>
      <th style='padding:8px 10px;text-align:left;'>Sortie</th>
      <th style='padding:8px 10px;text-align:right;'>Univers</th>
      <th style='padding:8px 10px;text-align:right;'>ACHETER</th>
      <th style='padding:8px 10px;text-align:right;'>Edge</th>
      <th style='padding:8px 10px;text-align:right;'>ÉVITER</th>
      <th style='padding:8px 10px;text-align:right;'>Utilité*</th>
    </tr></thead>
    <tbody>{lignes}</tbody>
  </table>
  <p style='margin:6px 0 0;font-size:11px;color:#999;'>* Utilité ÉVITER = univers moins ÉVITER : positif quand les valeurs évitées font effectivement pire que le marché.</p>
  <h3 style='font-size:14px;margin:20px 0 8px;'>Le score discrimine-t-il ? (ACHETER à J+5, par bucket)</h3>
  <table style='width:60%;border-collapse:collapse;font-size:13px;'>
    <thead><tr style='background:#f5f5f5;'>
      <th style='padding:8px 10px;text-align:left;'>Bucket</th>
      <th style='padding:8px 10px;'>N</th>
      <th style='padding:8px 10px;text-align:right;'>Rdt moyen</th>
    </tr></thead>
    <tbody>{lignes_buckets}</tbody>
  </table>
  <p style='margin-top:16px;font-size:12px;color:#999;'>
    Rendements bruts (sans frais) : on mesure ici la qualité informationnelle du signal.
    Les frais (~1% l'aller-retour) sont à déduire pour tout usage réel : un edge sous +1% par trade ne couvre pas les frais.
    Évaluation rétroactive sur tout l'historique disponible (90 jours glissants).
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
    print(f"Agent Évaluateur — {now.date()} {now.strftime('%H:%M')} (Paris)")

    historique = charger_historique()
    print(f"{len(historique)} jours de recos dans l'historique")

    print("Récupération des clôtures (39 valeurs)...")
    closes = charger_closes()

    obs = rendements_forward(historique, closes)
    print(f"{len(obs)} observations valeur×jour")

    stats_h    = {h: stats_horizon(obs, h) for h in HORIZONS}
    buckets_j5 = stats_buckets(obs, 5)
    verdict_txt = verdict(stats_h, buckets_j5)
    print(f"Verdict : {verdict_txt}")

    rapport = {
        "date":       now.date().isoformat(),
        "n_jours":    len({o["date"] for o in obs}),
        "n_obs":      len(obs),
        "horizons":   {f"J+{h}": stats_h[h] for h in HORIZONS},
        "buckets_j5": buckets_j5,
        "verdict":    verdict_txt,
    }
    with open(FICHIER_RAPPORT, "w", encoding="utf-8") as f:
        json.dump(rapport, f, ensure_ascii=False, indent=2)

    print("Envoi rapport hebdo...")
    html = generer_html(now, obs, stats_h, buckets_j5, verdict_txt)
    envoyer(f"Évaluateur — edge réel des signaux multi-horizons — {now.strftime('%d/%m/%Y')}", html)

    print("Terminé.")
