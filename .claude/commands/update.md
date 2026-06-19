# /update

> Commande pour mettre à jour mes fichiers de contexte après une session importante ou suite à un changement significatif.

---

## Mission

Quand je lance `/update`, exécute la séquence suivante :

### Étape 1 : Identifier ce qui a changé

Demande-moi clairement :

```
On va mettre à jour ton contexte. Réponds simplement aux questions :

1. Qu'est-ce qui a changé depuis ta dernière mise à jour ?
   (Nouveau projet, nouvel objectif, changement de situation, décision prise, résultat obtenu, etc.)

2. Y a-t-il des informations dans CONTEXT.md qui ne sont plus exactes ?

3. Veux-tu ajouter une entrée spécifique dans HISTORY.md pour tracer cette session ?
```

### Étape 2 : Analyser et proposer les modifications

Pour chaque changement, identifie :
- Quel(s) fichier(s) doivent être mis à jour : CLAUDE.md, CONTEXT.md, HISTORY.md
- Quelle(s) section(s) précise(s) doivent être modifiées
- Quelles modifications proposer

Présente un plan clair avant d'écrire :

```
Voici ce que je vais faire :

1. Mettre à jour [fichier] dans la section [section] :
   - Avant : [ancien contenu]
   - Après : [nouveau contenu]

2. Ajouter une entrée dans HISTORY.md :
   [aperçu de l'entrée]

Tu valides ?
```

### Étape 3 : Exécuter les modifications

Une fois validé :
1. Modifie les fichiers concernés
2. Ajoute une entrée datée dans HISTORY.md sous le format suivant :

```
## [Date du jour au format AAAA-MM-JJ]

### [Titre court de la session ou du changement]
- [Bullet point 1]
- [Bullet point 2]
- [Bullet point 3]
```

### Étape 4 : Confirmer

Annonce ce qui a été fait :

```
C'est fait. Voici ce que j'ai mis à jour :
- [Liste des modifications]

Ton contexte est à jour. Tu peux relancer /prime à ta prochaine session pour vérifier.
```

---

## Règles importantes

- Ne modifie jamais un fichier sans avoir présenté un plan et reçu validation
- Garde HISTORY.md chronologique avec le plus récent en haut
- Garde CONTEXT.md synthétique, si une section devient trop longue, propose de créer un fichier dédié dans `context/import/`
- Préserve la structure et le formatage des fichiers existants
- Pas de tirets longs (em dashes) dans les écritures
- Communication en français systématique
