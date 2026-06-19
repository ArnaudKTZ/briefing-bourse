#!/usr/bin/env python3
"""
Briefing Bourse quotidien — envoi automatique par email
"""

import smtplib
import datetime
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import anthropic

# ─── CONFIGURATION ───────────────────────────────────────────────────────────

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "COLLE_TA_CLE_ICI")
ZOHO_EMAIL        = os.environ.get("ZOHO_EMAIL", "Arnaud.kuntz@zoho.eu")
ZOHO_PASSWORD     = os.environ.get("ZOHO_PASSWORD", "2a6xXFJMr4GN")
ZOHO_SMTP         = "smtp.zoho.eu"
ZOHO_PORT         = 587

DESTINATAIRES = [
    "xtrem111team@gmail.com",
    "ferrey83400@gmail.com",
]

# ─── PROMPT BRIEFING ─────────────────────────────────────────────────────────

def construire_prompt():
    today = datetime.date.today()
    jours = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
    jour = jours[today.weekday()]
    est_lundi = today.weekday() == 0

    section_dividendes = ""
    if est_lundi:
        section_dividendes = """
### 2. [LUNDI] Dividendes de la semaine

Recherche les valeurs du CAC 40 qui détachent un dividende cette semaine. Pour chacune :
- Date de détachement
- Montant
- Rendement approximatif

Format :
**Dividendes de la semaine**
| Valeur | Date détachement | Montant | Rendement |
|--------|-----------------|---------|-----------|

Si aucune cette semaine, indique-le en une ligne.
"""

    return f"""Tu es l'assistant personnel d'Arnaud, investisseur débutant avec un PEA.
Nous sommes le {jour} {today.strftime('%d/%m/%Y')}.

Génère un briefing bourse complet en français, tutoiement, direct et sans blabla.

## Les 40 valeurs du CAC 40 à analyser

LVMH, TotalEnergies, Hermès, Airbus, Schneider Electric, L'Oréal, Sanofi, BNP Paribas,
Air Liquide, Safran, Danone, Vinci, Kering, Société Générale, Stellantis, Saint-Gobain,
ArcelorMittal, Pernod Ricard, Michelin, Capgemini, Renault, Legrand, Publicis, Bouygues,
Engie, Orange, Vivendi, Eurofins Scientific, Teleperformance, Alstom, Worldline, Veolia,
STMicroelectronics, Dassault Systèmes, Edenred, Accor, Eurazeo, Thales, Forvia, Compagnie de Saint-Gobain.

## Structure du briefing

---

**BRIEFING BOURSE — {jour.capitalize()} {today.strftime('%d/%m/%Y')}**

**Contexte macro**
[3-4 lignes : indices, BCE/Fed, géopolitique, sentiment de marché]

**Signal ETFs long terme : [FAVORABLE / NEUTRE / ATTENDRE]**
[2-3 lignes : DCA cette semaine ou attendre ? ETFs visés : CW8, CAC 40, S&P 500 éligibles PEA]
{section_dividendes}
**CAC 40 par secteur**

| Valeur | Tendance | Signal | Note rapide |
|--------|----------|--------|-------------|
[Regroupe par secteur : Luxe, Énergie, Industrie/Défense, Banques, Santé, Tech, Télécom/Média, Conso/Autre]
[Signal = ACHETER / SURVEILLER / ÉVITER]

**Top 3 opportunités du jour**
1. [Valeur] — [justification 2 lignes max]
2. [Valeur] — [justification 2 lignes max]
3. [Valeur] — [justification 2 lignes max]

**Rappel** : Ce briefing est informatif. Tu prends tes propres décisions d'investissement.

---

Pas de tirets longs (em dashes) dans les réponses."""


# ─── GÉNÉRATION DU BRIEFING ───────────────────────────────────────────────────

def generer_briefing():
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    message = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=4096,
        messages=[{"role": "user", "content": construire_prompt()}]
    )
    return message.content[0].text


# ─── ENVOI EMAIL ─────────────────────────────────────────────────────────────

def markdown_vers_html(texte: str) -> str:
    import re
    lignes = texte.split("\n")
    html_lignes = []
    dans_tableau = False

    for ligne in lignes:
        # Ligne de séparation tableau (|---|---|)
        if re.match(r"^\|[-| :]+\|$", ligne):
            continue

        # Ligne de tableau
        if ligne.startswith("|") and ligne.endswith("|"):
            cellules = [c.strip() for c in ligne.strip("|").split("|")]
            if not dans_tableau:
                html_lignes.append(
                    "<table style='border-collapse:collapse;width:100%;font-size:13px;margin:12px 0;'>"
                    "<thead style='background:#1a1a2e;color:white;'>"
                )
                dans_tableau = True
                balise = "th"
            else:
                balise = "td"

            # Couleur selon signal
            style_ligne = ""
            ligne_str = " ".join(cellules)
            if "ACHETER" in ligne_str:
                style_ligne = "background:#e8f5e9;"
            elif "ÉVITER" in ligne_str:
                style_ligne = "background:#ffebee;"
            elif any(s in ligne_str for s in ["LVMH","TotalEnergies","Hermès","Airbus","Schneider",
                "L'Oréal","Sanofi","BNP","Air Liquide","Safran","Danone","Vinci","Kering",
                "Société Générale","Stellantis","Saint-Gobain","ArcelorMittal","Pernod",
                "Michelin","Capgemini","Renault","Legrand","Publicis","Bouygues","Engie",
                "Orange","Vivendi","Eurofins","Teleperformance","Alstom","Worldline","Veolia",
                "STMicro","Dassault","Edenred","Accor","Eurazeo","Thales","Forvia"]):
                style_ligne = "background:#ffffff;"

            # En-têtes de secteur (une seule cellule non vide)
            non_vides = [c for c in cellules if c]
            if len(non_vides) == 1 and balise == "td":
                html_lignes.append(
                    f"<tr><td colspan='4' style='padding:6px 8px;font-weight:bold;"
                    f"background:#2c3e50;color:white;font-size:12px;'>{non_vides[0]}</td></tr>"
                )
                continue

            cellules_html = "".join(
                f"<{balise} style='padding:6px 8px;border-bottom:1px solid #ddd;'>{c}</{balise}>"
                for c in cellules
            )
            if balise == "th":
                html_lignes.append(f"<tr>{cellules_html}</tr></thead><tbody>")
            else:
                html_lignes.append(f"<tr style='{style_ligne}'>{cellules_html}</tr>")
            continue

        # Fin de tableau
        if dans_tableau:
            html_lignes.append("</tbody></table>")
            dans_tableau = False

        # Titres **...**
        ligne = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", ligne)

        # Ligne vide
        if ligne.strip() == "":
            html_lignes.append("<br>")
        elif ligne.strip() == "---":
            html_lignes.append("<hr style='border:1px solid #ddd;margin:8px 0;'>")
        else:
            html_lignes.append(f"<p style='margin:4px 0;'>{ligne}</p>")

    if dans_tableau:
        html_lignes.append("</tbody></table>")

    return "\n".join(html_lignes)


def envoyer_email(briefing: str):
    today = datetime.date.today()
    sujet = f"Briefing Bourse — {today.strftime('%d/%m/%Y')}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = sujet
    msg["From"]    = ZOHO_EMAIL
    msg["To"]      = ", ".join(DESTINATAIRES)

    msg.attach(MIMEText(briefing, "plain", "utf-8"))

    contenu_html = markdown_vers_html(briefing)
    html = f"""<html><body style='font-family:Arial,sans-serif;font-size:14px;
color:#222;max-width:800px;margin:auto;padding:20px;'>
<div style='background:#1a1a2e;color:white;padding:16px 20px;border-radius:8px 8px 0 0;'>
  <h2 style='margin:0;font-size:18px;'>Briefing Bourse — {today.strftime('%d/%m/%Y')}</h2>
</div>
<div style='border:1px solid #ddd;border-top:none;padding:20px;border-radius:0 0 8px 8px;'>
{contenu_html}
</div>
</body></html>"""

    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP(ZOHO_SMTP, ZOHO_PORT) as serveur:
        serveur.starttls()
        serveur.login(ZOHO_EMAIL, ZOHO_PASSWORD)
        serveur.sendmail(ZOHO_EMAIL, DESTINATAIRES, msg.as_string())

    print(f"Briefing envoyé à : {', '.join(DESTINATAIRES)}")


# ─── MAIN ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Génération du briefing en cours...")
    briefing = generer_briefing()
    print("Envoi par email...")
    envoyer_email(briefing)
    print("Terminé.")
