#!/usr/bin/env python3
"""
Test rétroactif du circuit-breaker de drawdown proposé par le Stratège (04/10).

Origine : le satellite V4 (baseline) est à -27,8% de drawdown max (-23,8% au
09/10) avec un edge net mesuré négatif par l'Évaluateur et le Shadow depuis
juillet, et continue pourtant d'ouvrir des positions à taille pleine (2000€).
Le Stratège propose une règle simple et fixée a priori (P1/P12, Turtles /
Druckenmiller) :
  - si le drawdown courant du satellite dépasse -15%, toute NOUVELLE position
    est ouverte à taille réduite de moitié (1000€ au lieu de 2000€) ;
  - si le drawdown dépasse -25%, aucune nouvelle position n'est ouverte,
    jusqu'au retour au-dessus de -15%.
Aucun seuil optimisé sur les données : -15/-25 sont posés à froid.

Protocole (repris tel que proposé) : reprendre les 75 trades clos de
portefeuille_virtuel.json (date d'entrée/sortie, prix d'entrée/sortie), et
rejouer DEUX bras avec la même liste de trades (mêmes signaux, mêmes dates) :
  A. Baseline  : taille fixe 2000€ sur chaque trade (ce qui s'est réellement
                 passé).
  B. Circuit-breaker : taille adaptée au drawdown réalisé AU MOMENT DE
                 L'ENTRÉE (0, 1000 ou 2000€ selon la règle ci-dessus).
Dans les deux bras, les frais sont recalculés avec la même formule que le
code de production (calculer_frais, 0,5%/côté, min 0,50€), appliquée à la
taille effective de chaque trade — pas aux montants déjà enregistrés, pour
que les deux bras soient strictement comparables entre eux.

LIMITE ASSUMÉE (à ne pas cacher) : le drawdown utilisé pour déclencher la
règle est calculé sur l'équité RÉALISÉE (capital de départ + P&L des trades
déjà clos au moment de l'entrée), pas sur une valorisation intrajournalière
des positions ouvertes (qu'on n'a pas, seuls entrée/sortie sont connus par
trade). Le vrai système aurait donc pu réagir un peu plus tôt ou plus tard
selon les mouvements intraday des positions encore ouvertes. Cette limite
joue dans les deux sens, elle n'avantage pas artificiellement le circuit-
breaker.

Critère de passage fixé par le Stratège : si le circuit-breaker ne réduit
pas le drawdown maximal d'au moins 5 points sur cet historique, il ne passe
pas en prod.

Ne touche à rien en prod (ne lit que portefeuille_virtuel.json, n'écrit que
circuit_breaker_resultats.json).
"""

import json
import datetime

FICHIER_PORTEFEUILLE = "portefeuille_virtuel.json"
FICHIER_RESULTATS    = "circuit_breaker_resultats.json"

CAPITAL_DEPART   = 10000.0
BUDGET_PLEIN     = 2000.0
BUDGET_REDUIT    = 1000.0
SEUIL_REDUCTION  = -15.0   # % : sous ce drawdown, taille réduite de moitié
SEUIL_STOP       = -25.0   # % : sous ce drawdown, aucune nouvelle position

FRAIS_TAUX    = 0.005
FRAIS_MINIMUM = 0.50


def calculer_frais(montant):
    return round(max(FRAIS_MINIMUM, montant * FRAIS_TAUX), 2)


def charger_trades():
    with open(FICHIER_PORTEFEUILLE, "r", encoding="utf-8") as f:
        pf = json.load(f)
    return pf.get("trades", [])


def _dt(date_s, heure_s):
    heure_s = heure_s or "07:00"
    try:
        return datetime.datetime.strptime(f"{date_s} {heure_s}", "%Y-%m-%d %H:%M")
    except ValueError:
        return datetime.datetime.strptime(date_s, "%Y-%m-%d")


def cashflow_trade(entree, sortie, budget):
    """Reproduit exactement la mécanique de scoring_intraday.py (nombre
    d'actions entier, frais 0,5%/côté, min 0,50€) pour une taille donnée."""
    nb = int(budget / entree)
    if nb <= 0:
        return 0.0, 0.0
    cout          = nb * entree
    frais_achat   = calculer_frais(cout)
    valeur_sortie = nb * sortie
    frais_vente   = calculer_frais(valeur_sortie)
    net_cashflow  = (valeur_sortie - frais_vente) - (cout + frais_achat)
    frais_total   = round(frais_achat + frais_vente, 2)
    return round(net_cashflow, 2), frais_total


def simuler(trades, avec_circuit_breaker):
    """Rejoue les trades en ordre chronologique d'ENTRÉE pour décider la
    taille (si circuit-breaker actif), applique le cashflow à la date de
    SORTIE, et trace la courbe d'équité réalisée pour mesurer le drawdown."""
    events = []
    for i, t in enumerate(trades):
        entree_dt = _dt(t["date_entree"], t.get("heure_entree"))
        sortie_dt = _dt(t["date_sortie"], t.get("heure_sortie"))
        events.append((entree_dt, "entree", i))
        events.append((sortie_dt, "sortie", i))
    events.sort(key=lambda e: (e[0], 0 if e[1] == "entree" else 1))

    equity        = CAPITAL_DEPART
    pic           = CAPITAL_DEPART
    equity_curve  = [("depart", equity)]
    budget_choisi = {}
    frais_cumules = 0.0
    n_reduits     = 0
    n_skip        = 0
    skip          = set()

    for dt, kind, i in events:
        t = trades[i]
        if kind == "entree":
            drawdown_pct = (equity - pic) / pic * 100 if pic > 0 else 0.0
            if avec_circuit_breaker and drawdown_pct <= SEUIL_STOP:
                budget_choisi[i] = 0.0
                skip.add(i)
                n_skip += 1
            elif avec_circuit_breaker and drawdown_pct <= SEUIL_REDUCTION:
                budget_choisi[i] = BUDGET_REDUIT
                n_reduits += 1
            else:
                budget_choisi[i] = BUDGET_PLEIN
        else:  # sortie
            if i in skip:
                continue
            budget = budget_choisi.get(i, BUDGET_PLEIN)
            net_cashflow, frais_total = cashflow_trade(t["entree"], t["sortie"], budget)
            equity += net_cashflow
            frais_cumules += frais_total
            pic = max(pic, equity)
            equity_curve.append((f"{t['date_sortie']} {t.get('heure_sortie','')} {t['nom']}", round(equity, 2)))

    # Drawdown max sur la courbe réalisée
    pic_run = CAPITAL_DEPART
    dd_max = 0.0
    for _, v in equity_curve:
        pic_run = max(pic_run, v)
        dd = (v - pic_run) / pic_run * 100 if pic_run > 0 else 0.0
        dd_max = min(dd_max, dd)

    return {
        "equity_finale": round(equity, 2),
        "pnl_total_pct": round((equity - CAPITAL_DEPART) / CAPITAL_DEPART * 100, 2),
        "drawdown_max_pct": round(dd_max, 2),
        "frais_cumules_eur": round(frais_cumules, 2),
        "n_trades_executes": len(trades) - n_skip,
        "n_trades_taille_reduite": n_reduits,
        "n_trades_skippes": n_skip,
    }


def main():
    trades = charger_trades()
    print(f"Trades clos chargés : {len(trades)}")

    base = simuler(trades, avec_circuit_breaker=False)
    cb   = simuler(trades, avec_circuit_breaker=True)

    delta_dd    = cb["drawdown_max_pct"] - base["drawdown_max_pct"]  # positif = amélioration
    delta_frais = base["frais_cumules_eur"] - cb["frais_cumules_eur"]
    delta_pnl   = cb["pnl_total_pct"] - base["pnl_total_pct"]

    passe = delta_dd >= 5.0
    verdict = (
        f"Circuit-breaker : drawdown {base['drawdown_max_pct']}% -> {cb['drawdown_max_pct']}% "
        f"({'+' if delta_dd >= 0 else ''}{round(delta_dd,2)} pts). "
        f"Frais {base['frais_cumules_eur']}€ -> {cb['frais_cumules_eur']}€ "
        f"({'-' if delta_frais >= 0 else '+'}{abs(round(delta_frais,2))}€). "
        f"P&L {base['pnl_total_pct']}% -> {cb['pnl_total_pct']}% "
        f"({'+' if delta_pnl >= 0 else ''}{round(delta_pnl,2)} pts). "
        f"Critère Stratège (réduction DD >= 5 pts) : {'PASSE' if passe else 'NE PASSE PAS'}."
    )

    print()
    print("=== SANS circuit-breaker (baseline réelle, taille fixe 2000€) ===")
    print(json.dumps(base, ensure_ascii=False, indent=2))
    print()
    print("=== AVEC circuit-breaker (-15% -> 1000€, -25% -> stop) ===")
    print(json.dumps(cb, ensure_ascii=False, indent=2))
    print()
    print(verdict)

    resultats = {
        "date_test": datetime.date.today().isoformat(),
        "n_trades_source": len(trades),
        "seuils": {"reduction_pct": SEUIL_REDUCTION, "stop_pct": SEUIL_STOP,
                   "budget_plein": BUDGET_PLEIN, "budget_reduit": BUDGET_REDUIT},
        "baseline": base,
        "circuit_breaker": cb,
        "delta_drawdown_pts": round(delta_dd, 2),
        "delta_frais_eur": round(delta_frais, 2),
        "delta_pnl_pts": round(delta_pnl, 2),
        "critere_stratege_passe": passe,
        "verdict": verdict,
        "limite_assumee": (
            "Drawdown de déclenchement calculé sur l'équité RÉALISÉE (trades déjà "
            "clos), pas sur une valorisation intrajournalière des positions encore "
            "ouvertes (non disponible à partir de la seule liste entrée/sortie)."
        ),
    }
    with open(FICHIER_RESULTATS, "w", encoding="utf-8") as f:
        json.dump(resultats, f, ensure_ascii=False, indent=2)
    print(f"\nRésultats écrits dans {FICHIER_RESULTATS}")


if __name__ == "__main__":
    main()
