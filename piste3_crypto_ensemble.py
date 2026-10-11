#!/usr/bin/env python3
"""
Piste 3 — Lookback crypto en ENSEMBLE de fenêtres canoniques (pas optimisé).

Origine (recherche du 11/10, research_notes/Evolutions agent bourse PEA/
crypto_momentum_vol_sizing.md) : l'agent Crypto DM est resté en refuge
stablecoin depuis juillet pendant que BTC faisait un fort rally — lookback
12 mois fixe trop lent pour ce cycle. Le walk-forward optimisé (grille de
lookbacks, crypto_dm_backtest.py, mode 1) a déjà été rejeté : il sélectionne
des fenêtres courtes qui brillent en train puis se font hacher en test
(signe de surapprentissage). La littérature crypto (Padysak & Vojtko,
Quantpedia ; Rohrbach et al. ; Concretum Group) suggère une troisième voie,
ni optimisée ni figée sur un seul horizon : un ENSEMBLE de lookbacks
CANONIQUES (1/3/6/12 mois, les horizons standards déjà validés par
Moskowitz-Ooi-Pedersen sur futures traditionnels), combinés par un vote de
majorité plutôt qu'un seul paramètre optimisé sur nos propres données.

Mécanisme (posé a priori, AUCUN lookback choisi en regardant nos résultats) :
  - Pour chaque actif, on compte parmi {1, 3, 6, 12} mois combien ont un
    momentum positif ("votes", de 0 à 4).
  - L'actif avec le plus de votes est candidat (égalité : momentum 12 mois,
    le standard historique, tranche).
  - Si son score est < 2 (moins de la moitié des horizons d'accord à la
    hausse) : refuge stablecoin (c'est l'équivalent "momentum absolu" en
    version votes plutôt qu'un seul chiffre).
  - Anti-whipsaw : on garde la position actuelle si son score reste >= 2 et
    que le challenger ne la dépasse pas d'au moins 1 vote.

GARDE-FOU TURNOVER (fixé avant de lancer, exactement le piège documenté par
Han, Kang & Ryu et par l'étude arXiv 2602.11708 citée dans la recherche) :
l'ensemble n'est adoptable QUE s'il bat le réglage fixe 12 mois actuel en
Sharpe, SANS faire plus du double de ses trades/an (le turnover mange les
frais 0,5%/rotation plus vite que le gain de réactivité ne rapporte).

Réutilise le chargement de données et les métriques de crypto_dm_backtest.py
(même historique, mêmes frais, pas de nouvelle collecte). Ne touche à rien
en prod. Sortie : console + piste3_crypto_ensemble_resultats.json.
"""

import warnings
warnings.filterwarnings("ignore")

import json

import numpy as np

from crypto_dm_backtest import (
    charger_donnees, metriques, valide, momentum, rendements_rotation,
    TICKERS, FRAIS_PAR_TRADE, LOOKBACK_FIXE, BUFFER_FIXE,
)

HORIZONS = [1, 3, 6, 12]   # canoniques, mêmes que Moskowitz-Ooi-Pedersen
SEUIL_VOTES = 2            # majorité sur 4 horizons


def score_votes(px, i, actif):
    """Nombre d'horizons (sur HORIZONS) où le momentum de l'actif est positif.
    None si aucun horizon n'est calculable (historique trop court)."""
    votes, calculables = 0, 0
    for h in HORIZONS:
        m = momentum(px[actif], i, h)
        if m is not None:
            calculables += 1
            if m > 0:
                votes += 1
    return votes if calculables == len(HORIZONS) else None


def rendements_ensemble(px, rends, i_debut, i_fin, rotation):
    out, journal = [], []
    position = None
    trades = 0

    for i in range(i_debut, i_fin):
        scores = {}
        for actif in rotation:
            s = score_votes(px, i - 1, actif)
            if s is not None and valide(rends[actif].iloc[i]):
                scores[actif] = s

        if not scores:
            cible = "Cash"
        else:
            # Meilleur score ; égalité tranchée par le momentum 12 mois classique
            meilleur_score = max(scores.values())
            candidats = [a for a, s in scores.items() if s == meilleur_score]
            if len(candidats) > 1:
                mom12 = {a: momentum(px[a], i - 1, 12) or -99 for a in candidats}
                meilleur = max(mom12, key=mom12.get)
            else:
                meilleur = candidats[0]

            if scores[meilleur] < SEUIL_VOTES:
                cible = "Cash"
            elif (position in scores and scores[position] >= SEUIL_VOTES
                  and scores[meilleur] < scores.get(position, 0) + 1):
                cible = position   # anti-whipsaw : le challenger ne dépasse pas d'1 vote
            else:
                cible = meilleur

        r = 0.0 if cible == "Cash" else float(rends[cible].iloc[i])
        cout = 0.0
        if cible != position:
            cout = FRAIS_PAR_TRADE
            trades += 1
            journal.append((str(px.index[i].date()), cible, scores.get(cible)))
            position = cible

        out.append(r - cout)

    return out, journal, trades


if __name__ == "__main__":
    print("Chargement des données crypto (Yahoo, mensuel)...")
    px, rends = charger_donnees()
    print(f"Période : {px.index[0].date()} → {px.index[-1].date()} ({len(px)} mois)\n")

    configs = {"BTC seul": ["BTC"], "BTC/ETH": ["BTC", "ETH"]}

    # Fenêtre commune : il faut au moins 12 mois d'historique pour le plus
    # long horizon de l'ensemble, comme pour le réglage fixe actuel.
    i0 = max(HORIZONS) + 36   # même point de départ que le walk-forward existant (après 36 mois de "chauffe")

    print("="*92)
    print(f"{'':28}{'Sharpe':>10}{'CAGR':>9}{'PireChute':>11}{'Trades/an':>12}")
    print("-"*92)

    resultats = {}
    for nom, rotation in configs.items():
        # A. Réglage fixe actuel (12 mois), même fenêtre
        out_fixe, _, trades_fixe = rendements_rotation(
            px, rends, LOOKBACK_FIXE, BUFFER_FIXE, i0, len(px), rotation)
        m_fixe = metriques(out_fixe)

        # B. Ensemble de lookbacks canoniques
        out_ens, journal_ens, trades_ens = rendements_ensemble(px, rends, i0, len(px), rotation)
        m_ens = metriques(out_ens)

        n_annees = m_fixe["n_mois"] / 12
        tpy_fixe = trades_fixe / n_annees
        tpy_ens  = trades_ens / n_annees

        print(f"{nom + ' (fixe 12m)':28}{m_fixe['sharpe']:>10.2f}{m_fixe['cagr']*100:>8.1f}%"
              f"{m_fixe['max_dd']*100:>10.1f}%{tpy_fixe:>12.1f}")
        print(f"{nom + ' (ensemble)':28}{m_ens['sharpe']:>10.2f}{m_ens['cagr']*100:>8.1f}%"
              f"{m_ens['max_dd']*100:>10.1f}%{tpy_ens:>12.1f}")

        passe = (m_ens["sharpe"] > m_fixe["sharpe"]) and (tpy_ens <= 2 * tpy_fixe)
        resultats[nom] = {
            "fixe_12m": {**m_fixe, "trades_an": round(tpy_fixe, 1)},
            "ensemble": {**m_ens, "trades_an": round(tpy_ens, 1)},
            "critere_passe": passe,
            "derniers_signaux_ensemble": journal_ens[-6:],
        }
        print(f"  -> Critère (Sharpe ensemble > fixe ET trades/an <= 2x) : "
              f"{'PASSE' if passe else 'NE PASSE PAS'}")
        print("-"*92)

    print("="*92)

    with open("piste3_crypto_ensemble_resultats.json", "w", encoding="utf-8") as f:
        json.dump({
            "horizons": HORIZONS, "seuil_votes": SEUIL_VOTES,
            "periode": f"{px.index[i0].date()} → {px.index[-1].date()}",
            "resultats": resultats,
        }, f, ensure_ascii=False, indent=2)
    print("\nRésultats détaillés sauvegardés dans piste3_crypto_ensemble_resultats.json")
