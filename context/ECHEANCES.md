# Échéances et évolutions à faire

> Source de vérité unique des tâches datées. Lu automatiquement à chaque `/prime` :
> si une échéance est due ou dépassée, Claude me prévient en tête de session.
>
> **Format :** une ligne par tâche, `- [ ] AAAA-MM-JJ — description (projet)`.
> Cocher `[x]` quand c'est fait (garder la ligne pour la trace, ou la déplacer en bas).
> Une échéance sans date ferme = mettre `~AAAA-MM-JJ` (approximatif).

---

## À venir

- [ ] 2026-08-02 — **Trois décisions Agent Bourse** (rappel push déjà programmé) : (1) réactiver ou non les alertes email achat/vente suspendues, sur le verdict Shadow ; (2) sort des poids News/Espion neutralisés (supprimer / réduire / réactiver / tester signe contrarien News), après retest sur un mois propre ; (3) budget par position du satellite (2000€ → 500€ ?). (Agent Bourse)

- [ ] 2026-08-22 — **Recette forward du Risk Engine** : comparer les courbes réelles des deux portefeuilles virtuels (baseline vs risk_engine_portefeuille.json) sur ~1 mois de données forward, pas seulement le backtest rétroactif. Si le Risk Engine confirme son avantage (edge net, drawdown), ouvrir la question d'un premier budget réel réduit. (Agent Bourse)

## Sans date ferme (à sortir quand le moment est bon)

- [ ] Décision poche crypto réelle vs signal Crypto DM (posée le 13/07, réponse en attente) : (a) aligner BTC/ETH sur le signal refuge + trancher SOL, (b) signal appliqué aux seuls futurs apports, (c) ne rien toucher, l'agent observe. (Agent Bourse)
- [ ] Session promotion Naval Group à programmer un soir : objectif n°1, jamais travaillé ici. Arnaud doit amener le contexte (hiérarchie, échéances d'entretiens, ce qui a été dit). (Promotion)
- [ ] Sprint KTZ71 en attente : 3 infos mentions légales (adresse, hébergeur, statut juridique) puis rédaction RGPD + gabarit fiche annonce. (KTZ71)

- [ ] Agent Patrimoine global : nécessite une session dédiée avec les lignes réelles du PEA + épargne. (Agent Bourse)
- [ ] ~2027-06-16 — **Renouveler le token GitHub (PAT) des jobs cron-job.org** : il expire le 23/06/2027 (vu dans la réponse GitHub lors des tests du 13/07). À l'expiration, les 12 jobs tomberont en 401 d'un coup. (Agent Bourse)
- [ ] KTZ71.com : reprendre le plan d'action en 15 étapes (mentions légales, RGPD, page e-garage, refonte fiches annonces). (KTZ71)
- [ ] Idée en réserve Phase 1 V5 : sous-score "qualité" à critères durs chiffrés (ROE, marge, dette — calcul Python, pas LLM, inspiré du /quality-screen d'ai-berkshire). Préalable : auditer la disponibilité/fraîcheur des fondamentaux Yahoo sur les .PA (ce qui a tué l'Espion). Passage par la recette obligatoire. (Agent Bourse)

## Fait

- [x] 2026-07-22 — **Bilan des 30 jours : CAS 1 tranché sur les critères figés à froid.** Fenêtre propre (546 obs, 14 j depuis le 02/07) : edge NET J+5 = **-1,2 pt** (perdant net de frais), IC J+5 = +0,077. Grille = CAS 1 car edge net ≤ 0 → **satellite gelé 100% virtuel, aucun passage en réel, effort bascule sur la Phase 1 V5**. Twist honnête : l'IC a grimpé de -0,05 (13/07) à +0,077 (exploitable AVANT frais), le score s'est mis à discriminer (buckets 85+/75-84 battent 65-74). Le signal a donc un vrai pouvoir de classement désormais, mais les frais (~1%) mangent tout l'edge. Ça ne change pas la décision (net ≤ 0), ça reformule la mission Phase 1 V5 : le problème n'est plus "le score est nul" mais "l'edge est réel et trop petit pour payer le péage". Prudence : 14 j = IC volatil, le seul fait ROBUSTE est l'edge net constamment négatif.
- [x] 2026-07-13 — Jobs cron-job.org Dividendes (lundi 8h05) et Crypto DM (1er du mois 8h15) créés par clonage (token jamais manipulé), testés 204, revérifiés après rechargement. 12 jobs actifs.
- [x] 2026-07-13 — Crypto Dual Momentum (BTC/ETH, lookback 12 fixe, refuge stablecoin, SOL rejeté) : décision Arnaud, agent en production (agent_crypto_dm.py, 1er du mois 8h15). Premier signal : refuge stablecoin (BTC -45%, ETH -37% sur 12 mois).

- [x] 2026-07-05 — Audit malus VIX : retiré (contre-productif sur 26 ans, comme le F&G). IC Spearman + régime MM200 ajoutés à l'Évaluateur. Agent Dividendes PEA créé. Tableau Cœur DM enrichi (gain/perte €, historique mensuel).
- [x] 2026-07-02 — Audit complet Agent Bourse, 3 bugs critiques corrigés, agents Shadow + Évaluateur créés, poids News/Espion neutralisés.
