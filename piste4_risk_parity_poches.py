#!/usr/bin/env python3
"""
Piste 4 — Répartir le capital RÉEL (futur) entre poches par inverse de la
volatilité, plutôt que par pourcentages fixes choisis à la main.

Origine (recherche du 11/10, research_notes/Evolutions agent bourse PEA/
risk_parity_vol_targeting.md) : le risk parity institutionnel (Bridgewater,
PanAgora) nécessite du levier pour être efficace — inapplicable en PEA sans
marge. Mais sa version "naïve" (pondération inverse-volatilité, sans levier,
documentée par CXO Advisory et la méthode "handcrafting" de Rob Carver)
reste utilisable : répartir le capital entre poches proportionnellement à
1/volatilité de chacune, plutôt que des pourcentages arbitraires (actuels :
~80-85% cœur / 15-20% satellite, satellite fixé à la main sans lien avec son
risque réel).

RÈGLE DE GARDE, posée par la recherche elle-même : le risk parity est
agnostique au RENDEMENT attendu, il ne regarde que le risque. L'appliquer à
une poche dont l'edge net est prouvé négatif (le satellite) lui donnerait du
capital simplement parce qu'elle n'est pas infiniment volatile — ce serait
une régression par rapport au gel déjà décidé. Cette répartition ne
s'applique donc QU'ENTRE les poches dont l'edge est positif ou en cours de
validation (cœur DM, crypto DM), jamais au satellite.

Ce calcul ne déplace aucun euro réel (tout reste virtuel) : c'est un cadre
prêt à appliquer le jour où du capital réel entre sur plus d'une poche à la
fois, pour remplacer un pourcentage choisi à la main par un calcul.

Données utilisées (déjà produites par les backtests de ce dossier, aucune
collecte nouvelle) :
  - Volatilité du cœur Dual Momentum (World/USA + refuge monétaire, socle 0%,
    recette post-08/09) : voir piste2_canari_resultats.json -> sans_canari.vol
  - Volatilité de la rotation Crypto DM (BTC/ETH, lookback 12 fixe, réglage
    actuellement en prod) : voir piste3_crypto_ensemble_resultats.json ->
    BTC/ETH.fixe_12m.vol

Sortie : console + piste4_risk_parity_resultats.json. Ne touche à rien en
prod (ne lit que les deux fichiers de résultats déjà produits).
"""

import json

FICHIER_CANARI   = "piste2_canari_resultats.json"
FICHIER_ENSEMBLE = "piste3_crypto_ensemble_resultats.json"


def charger_vol_coeur():
    with open(FICHIER_CANARI, "r", encoding="utf-8") as f:
        return json.load(f)["sans_canari"]["vol"] / 100   # % -> fraction


def charger_vol_crypto():
    with open(FICHIER_ENSEMBLE, "r", encoding="utf-8") as f:
        return json.load(f)["resultats"]["BTC/ETH"]["fixe_12m"]["vol"]  # déjà en fraction


def poids_inverse_vol(vols):
    """vols : {nom: volatilité annualisée (fraction)}. Retourne les poids
    normalisés proportionnels à 1/vol (risk parity naïf, sans corrélations,
    sans levier — méthode CXO Advisory / Carver 'handcrafting')."""
    inv = {nom: 1.0 / v for nom, v in vols.items()}
    total = sum(inv.values())
    return {nom: round(i / total * 100, 1) for nom, i in inv.items()}


if __name__ == "__main__":
    vol_coeur  = charger_vol_coeur()
    vol_crypto = charger_vol_crypto()

    vols = {"Cœur Dual Momentum": vol_coeur, "Crypto DM (BTC/ETH)": vol_crypto}
    poids = poids_inverse_vol(vols)

    print("="*70)
    print("Répartition par inverse de la volatilité (satellite exclu, edge négatif)")
    print("="*70)
    for nom in vols:
        print(f"  {nom:26} vol {vols[nom]*100:>6.1f}%/an  ->  poids {poids[nom]:>5.1f}%")
    print("-"*70)
    ratio = vol_crypto / vol_coeur
    print(f"La crypto est {ratio:.1f}x plus volatile que le cœur : à risque égal, "
          f"elle ne mérite qu'une fraction {ratio:.1f}x plus petite du capital.")
    print(f"Comparaison : un partage naïf 50/50 exposerait {ratio:.1f}x plus de "
          f"risque côté crypto que côté cœur, sans aucune raison liée au risque réel.")
    print("="*70)

    resultats = {
        "volatilites_annualisees": vols,
        "poids_inverse_vol_pct": poids,
        "ratio_vol_crypto_sur_coeur": round(ratio, 2),
        "regle_de_garde": (
            "Applicable seulement entre poches a edge positif ou en cours de "
            "validation (coeur DM, crypto DM). Jamais au satellite (edge net "
            "negatif prouve) : le risk parity ignore le rendement attendu, "
            "l'appliquer au satellite lui redonnerait du capital par le seul "
            "fait qu'il n'est pas infiniment volatil."
        ),
        "statut": "Cadre pret, aucun euro reel deplace. A activer le jour ou du "
                   "capital reel entre sur plus d'une poche a la fois.",
    }
    with open("piste4_risk_parity_resultats.json", "w", encoding="utf-8") as f:
        json.dump(resultats, f, ensure_ascii=False, indent=2)
    print("\nRésultats sauvegardés dans piste4_risk_parity_resultats.json")
