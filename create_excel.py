from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side, PatternFill
from openpyxl.utils import get_column_letter

wb = Workbook()

# ─── COULEURS ───────────────────────────────────────────────────────────────
TEAL       = "1A7A6E"
TEAL_LIGHT = "E8F5F3"
ORANGE     = "E67E22"
ORANGE_LT  = "FEF3E2"
GRAY       = "F5F5F5"
GRAY2      = "DDDDDD"
WHITE      = "FFFFFF"
GREEN      = "27AE60"
GREEN_LT   = "EAFAF1"
RED        = "C0392B"
RED_LT     = "FDEDEC"
YELLOW     = "F9E79F"

def side(color="DDDDDD"): return Side(style="thin", color=color)
def border(color="DDDDDD"): return Border(left=side(color), right=side(color), top=side(color), bottom=side(color))
def fill(color): return PatternFill("solid", fgColor=color)
def font(bold=False, color="000000", size=10, italic=False): return Font(name="Arial", bold=bold, color=color, size=size, italic=italic)
def align(h="left", v="center", wrap=False): return Alignment(horizontal=h, vertical=v, wrap_text=wrap)

def style(cell, bg=None, bold=False, color="000000", size=10, h="left", wrap=False, italic=False, border_color="DDDDDD"):
    if bg: cell.fill = fill(bg)
    cell.font = font(bold=bold, color=color, size=size, italic=italic)
    cell.alignment = align(h=h, wrap=wrap)
    cell.border = border(border_color)

# ══════════════════════════════════════════════════════════════════════════
# FEUILLE 1 — LISTE DE MATÉRIAUX
# ══════════════════════════════════════════════════════════════════════════
ws1 = wb.active
ws1.title = "Liste Matériaux"

ws1.column_dimensions["A"].width = 40
ws1.column_dimensions["B"].width = 22
ws1.column_dimensions["C"].width = 12
ws1.column_dimensions["D"].width = 10

# Titre principal
ws1.merge_cells("A1:D1")
c = ws1["A1"]
c.value = "LISTE DE MATÉRIAUX — Piscine Magnelis Océane"
style(c, bg=TEAL, bold=True, color=WHITE, size=14, h="center")
ws1.row_dimensions[1].height = 30

ws1.merge_cells("A2:D2")
c = ws1["A2"]
c.value = "⚠️  Quantités à adapter selon la dimension exacte de votre bassin (voir tableau page 5 de la notice)"
style(c, bg=ORANGE_LT, color=ORANGE, size=10, italic=True, h="center")
ws1.row_dimensions[2].height = 20

def section_header(ws, row, title):
    ws.merge_cells(f"A{row}:D{row}")
    c = ws[f"A{row}"]
    c.value = title
    style(c, bg=TEAL_LIGHT, bold=True, color=TEAL, size=11)
    ws.row_dimensions[row].height = 22

def col_headers(ws, row):
    headers = ["Matériau / Référence", "Quantité / Note", "Unité", "✅ Acheté"]
    cols = ["A", "B", "C", "D"]
    for col, h in zip(cols, headers):
        c = ws[f"{col}{row}"]
        c.value = h
        style(c, bg=GRAY, bold=True, color="555555", size=10, h="center")
    ws.row_dimensions[row].height = 18

def row_item(ws, row, mat, qty, unit, alt=False):
    bg = GRAY if alt else WHITE
    data = [mat, qty, unit, "☐"]
    cols = ["A", "B", "C", "D"]
    for col, val in zip(cols, data):
        c = ws[f"{col}{row}"]
        c.value = val
        h = "center" if col in ["C", "D"] else "left"
        style(c, bg=bg, size=10, h=h, wrap=(col=="A"))
    ws.row_dimensions[row].height = 16

row = 3

# ─── GROS OEUVRE ─────────────────────────────────────────────────────────
section_header(ws1, row, "🏗️  GROS OEUVRE"); row += 1
col_headers(ws1, row); row += 1
items = [
    ("Mini-pelle (location)", "1 journée", "loc."),
    ("Béton dosé 350 kg/m3", "Selon volume dalle", "m³"),
    ("Treillis soudé (dalle)", "Selon surface dalle", "m²"),
    ("Cales béton (surélever treillis)", "~10", "pièces"),
    ("Gravier concassé petite granulométrie (remblai périmétrie)", "Selon volume", "m³"),
    ("Ciment ceinture béton", "Selon volume", "sacs"),
    ("Treillis soudé ceinture béton", "Selon périmètre", "ml"),
    ("Mortier de scellement bonde", "1", "sac"),
    ("Scotch de protection bonde", "1", "rouleau"),
]
for i, (m, q, u) in enumerate(items):
    row_item(ws1, row, m, q, u, alt=(i%2==0)); row += 1

# ─── STRUCTURE PISCINE ───────────────────────────────────────────────────
ws1.row_dimensions[row].height = 6; row += 1
section_header(ws1, row, "🔩  STRUCTURE PISCINE (fourni dans le kit — à vérifier à réception)"); row += 1
col_headers(ws1, row); row += 1
items = [
    ("Panneaux plein 1m", "Voir tableau page 5 notice", "pièces"),
    ("Panneau Skimmer", "Voir tableau page 5 notice", "pièces"),
    ("Panneau Buse", "Voir tableau page 5 notice", "pièces"),
    ("Panneau plein 50 cm", "Voir tableau page 5 notice", "pièces"),
    ("Équerre d'angle", "4", "pièces"),
    ("Jambes de force", "Voir tableau page 5 notice", "pièces"),
    ("Rail PVC 240 cm", "Voir tableau page 5 notice", "pièces"),
    ("Panneau A", "2", "pièces"),
    ("Panneau B", "2", "pièces"),
    ("Profil accrochage Hung (liner)", "Selon périmètre", "ml"),
]
for i, (m, q, u) in enumerate(items):
    row_item(ws1, row, m, q, u, alt=(i%2==0)); row += 1

# ─── VISSERIE ─────────────────────────────────────────────────────────────
ws1.row_dimensions[row].height = 6; row += 1
section_header(ws1, row, "🔧  VISSERIE (fourni dans le kit — à vérifier à réception)"); row += 1
col_headers(ws1, row); row += 1
items = [
    ("Vis TH Fil Tot M10x25 IX A2", "Voir tableau page 5", "pièces"),
    ("Écrou HU M10 INOX A2", "Voir tableau page 5", "pièces"),
    ("Rondelle plate MOY M10 IX A2", "Voir tableau page 5", "pièces"),
    ("Tirefond TH 10x60 INOX A2", "Voir tableau page 5", "pièces"),
    ("Cheville nylon S12", "Voir tableau page 5", "pièces"),
    ("Cheville M12x50", "Voir tableau page 5", "pièces"),
    ("Tirefond M10x50", "Voir tableau page 5", "pièces"),
    ("Rondelle M10", "Voir tableau page 5", "pièces"),
    ("Vis autoforeuse", "Voir tableau page 5", "pièces"),
    ("Rondelles d'étanchéité panneaux A et B", "12", "pièces"),
]
for i, (m, q, u) in enumerate(items):
    row_item(ws1, row, m, q, u, alt=(i%2==0)); row += 1

# ─── PLOMBERIE ────────────────────────────────────────────────────────────
ws1.row_dimensions[row].height = 6; row += 1
section_header(ws1, row, "🚿  PLOMBERIE"); row += 1
col_headers(ws1, row); row += 1
items = [
    ("Bonde de fond", "1", "pièce"),
    ("Tuyau souple PVC (liaison piscine/local technique)", "Selon distance", "ml"),
    ("Tuyau rigide PVC", "Selon plan", "ml"),
    ("Coude PVC grand rayon", "~6 à 8", "pièces"),
    ("T PVC", "2 à 3", "pièces"),
    ("Colle PVC", "2", "tubes"),
    ("Décapant PVC", "1", "flacon"),
    ("Mastic-colle", "1", "tube"),
    ("Embout fileté", "1", "pièce"),
    ("Skimmer insertion", "1", "pièce"),
    ("Buse de refoulement", "Selon bassin", "pièces"),
    ("Prise balai", "1", "pièce"),
    ("Joint buse de refoulement", "Selon nb buses", "pièces"),
    ("Joint skimmer", "1", "pièce"),
    ("Boîte de connexion projecteur", "1", "pièce"),
    ("PVC courbe grand rayon (projecteur)", "1", "pièce"),
]
for i, (m, q, u) in enumerate(items):
    row_item(ws1, row, m, q, u, alt=(i%2==0)); row += 1

# ─── FILTRATION ───────────────────────────────────────────────────────────
ws1.row_dimensions[row].height = 6; row += 1
section_header(ws1, row, "⚙️  FILTRATION"); row += 1
col_headers(ws1, row); row += 1
items = [
    ("Pompe", "1", "pièce"),
    ("Filtre à sable", "1", "pièce"),
    ("Sable de filtration", "Selon filtre", "kg"),
    ("Vanne 6 voies", "1", "pièce"),
    ("Manomètre", "1", "pièce"),
]
for i, (m, q, u) in enumerate(items):
    row_item(ws1, row, m, q, u, alt=(i%2==0)); row += 1

# ─── ELECTRICITE ──────────────────────────────────────────────────────────
ws1.row_dimensions[row].height = 6; row += 1
section_header(ws1, row, "⚡  ÉLECTRICITÉ"); row += 1
col_headers(ws1, row); row += 1
items = [
    ("Coffret électrique", "1", "pièce"),
    ("Disjoncteur différentiel 30 mA", "1", "pièce"),
    ("Câble 3 fils 1,5 mm² (alimentation pompe)", "Selon distance", "ml"),
    ("Câble 2 conducteurs min. 16 mm² (projecteur)", "Selon distance", "ml"),
    ("Transformateur projecteur", "1", "pièce"),
    ("Projecteur LED immergé", "1", "pièce"),
    ("Tire-fil d'électricien", "1", "pièce"),
]
for i, (m, q, u) in enumerate(items):
    row_item(ws1, row, m, q, u, alt=(i%2==0)); row += 1

# ─── LINER ET FEUTRE ──────────────────────────────────────────────────────
ws1.row_dimensions[row].height = 6; row += 1
section_header(ws1, row, "🟦  LINER ET FEUTRE"); row += 1
col_headers(ws1, row); row += 1
items = [
    ("Liner (aux dimensions du bassin)", "1", "pièce"),
    ("Feutre géotextile protection liner", "Selon surface parois", "m²"),
    ("Colle à feutre", "2 à 3", "bombes"),
]
for i, (m, q, u) in enumerate(items):
    row_item(ws1, row, m, q, u, alt=(i%2==0)); row += 1

# ─── FINITIONS ────────────────────────────────────────────────────────────
ws1.row_dimensions[row].height = 6; row += 1
section_header(ws1, row, "🏁  FINITIONS"); row += 1
col_headers(ws1, row); row += 1
items = [
    ("Margelles grès cérame", "Selon périmètre", "m²"),
    ("Colle spéciale margelle extérieure", "Selon surface", "sacs"),
    ("Joint carrelage extérieur", "Selon joints", "sacs"),
]
for i, (m, q, u) in enumerate(items):
    row_item(ws1, row, m, q, u, alt=(i%2==0)); row += 1

# ─── TRAITEMENT EAU ───────────────────────────────────────────────────────
ws1.row_dimensions[row].height = 6; row += 1
section_header(ws1, row, "💧  TRAITEMENT DE L'EAU (mise en route)"); row += 1
col_headers(ws1, row); row += 1
items = [
    ("Chlore choc (démarrage)", "1", "kg"),
    ("pH+", "1", "kg"),
    ("pH-", "1", "kg"),
    ("Anti-algues préventif", "1", "L"),
    ("Testeur pH / chlore", "1", "pièce"),
]
for i, (m, q, u) in enumerate(items):
    row_item(ws1, row, m, q, u, alt=(i%2==0)); row += 1

# ══════════════════════════════════════════════════════════════════════════
# FEUILLE 2 — PLANNING
# ══════════════════════════════════════════════════════════════════════════
ws2 = wb.create_sheet("Planning")

ws2.column_dimensions["A"].width = 18
ws2.column_dimensions["B"].width = 35
ws2.column_dimensions["C"].width = 22
ws2.column_dimensions["D"].width = 14
ws2.column_dimensions["E"].width = 12

# Titre
ws2.merge_cells("A1:E1")
c = ws2["A1"]
c.value = "PLANNING MONTAGE — Piscine Magnelis Océane"
style(c, bg=TEAL, bold=True, color=WHITE, size=14, h="center")
ws2.row_dimensions[1].height = 30

ws2.merge_cells("A2:E2")
c = ws2["A2"]
c.value = "⏱  Durée totale estimée : 5 à 6 semaines (6 jours de travail effectif + temps de séchage)"
style(c, bg=ORANGE_LT, color=ORANGE, size=10, italic=True, h="center")
ws2.row_dimensions[2].height = 20

# En-têtes colonnes
row = 3
headers = ["Phase / Jour", "Tâche", "Étape(s)", "Durée estimée", "✅ Fait"]
cols = ["A", "B", "C", "D", "E"]
for col, h in zip(cols, headers):
    c = ws2[f"{col}{row}"]
    c.value = h
    style(c, bg=GRAY, bold=True, color="555555", size=10, h="center")
ws2.row_dimensions[row].height = 20
row += 1

def phase_row(ws, row, title, color_bg, color_txt):
    ws.merge_cells(f"A{row}:E{row}")
    c = ws[f"A{row}"]
    c.value = title
    style(c, bg=color_bg, bold=True, color=color_txt, size=11)
    ws.row_dimensions[row].height = 22

def pause_row(ws, row, text):
    ws.merge_cells(f"A{row}:E{row}")
    c = ws[f"A{row}"]
    c.value = text
    style(c, bg=YELLOW, bold=True, color=RED, size=10, h="center")
    ws.row_dimensions[row].height = 22

def task_row(ws, row, jour, tache, etapes, duree, alt=False):
    bg = GRAY if alt else WHITE
    data = [jour, tache, etapes, duree, "☐"]
    cols_list = ["A", "B", "C", "D", "E"]
    for col, val in zip(cols_list, data):
        c = ws[f"{col}{row}"]
        c.value = val
        h = "center" if col in ["A", "D", "E"] else "left"
        style(c, bg=bg, size=10, h=h, wrap=(col=="B"))
    ws.row_dimensions[row].height = 16

# ─── PHASE 1 ──────────────────────────────────────────────────────────────
phase_row(ws2, row, "PHASE 1 — GÉNIE CIVIL", TEAL_LIGHT, TEAL); row += 1
task_row(ws2, row, "Jour 1 – Matin", "Terrassement (mini-pelle)", "Étape 01", "1 demi-journée"); row += 1
task_row(ws2, row, "Jour 1 – Après-midi", "Mise en place bonde de fond et canalisation", "Étape 02", "1h", alt=True); row += 1
task_row(ws2, row, "Jour 1 – Après-midi", "Mise en place treillis soudé", "Étape 03", "1h"); row += 1
task_row(ws2, row, "Jour 2", "Coulage dalle béton", "Étape 04", "1 journée", alt=True); row += 1
pause_row(ws2, row, "⏸  PAUSE SÉCHAGE DALLE — 15 à 20 jours obligatoires avant de reprendre"); row += 1

ws2.row_dimensions[row].height = 8; row += 1

# ─── PHASE 2 ──────────────────────────────────────────────────────────────
phase_row(ws2, row, "PHASE 2 — MONTAGE STRUCTURE (2 jours, à 2 personnes)", TEAL_LIGHT, TEAL); row += 1
task_row(ws2, row, "Jour 3 – Matin", "Traçage au sol", "Étape 05", "30 min"); row += 1
task_row(ws2, row, "Jour 3 – Matin", "Montage des panneaux", "Étape 06", "3 à 4h", alt=True); row += 1
task_row(ws2, row, "Jour 3 – Matin", "Fixation au sol", "Étape 07", "1h30"); row += 1
task_row(ws2, row, "Jour 3 – Après-midi", "Fixation jambes de force", "Étape 08", "2h", alt=True); row += 1
task_row(ws2, row, "Jour 3 – Après-midi", "Montage profilés fixation liner", "Étape 09", "1h"); row += 1
task_row(ws2, row, "Jour 3 – Après-midi", "Pose du skimmer", "Étape 10", "30 min", alt=True); row += 1
task_row(ws2, row, "Jour 3 – Après-midi", "Pose des pièces à sceller (buses, prise balai)", "Étape 11", "30 min"); row += 1
task_row(ws2, row, "Jour 4 – Matin", "Montage passe câble projecteur", "Étape 12", "30 min", alt=True); row += 1
task_row(ws2, row, "Jour 4 – Matin", "Raccordement buses à la pompe", "Étape 13", "2h"); row += 1
task_row(ws2, row, "Jour 4 – Matin", "Raccordement local technique  ⚡ électricien présent", "Étape 14", "2h", alt=True); row += 1
task_row(ws2, row, "Jour 4 – Après-midi", "Pose du feutre", "Étape 15", "1h30"); row += 1
task_row(ws2, row, "Jour 4 – Après-midi", "Pose des joints des pièces à sceller", "Étape 16", "30 min", alt=True); row += 1
task_row(ws2, row, "Jour 4 – Après-midi", "Positionnement du liner", "Étape 17", "1h"); row += 1
task_row(ws2, row, "Jour 4 – Après-midi", "Fixation du liner", "Étape 18", "1h", alt=True); row += 1
task_row(ws2, row, "Jour 4 – Fin de journée", "Bridage bonde de fond", "Étape 19", "30 min"); row += 1

ws2.row_dimensions[row].height = 8; row += 1

# ─── PHASE 3 ──────────────────────────────────────────────────────────────
phase_row(ws2, row, "PHASE 3 — REMPLISSAGE ET FINITIONS", TEAL_LIGHT, TEAL); row += 1
task_row(ws2, row, "Jour 5 – Journée", "Remblai simultané au remplissage (surveiller en continu)", "Étape 20", "Demi-journée", alt=True); row += 1
task_row(ws2, row, "Jour 5", "Bridage des pièces à sceller (buses + skimmer)", "Étape 21", "1h"); row += 1
task_row(ws2, row, "Jour 5", "Montage du projecteur", "Étape 22", "30 min", alt=True); row += 1
task_row(ws2, row, "Jour 5 – Fin", "Remplissage final du bassin (gravier arrêté à 20 cm du haut)", "Étape 23", "Selon volume"); row += 1
task_row(ws2, row, "Jour 6 – Matin", "Ceinture béton (coffrage + coulage)", "Étape 24", "1 journée", alt=True); row += 1
pause_row(ws2, row, "⏸  PAUSE SÉCHAGE CEINTURE BÉTON — 7 jours minimum"); row += 1
task_row(ws2, row, "Jour 7", "Fixation margelles d'habillage", "Étape 25", "1 journée"); row += 1
pause_row(ws2, row, "⏸  SÉCHAGE COLLE MARGELLES — 48h avant utilisation"); row += 1

ws2.row_dimensions[row].height = 8; row += 1

# ─── MISE EN ROUTE EAU ────────────────────────────────────────────────────
phase_row(ws2, row, "MISE EN ROUTE DE L'EAU (après remplissage complet)", GREEN_LT, GREEN); row += 1
tasks_eau = [
    ("Après remplissage", "Amorcer la pompe et lancer un cycle de filtration", "—", "30 min"),
    ("", "Vérifier l'absence de fuites sur tous les raccords", "—", "30 min"),
    ("", "Mesurer le pH initial et ajuster (cible 7,2 à 7,4)", "—", "30 min"),
    ("", "Traitement choc chlore au démarrage", "—", "15 min"),
    ("", "Ajouter anti-algues préventif", "—", "15 min"),
    ("", "Laisser filtrer 24h avant première baignade !", "—", "24h"),
]
for i, (j, t, e, d) in enumerate(tasks_eau):
    task_row(ws2, row, j, t, e, d, alt=(i%2==0)); row += 1

ws2.row_dimensions[row].height = 8; row += 1

# ─── RECAP ────────────────────────────────────────────────────────────────
phase_row(ws2, row, "RÉCAPITULATIF DES DÉLAIS", GRAY, "333333"); row += 1
recap_headers = ["Phase", "Jours de travail", "Attente / Séchage", "Total phase", ""]
for col, h in zip(["A", "B", "C", "D", "E"], recap_headers):
    c = ws2[f"{col}{row}"]
    c.value = h
    style(c, bg=GRAY, bold=True, color="555555", size=10, h="center")
ws2.row_dimensions[row].height = 18; row += 1

recap_data = [
    ("Génie civil", "2 jours", "15-20 jours (dalle)", "~3 semaines"),
    ("Montage structure", "2 jours", "Aucune", "2 jours"),
    ("Remplissage + finitions", "2-3 jours", "7 j (ceinture) + 48h (margelles)", "~10 jours"),
    ("TOTAL", "~6 jours de travail", "~4 semaines d'attente", "5 à 6 semaines"),
]
for i, (p, j, a, t) in enumerate(recap_data):
    alt = (i % 2 == 0)
    is_total = (i == 3)
    bg = TEAL_LIGHT if is_total else (GRAY if alt else WHITE)
    bold = is_total
    for col, val in zip(["A", "B", "C", "D"], [p, j, a, t]):
        c = ws2[f"{col}{row}"]
        c.value = val
        style(c, bg=bg, bold=bold, color=TEAL if is_total else "333333", size=10, h="center")
    c = ws2[f"E{row}"]
    style(c, bg=bg, size=10)
    ws2.row_dimensions[row].height = 18; row += 1

wb.save("/Users/arnaudkuntz/Downloads/Piscine_Oceane_Materiaux_Planning.xlsx")
print("✅ Excel créé : Piscine_Oceane_Materiaux_Planning.xlsx")
