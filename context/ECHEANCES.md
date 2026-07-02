# Échéances et évolutions à faire

> Source de vérité unique des tâches datées. Lu automatiquement à chaque `/prime` :
> si une échéance est due ou dépassée, Claude me prévient en tête de session.
>
> **Format :** une ligne par tâche, `- [ ] AAAA-MM-JJ — description (projet)`.
> Cocher `[x]` quand c'est fait (garder la ligne pour la trace, ou la déplacer en bas).
> Une échéance sans date ferme = mettre `~AAAA-MM-JJ` (approximatif).

---

## À venir

- [ ] 2026-07-22 — **Bilan Agent Bourse 30 jours** : analyser la précision par secteur/indicateur sur données propres (depuis le 02/07), via le rapport de l'Évaluateur. Démarrer si pertinent la Phase 1 V5 (Data Quality, Feature Engine, Score Engine 4 sous-scores). (Agent Bourse)
- [ ] 2026-08-02 — **Trois décisions Agent Bourse** (rappel push déjà programmé) : (1) réactiver ou non les alertes email achat/vente suspendues, sur le verdict Shadow ; (2) sort des poids News/Espion neutralisés (supprimer / réduire / réactiver / tester signe contrarien News), après retest sur un mois propre ; (3) budget par position du satellite (2000€ → 500€ ?). (Agent Bourse)

## Sans date ferme (à sortir quand le moment est bon)

- [ ] Audit du malus VIX dans le scoring (même méthode que l'audit Fear&Greed du 26/06 qui l'avait fait retirer). (Agent Bourse)
- [ ] Agent Dividendes PEA : calendrier des détachements CAC 40, rendements. Quick win, 100% factuel. (Agent Bourse)
- [ ] Agent Patrimoine global : nécessite une session dédiée avec les lignes réelles du PEA + épargne. (Agent Bourse)
- [ ] Crypto Dual Momentum (BTC/ETH/SOL) : à valider via le harnais avant prod. (Agent Bourse)
- [ ] KTZ71.com : reprendre le plan d'action en 15 étapes (mentions légales, RGPD, page e-garage, refonte fiches annonces). (KTZ71)

## Fait

- [x] 2026-07-02 — Audit complet Agent Bourse, 3 bugs critiques corrigés, agents Shadow + Évaluateur créés, poids News/Espion neutralisés.
