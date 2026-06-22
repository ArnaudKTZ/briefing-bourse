#!/usr/bin/env python3
"""
Scoring intraday — collecte les scores 3x/jour sans appeler Claude.
Tourne à 9h, 12h et 16h via GitHub Actions.
Sauvegarde dans intraday_scores.json pour enrichir le briefing du lendemain.
"""

import datetime
import json
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import yfinance as yf
import pandas as pd
import numpy as np

ZOHO_EMAIL    = os.environ.get("ZOHO_EMAIL", "Arnaud.kuntz@zoho.eu")
ZOHO_PASSWORD = os.environ.get("ZOHO_PASSWORD", "")
ZOHO_SMTP     = "smtp.zoho.eu"
ZOHO_PORT     = 587

DESTINATAIRES = [
    "xtrem111team@gmail.com",
    "ferrey83400@gmail.com",
    "Arnaud.kuntz@zoho.eu",
]

SEUIL_ALERTE         = 85
FICHIER_ALERTES_VUE  = "alertes_envoyees.json"
FICHIER_PORTEFEUILLE = "portefeuille_virtuel.json"
FRAIS_TAUX           = 0.005
FRAIS_MINIMUM        = 0.50
BUDGET_PAR_POSITION  = 2000.0
MAX_POSITIONS        = 5
SEUIL_ACHAT_INTRADAY = 80   # score pour ouvrir une position intraday
SEUIL_STOP_LOSS      = -5.0
SEUIL_TAKE_PROFIT    = 8.0

try:
    from ta.momentum import RSIIndicator, StochasticOscillator
    from ta.trend import MACD, SMAIndicator
    from ta.volatility import BollingerBands, AverageTrueRange
    TA_DISPONIBLE = True
except ImportError:
    TA_DISPONIBLE = False

FICHIER_INTRADAY = "intraday_scores.json"

CAC40 = {
    "LVMH":               "MC.PA",
    "TotalEnergies":      "TTE.PA",
    "Hermès":             "RMS.PA",
    "Airbus":             "AIR.PA",
    "Schneider Electric": "SU.PA",
    "L'Oréal":            "OR.PA",
    "Sanofi":             "SAN.PA",
    "BNP Paribas":        "BNP.PA",
    "Air Liquide":        "AI.PA",
    "Safran":             "SAF.PA",
    "Danone":             "BN.PA",
    "Vinci":              "DG.PA",
    "Kering":             "KER.PA",
    "Société Générale":   "GLE.PA",
    "Stellantis":         "STLAM.MI",
    "Saint-Gobain":       "SGO.PA",
    "ArcelorMittal":      "MT",
    "Pernod Ricard":      "RI.PA",
    "Michelin":           "ML.PA",
    "Capgemini":          "CAP.PA",
    "Renault":            "RNO.PA",
    "Legrand":            "LR.PA",
    "Publicis":           "PUB.PA",
    "Bouygues":           "EN.PA",
    "Engie":              "ENGI.PA",
    "Orange":             "ORA.PA",
    "Vivendi":            "VIV.PA",
    "Eurofins Scientific":"ERF.PA",
    "Teleperformance":    "TEP.PA",
    "Alstom":             "ALO.PA",
    "Worldline":          "WLN.PA",
    "Veolia":             "VIE.PA",
    "STMicroelectronics": "STM",
    "Dassault Systèmes":  "DSY.PA",
    "Edenred":            "EDEN.PA",
    "Accor":              "AC.PA",
    "Eurazeo":            "RF.PA",
    "Thales":             "HO.PA",
    "Forvia":             "FRVIA.PA",
}


def scorer_action(nom, ticker):
    try:
        stock = yf.Ticker(ticker)
        hist  = stock.history(period="60d")

        if hist.empty or len(hist) < 20:
            return None

        cours      = round(float(hist["Close"].iloc[-1]), 2)
        cours_hier = round(float(hist["Close"].iloc[-2]), 2)
        ouverture  = round(float(hist["Open"].iloc[-1]), 2)
        variation  = round((cours - cours_hier) / cours_hier * 100, 2)
        volume     = int(hist["Volume"].iloc[-1])
        vol_moy    = int(hist["Volume"].iloc[-20:].mean())

        # Gap ouverture vs clôture hier
        gap_pct = round((ouverture - cours_hier) / cours_hier * 100, 2)

        score = 50

        if TA_DISPONIBLE:
            close = hist["Close"]

            rsi = RSIIndicator(close, window=14).rsi().iloc[-1]
            if not pd.isna(rsi):
                rsi = round(rsi, 1)
                if rsi < 25:   score += 20
                elif rsi < 35: score += 12
                elif rsi < 45: score += 5
                elif rsi > 75: score -= 20
                elif rsi > 65: score -= 12
                elif rsi > 55: score -= 5

            macd_ind  = MACD(close)
            macd_line = macd_ind.macd().iloc[-1]
            macd_sig  = macd_ind.macd_signal().iloc[-1]
            macd_hist = macd_ind.macd_diff()
            if not pd.isna(macd_line) and not pd.isna(macd_sig):
                if macd_line > macd_sig: score += 10
                else:                    score -= 10
            if len(macd_hist) >= 2:
                h1 = macd_hist.iloc[-1]
                h2 = macd_hist.iloc[-2]
                if not pd.isna(h1) and not pd.isna(h2):
                    if h1 > h2 and h1 > 0: score += 5
                    elif h1 < h2 and h1 < 0: score -= 5

            ma20  = SMAIndicator(close, window=20).sma_indicator().iloc[-1]
            ma50  = SMAIndicator(close, window=50).sma_indicator().iloc[-1]
            if not pd.isna(ma20) and not pd.isna(ma50):
                if cours > ma20 and cours > ma50:  score += 10
                elif cours < ma20 and cours < ma50: score -= 10

            bb = BollingerBands(close)
            bb_low  = bb.bollinger_lband().iloc[-1]
            bb_high = bb.bollinger_hband().iloc[-1]
            if not pd.isna(bb_low) and not pd.isna(bb_high):
                if cours < bb_low:   score += 10
                elif cours > bb_high: score -= 10

        # Volume anormal
        if vol_moy > 0:
            ratio_vol = round(volume / vol_moy, 1)
            if ratio_vol > 2:
                if variation > 0: score += 8
                else:             score -= 8

        # Gap haussier avec volume fort = signal positif
        if gap_pct > 0.5 and volume > vol_moy * 1.5: score += 5
        if gap_pct < -0.5 and volume > vol_moy * 1.5: score -= 5

        # Momentum intraday (cours vs ouverture)
        momentum_intraday = round((cours - ouverture) / ouverture * 100, 2) if ouverture else 0
        if momentum_intraday > 0.5:  score += 5
        elif momentum_intraday < -0.5: score -= 5

        score = max(0, min(100, round(score)))

        if score >= 65:   signal = "ACHETER"
        elif score <= 35: signal = "ÉVITER"
        else:             signal = "SURVEILLER"

        return {
            "nom":                nom,
            "cours":              cours,
            "variation":          variation,
            "gap_ouverture":      gap_pct,
            "momentum_intraday":  momentum_intraday,
            "volume_ratio":       round(volume / vol_moy, 1) if vol_moy > 0 else 1.0,
            "score":              score,
            "signal":             signal,
        }

    except Exception as e:
        print(f"  Erreur {nom} : {e}")
        return None


def charger_intraday():
    if os.path.exists(FICHIER_INTRADAY):
        with open(FICHIER_INTRADAY, "r") as f:
            return json.load(f)
    return {}


def sauvegarder_intraday(data):
    with open(FICHIER_INTRADAY, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def charger_alertes_envoyees():
    if os.path.exists(FICHIER_ALERTES_VUE):
        with open(FICHIER_ALERTES_VUE, "r") as f:
            return json.load(f)
    return {}


def sauvegarder_alertes_envoyees(data):
    with open(FICHIER_ALERTES_VUE, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def envoyer_alerte(alertes):
    if not alertes or not ZOHO_PASSWORD:
        return

    today = datetime.date.today().strftime("%d/%m/%Y")
    heure = datetime.datetime.now().strftime("%H:%M")
    sujet = f"ALERTE BOURSE — {len(alertes)} signal(s) exceptionnel(s) — {today} {heure}"

    lignes_html = ""
    for a in alertes:
        couleur = "#1b5e20" if a["signal"] == "ACHETER" else "#b71c1c"
        lignes_html += f"""
        <tr style='border-bottom:1px solid #eee;'>
          <td style='padding:10px;font-weight:bold;font-size:15px;'>{a['nom']}</td>
          <td style='padding:10px;text-align:center;'>
            <span style='background:{couleur};color:white;padding:4px 10px;border-radius:4px;font-weight:bold;'>
              {a['signal']} {a['score']}/100
            </span>
          </td>
          <td style='padding:10px;'>{a['cours']} € ({'+' if a['variation'] >= 0 else ''}{a['variation']}%)</td>
          <td style='padding:10px;color:#555;font-size:13px;'>{a['raison']}</td>
        </tr>"""

    html = f"""<html><body style='font-family:Arial,sans-serif;max-width:800px;margin:auto;padding:20px;'>
<div style='background:#b71c1c;color:white;padding:16px 20px;border-radius:8px 8px 0 0;'>
  <h2 style='margin:0;font-size:18px;'>ALERTE — Signal(s) exceptionnel(s) detecte(s)</h2>
  <p style='margin:6px 0 0;font-size:12px;opacity:0.9;'>{today} a {heure} — Score seuil : {SEUIL_ALERTE}/100</p>
</div>
<div style='border:1px solid #ddd;border-top:none;padding:20px;border-radius:0 0 8px 8px;'>
  <table style='width:100%;border-collapse:collapse;font-size:14px;'>
    <thead>
      <tr style='background:#f5f5f5;'>
        <th style='padding:10px;text-align:left;'>Valeur</th>
        <th style='padding:10px;text-align:center;'>Signal</th>
        <th style='padding:10px;text-align:left;'>Cours</th>
        <th style='padding:10px;text-align:left;'>Pourquoi</th>
      </tr>
    </thead>
    <tbody>{lignes_html}</tbody>
  </table>
  <p style='margin-top:16px;font-size:12px;color:#999;'>
    Ce briefing est informatif. Tu prends tes propres decisions d investissement.
  </p>
</div>
</body></html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = sujet
    msg["From"]    = ZOHO_EMAIL
    msg["To"]      = ", ".join(DESTINATAIRES)
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        with smtplib.SMTP(ZOHO_SMTP, ZOHO_PORT) as serveur:
            serveur.starttls()
            serveur.login(ZOHO_EMAIL, ZOHO_PASSWORD)
            serveur.sendmail(ZOHO_EMAIL, DESTINATAIRES, msg.as_string())
        print(f"Alerte envoyee : {[a['nom'] for a in alertes]}")
    except Exception as e:
        print(f"Erreur envoi alerte : {e}")


def detecter_alertes(snapshot, alertes_envoyees, today, heure):
    alertes = []
    for nom, d in snapshot.items():
        score  = d["score"]
        signal = d["signal"]
        cle    = f"{today}_{nom}"

        if cle in alertes_envoyees:
            continue

        raisons = []

        if score >= SEUIL_ALERTE and signal == "ACHETER":
            raisons.append(f"Score exceptionnel {score}/100")

        if d.get("gap_ouverture", 0) > 2 and d.get("volume_ratio", 1) > 2:
            raisons.append(f"Gap haussier +{d['gap_ouverture']}% avec volume x{d['volume_ratio']}")

        if d.get("momentum_intraday", 0) > 2 and score >= 70:
            raisons.append(f"Momentum intraday fort +{d['momentum_intraday']}%")

        if raisons:
            alertes.append({
                "nom":       nom,
                "cours":     d["cours"],
                "variation": d["variation"],
                "score":     score,
                "signal":    signal,
                "raison":    " | ".join(raisons),
            })
            alertes_envoyees[cle] = heure

    return alertes, alertes_envoyees


def calculer_frais(montant):
    return round(max(FRAIS_MINIMUM, montant * FRAIS_TAUX), 2)


def gerer_portefeuille_intraday(snapshot, heure):
    """Ouvre/ferme des positions en cours de journée selon les signaux intraday."""
    if not os.path.exists(FICHIER_PORTEFEUILLE):
        return [], []

    with open(FICHIER_PORTEFEUILLE, "r") as f:
        pf = json.load(f)

    today    = datetime.date.today().isoformat()
    fermes   = []
    ouverts  = []

    # Fermeture des positions si signal ÉVITER, stop-loss ou take-profit
    positions_a_fermer = []
    for nom, pos in pf["positions"].items():
        d = snapshot.get(nom)
        if not d:
            continue
        signal       = d["signal"]
        cours_actuel = d["cours"]
        pnl_pct      = (cours_actuel - pos["prix_entree"]) / pos["prix_entree"] * 100

        if signal == "ÉVITER" or pnl_pct <= SEUIL_STOP_LOSS or pnl_pct >= SEUIL_TAKE_PROFIT:
            positions_a_fermer.append((nom, cours_actuel, pnl_pct, signal))

    for nom, cours_sortie, pnl_pct, raison_signal in positions_a_fermer:
        pos           = pf["positions"][nom]
        valeur_sortie = pos["nb_actions"] * cours_sortie
        frais_vente   = calculer_frais(valeur_sortie)
        net_sortie    = valeur_sortie - frais_vente
        frais_total   = round(pos.get("frais_achat", 0) + frais_vente, 2)
        pnl_net       = round((net_sortie - pos["cout_total"]) / pos["cout_total"] * 100, 2)
        pf["capital"] += net_sortie

        raison = "ÉVITER intraday" if raison_signal == "ÉVITER" else (
            f"Stop-loss {pnl_pct:.1f}%" if pnl_pct <= SEUIL_STOP_LOSS else f"Take-profit {pnl_pct:.1f}%"
        )

        pf["trades"].append({
            "nom":           nom,
            "entree":        pos["prix_entree"],
            "sortie":        cours_sortie,
            "date_entree":   pos["date_entree"],
            "heure_entree":  pos.get("heure_entree", "07:00"),
            "source_entree": pos.get("source_entree", "Briefing"),
            "date_sortie":   today,
            "heure_sortie":  heure,
            "source_sortie": "Intraday",
            "pnl_pct":       pnl_net,
            "frais_total":   frais_total,
            "raison_sortie": raison,
        })
        del pf["positions"][nom]
        fermes.append({"nom": nom, "cours": cours_sortie, "pnl": pnl_net, "raison": raison})

    # Ouverture de nouvelles positions si score >= seuil intraday
    for nom, d in snapshot.items():
        if (d["score"] >= SEUIL_ACHAT_INTRADAY and
                d["signal"] == "ACHETER" and
                nom not in pf["positions"] and
                len(pf["positions"]) < MAX_POSITIONS and
                pf["capital"] >= BUDGET_PAR_POSITION):
            cours       = d["cours"]
            nb          = int(BUDGET_PAR_POSITION / cours)
            if nb > 0:
                cout        = nb * cours
                frais_achat = calculer_frais(cout)
                pf["capital"] -= (cout + frais_achat)
                pf["positions"][nom] = {
                    "nb_actions":   nb,
                    "prix_entree":  cours,
                    "date_entree":  today,
                    "heure_entree": heure,
                    "source_entree":"Intraday",
                    "cout_total":   cout,
                    "frais_achat":  frais_achat,
                }
                ouverts.append({"nom": nom, "cours": cours, "score": d["score"]})

    # Mise à jour valeur totale
    valeur_positions = sum(
        pos["nb_actions"] * snapshot.get(nom, {}).get("cours", pos["prix_entree"])
        for nom, pos in pf["positions"].items()
    )
    valeur_totale = round(pf["capital"] + valeur_positions, 2)
    pf["historique_valeur"][today] = valeur_totale

    with open(FICHIER_PORTEFEUILLE, "w") as f:
        json.dump(pf, f, ensure_ascii=False, indent=2)

    return fermes, ouverts


if __name__ == "__main__":
    now   = datetime.datetime.now()
    today = datetime.date.today().isoformat()
    heure = now.strftime("%H:%M")

    print(f"Scoring intraday — {today} {heure}")

    data = charger_intraday()

    # Garde seulement les 5 derniers jours
    jours = sorted(data.keys())
    while len(jours) > 5:
        del data[jours.pop(0)]

    if today not in data:
        data[today] = {}

    snapshot = {}
    ok = 0
    for nom, ticker in CAC40.items():
        print(f"  {nom}...")
        result = scorer_action(nom, ticker)
        if result:
            snapshot[nom] = result
            ok += 1

    data[today][heure] = snapshot
    sauvegarder_intraday(data)
    print(f"OK : {ok}/39 snapshots sauvegardés à {heure}")

    print("Détection alertes exceptionnelles...")
    alertes_envoyees = charger_alertes_envoyees()
    sept_jours = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
    alertes_envoyees = {k: v for k, v in alertes_envoyees.items() if k[:10] >= sept_jours}

    alertes, alertes_envoyees = detecter_alertes(snapshot, alertes_envoyees, today, heure)
    sauvegarder_alertes_envoyees(alertes_envoyees)

    print("Gestion portefeuille intraday...")
    fermes, ouverts = gerer_portefeuille_intraday(snapshot, heure)
    if fermes:
        print(f"  Positions fermées : {[f['nom'] for f in fermes]}")
    if ouverts:
        print(f"  Positions ouvertes : {[o['nom'] for o in ouverts]}")

    # Fusionne les mouvements de portefeuille dans les alertes si pertinent
    for o in ouverts:
        cle = f"{today}_{o['nom']}_achat"
        if cle not in alertes_envoyees:
            alertes.append({
                "nom":       o["nom"],
                "cours":     o["cours"],
                "variation": snapshot.get(o["nom"], {}).get("variation", 0),
                "score":     o["score"],
                "signal":    "ACHETER",
                "raison":    f"Position ouverte en portefeuille virtuel (score {o['score']}/100)",
            })
            alertes_envoyees[cle] = heure

    for f in fermes:
        cle = f"{today}_{f['nom']}_vente"
        if cle not in alertes_envoyees:
            alertes.append({
                "nom":       f["nom"],
                "cours":     f["cours"],
                "variation": snapshot.get(f["nom"], {}).get("variation", 0),
                "score":     snapshot.get(f["nom"], {}).get("score", 0),
                "signal":    "VENTE",
                "raison":    f"Position fermée — {f['raison']} | P&L : {'+' if f['pnl'] >= 0 else ''}{f['pnl']:.2f}%",
            })
            alertes_envoyees[cle] = heure

    sauvegarder_alertes_envoyees(alertes_envoyees)

    if alertes:
        print(f"  {len(alertes)} alerte(s) — envoi email...")
        envoyer_alerte(alertes)
    else:
        print("  Aucune alerte.")

    print("Scoring intraday terminé.")
