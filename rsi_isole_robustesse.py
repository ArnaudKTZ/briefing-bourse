#!/usr/bin/env python3
"""
Robustesse du signal RSI isolé — coûts réels + bootstrap + correction multi-tests.

Origine (recherche "Super agents et compétences bourse", 01/11) : l'edge RSI
isolé trouvé le même jour (survente <30 : +1,21 pt à J+5 ; surachat >=70 :
-0,84 pt) est mesuré comme un point estimé unique, sur 4 horizons testés en
même temps — exactement le design qui, selon la recherche, peut produire des
"significativités" apparentes par pur hasard de tests multiples. Le papier
le plus rigoureux identifié ("Retail Trader's Ruin") impose trois choses
avant de croire un edge technique retail : (1) des coûts de transaction
réalistes, pas théoriques, (2) un bootstrap pour obtenir un intervalle de
confiance plutôt qu'un seul chiffre, (3) une correction pour tests multiples
(ici : 2 buckets × 4 horizons = 8 comparaisons).

CONTRAINTE PEA : pas de vente à découvert. Le bucket "survente" (RSI<30) est
un signal LONG tradeable (achat J, hold, vente J+N) : son coût réaliste est
le péage à l'aller-retour déjà utilisé par agent_evaluateur.py (1%, 0,5%/
côté Boursobank). Le bucket "surachat" (RSI>=70) ne PEUT PAS être monétisé en
position courte dans ce portefeuille — c'est au mieux un filtre ("ne pas
acheter") ou un signal de sortie anticipée, jamais un aller-retour
indépendant. Son edge brut est rapporté pour la discrimination, mais aucun
coût de transaction aller-retour ne lui est appliqué (il n'y en a pas,
puisqu'il ne déclenche pas de nouvelle position).

Ne touche à rien en prod (relit seulement performance.json via les fonctions
déjà existantes d'agent_evaluateur.py). Sortie : console +
rsi_isole_robustesse_resultats.json.
"""

import json
import warnings

import numpy as np

from agent_evaluateur import (
    charger_historique, charger_closes, rendements_forward,
    rsi_bucket, FRAIS_ALLER_RETOUR,
)

warnings.filterwarnings("ignore")

HORIZONS = [1, 3, 5, 10]
N_BOOTSTRAP = 2000
N_TESTS = 2 * len(HORIZONS)   # 2 buckets x 4 horizons = 8 comparaisons
SEED = 42


def bootstrap_edge(vals_bucket, vals_univers, n=N_BOOTSTRAP, seed=SEED):
    """Intervalle de confiance par bootstrap de l'edge = moyenne(bucket) -
    moyenne(univers), en rééchantillonnant les deux groupes séparément avec
    remise (bootstrap non-paramétrique standard)."""
    rng = np.random.default_rng(seed)
    b = np.array(vals_bucket)
    u = np.array(vals_univers)
    if len(b) < 10 or len(u) < 10:
        return None
    edges = []
    for _ in range(n):
        tirage_b = rng.choice(b, size=len(b), replace=True)
        tirage_u = rng.choice(u, size=len(u), replace=True)
        edges.append(tirage_b.mean() - tirage_u.mean())
    edges = np.array(edges)
    return {
        "edge_point": round(float(b.mean() - u.mean()), 3),
        "ci_95_bas": round(float(np.percentile(edges, 2.5)), 3),
        "ci_95_haut": round(float(np.percentile(edges, 97.5)), 3),
        "ci_corrige_bas": round(float(np.percentile(edges, 100 * 0.025 / N_TESTS)), 3),
        "ci_corrige_haut": round(float(np.percentile(edges, 100 * (1 - 0.025 / N_TESTS))), 3),
        "pct_bootstrap_positif": round(float((edges > 0).mean() * 100), 1),
    }


if __name__ == "__main__":
    print("Chargement de l'historique (performance.json + clôtures)...")
    historique = charger_historique()
    closes = charger_closes()
    obs = rendements_forward(historique, closes)
    print(f"{len(obs)} observations valeur×jour\n")

    print(f"Correction Bonferroni pour {N_TESTS} comparaisons : seuil ajusté = {0.05/N_TESTS:.4f} "
          f"(IC élargi à {100*(1-0.05/N_TESTS):.2f}%)\n")

    resultats = {}
    print(f"{'Horizon':8}{'Bucket':20}{'Edge brut':>10}{'IC 95%':>20}{'IC corrigé (8 tests)':>24}{'Edge NET (survente)':>20}")
    print("-" * 102)

    for h in HORIZONS:
        univers_vals = [o["rends"].get(h) for o in obs if o["rends"].get(h) is not None]

        for label_bucket, nom_court in [("survente (<30)", "survente"), ("surachat (>=70)", "surachat")]:
            vals = [o["rends"].get(h) for o in obs
                     if rsi_bucket(o.get("rsi")) == label_bucket and o["rends"].get(h) is not None]
            bs = bootstrap_edge(vals, univers_vals)
            if bs is None:
                print(f"J+{h:<6}{nom_court:20}{'n/a (trop peu d_obs)':>60}")
                continue

            edge_net = round(bs["edge_point"] - FRAIS_ALLER_RETOUR, 3) if nom_court == "survente" else None
            ic_str = f"[{bs['ci_95_bas']:+.2f}, {bs['ci_95_haut']:+.2f}]"
            ic_corr_str = f"[{bs['ci_corrige_bas']:+.2f}, {bs['ci_corrige_haut']:+.2f}]"
            net_str = f"{edge_net:+.2f} pts" if edge_net is not None else "— (pas de short en PEA)"

            print(f"J+{h:<6}{nom_court:20}{bs['edge_point']:>+9.2f}{ic_str:>20}{ic_corr_str:>24}{net_str:>20}")

            resultats[f"J{h}_{nom_court}"] = {**bs, "n_obs": len(vals), "edge_net_pct": edge_net}

    # Verdict honnête : le signal survient-il à l'IC corrigé AVEC frais déduits ?
    print("\n" + "=" * 70)
    survente_j5 = resultats.get("J5_survente", {})
    net_j5 = survente_j5.get("edge_net_pct")
    ci_bas_corr = survente_j5.get("ci_corrige_bas")
    ci_bas_corr_net = round(ci_bas_corr - FRAIS_ALLER_RETOUR, 3) if ci_bas_corr is not None else None

    if ci_bas_corr_net is not None and ci_bas_corr_net > 0:
        verdict = (f"Survente J+5 : edge NET {net_j5:+.2f} pt, et même la borne basse de l'IC "
                   f"corrigé pour 8 tests reste positive une fois les frais déduits "
                   f"({ci_bas_corr_net:+.2f} pt). Signal robuste à ce niveau de test.")
    elif net_j5 is not None and net_j5 > 0:
        verdict = (f"Survente J+5 : edge NET {net_j5:+.2f} pt (positif), MAIS la borne basse de "
                   f"l'IC corrigé pour tests multiples devient négative une fois les frais déduits "
                   f"({ci_bas_corr_net:+.2f} pt si disponible) : le signal pourrait être du bruit "
                   f"une fois la rigueur statistique appliquée. Pas assez solide pour un système "
                   f"dédié en l'état.")
    else:
        verdict = f"Survente J+5 : edge NET {net_j5} — ne survit pas aux frais réalistes du PEA."
    print(verdict)
    print("\nRappel : le bucket 'surachat' ne peut pas être monétisé en PEA (pas de short). "
          "Son edge négatif reste utile comme filtre ('ne pas acheter') ou signal de sortie "
          "anticipée, jamais comme trade indépendant — donc jamais de notion d'edge NET pour lui.")

    with open("rsi_isole_robustesse_resultats.json", "w", encoding="utf-8") as f:
        json.dump({
            "n_tests_bonferroni": N_TESTS,
            "frais_aller_retour_pct": FRAIS_ALLER_RETOUR,
            "resultats": resultats,
            "verdict": verdict,
        }, f, ensure_ascii=False, indent=2)
    print("\nRésultats sauvegardés dans rsi_isole_robustesse_resultats.json")
