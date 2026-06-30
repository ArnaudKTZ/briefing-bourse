#!/usr/bin/env python3
"""
test_agents.py — Vérification de santé du système Agent Bourse.

Vérifie :
  1. Syntaxe Python de tous les agents
  2. Cohérence pip install vs imports dans chaque workflow
  3. Secrets requis présents dans chaque workflow
  4. Fraîcheur des fichiers JSON produits par les agents

Usage :
  python test_agents.py
  python test_agents.py --strict   (code de retour 1 si erreur)
"""

import ast
import json
import os
import sys
import datetime

# ─── CONFIGURATION ────────────────────────────────────────────────────────────

AGENTS = [
    "briefing_bourse_v3.py",
    "scoring_intraday.py",
    "agent_professeur.py",
    "agent_watchdog.py",
    "agent_news.py",
    "agent_espion.py",
    "agent_dual_momentum.py",
    "agent_veille.py",
]

# Packages tiers connus (stdlib exclus)
PACKAGES_TIERS = {
    "anthropic", "yfinance", "pandas", "numpy", "ta", "requests", "bs4",
    "feedparser", "lxml", "openpyxl", "matplotlib", "scipy",
}

# Workflow → script principal
WORKFLOWS = {
    ".github/workflows/briefing_bourse.yml":   "briefing_bourse_v3.py",
    ".github/workflows/scoring_intraday.yml":  "scoring_intraday.py",
    ".github/workflows/professeur.yml":        "agent_professeur.py",
    ".github/workflows/agent_watchdog.yml":    "agent_watchdog.py",
    ".github/workflows/agent_news.yml":        "agent_news.py",
    ".github/workflows/agent_espion.yml":      "agent_espion.py",
    ".github/workflows/dual_momentum.yml":     "agent_dual_momentum.py",
    ".github/workflows/veille.yml":            "agent_veille.py",
}

# Secrets requis par agent (si l'agent envoie des emails ou appelle l'API)
SECRETS_REQUIS = {
    "briefing_bourse_v3.py":   {"ANTHROPIC_API_KEY", "ZOHO_EMAIL", "ZOHO_PASSWORD"},
    "scoring_intraday.py":     {"ANTHROPIC_API_KEY", "ZOHO_EMAIL", "ZOHO_PASSWORD"},
    "agent_professeur.py":     {"ZOHO_EMAIL", "ZOHO_PASSWORD"},
    "agent_watchdog.py":       {"ZOHO_EMAIL", "ZOHO_PASSWORD"},
    "agent_news.py":           set(),
    "agent_espion.py":         set(),
    "agent_dual_momentum.py":  {"ZOHO_EMAIL", "ZOHO_PASSWORD"},
    "agent_veille.py":         {"ZOHO_EMAIL", "ZOHO_PASSWORD"},
}

# JSON produits → fraîcheur max attendue en heures (None = pas vérifié)
JSON_FRAICHEUR = {
    "dernier_briefing.json":          26,
    "intraday_scores.json":           26,
    "rapport_news.json":              26,
    "dual_momentum_statut.json":      None,
    "portefeuille_virtuel.json":      26,
    "dual_momentum_portefeuille.json": 26,
    "professeur_rapport.json":        None,
}

# ─── HELPERS ──────────────────────────────────────────────────────────────────

OK   = "\033[32m✓\033[0m"
FAIL = "\033[31m✗\033[0m"
WARN = "\033[33m⚠\033[0m"

erreurs = []
avertissements = []

def ok(msg):    print(f"  {OK}  {msg}")
def fail(msg):  print(f"  {FAIL}  {msg}"); erreurs.append(msg)
def warn(msg):  print(f"  {WARN}  {msg}"); avertissements.append(msg)


def imports_tiers(fichier):
    """Retourne l'ensemble des packages tiers importés dans un fichier Python."""
    try:
        with open(fichier, encoding="utf-8") as f:
            tree = ast.parse(f.read())
    except SyntaxError:
        return set()
    pkgs = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                pkgs.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                pkgs.add(node.module.split(".")[0])
    return pkgs & PACKAGES_TIERS


def pip_packages(workflow):
    """Retourne les packages installés dans un workflow YAML."""
    pkgs = set()
    try:
        with open(workflow, encoding="utf-8") as f:
            for line in f:
                if "pip install" in line:
                    parts = line.split("pip install", 1)[1].split()
                    pkgs.update(p for p in parts if not p.startswith("-"))
    except FileNotFoundError:
        pass
    return pkgs


def secrets_workflow(workflow):
    """Retourne les secrets référencés dans un workflow YAML."""
    secrets = set()
    try:
        with open(workflow, encoding="utf-8") as f:
            for line in f:
                if "secrets." in line:
                    parts = line.split("secrets.")
                    for part in parts[1:]:
                        secret = part.split("}}")[0].split()[0].strip()
                        secrets.add(secret)
    except FileNotFoundError:
        pass
    return secrets


# ─── TEST 1 : SYNTAXE PYTHON ──────────────────────────────────────────────────

print("\n── 1. Syntaxe Python ──────────────────────────────────────────────")
for agent in AGENTS:
    if not os.path.exists(agent):
        warn(f"{agent} introuvable")
        continue
    try:
        with open(agent, encoding="utf-8") as f:
            source = f.read()
        ast.parse(source)
        ok(agent)
    except SyntaxError as e:
        fail(f"{agent} — erreur syntaxe ligne {e.lineno} : {e.msg}")


# ─── TEST 2 : PIP INSTALL vs IMPORTS ─────────────────────────────────────────

print("\n── 2. Cohérence pip install / imports ─────────────────────────────")
for workflow, script in WORKFLOWS.items():
    if not os.path.exists(script):
        warn(f"{script} introuvable — test ignoré")
        continue
    pkgs_installees = pip_packages(workflow)
    pkgs_utilisees  = imports_tiers(script)
    manquantes = pkgs_utilisees - pkgs_installees
    if manquantes:
        fail(f"{os.path.basename(workflow)} — packages manquants : {', '.join(sorted(manquantes))}")
    else:
        ok(f"{os.path.basename(workflow)} ({', '.join(sorted(pkgs_utilisees)) or 'stdlib only'})")


# ─── TEST 3 : SECRETS ────────────────────────────────────────────────────────

print("\n── 3. Secrets dans les workflows ───────────────────────────────────")
for workflow, script in WORKFLOWS.items():
    requis  = SECRETS_REQUIS.get(script, set())
    if not requis:
        ok(f"{os.path.basename(workflow)} — aucun secret requis")
        continue
    presents = secrets_workflow(workflow)
    manquants = requis - presents
    if manquants:
        fail(f"{os.path.basename(workflow)} — secrets manquants : {', '.join(sorted(manquants))}")
    else:
        ok(f"{os.path.basename(workflow)} — {', '.join(sorted(requis))}")


# ─── TEST 4 : FRAÎCHEUR DES JSON ─────────────────────────────────────────────

print("\n── 4. Fraîcheur des fichiers JSON ──────────────────────────────────")
maintenant = datetime.datetime.now()
for fichier, max_heures in JSON_FRAICHEUR.items():
    if not os.path.exists(fichier):
        warn(f"{fichier} absent (jamais produit ou pas encore exécuté)")
        continue
    mtime = datetime.datetime.fromtimestamp(os.path.getmtime(fichier))
    age_h = (maintenant - mtime).total_seconds() / 3600
    if max_heures is None:
        ok(f"{fichier} — présent (age {age_h:.0f}h, fraîcheur non contrôlée)")
    elif age_h > max_heures:
        warn(f"{fichier} — trop ancien ({age_h:.0f}h > {max_heures}h attendu)")
    else:
        ok(f"{fichier} — {age_h:.0f}h")


# ─── BILAN ────────────────────────────────────────────────────────────────────

print("\n── Bilan ───────────────────────────────────────────────────────────")
print(f"  {len(erreurs)} erreur(s)    {len(avertissements)} avertissement(s)")

if erreurs:
    print("\n  Erreurs à corriger :")
    for e in erreurs:
        print(f"    {FAIL}  {e}")

if avertissements:
    print("\n  Points à vérifier :")
    for a in avertissements:
        print(f"    {WARN}  {a}")

if not erreurs and not avertissements:
    print(f"\n  {OK}  Tout est OK.")

if "--strict" in sys.argv and erreurs:
    sys.exit(1)
