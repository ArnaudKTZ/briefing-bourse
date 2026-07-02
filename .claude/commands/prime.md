# /prime

> Commande pour démarrer une nouvelle session avec contexte complet.

---

## Mission

Quand je lance `/prime` au début d'une session, exécute la séquence suivante :

### Étape 1 : Charger le contexte

Lis dans cet ordre, en intégralité :
1. `CLAUDE.md` (le fichier racine du workspace)
2. `context/CONTEXT.md` (mon contexte personnel et professionnel)
3. `context/HISTORY.md` (l'historique de mes sessions précédentes)
4. `context/ECHEANCES.md` (les tâches et évolutions datées à ne pas oublier)

### Étape 1 bis : Vérifier les échéances

Compare la date du jour aux échéances non cochées de `context/ECHEANCES.md`.
Une échéance est **due** si sa date est aujourd'hui ou dans les 3 prochains jours,
**dépassée** si sa date est passée et qu'elle n'est pas cochée `[x]`.
S'il y en a, tu DOIS me prévenir en tête de résumé (bloc "À faire maintenant"
ci-dessous). S'il n'y a rien de dû ni de dépassé, n'affiche pas ce bloc.

### Étape 2 : Résumer ta compréhension

Présente-moi un résumé clair et synthétique en suivant cette structure
(le bloc "À faire maintenant" n'apparaît que s'il y a une échéance due/dépassée) :

```
Bonjour [Prénom], j'ai bien chargé ton contexte. Voici où on en est :

**⚠️ À faire maintenant** (seulement si échéance due ou dépassée)
- [Date + description de chaque échéance due ou dépassée, avec le nb de jours de retard éventuel]

**Qui tu es**
- [Synthèse en 2-3 lignes du profil]

**Tes objectifs court terme**
- [Top 3 des objectifs en cours]

**Tes projets actifs**
- [Liste des projets en cours]

**Dernière session**
- [Si HISTORY.md contient une entrée récente, la résumer]

**Prochaines échéances**
- [Les 1 à 3 prochaines échéances datées à venir de ECHEANCES.md, pour visibilité]

Je suis prêt à t'aider. Que veux-tu faire aujourd'hui ?
```

### Étape 3 : Attendre les instructions

Ne lance aucune action de toi-même. Attends que je te donne le sujet de la session.

---

## Règles importantes

- Si certains fichiers sont vides ou incomplets, signale-le et propose de les remplir
- Si tu détectes une incohérence entre les fichiers, signale-le calmement
- Ne fais pas de suppositions sur ce qu'on doit faire aujourd'hui, attends mes instructions
- Le résumé doit être en français et utiliser le tutoiement
- Pas de tirets longs (em dashes) dans tes réponses
