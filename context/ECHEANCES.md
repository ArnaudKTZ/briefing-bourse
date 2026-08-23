# Échéances et évolutions à faire

> Source de vérité unique des tâches datées. Lu automatiquement à chaque `/prime` :
> si une échéance est due ou dépassée, Claude me prévient en tête de session.
>
> **Format :** une ligne par tâche, `- [ ] AAAA-MM-JJ — description (projet)`.
> Cocher `[x]` quand c'est fait (garder la ligne pour la trace, ou la déplacer en bas).
> Une échéance sans date ferme = mettre `~AAAA-MM-JJ` (approximatif).

---

## À venir

- [ ] **PIVOT STRATÉGIQUE acté le 23/08 : le trading actif ne bat pas le buy&hold à cette échelle.** Chapitre "battre le marché par le satellite actif" fermé. Le Risk Engine reste airbag de krach uniquement (continue en forward). Satellite = labo d'apprentissage, pas machine à gains. Argent réel éventuel → cœur passif ETF, jamais le joueur. Rien à faire d'urgent, c'est un cadre de décision. (Agent Bourse)

## Sans date ferme (à sortir quand le moment est bon)

- [ ] Lire "The Science and Practice of Trend-Following Systems" (arXiv 2607.19497) : pourrait affiner le signal momentum du cœur Dual Momentum. Non prioritaire. (Agent Bourse)
- [ ] Décision poche crypto réelle vs signal Crypto DM (posée le 13/07, réponse en attente) : (a) aligner BTC/ETH sur le signal refuge + trancher SOL, (b) signal appliqué aux seuls futurs apports, (c) ne rien toucher, l'agent observe. (Agent Bourse)
- [ ] Session promotion Naval Group à programmer un soir : objectif n°1, jamais travaillé ici. Arnaud doit amener le contexte (hiérarchie, échéances d'entretiens, ce qui a été dit). (Promotion)
- [ ] Sprint KTZ71 en attente : 3 infos mentions légales (adresse, hébergeur, statut juridique) puis rédaction RGPD + gabarit fiche annonce. (KTZ71)

- [ ] Agent Patrimoine global : nécessite une session dédiée avec les lignes réelles du PEA + épargne. (Agent Bourse)
- [ ] ~2027-06-16 — **Renouveler le token GitHub (PAT) des jobs cron-job.org** : il expire le 23/06/2027 (vu dans la réponse GitHub lors des tests du 13/07). À l'expiration, les 12 jobs tomberont en 401 d'un coup. (Agent Bourse)
- [ ] KTZ71.com : reprendre le plan d'action en 15 étapes (mentions légales, RGPD, page e-garage, refonte fiches annonces). (KTZ71)
- [ ] Idée évidence-based sans urgence (issue du pivot 23/08) : élargir le cœur Dual Momentum à quelques ETF sectoriels (le seul mécanisme qui marche vraiment), via le harnais. À sortir quand Arnaud a de l'énergie pour le projet. (Agent Bourse)

## Fait

- [x] 2026-08-23 — **Recette forward Risk Engine (22/08) + stress-test krach + évolution momentum testée.** Recette forward : Risk Engine +0,76% vs baseline -1,39% = +2,15 pts, mais airbags P7/P12 jamais déclenchés, un seul épisode → verdict = prolonger le forward, aucun euro réel. Stress-test krach (`stress_test_krach.py`) : airbag décisif en krach rapide (COVID drawdown -8,6% vs -38,7%), mitigé en bear lent (2022). Évolution momentum+qualité construite (`selection_qm.py`, `selection_backtest.py`) et REJETÉE comme moteur : sur 2020-2026, tout overlay actif fait moins bien que le buy&hold (Momentum+Risk +0,06% vs CAC +40%). PIVOT acté : trading actif abandonné comme source de gains, Risk Engine = airbag krach seulement, argent réel → cœur passif. Vérif stabilité du score (piste 11/08) et sous-score qualité (audit data feu vert) absorbés dans cette session. (Agent Bourse)
- [x] 2026-08-11 — **Trois décisions du 02/08 arbitrées** (chiffres frais 07-09/08 à l'appui). (1) Alertes achat/vente : MAINTENUES SUSPENDUES (Shadow NUISIBLES -0,64 pt, Évaluateur edge net J+5 -1,55 pt, + "Retail Trader's Ruin") ; flag déjà False, rien à changer. (2) News/Espion : **Espion SUPPRIMÉ** (agent, workflow, rapport, refs tests/Professeur retirés ; edge non mesurable par construction sur les .PA), News maintenu à 0. (3) Budget satellite : STATU QUO 2000€ jusqu'à la recette du 22/08 (ne pas casser le groupe témoin de l'A/B). En parallèle : xtrem111team@gmail.com retiré des 6 agents hebdo (boîte saturée) ; reste à Arnaud de retirer xtrem111 du secret GitHub DESTINATAIRES (agents à fort volume) et de supprimer le job cron-job.org "Espion lundi 6h15". (Agent Bourse)

- [x] 2026-07-29 — **Lu "Retail Trader's Ruin" (arXiv 2607.20093).** RSI(14,30/70)/MACD(12,26,9)/Bollinger(20,2σ) — exactement les paramètres du scoring — testés sur 10 331 jours NASDAQ-100 : **REFUTED** statistiquement (Sharpe-gap 95% CI [-0,608,-0,175]) et économiquement (CAGR-gap 95% CI [-0,149,-0,044]), significativement négatif, pas juste absent d'edge. Réplication EU (6 pays dont France) confirme : aucun effet positif après correction. Nuance clé : le trend/golden-death cross est INCONCLUSIVE, pas REFUTED — le cœur Dual Momentum n'est pas visé. Confirme, par une voie académique indépendante, le pivot du 22/07 (satellite gelé, effort sur Risk Engine/DM). Renforce l'argument pour ne pas réactiver les alertes achat/vente à la décision du 02/08.
- [x] 2026-07-22 — **Bilan des 30 jours : CAS 1 tranché sur les critères figés à froid.** Fenêtre propre (546 obs, 14 j depuis le 02/07) : edge NET J+5 = **-1,2 pt** (perdant net de frais), IC J+5 = +0,077. Grille = CAS 1 car edge net ≤ 0 → **satellite gelé 100% virtuel, aucun passage en réel, effort bascule sur la Phase 1 V5**. Twist honnête : l'IC a grimpé de -0,05 (13/07) à +0,077 (exploitable AVANT frais), le score s'est mis à discriminer (buckets 85+/75-84 battent 65-74). Le signal a donc un vrai pouvoir de classement désormais, mais les frais (~1%) mangent tout l'edge. Ça ne change pas la décision (net ≤ 0), ça reformule la mission Phase 1 V5 : le problème n'est plus "le score est nul" mais "l'edge est réel et trop petit pour payer le péage". Prudence : 14 j = IC volatil, le seul fait ROBUSTE est l'edge net constamment négatif.
- [x] 2026-07-13 — Jobs cron-job.org Dividendes (lundi 8h05) et Crypto DM (1er du mois 8h15) créés par clonage (token jamais manipulé), testés 204, revérifiés après rechargement. 12 jobs actifs.
- [x] 2026-07-13 — Crypto Dual Momentum (BTC/ETH, lookback 12 fixe, refuge stablecoin, SOL rejeté) : décision Arnaud, agent en production (agent_crypto_dm.py, 1er du mois 8h15). Premier signal : refuge stablecoin (BTC -45%, ETH -37% sur 12 mois).

- [x] 2026-07-05 — Audit malus VIX : retiré (contre-productif sur 26 ans, comme le F&G). IC Spearman + régime MM200 ajoutés à l'Évaluateur. Agent Dividendes PEA créé. Tableau Cœur DM enrichi (gain/perte €, historique mensuel).
- [x] 2026-07-02 — Audit complet Agent Bourse, 3 bugs critiques corrigés, agents Shadow + Évaluateur créés, poids News/Espion neutralisés.
