#!/usr/bin/env python3
"""
Sentinelle Look-Ahead — garde-fou anti-biais temporel (ajout du 01/11).

Origine (recherche du 01/11, rapport "Super agents et compétences bourse") :
aucun système multi-agent financier documenté dans la littérature académique
recensée n'intègre d'agent anti-look-ahead bias dans la construction même de
la stratégie — une étude indépendante montre que ce seul biais (utiliser des
données comptables révisées ou non encore publiées à la date simulée) peut
gonfler un backtest de +2,98 points de CAGR sur un screening fondamental, et
faire disparaître entièrement un edge mesuré une fois les coûts réalistes
ajoutés. Les prix (OHLC) ne sont pas concernés de la même façon (la clôture
du jour J est connue dès J) ; le risque concerne spécifiquement les données
FONDAMENTALES et de CONSENSUS (ROE, marges, dette, recommandations
analystes), qui reflètent l'état ACTUEL au moment où on les interroge, pas
l'état qu'on aurait connu à une date passée.

Deux usages :
  1. verifier_lag_publication() — garde-fou réutilisable pour tout futur
     backtest qui voudrait utiliser des données fondamentales sur des dates
     passées (ex. historiciser le Screener Fondamental CAC40 un jour).
  2. auditer_usage_fondamentaux() — audit du dépôt : liste les scripts qui
     touchent des champs fondamentaux/consensus (yfinance .info) et les
     confronte à un registre de verdicts déjà établis. Un nouveau fichier
     non recensé est signalé "À VÉRIFIER", jamais classé automatiquement
     "sûr" par défaut. Appelé par agent_watchdog.py à chaque passage.

Audit du 01/11 (baseline) : 3 fichiers touchent ces champs, tous vérifiés
sûrs — briefing_bourse_v3.py et scoring_intraday.py les utilisent pour une
décision LIVE sur la date du jour (pas de simulation du passé, donc pas de
look-ahead possible par construction) ; selection_qm.py les utilise mais
neutralise explicitement la porte qualité en mode backtest (infos_par_nom=
None), précisément pour éviter ce biais — décision prise le 23/08, avant que
ce module n'existe. Rien à corriger, l'audit confirme une discipline déjà
bonne.
"""

import glob
import re

# Champs dont la valeur "actuelle" (yfinance .info) ne doit jamais être
# traitée comme connue à une date passée dans un backtest.
CHAMPS_RISQUE = [
    r"\.info\[", r"\.info\.get\(",
    r"recommendationMean", r"targetMeanPrice",
    r"returnOnEquity", r"freeCashflow",
    r"grossMargins", r"profitMargins",
]

# Registre des verdicts déjà établis (audit du 01/11). Un fichier absent de
# ce registre est signalé "À VÉRIFIER", jamais classé sûr par défaut.
FICHIERS_AUDITES = {
    "briefing_bourse_v3.py": "SÛR — usage live (décision sur la date du jour, pas de simulation du passé).",
    "scoring_intraday.py":   "SÛR — usage live (décision sur la date du jour, pas de simulation du passé).",
    "selection_qm.py":       "SÛR — porte qualité explicitement neutralisée en mode backtest "
                             "(infos_par_nom=None), décision du 23/08, confirmée le 01/11.",
    "agent_screener_fondamental.py": "SÛR — usage live (score du jour sur données du jour, aucune "
                             "simulation de date passée). Si historicisé un jour pour un backtest, "
                             "passer par verifier_lag_publication() avant d'utiliser une donnée "
                             "fondamentale comme connue à une date donnée.",
}


def verifier_lag_publication(date_simulee, date_publication_connue, lag_jours_min=45):
    """Garde-fou pour un futur backtest sur données fondamentales : refuse
    d'utiliser une donnée publiée après (date_simulee - lag_jours_min), le
    délai de publication réel des comptes trimestriels/annuels n'étant pas
    instantané. Dates au format ISO (YYYY-MM-DD) ou datetime.date.
    Retourne (ok: bool, message: str)."""
    import datetime as _dt

    def _d(x):
        if isinstance(x, str):
            return _dt.date.fromisoformat(x)
        return x

    ds, dp = _d(date_simulee), _d(date_publication_connue)
    ecart = (ds - dp).days
    if ecart < lag_jours_min:
        return False, (f"Donnée publiée le {dp} utilisée pour simuler le {ds} "
                        f"({ecart} j d'écart, minimum {lag_jours_min} j) : risque de look-ahead.")
    return True, f"OK — {ecart} j entre publication ({dp}) et simulation ({ds})."


def auditer_usage_fondamentaux(repertoire="."):
    """Scanne les .py du dépôt pour l'usage de champs fondamentaux/consensus,
    confronte à FICHIERS_AUDITES. Retourne un dict {fichier: verdict}."""
    motif = re.compile("|".join(CHAMPS_RISQUE))
    resultats = {}
    for chemin in sorted(glob.glob(f"{repertoire}/*.py")):
        nom = chemin.split("/")[-1]
        if nom in ("lookahead_guard.py", "test_agents.py"):
            continue
        try:
            with open(chemin, "r", encoding="utf-8") as f:
                contenu = f.read()
        except Exception:
            continue
        if motif.search(contenu):
            resultats[nom] = FICHIERS_AUDITES.get(
                nom, "À VÉRIFIER — fichier non recensé, usage non audité.")
    return resultats


if __name__ == "__main__":
    print("Audit look-ahead — usage de données fondamentales/consensus dans le dépôt :")
    resultats = auditer_usage_fondamentaux()
    for fichier, verdict in resultats.items():
        print(f"  {fichier:30} {verdict}")
    a_verifier = [f for f, v in resultats.items() if v.startswith("À VÉRIFIER")]
    if a_verifier:
        print(f"\n{len(a_verifier)} fichier(s) non audité(s) : {a_verifier}")
    else:
        print("\nAucun fichier non audité. Tous les usages connus sont vérifiés sûrs.")
