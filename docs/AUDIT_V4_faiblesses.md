# Audit Agent Bourse V4 — Faiblesses consolidées

> Analyse du 2026-06-25 (Opus 4.8). Lecture intégrale du code des 5 agents
> croisée avec les données réelles de `performance.json` et `portefeuille_virtuel.json`.

---

## Constat central

**Le système prédit aujourd'hui moins bien qu'un tirage à pile ou face.**

- Précision globale : **42,9%** (54/126 signaux)
- ACHETER : **42%** (29/69) | ÉVITER : **43,9%** (25/57)
- Référence hasard sur prédiction binaire hausse/baisse : ~50%

Nuance statistique : échantillon de 126 signaux sur 5 jours seulement.
42,9% n'est qu'à ~1,6 écart-type de 50%, donc ce n'est pas *prouvé* pire que
le hasard. Mais **aucune preuve d'edge** non plus. Conclusion : énormément
construit avant d'avoir établi que le signal vaut quelque chose.

---

## A. Qualité du signal (priorité absolue)

1. **Évaluation incohérente avec le trading.**
   `evaluer_performance_hier` note "correct" sur une comparaison à **1 jour**
   (`prix_auj > prix_hier`), alors que le portefeuille tient les positions
   **jusqu'à 10 jours**. Horizon d'évaluation ≠ horizon de trading.
   De plus "correct" = n'importe quelle hausse, même +0,01% : pas de seuil,
   le bruit domine.

2. **Soupe additive avec double comptage.**
   Score = 50 + ~25 termes linéaires. Le **momentum de prix est compté 3-4 fois**
   (convergence multi-timeframe + momentum relatif CAC + rotation ETF + pente MA200).
   RSI compté 3 fois (score brut + indicateurs appris + divergence).
   La règle "croise 3 indicateurs indépendants" est fausse : ils sont corrélés.
   → fausse conviction, pas de vraie diversification.

3. **Aucun poids calibré.**
   Tous les +20/+12/+15 et les seuils 65/35 sont choisis à la main, jamais
   validés contre les résultats. L'"auto-apprentissage" est cosmétique :
   ajuste seulement RSI/MACD par secteur, dès ≥5 échantillons (à peine atteint),
   effet plafonné à ±10 sur 100.

4. **Le malus global ne change pas le classement.**
   VIX/Fear&Greed/BCE appliqués uniformément à toutes les valeurs : décale la
   distribution sans changer quelle action est mieux classée. Effet réel limité
   au nombre de valeurs franchissant 65.

---

## B. Robustesse

5. **`except:` nus qui masquent les pannes.** (CRITIQUE)
   Des dizaines de try/except retournant silencieusement 0/None/neutre.
   Si Yahoo se dégrade, les scores glissent vers 50 sans alerte. Un "SURVEILLER 50"
   peut signifier "vraiment neutre" OU "données échouées" : indistinguable.
   Le Watchdog ne le détecte pas (il vérifie l'existence des fichiers, pas la
   validité des données).

6. **Dépendance Yahoo unique + redondance réseau.**
   `stock.info` appelé 2x/action ×39. `calculer_momentum_relatif_cac` re-télécharge
   1 mois d'historique pour les 39 valeurs alors qu'1 an est déjà en mémoire.
   Double charge = lenteur + risque de rate-limit = plus de pannes silencieuses.

7. **Bug timezone dans 3 autres fichiers.**
   `scoring_intraday.py`, `agent_news.py`, `agent_espion.py` utilisent encore
   `datetime.now()` naïf (UTC). Horodatages JSON faux de 2h.
   (Corrigé dans `agent_watchdog.py` et `briefing_bourse_v3.py` le 2026-06-25.)

8. **Duplication massive.**
   Dict `CAC40` copié dans 4 fichiers. `DATES_BANQUES_CENTRALES` dans 2.
   Logique VIX/Fear&Greed dupliquée. Taxonomies sectorielles **divergentes**
   entre fichiers (briefing "Industrie/Défense" vs intraday/espion "Industrie").
   Risque : modifier un endroit, oublier les autres.

9. **P&L portefeuille optimiste.**
   Stop-loss -5% testé uniquement aux snapshots (7h/9h/12h/16h). Un gap nocturne
   -15% est "fermé" au prix du snapshot, pas au stop. La P&L virtuelle est
   meilleure que la réalité : ne pas la prendre comme validation.

---

## C. Architecture / Roadmap V5

10. **L'ordre de la roadmap est inversé.**
    V5 ajoute des moteurs (Risk, Feature, Score 4 sous-scores, Macro+, Insider)
    sur un signal non validé. La **Phase 3 actuelle (backtest / walk-forward /
    calibration) devrait être la Phase 1.** Question à trancher AVANT tout ajout :
    le scoring bat-il (a) le hasard, (b) le buy-and-hold CAC40, (c) un simple
    RSI<30 ? S'il ne bat pas le buy-and-hold, simplifier, pas enrichir.

11. **Diversification des sources sous-priorisée.**
    Tout dépend de Yahoo et les `except:` cachent les pannes. Plus urgent que
    sa place en Phase 4.

---

## Priorisation recommandée

| # | Action | Pourquoi |
|---|--------|----------|
| 1 | Backtest harness + baseline vs buy-and-hold | Sans ça, pilotage à l'aveugle |
| 2 | Remplacer `except:` nus par logging + flag "données manquantes" au Watchdog | Impossible de faire confiance aux scores actuels |
| 3 | Centraliser CAC40 / secteurs / macro dans un module partagé | Stoppe la dérive entre fichiers |
| 4 | Évaluation : horizon cohérent (3-5j) + seuil de mouvement (±1%) | Mesurer un signal, pas du bruit |
| 5 | Dédupliquer les facteurs de momentum corrélés | Réduire la fausse conviction |
| 6 | *Ensuite seulement* : nouveaux moteurs V5 | Une fois l'edge prouvé |

---

## Ce qui est solide

Modularité propre (agents séparés, handoffs JSON), résilience cron via
cron-job.org, séparation des appels payants (seul le briefing appelle Claude).
Le problème n'est pas la qualité du code, c'est l'absence de validation d'edge
avant industrialisation.
