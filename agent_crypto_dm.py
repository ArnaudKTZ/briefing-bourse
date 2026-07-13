#!/usr/bin/env python3
"""
Agent Crypto Dual Momentum — la rotation mensuelle BTC/ETH.

Stratégie (validée par la recette le 09/07, décision Arnaud le 13/07) :
  - Poche 100% rotative (PAS de socle buy & hold, contrairement au cœur
    actions) : chaque mois, on détient UN seul actif ou le refuge.
  - Compare BTC vs ETH sur 12 mois (clôtures de fin de mois UNIQUEMENT,
    comme le backtest : la décision du 1er se prend sur le mois clos).
  - Garde le meilleur s'il est en hausse (momentum absolu positif).
  - Sinon, refuge en stablecoin/cash : c'est L'AIRBAG, la raison d'être de
    la stratégie sur crypto (les bear markets y détruisent -70/-80%).

Ce qui a passé la recette (crypto_dm_backtest.py, fenêtre 2018-2026) :
  lookback 12 FIXE (le standard Antonacci, non optimisé sur ces données),
  BTC/ETH sans SOL (SOL détruit tout : DD -90%), buffer sans effet mesuré.
  Résultat : CAGR 46% vs 32% B&H BTC, drawdown -51% vs -73%, Sharpe 0.73
  vs 0.46. Le walk-forward optimisé, lui, ÉCHOUE (lookbacks courts hachés) :
  ne jamais "améliorer" cet agent en raccourcissant le lookback sans re-recette.

Limites honnêtes (à relire avant de juger le live) :
  - Historique court, un seul grand régime haussier : l'edge de rendement
    exact est fragile, seul l'airbag (DD réduit) est robuste sur tous les
    lookbacks testés.
  - Si le live fait +0.2 Sharpe de moins que le backtest, suspicion de
    contamination (règle anti-leakage du 05/07).

Poche TOTALEMENT séparée du PEA (exchange, pas Boursobank). Le portefeuille
virtuel est en USD (les cours de référence BTC-USD/ETH-USD le sont).
Fiscalité France, pour mémoire : un échange crypto→crypto (y compris vers
stablecoin) n'est pas un événement imposable ; seul le passage crypto→euros
l'est (art. 150 VH bis, à valider selon situation). Le refuge stablecoin
plutôt qu'euros évite donc de cristalliser la flat tax à chaque airbag.

Tourne 1x par mois (le 1er, après le DM actions). Pas d'appel API payant.
L'agent conseille, Arnaud passe les ordres lui-même.
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
_dest_env     = os.environ.get("DESTINATAIRES", "")
DESTINATAIRES = [d.strip() for d in _dest_env.split(",") if d.strip()] if _dest_env else []

FICHIER_ETAT = "crypto_dm_etat.json"
FICHIER_PF   = "crypto_dm_portefeuille.json"

CAPITAL_DEPART_USD = 1000.0   # virtuel, proportionnel : seuls les % comptent

# Réglages FIGÉS par la recette du 09/07. Ne pas toucher sans repasser
# crypto_dm_backtest.py : le lookback 12 est le seul qui a passé la
# validation, les lookbacks courts optimisés ont échoué en hors-échantillon.
LOOKBACK_MOIS   = 12
BUFFER_SWITCH   = 0.0     # sans effet mesuré (écarts de momentum crypto larges)
FRAIS_PAR_TRADE = 0.005   # 0,5% par rotation (exchange + slippage), comme le backtest

UNIVERS = {
    "BTC": {"ticker": "BTC-USD", "nom": "Bitcoin"},
    "ETH": {"ticker": "ETH-USD", "nom": "Ethereum"},
}
REFUGE = "Stable"   # stablecoin/cash, rendement supposé nul (conservateur)


def momentum_12m(ticker, now):
    """Momentum 12 mois sur clôtures de fin de mois COMPLETS (le mois en cours
    est exclu : la décision du 1er se prend sur le mois clos, comme le
    backtest — la crypto cote 24/7, le 1er au matin le 'mois courant' existe
    déjà dans le resample). Retourne (momentum %, dernière clôture mensuelle,
    cours spot)."""
    hist = yf.Ticker(ticker).history(period="16mo")
    if hist.empty or len(hist) < 300:
        raise RuntimeError(f"Données insuffisantes pour {ticker} ({len(hist)} lignes)")
    spot = float(hist["Close"].iloc[-1])
    mensuel = hist["Close"].resample("ME").last().dropna()
    mois_courant = now.strftime("%Y-%m")
    complets = mensuel[[d.strftime("%Y-%m") < mois_courant for d in mensuel.index]]
    if len(complets) < LOOKBACK_MOIS + 1:
        raise RuntimeError(f"Pas assez de mois complets pour {ticker} ({len(complets)})")
    actuel = float(complets.iloc[-1])
    ref    = float(complets.iloc[-(LOOKBACK_MOIS + 1)])
    # Momentum NON arrondi : même valeur que la recette, arrondi à l'affichage.
    return (actuel / ref - 1) * 100, round(actuel, 2), round(spot, 2)


def charger_etat():
    if os.path.exists(FICHIER_ETAT):
        with open(FICHIER_ETAT, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"position": None, "date": None, "historique": []}


def sauvegarder_etat(etat):
    with open(FICHIER_ETAT, "w", encoding="utf-8") as f:
        json.dump(etat, f, ensure_ascii=False, indent=2)


def decider_position(momentums, position_actuelle):
    """momentums : {"BTC": (mom, close_mensuel, spot), ...}
    Retourne "BTC", "ETH" ou REFUGE. Même logique que le backtest validé."""
    classement = sorted(momentums.items(), key=lambda x: x[1][0], reverse=True)
    meilleur, (mom_meilleur, _, _) = classement[0]

    # Momentum absolu : si même le meilleur baisse sur 12 mois, refuge
    if mom_meilleur <= 0:
        return REFUGE

    # Anti-whipsaw (buffer 0 = on garde la position tant qu'elle n'est pas battue)
    if position_actuelle in momentums:
        mom_actuel = momentums[position_actuelle][0]
        if mom_actuel > 0 and mom_meilleur < mom_actuel + BUFFER_SWITCH * 100:
            return position_actuelle

    return meilleur


def gerer_portefeuille(momentums, cible, now):
    """Portefeuille virtuel : 1 000 $ au départ, une seule position à la fois,
    frais de 0,5% à chaque rotation (comme le backtest). Benchmark : B&H BTC
    depuis le même départ. Valorisé au spot du jour de la revue."""
    spots = {a: momentums[a][2] for a in momentums}
    today = now.date().isoformat()

    if os.path.exists(FICHIER_PF):
        with open(FICHIER_PF, "r", encoding="utf-8") as f:
            pf = json.load(f)
    else:
        pf = {"date_init": today, "capital_depart_usd": CAPITAL_DEPART_USD,
              "position": None, "units": 0.0, "cash_usd": CAPITAL_DEPART_USD,
              "frais_cumules_usd": 0.0, "n_rotations": 0,
              "btc_bh_units": round(CAPITAL_DEPART_USD / spots["BTC"], 8),
              "historique_valeur": {}}

    # Valeur courante au spot
    if pf["position"] in spots:
        valeur = pf["units"] * spots[pf["position"]]
    else:
        valeur = pf["cash_usd"]

    # Rotation si la cible change. Frais 0,5% sur le montant déplacé,
    # y compris l'achat initial (le backtest les compte aussi).
    if cible != pf["position"]:
        frais = round(valeur * FRAIS_PAR_TRADE, 2)
        valeur -= frais
        pf["frais_cumules_usd"] = round(pf.get("frais_cumules_usd", 0) + frais, 2)
        pf["n_rotations"] = pf.get("n_rotations", 0) + 1
        if cible in spots:
            pf["units"], pf["cash_usd"] = round(valeur / spots[cible], 8), 0.0
        else:
            pf["units"], pf["cash_usd"] = 0.0, round(valeur, 2)
        pf["position"] = cible

    pf["historique_valeur"][today] = round(valeur, 2)
    pf["dernier_spot"] = spots
    pf["valeur_actuelle"] = round(valeur, 2)
    pf["btc_bh_valeur"] = round(pf["btc_bh_units"] * spots["BTC"], 2)

    with open(FICHIER_PF, "w", encoding="utf-8") as f:
        json.dump(pf, f, ensure_ascii=False, indent=2)

    return pf


def libelle(pos):
    if pos is None:     return "—"
    if pos == REFUGE:   return "stablecoin (refuge)"
    return UNIVERS[pos]["nom"]


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


def generer_html(now, momentums, ancienne, nouvelle, action, pf):
    lignes_mom = ""
    for actif, (mom, close_m, spot) in momentums.items():
        c = "#2e7d32" if mom > 0 else "#c62828"
        lignes_mom += f"""<tr style='border-bottom:1px solid #eee;'>
          <td style='padding:8px 10px;font-weight:500;'>{UNIVERS[actif]['nom']}</td>
          <td style='padding:8px 10px;text-align:right;'>{spot:,.0f} $</td>
          <td style='padding:8px 10px;text-align:right;color:{c};font-weight:600;'>{mom:+.1f}%</td>
        </tr>"""

    if action == "BASCULE":
        note_fiscale = ""
        if nouvelle == REFUGE or ancienne == "stablecoin (refuge)":
            note_fiscale = "<p style='margin:8px 0 0;font-size:12px;color:#795548;'>Rappel : passer par un stablecoin (pas par des euros) évite de cristalliser la flat tax (échange crypto→crypto non imposable, art. 150 VH bis — à valider selon ta situation).</p>"
        bloc_action = f"""<div style='background:#fff3e0;border-left:4px solid #e65100;padding:14px 16px;border-radius:6px;'>
          <p style='margin:0;font-weight:600;color:#e65100;'>Action ce mois-ci : rotation</p>
          <p style='margin:8px 0 0;font-size:14px;'>Vends <strong>{ancienne}</strong>, achète <strong>{nouvelle}</strong>.</p>
          {note_fiscale}
        </div>"""
    else:
        bloc_action = f"""<div style='background:#e8f5e9;border-left:4px solid #2e7d32;padding:14px 16px;border-radius:6px;'>
          <p style='margin:0;font-weight:600;color:#2e7d32;'>Rien à faire ce mois-ci.</p>
          <p style='margin:8px 0 0;font-size:14px;'>La position reste sur <strong>{nouvelle}</strong>.</p>
        </div>"""

    v, bh = pf["valeur_actuelle"], pf["btc_bh_valeur"]
    depart = pf["capital_depart_usd"]
    perf   = (v / depart - 1) * 100
    perf_bh = (bh / depart - 1) * 100
    c_pf = "#2e7d32" if v >= bh else "#c62828"

    return f"""<html><body style='font-family:Arial,sans-serif;max-width:640px;margin:auto;padding:20px;color:#222;'>
<div style='background:linear-gradient(135deg,#b45309,#f7931a);color:white;padding:16px 20px;border-radius:8px 8px 0 0;'>
  <h2 style='margin:0;font-size:18px;'>Crypto Dual Momentum — revue mensuelle</h2>
  <p style='margin:6px 0 0;font-size:12px;opacity:0.9;'>{now.strftime('%d/%m/%Y')} — rotation BTC/ETH, refuge stablecoin, poche séparée du PEA</p>
</div>
<div style='border:1px solid #ddd;border-top:none;padding:20px;border-radius:0 0 8px 8px;'>
  {bloc_action}
  <h3 style='font-size:14px;margin:20px 0 8px;'>Position cible</h3>
  <p style='font-size:15px;margin:0;padding:10px 12px;background:#f5f5f5;border-radius:6px;'>100% {nouvelle}</p>
  <h3 style='font-size:14px;margin:20px 0 8px;'>Momentum 12 mois (clôtures mensuelles, mois en cours exclu)</h3>
  <table style='width:100%;border-collapse:collapse;font-size:14px;'>
    <thead><tr style='background:#f5f5f5;'>
      <th style='padding:8px 10px;text-align:left;'>Actif</th>
      <th style='padding:8px 10px;text-align:right;'>Cours</th>
      <th style='padding:8px 10px;text-align:right;'>Perf 12 mois</th>
    </tr></thead>
    <tbody>{lignes_mom}</tbody>
  </table>
  <h3 style='font-size:14px;margin:20px 0 8px;'>Portefeuille virtuel (départ {depart:,.0f} $ le {pf['date_init']})</h3>
  <p style='font-size:14px;margin:0;'>Stratégie : <strong style='color:{c_pf};'>{v:,.2f} $ ({perf:+.1f}%)</strong>
     &nbsp;·&nbsp; Buy &amp; hold BTC : {bh:,.2f} $ ({perf_bh:+.1f}%)
     &nbsp;·&nbsp; {pf.get('n_rotations', 0)} rotation(s), {pf.get('frais_cumules_usd', 0):.2f} $ de frais</p>
  <p style='margin-top:16px;font-size:12px;color:#999;'>
    Règle validée par la recette (09/07) : 100% sur le meilleur momentum 12 mois de BTC/ETH,
    refuge stablecoin si tout baisse. Lookback 12 FIXE : les réglages courts optimisés ont échoué
    en hors-échantillon, ne pas y toucher sans repasser le backtest. L'attendu principal est
    l'airbag (drawdown -51% vs -73%), pas le rendement. Revue le 1er de chaque mois.
    Ceci est une aide à la décision, tu restes maître de tes ordres.
  </p>
</div>
</body></html>"""


if __name__ == "__main__":
    now = datetime.datetime.now(TZ_PARIS)
    print(f"Agent Crypto Dual Momentum — {now.date()} {now.strftime('%H:%M')} (Paris)")

    print("Calcul des momentums 12 mois (clôtures mensuelles)...")
    momentums = {}
    for actif, cfg in UNIVERS.items():
        mom, close_m, spot = momentum_12m(cfg["ticker"], now)
        momentums[actif] = (mom, close_m, spot)
        print(f"  {actif} : {mom:+.1f}% sur 12 mois (clôture mensuelle {close_m:,.0f} $, spot {spot:,.0f} $)")

    etat = charger_etat()
    ancienne = etat.get("position")

    nouvelle = decider_position(momentums, ancienne)
    print(f"Position : {ancienne} -> {nouvelle}")

    action = "BASCULE" if (ancienne is not None and nouvelle != ancienne) else "RIEN"

    etat["position"] = nouvelle
    etat["date"] = now.date().isoformat()
    etat.setdefault("historique", []).append({
        "date": now.date().isoformat(),
        "position": nouvelle,
        "momentums": {k: round(v[0], 1) for k, v in momentums.items()},
    })
    etat["historique"] = etat["historique"][-36:]
    sauvegarder_etat(etat)

    pf = gerer_portefeuille(momentums, nouvelle, now)
    print(f"Portefeuille virtuel : {pf['valeur_actuelle']:,.2f} $ "
          f"(B&H BTC : {pf['btc_bh_valeur']:,.2f} $)")

    print("Envoi email mensuel...")
    sujet = (f"Crypto DM — {'ROTATION ' + libelle(ancienne) + ' vers ' + libelle(nouvelle) if action == 'BASCULE' else 'rien a faire'} "
             f"— {now.strftime('%m/%Y')}")
    html = generer_html(now, momentums, libelle(ancienne), libelle(nouvelle), action, pf)
    envoyer_email(sujet, html)

    print("Terminé.")
