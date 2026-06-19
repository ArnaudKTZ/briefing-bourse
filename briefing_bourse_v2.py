#!/usr/bin/env python3
"""
Agent Bourse V2 — Données temps réel + indicateurs techniques + auto-amélioration
"""

import smtplib
import datetime
import os
import json
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import anthropic
import yfinance as yf

try:
    from ta.momentum import RSIIndicator
    from ta.trend import MACD, SMAIndicator
    from ta.volatility import BollingerBands
    TA_DISPONIBLE = True
except ImportError:
    TA_DISPONIBLE = False

# ─── CONFIGURATION ────────────────────────────────────────────────────────────

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "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")
ZOHO_EMAIL        = os.environ.get("ZOHO_EMAIL", "Arnaud.kuntz@zoho.eu")
ZOHO_PASSWORD     = os.environ.get("ZOHO_PASSWORD", "2a6xXFJMr4GN")
ZOHO_SMTP         = "smtp.zoho.eu"
ZOHO_PORT         = 587

DESTINATAIRES = [
    "xtrem111team@gmail.com",
    "ferrey83400@gmail.com",
]

FICHIER_PERFORMANCE = "performance.json"

# ─── CAC 40 TICKERS ───────────────────────────────────────────────────────────

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

SECTEURS = {
    "Luxe":              ["LVMH", "Hermès", "Kering", "L'Oréal", "Pernod Ricard"],
    "Énergie":           ["TotalEnergies", "Engie"],
    "Industrie/Défense": ["Airbus", "Schneider Electric", "Safran", "Vinci", "Saint-Gobain",
                          "Legrand", "ArcelorMittal", "Alstom", "Forvia", "Bouygues", "Thales"],
    "Banques/Finance":   ["BNP Paribas", "Société Générale", "Eurazeo"],
    "Santé":             ["Sanofi", "Air Liquide", "Eurofins Scientific"],
    "Tech":              ["Capgemini", "Dassault Systèmes", "STMicroelectronics", "Worldline"],
    "Télécom/Média":     ["Orange", "Vivendi", "Publicis", "Teleperformance"],
    "Conso/Autre":       ["Danone", "Michelin", "Renault", "Stellantis", "Accor", "Edenred", "Veolia"],
}

# ─── RÉCUPÉRATION DES DONNÉES ─────────────────────────────────────────────────

def recuperer_donnees_action(nom, ticker):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="3mo")
        if hist.empty:
            return {"nom": nom, "ticker": ticker, "erreur": "Pas de données"}

        cours       = round(hist["Close"].iloc[-1], 2)
        cours_hier  = round(hist["Close"].iloc[-2], 2) if len(hist) > 1 else cours
        variation   = round((cours - cours_hier) / cours_hier * 100, 2)
        volume      = int(hist["Volume"].iloc[-1])

        rsi = macd_signal = ma20 = ma50 = boll_zone = None

        if TA_DISPONIBLE and len(hist) >= 20:
            close = hist["Close"]

            rsi_val = RSIIndicator(close=close, window=14).rsi().iloc[-1]
            rsi = round(rsi_val, 1)

            macd_ind = MACD(close=close)
            macd_val = macd_ind.macd().iloc[-1]
            macd_sig = macd_ind.macd_signal().iloc[-1]
            macd_signal = "haussier" if macd_val > macd_sig else "baissier"

            ma20 = round(SMAIndicator(close=close, window=20).sma_indicator().iloc[-1], 2)
            if len(hist) >= 50:
                ma50 = round(SMAIndicator(close=close, window=50).sma_indicator().iloc[-1], 2)

            boll = BollingerBands(close=close, window=20, window_dev=2)
            b_inf = boll.bollinger_lband().iloc[-1]
            b_sup = boll.bollinger_hband().iloc[-1]
            if cours < b_inf:
                boll_zone = "SOUS bande inf (survendu)"
            elif cours > b_sup:
                boll_zone = "AU-DESSUS bande sup (suracheté)"
            else:
                boll_zone = "dans les bandes"

        # News Yahoo Finance
        news = []
        try:
            for n in stock.news[:3]:
                title = n.get("content", {}).get("title", "") or n.get("title", "")
                if title:
                    news.append(title)
        except:
            pass

        return {
            "nom":        nom,
            "ticker":     ticker,
            "cours":      cours,
            "cours_hier": cours_hier,
            "variation":  variation,
            "volume":     volume,
            "rsi":        rsi,
            "macd":       macd_signal,
            "ma20":       ma20,
            "ma50":       ma50,
            "boll_zone":  boll_zone,
            "news":       news,
        }

    except Exception as e:
        return {"nom": nom, "ticker": ticker, "erreur": str(e)}


def recuperer_indice_cac():
    try:
        hist = yf.Ticker("^FCHI").history(period="5d")
        if not hist.empty:
            cours    = round(hist["Close"].iloc[-1], 0)
            hier     = round(hist["Close"].iloc[-2], 0)
            variation = round((cours - hier) / hier * 100, 2)
            return cours, variation
    except:
        pass
    return None, None


# ─── PERFORMANCE TRACKING ─────────────────────────────────────────────────────

def charger_performance():
    if os.path.exists(FICHIER_PERFORMANCE):
        with open(FICHIER_PERFORMANCE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"historique": {}, "stats": {"total": 0, "corrects": 0, "precision": 0.0}}


def evaluer_performance_hier(perf, donnees_actuelles):
    if not perf["historique"]:
        return perf, "Pas encore d'historique. L'agent commencera à s'auto-évaluer dès demain."

    # Trouve le dernier jour enregistré
    date_hier = None
    for i in range(1, 8):
        date_test = (datetime.date.today() - datetime.timedelta(days=i)).isoformat()
        if date_test in perf["historique"]:
            date_hier = date_test
            break

    if not date_hier:
        return perf, "Pas encore d'historique récent à évaluer."

    reco_hier = perf["historique"][date_hier]
    donnees_dict = {d["nom"]: d for d in donnees_actuelles if "erreur" not in d}

    corrects = 0
    total    = 0
    bons     = []
    mauvais  = []

    for nom, data in reco_hier.items():
        signal    = data.get("signal")
        prix_hier = data.get("prix")
        if signal not in ["ACHETER", "ÉVITER"] or not prix_hier:
            continue

        d_auj = donnees_dict.get(nom)
        if not d_auj:
            continue

        prix_auj = d_auj.get("cours")
        if not prix_auj:
            continue

        hausse  = prix_auj > prix_hier
        correct = (signal == "ACHETER" and hausse) or (signal == "ÉVITER" and not hausse)
        variation = round((prix_auj - prix_hier) / prix_hier * 100, 2)
        total  += 1
        corrects += int(correct)

        signe = "+" if variation > 0 else ""
        if correct:
            bons.append(f"{nom} ({signal} -> {signe}{variation}%)")
        else:
            mauvais.append(f"{nom} ({signal} -> {signe}{variation}%)")

    if total > 0:
        perf["stats"]["total"]    += total
        perf["stats"]["corrects"] += corrects
        perf["stats"]["precision"] = round(perf["stats"]["corrects"] / perf["stats"]["total"] * 100, 1)

    resume = f"Performance J-1 ({date_hier}) : {corrects}/{total} correctes"
    if bons:
        resume += f"\nBons signaux : {', '.join(bons[:5])}"
    if mauvais:
        resume += f"\nErreurs : {', '.join(mauvais[:5])}"

    return perf, resume


def sauvegarder_recommandations(perf, donnees_actuelles, briefing_texte):
    today = datetime.date.today().isoformat()
    perf["historique"][today] = {}

    donnees_dict = {d["nom"]: d for d in donnees_actuelles if "erreur" not in d}

    for nom, d in donnees_dict.items():
        signal = "SURVEILLER"
        idx = briefing_texte.find(nom)
        if idx >= 0:
            extrait = briefing_texte[idx:idx+150]
            if "ACHETER" in extrait:
                signal = "ACHETER"
            elif "ÉVITER" in extrait:
                signal = "ÉVITER"
        perf["historique"][today][nom] = {
            "signal": signal,
            "prix":   d.get("cours")
        }

    # Garde 60 jours max
    dates = sorted(perf["historique"].keys())
    for vieille in dates[:-60]:
        del perf["historique"][vieille]

    with open(FICHIER_PERFORMANCE, "w", encoding="utf-8") as f:
        json.dump(perf, f, ensure_ascii=False, indent=2)


# ─── CONSTRUCTION DU PROMPT ───────────────────────────────────────────────────

def construire_prompt(donnees, cac_cours, cac_var, perf_resume, perf_stats, est_lundi):
    today = datetime.date.today()
    jours = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
    jour  = jours[today.weekday()]

    donnees_dict = {d["nom"]: d for d in donnees if "erreur" not in d}

    bloc_donnees = ""
    for secteur, valeurs in SECTEURS.items():
        bloc_donnees += f"\n### {secteur}\n"
        for nom in valeurs:
            d = donnees_dict.get(nom)
            if not d:
                continue
            ligne = f"- **{nom}** : {d['cours']}€ ({'+' if d['variation'] > 0 else ''}{d['variation']}% vs hier)"
            if d.get("rsi"):
                mention = ""
                if d["rsi"] < 30:
                    mention = " *** SURVENDU ***"
                elif d["rsi"] > 70:
                    mention = " *** SURACHETÉ ***"
                ligne += f" | RSI={d['rsi']}{mention}"
            if d.get("macd"):
                ligne += f" | MACD {d['macd']}"
            if d.get("ma20") and d.get("ma50"):
                pos = "prix > MA20 et MA50" if d["cours"] > d["ma20"] and d["cours"] > d["ma50"] else \
                      "prix > MA20 seulement" if d["cours"] > d["ma20"] else \
                      "prix < MA20 et MA50"
                ligne += f" | {pos}"
            if d.get("boll_zone"):
                ligne += f" | Bollinger : {d['boll_zone']}"
            if d.get("news"):
                ligne += f"\n  Actualités : {' // '.join(d['news'][:2])}"
            bloc_donnees += ligne + "\n"

    indice_txt = ""
    if cac_cours:
        indice_txt = f"CAC 40 : {cac_cours:.0f} pts ({'+' if cac_var > 0 else ''}{cac_var}%)"

    perf_txt = ""
    if perf_stats["total"] > 0:
        perf_txt = f"""
## Ton historique de performance (auto-amélioration)
- Total recommandations évaluées : {perf_stats['total']}
- Taux de précision : **{perf_stats['precision']}%**
- {perf_resume}

Analyse tes erreurs passées et ajuste tes critères pour améliorer ta précision.
Si tu as fait des erreurs sur certains types de signaux ou secteurs, tiens-en compte.
"""

    section_lundi = ""
    if est_lundi:
        section_lundi = """
**Dividendes de la semaine** (section lundi uniquement)
Identifie parmi les valeurs les plus connues celles susceptibles de détacher un dividende cette semaine.
| Valeur | Date estimée | Montant estimé | Rendement |
|--------|-------------|----------------|-----------|
"""

    return f"""Tu es un agent trader IA expert en analyse technique et fondamentale.
Tu es l'assistant personnel d'Arnaud, investisseur débutant avec un PEA (niveau débutant, mise modeste).
Nous sommes le {jour} {today.strftime('%d/%m/%Y')}.

## Données de marché temps réel

{indice_txt}

{bloc_donnees}

{perf_txt}

## Tes instructions

1. Analyse UNIQUEMENT les données réelles fournies ci-dessus (cours, RSI, MACD, moyennes mobiles, Bollinger, news)
2. Donne des signaux ACHETER / SURVEILLER / ÉVITER basés sur les indicateurs, pas sur tes connaissances générales
3. Quand RSI < 30 + MACD haussier = signal fort ACHETER
4. Quand RSI > 70 + MACD baissier = signal fort ÉVITER
5. Croise toujours au moins 2 indicateurs avant de donner un signal fort
6. Sois honnête quand les signaux sont contradictoires : dis SURVEILLER
7. Adapte-toi à ta performance passée : si tu t'es trompé sur un secteur, sois plus prudent

## Format de sortie STRICT

---

**BRIEFING BOURSE — {jour.capitalize()} {today.strftime('%d/%m/%Y')}**

**{indice_txt}**

**Contexte du jour**
[3-4 lignes : analyse des tendances observées dans les données réelles, secteurs qui surperforment/sous-performent]

**Signal ETFs long terme : [FAVORABLE / NEUTRE / ATTENDRE]**
[Justification basée sur les données]

**Taux de précision de l'agent : {perf_stats['precision']}% ({perf_stats['total']} signaux évalués)**
[Si historique disponible : 1-2 lignes sur les ajustements faits aujourd'hui]

{section_lundi}

**CAC 40 par secteur**

| Valeur | Cours | Var% | RSI | MACD | Signal | Raison |
|--------|-------|------|-----|------|--------|--------|
[Une ligne par valeur avec les vraies données]

**Top 3 opportunités du jour**
1. **[Valeur]** — RSI=[X], MACD=[X] : [justification technique en 1 ligne]
2. **[Valeur]** — RSI=[X], MACD=[X] : [justification technique en 1 ligne]
3. **[Valeur]** — RSI=[X], MACD=[X] : [justification technique en 1 ligne]

**Rappel** : Ce briefing est informatif. Tu prends tes propres décisions d'investissement.

---

Pas de tirets longs (em dashes). Données réelles uniquement."""


# ─── MISE EN FORME HTML ───────────────────────────────────────────────────────

def markdown_vers_html(texte):
    lignes = texte.split("\n")
    html   = []
    tableau_ouvert = False

    for ligne in lignes:
        if re.match(r"^\|[-| :]+\|$", ligne):
            continue

        if ligne.startswith("|") and ligne.endswith("|"):
            cellules = [c.strip() for c in ligne.strip("|").split("|")]

            if not tableau_ouvert:
                html.append("<table style='border-collapse:collapse;width:100%;font-size:12px;margin:12px 0;'>")
                html.append("<thead style='background:#1a1a2e;color:white;'>")
                tableau_ouvert = True
                balise = "th"
            else:
                balise = "td"

            style = ""
            ligne_str = " ".join(cellules)
            if "ACHETER" in ligne_str:
                style = "background:#e8f5e9;"
            elif "ÉVITER" in ligne_str:
                style = "background:#ffebee;"

            non_vides = [c for c in cellules if c]
            if len(non_vides) == 1 and balise == "td":
                html.append(f"<tr><td colspan='7' style='padding:5px 8px;font-weight:bold;"
                            f"background:#2c3e50;color:white;font-size:11px;'>{non_vides[0]}</td></tr>")
                continue

            cells_html = "".join(
                f"<{balise} style='padding:5px 8px;border-bottom:1px solid #ddd;'>{c}</{balise}>"
                for c in cellules
            )
            if balise == "th":
                html.append(f"<tr>{cells_html}</tr></thead><tbody>")
            else:
                html.append(f"<tr style='{style}'>{cells_html}</tr>")
            continue

        if tableau_ouvert:
            html.append("</tbody></table>")
            tableau_ouvert = False

        ligne = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", ligne)

        if ligne.strip() == "":
            html.append("<br>")
        elif ligne.strip() == "---":
            html.append("<hr style='border:1px solid #ddd;margin:8px 0;'>")
        else:
            html.append(f"<p style='margin:3px 0;'>{ligne}</p>")

    if tableau_ouvert:
        html.append("</tbody></table>")

    return "\n".join(html)


def envoyer_email(briefing, perf_stats):
    today = datetime.date.today()
    precision = perf_stats.get("precision", 0)
    sujet = f"Briefing Bourse — {today.strftime('%d/%m/%Y')} | Précision agent : {precision}%"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = sujet
    msg["From"]    = ZOHO_EMAIL
    msg["To"]      = ", ".join(DESTINATAIRES)

    msg.attach(MIMEText(briefing, "plain", "utf-8"))

    contenu = markdown_vers_html(briefing)
    html = f"""<html><body style='font-family:Arial,sans-serif;font-size:13px;
color:#222;max-width:900px;margin:auto;padding:20px;'>
<div style='background:#1a1a2e;color:white;padding:16px 20px;border-radius:8px 8px 0 0;'>
  <h2 style='margin:0;font-size:18px;'>Briefing Bourse — {today.strftime('%d/%m/%Y')}</h2>
  <p style='margin:6px 0 0;font-size:12px;opacity:0.8;'>
    Données temps réel Yahoo Finance + analyse technique RSI/MACD/Bollinger
    | Précision agent : <strong>{precision}%</strong>
  </p>
</div>
<div style='border:1px solid #ddd;border-top:none;padding:20px;border-radius:0 0 8px 8px;'>
{contenu}
</div>
</body></html>"""

    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP(ZOHO_SMTP, ZOHO_PORT) as serveur:
        serveur.starttls()
        serveur.login(ZOHO_EMAIL, ZOHO_PASSWORD)
        serveur.sendmail(ZOHO_EMAIL, DESTINATAIRES, msg.as_string())

    print(f"Email envoyé à : {', '.join(DESTINATAIRES)}")


# ─── MAIN ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    today    = datetime.date.today()
    est_lundi = today.weekday() == 0

    print("Chargement de l'historique de performance...")
    perf = charger_performance()

    print("Récupération du CAC 40...")
    cac_cours, cac_var = recuperer_indice_cac()

    print("Récupération des données temps réel...")
    donnees = []
    for nom, ticker in CAC40.items():
        print(f"  {nom} ({ticker})...")
        d = recuperer_donnees_action(nom, ticker)
        if d:
            donnees.append(d)

    ok    = [d for d in donnees if "erreur" not in d]
    erreurs = [d for d in donnees if "erreur" in d]
    print(f"Données OK : {len(ok)}/39 | Erreurs : {len(erreurs)}")

    print("Évaluation de la performance hier...")
    perf, perf_resume = evaluer_performance_hier(perf, donnees)

    print("Génération du briefing par Claude...")
    prompt  = construire_prompt(donnees, cac_cours, cac_var, perf_resume, perf["stats"], est_lundi)
    briefing = None
    client  = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    message = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}]
    )
    briefing = message.content[0].text

    print("Sauvegarde des recommandations pour suivi...")
    sauvegarder_recommandations(perf, donnees, briefing)

    print("Envoi par email...")
    envoyer_email(briefing, perf["stats"])

    print("Terminé.")
