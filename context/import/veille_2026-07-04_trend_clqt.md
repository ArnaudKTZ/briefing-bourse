# Veille du 04/07/2026 — analyse des 2 papiers prioritaires

> Source : email hebdo de l'agent Éclaireur (top 8 finance quantitative).
> Triage : 2 papiers lus en détail, 2 notés, 4 écartés (bruit pour notre échelle).
> Analyse du 05/07, en appui des décisions du 02/08.

---

## Papier 1 — "Is Trend Still Your Friend?" (Bouchaud et al., arXiv 2607.01550)

**Thèse : le trend-following court terme est structurellement mort depuis ~2009.**

Chiffres clés (~100 futures liquides, 1995-2025) :
- Trend 5-20 jours : Sharpe 0.84 avant 2009 → 0.12 après (-86%)
- Trend 50-200 jours : Sharpe 0.70 → 0.40 (-43%), dégradé mais vivant
- Variable discriminante : le tick size normalisé par la volatilité. Petit tick
  (indices actions, devises) = effondrement total. Gros tick (commodités,
  taux) = trend intact

Mécanisme : les HFT ont remplacé les market makers classiques et retirent la
liquidité devant tout flux directionnel prévisible. La boucle auto-réalisatrice
du trend (signal → achat → impact prix → signal renforcé) est cassée sur les
instruments à petit tick. **Structurel, pas cyclique** : aucun rebond depuis
2018 malgré le retour de la liquidité.

Limites d'application chez nous : étude sur futures, pas actions individuelles,
et le satellite est du scoring multi-facteurs, pas du trend pur. C'est un
faisceau convergent avec nos propres mesures (Évaluateur : edge +0.70 pt à
J+5 < frais ~1%), pas une preuve directe.

**Implications :**
- Décision budget satellite du 02/08 : le fardeau de la preuve est du côté du
  satellite. IC significatif et edge net de frais, sinon budget symbolique ou zéro
- Le cœur Dual Momentum mensuel (signal lent) sort renforcé : les horizons
  longs survivent
- Ne pas attendre que "ça revienne" : les auteurs montrent que c'est perdant

## Papier 2 — CLQT, benchmark d'agents LLM de portefeuille (arXiv 2606.29771)

**Trouvaille principale : les agents LLM racontent une analyse et font autre
chose.** Accord signal-action 0.60 mais cohérence jugée indépendamment 0.27
(écart +0.33). Deuxième trouvaille : acuity faible partout (0.06-0.18 même pour
les meilleurs modèles) — les agents suivent le bruit autant que le signal.
Notre bucket 85+ qui fait pire que 75-84 est exactement ce symptôme.

**Repris chez nous (implémenté le 05/07 dans agent_evaluateur.py) :**
1. IC de Spearman à J+5 : corrélation de rang score→rendement forward, coupe
   transversale quotidienne (~39 valeurs/jour) puis moyennée. Repères : ~0
   aucun pouvoir de classement, 0.03 faible, 0.05 exploitable (avant frais)
2. Ventilation par régime de marché (CAC vs MM200) : edge et IC séparés
   haussier/baissier

Premier résultat (10 jours d'historique, 6 coupes avec recul J+5) :
**IC moyen +0.021, 33% de jours positifs = le score n'a aucun pouvoir de
classement.** Cohérent avec les buckets. Tout l'historique est en régime
haussier pour l'instant.

**Gardé pour plus tard (harnais crypto et tout futur backtest) :**
- Accès aux données strictement point-in-time (TimeGate)
- Si le backtest dépasse le live de plus de 0.2 de Sharpe : suspecter une
  contamination look-ahead
- Le reste du framework (chaîne de hash, mémoire 3 niveaux, 5 axes) :
  surdimensionné pour nous

## Les 2 notés sans lecture complète

- "When Do AI Models Beat Simple Rules?" (arXiv, 01/07) : valide le choix
  d'un cœur en règles simples. Lire abstract + conclusion à l'occasion
- Leakage-aware benchmarking LLM (21/06) : rappel leakage, couvert par les
  règles CLQT ci-dessus

## Les 4 écartés (avec raison)

- GAMLSS/ZAGA et HMM continu : validation sophistiquée surdimensionnée pour
  un portefeuille de notre taille avec 6 mois d'historique
- "Heads not backbones" : on n'entraîne pas de modèles
- Liquidity tail risk : microstructure institutionnelle, sans effet sur des
  ordres de 500-2000€ sur large caps CAC 40
