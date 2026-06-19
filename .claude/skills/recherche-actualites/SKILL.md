---
name: recherche-actualites-contextualisees
description: Skill pour effectuer une veille personnalisée des actualités. Quand l'utilisateur demande "fais-moi un point sur les actualités", "donne-moi les news du jour", "qu'est-ce que je dois savoir aujourd'hui", "fais-moi une veille", ou utilise la commande /morning, cette skill prend le relais pour effectuer une recherche d'actualités, les filtrer selon le contexte personnel de l'utilisateur (CONTEXT.md), et ne garder que celles qui sont pertinentes pour ses objectifs et projets actifs.
---

# Skill : Recherche d'Actualités Contextualisées

## Mission

Effectuer une veille intelligente des actualités, **filtrée selon le contexte personnel de l'utilisateur**. L'objectif n'est pas de tout dire, mais de ne garder que ce qui concerne vraiment l'utilisateur dans sa situation actuelle.

---

## Phase 1 : Charger le contexte de l'utilisateur

Avant toute recherche, lire ces fichiers pour comprendre qui est l'utilisateur :

1. `context/CONTEXT.md` (qui il est, ce qu'il fait, ses objectifs, ses projets)
2. `context/HISTORY.md` (les sessions récentes pour comprendre les sujets actifs)

Identifie en interne :
- Le **profil dominant** (étudiant, employé, entrepreneur, indépendant)
- L'**activité principale** et le secteur
- Les **objectifs court terme** (3-6 mois)
- Les **projets en cours**
- Le **domaine d'aide prioritaire**

Ces 5 éléments forment le **filtre de pertinence**.

---

## Phase 2 : Demander le périmètre de la veille

Si l'utilisateur n'a pas précisé le sujet, demande-lui :

```
Sur quel domaine voulez-vous votre veille du jour ?

1. Actualités IA et nouvelles technologies (recommandé par défaut)
2. Actualités de votre secteur d'activité
3. Actualités économiques et business
4. Un sujet spécifique (à préciser)
```

Si l'utilisateur tape directement `/morning` ou demande une routine matinale, lance directement la veille IA + secteur d'activité par défaut, sans poser la question.

---

## Phase 3 : Effectuer la recherche

Utilise les outils de recherche web disponibles (web_search ou un MCP comme Perplexity si connecté) pour récupérer les actualités du jour ou des derniers jours sur le périmètre demandé.

**Stratégie de recherche :**
- 3 à 5 recherches ciblées maximum
- Privilégier les sources récentes (moins de 48 heures idéalement)
- Couvrir 3 angles : annonces majeures, tendances émergentes, signaux faibles intéressants
- Sources francophones en priorité, internationales si nécessaire

**Exemples de queries selon le profil :**

Si profil = étudiant en marketing digital :
- "actualités IA marketing digital cette semaine"
- "outils IA gratuits étudiants 2026"
- "tendances marketing automation"

Si profil = entrepreneur SaaS :
- "actualités IA business SaaS"
- "nouvelles fonctionnalités Claude OpenAI"
- "outils productivité entrepreneur"

Si profil = employé en santé :
- "IA secteur santé actualités"
- "régulation IA Europe santé"
- "nouveaux outils professionnels santé"

Adapte intelligemment selon le contexte chargé en Phase 1.

---

## Phase 4 : Filtrer selon le contexte

C'est l'étape clé qui différencie cette skill d'une simple recherche Google.

Pour chaque actualité trouvée, pose-toi 3 questions :

1. **Est-ce que cette actualité concerne directement les objectifs de l'utilisateur ?**
2. **Est-ce que cette actualité a un impact sur ses projets en cours ?**
3. **Est-ce que cette actualité change quelque chose dans son secteur ou son domaine prioritaire ?**

Si la réponse est "non" aux 3 questions → écarter l'actualité.
Si la réponse est "oui" à au moins 1 question → garder l'actualité.

Note pour toi-même : il vaut mieux présenter 3 actualités vraiment pertinentes que 10 actualités génériques. La valeur de cette skill, c'est le filtre.

---

## Phase 5 : Présenter le résultat

Présente la veille sous ce format exact :

```
📰 Votre veille du [date du jour]

Filtrée selon votre contexte : [résumé en 1 ligne du profil et du focus actuel]

---

🔥 Ce que vous devez absolument savoir

[Actualité 1]
- Pourquoi c'est important pour vous : [explication personnalisée en 1-2 lignes]
- Source : [lien]

[Actualité 2]
- Pourquoi c'est important pour vous : [explication personnalisée]
- Source : [lien]

---

💡 Bon à savoir aussi

[Actualité 3 ou 4 - bullet points courts]

---

🎯 Action recommandée

[1 action concrète que l'utilisateur peut prendre aujourd'hui basée sur la veille]
```

---

## Règles importantes

- **Toujours expliquer pourquoi c'est pertinent pour CET utilisateur**, pas juste "voici les news"
- **Maximum 3-4 actualités**, pas plus, sinon c'est du bruit
- **Action recommandée à la fin** : c'est ce qui transforme la veille en valeur concrète
- **Ne jamais inventer** d'actualité ou de source. Si la recherche ne donne rien d'intéressant, le dire honnêtement
- **Pas de tirets longs** (em dashes) dans les réponses
- **Communication en français systématique**

---

## Si aucune actualité pertinente trouvée

Si après recherche, aucune actualité ne passe le filtre de pertinence, sois honnête :

```
📰 Votre veille du [date]

J'ai effectué une recherche sur [domaines couverts] mais je n'ai pas trouvé d'actualité majeure qui impacte directement vos objectifs ou projets en cours aujourd'hui.

Pas de bruit pour vous aujourd'hui. Voulez-vous que j'élargisse la recherche à un autre domaine ?
```

C'est mieux que de remplir avec du contenu générique qui ne sert à rien.
