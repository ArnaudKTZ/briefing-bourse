# Les méthodes des grands traders — dossier de recherche

> Phase A du projet Agent Stratège ("Loup de Wall Street"), demandé par Arnaud le 15/07/2026.
> Recherche web vérifiée + littérature de référence. Inclut la Phase B : audit de notre
> flotte d'agents contre ces principes.
>
> Règle de lecture : ce dossier sépare systématiquement ce qui est VÉRIFIÉ (chiffres,
> études, règles documentées) de ce qui est LÉGENDE. Et il sépare ce qui est COPIABLE
> à notre échelle de ce qui ne l'est pas.

---

## 0. L'avertissement honnête (à relire avant chaque décision)

Trois chiffres, trois études académiques indépendantes, trois marchés différents :

| Étude | Marché | Résultat |
|---|---|---|
| Chague, De-Losso & Giovannetti (2020) | Futures Brésil, tous les débutants 2013-2015 | **97% des day traders persistants (300+ jours) perdent de l'argent.** 1,1% gagnent plus que le SMIC local. Aucune preuve d'apprentissage avec l'expérience |
| Barber & Odean, "Trading is Hazardous to Your Wealth" | 66 465 comptes US 1991-1996 | Les 20% qui tradent le plus : 11,4%/an. Les 20% qui tradent le moins : 18,5%/an. **L'activité coûte 7 points par an** |
| Barber, Lee, Liu & Odean | Taïwan, 15 ans de données complètes | 8 day traders sur 10 perdent chaque semestre. **Moins de 1% ont un edge fiable net de frais** |

Le biais du survivant fait le reste : les millions de perdants ne publient ni livres ni
vidéos. Quand on "étudie les millionnaires du trading", on étudie la queue de distribution
d'une loterie en ignorant les tickets perdants.

**Et pourtant ce dossier existe**, parce qu'en étudiant ce que les survivants documentés
ont EN COMMUN, on ne trouve presque jamais des techniques de prédiction. On trouve des
règles de gestion. Et ça, c'est copiable, testable, et notre système n'en a qu'une partie.

---

## 1. Le panthéon, par famille de méthode

### 1.1 Jim Simons — Renaissance / fonds Medallion (le quant absolu)

**Palmarès vérifié** : 66%/an brut, 39%/an net de frais, de 1988 à ~2018. Plus de 100
milliards de dollars de gains. Le meilleur track record de l'histoire, sans débat.

**La méthode réelle** (source : Zuckerman, "The Man Who Solved the Market") :
- Des centaines de docteurs en maths/physique, des données propriétaires remontant à des décennies
- Un taux de réussite de **50,75% seulement** (dixit Robert Mercer) : un edge minuscule, répété sur des millions de trades, avec un levier moyen de 12,5x
- Fonds **fermé aux investisseurs extérieurs depuis 2005** : quand une machine marche vraiment, on n'en vend pas l'accès

**Copiable ?** La machine, non : c'est une usine industrielle. Les leçons, oui :
(1) l'edge réel est minuscule, celui qui promet 80% de réussite ment ;
(2) tout se mesure, rien ne se raconte ;
(3) un edge ne survit que gardé secret et exploité avec discipline.

### 1.2 Paul Tudor Jones (macro + trend, le gestionnaire du risque)

Célèbre pour avoir prédit et shorté le krach de 1987. Toujours en activité, milliardaire.

**Ses trois règles documentées** :
- **La moyenne mobile 200 jours comme garde-fou universel** : "je sors de tout ce qui passe sous sa MM200". C'est exactement le momentum absolu de notre Dual Momentum
- **"Losers average losers"** (pancarte au-dessus de son bureau) : on ne renforce JAMAIS une position perdante. Si le marché va contre toi, il t'informe que tu as tort
- **Asymétrie 5:1 exigée à l'entrée** : risquer 1 pour espérer 5. À ce ratio, on peut se tromper 80% du temps et survivre

Sa philosophie : "le plus important est de jouer une excellente défense, pas une
excellente attaque."

### 1.3 Soros / Druckenmiller (macro concentré, le sizing par conviction)

Druckenmiller : ~30% par an pendant 30 ans, jamais d'année perdante. Soros : le
"casse de la Banque d'Angleterre" (1992).

**Leur vraie leçon n'est pas la prédiction, c'est la TAILLE** :
- "Ce qui compte n'est pas d'avoir raison ou tort, c'est combien tu gagnes quand tu as raison et combien tu perds quand tu as tort"
- "La préservation du capital et les home runs" : petit ou absent quand la conviction est faible, énorme quand tout s'aligne ("it takes courage to be a pig")
- La seule fois où Soros engueulait Druckenmiller : quand il avait RAISON avec une position trop PETITE

**Copiable ?** Le principe de sizing par conviction, oui, avec des garde-fous. Le levier
macro et les réseaux d'information, non.

### 1.4 Richard Dennis et les Turtles (LA preuve que la discipline s'enseigne)

L'expérience la plus importante de l'histoire du trading pour nous : en 1983, Dennis
parie qu'il peut former des débutants complets. Il recrute 23 personnes ordinaires, leur
donne des règles ÉCRITES et MÉCANIQUES. Résultat : ~175 millions de dollars en 5 ans.

**Les règles complètes sont publiques** (The Original Turtle Trading Rules) :
- Entrée : cassure des plus hauts 20 jours (système 1) ou 55 jours (système 2). Aucune analyse, aucune opinion
- **Risque max 2% du capital par trade**, taille calculée sur la volatilité ("N", l'ATR) : position petite si le marché est nerveux, plus grande s'il est calme
- Stop connu AVANT l'entrée
- Pyramidage uniquement dans le sens du gain, limites strictes d'unités par marché et par direction (limite de corrélation)
- Sortie mécanique en trailing (cassure inverse 10/20 jours)

**L'honnêteté d'après** : l'edge breakout brut s'est érodé depuis les années 90. Ce qui
reste éternel, c'est la structure : système écrit + sizing par risque + exécution mécanique.

### 1.5 O'Neil / Minervini (momentum actions, le stop discipline)

O'Neil (CANSLIM) et Minervini (champion US Investing 1997, +155% dans l'année) :
- **Stop-loss dur à 7-8% sous le prix d'achat, sans exception ni discussion**
- Ratio gain moyen / perte moyenne surveillé en permanence (viser 2:1 minimum)
- **On ne trade agressivement qu'en marché haussier confirmé** : le filtre de régime avant le stock picking
- Ne jamais moyenner à la baisse (encore et toujours)

### 1.6 Les Market Wizards de Schwager (la synthèse des synthèses)

Schwager a interviewé des dizaines de traders d'exception sur 30 ans. Ses invariants :
- **Tous** mettent la gestion du risque au-dessus de la méthode d'entrée
- Ed Seykota : "coupe tes pertes, laisse courir tes gains, gère ton risque" ; "tout le monde a exactement ce qu'il veut dans le marché" (la psychologie prime)
- Bruce Kovner : "les débutants tradent 5 à 10 fois trop gros" ; le stop est décidé avant d'entrer ; dans le doute, on divise la position par deux
- Chaque wizard a un style qui colle à SA personnalité : copier le style d'un autre échoue

### 1.7 Buffett / Munger (le contrepoint : ne pas trader du tout)

Pas des traders : l'anti-trading. Qualité + temps + coûts faibles + levier gratuit des
assurances. "Règle n°1 : ne jamais perdre d'argent. Règle n°2 : ne jamais oublier la
règle n°1." Le rappel que le moteur de richesse le plus prouvé est la capitalisation
lente, pas la rotation rapide.

### 1.8 Jesse Livermore (le conte moral obligatoire)

Le plus grand lecteur de trend de son époque, 100 millions de dollars en 1929
(~1,5 milliard actuels). **Quatre faillites. Mort ruiné en 1940.** Ses propres maximes
("coupe tes pertes", "le marché a toujours raison") sont excellentes ; il ne les a pas
suivies. La leçon : sans gestion du risque SYSTÉMATIQUE (pas volontariste), le talent
finit à zéro. C'est l'argument définitif pour des agents mécaniques plutôt que des
résolutions humaines.

---

## 2. Le contre-poids académique (ce que la science valide et invalide)

- **Invalidé** : le trading discrétionnaire court terme des particuliers (les 3 études du chapitre 0), et les signaux techniques rapides en général (Bouchaud et al. 2026, déjà dans notre veille : le trend court est structurellement mort depuis 2009)
- **Validé, et massivement** : le trend following LENT. AQR, "A Century of Evidence on Trend-Following Investing" (Hurst, Ooi, Pedersen) : sur 137 ans (1880-2016), 67 marchés, 4 classes d'actifs, le time-series momentum est **positif à chaque décennie** et a bien performé dans **8 des 10 pires crises** du portefeuille 60/40
- Rappel CLQT (veille du 04/07) : les agents LLM qui "analysent les marchés" racontent une chose et font autre chose. Le LLM narre, il ne décide pas : principe déjà acté chez nous

**La conclusion qui tue** : la seule méthode de "grand trader" validée sur un siècle est
celle de notre cœur Dual Momentum. On l'avait choisie avant de faire cette recherche.

---

## 3. La bibliothèque du Stratège : 20 principes codifiés et testables

| ID | Principe | Sources | Traduction opérationnelle (testable) |
|----|----------|---------|--------------------------------------|
| P1 | Défense d'abord : risque max 1-2% du capital par position | Turtles, PTJ, Kovner | perte_max_position = capital × 2% ; taille = perte_max / distance_au_stop |
| P2 | Taille inversement proportionnelle à la volatilité | Turtles ("N") | position_eur = budget_risque / ATR20 |
| P3 | Stop décidé AVANT l'entrée, jamais déplacé contre soi | Kovner, Minervini | tout ordre virtuel porte stop et taille à la création |
| P4 | Ne JAMAIS moyenner une position perdante | PTJ ("losers average losers") | interdiction mécanique de renforcer sous le prix d'entrée |
| P5 | Asymétrie exigée à l'entrée (gain espéré / risque ≥ 2, idéal 5) | PTJ, Minervini | pas d'entrée sans take-profit/stop explicites et ratio ≥ seuil |
| P6 | Couper vite, laisser courir | Seykota, tous | temps de détention moyen des gagnants > perdants (mesurable) |
| P7 | Filtre de régime : agressif seulement en marché confirmé | PTJ (MM200), O'Neil | pas de nouvelle position satellite si CAC < MM200 |
| P8 | Le cash est une position | PTJ, notre DM | refuge explicite quand rien ne monte (on l'a) |
| P9 | Sizing par conviction : gros si tout s'aligne, sinon petit ou rien | Soros/Druckenmiller | taille modulée par le nombre de signaux indépendants alignés |
| P10 | Pyramider les gagnants, jamais les perdants | Turtles, Livermore | renforcement autorisé seulement au-dessus du prix d'entrée |
| P11 | Limites d'exposition corrélée | Turtles (max unités/direction) | max N positions par secteur (ex. pas 3 banques en même temps) |
| P12 | Frein après drawdown : réduire la voilure quand on perd | Druckenmiller, PTJ | si drawdown poche > X%, tailles divisées par 2 jusqu'à récupération |
| P13 | Journal de bord + revue à froid systématique | tous, Minervini | on l'a : Shadow, Évaluateur, Professeur, HISTORY |
| P14 | Système ÉCRIT, exécution mécanique, zéro discrétion en séance | Turtles, Seykota, leçon Livermore | on l'a : agents à règles fixes |
| P15 | Edge mesuré NET de frais avant de risquer un euro | Simons (50,75%!) | on l'a depuis ce matin : edge net dans l'Évaluateur |
| P16 | Si l'edge est lent, la fréquence doit être basse | AQR, Bouchaud | on l'a : cadence mensuelle du cœur et de la crypto |
| P17 | La méthode doit coller à ta personnalité et tes contraintes | Schwager (invariant n°1) | Arnaud : ingénieur, temps limité, pas d'écran en journée → mensuel/quotidien passif uniquement |
| P18 | Préservation du capital avant le rendement | Soros, Buffett | l'airbag prime sur le moteur (déjà notre philosophie cœur) |
| P19 | Poche spéculative étanche, jamais le patrimoine entier | tous les survivants | on l'a : cœur / satellite / crypto séparés |
| P20 | Se méfier de sa propre narration : mesurer, pas raconter | Simons, CLQT | on l'a : c'est la recette et les trois juges |

---

## 4. Phase B — Audit de la flotte (nos 12 agents face aux 20 principes)

### Ce qu'on a déjà, et bien (7 principes sur 20)

P8, P13, P14, P15, P16, P19, P20. Notre système est **excellent sur la mesure, la
discipline mécanique et l'étanchéité des poches**. C'est rare et c'est précieux : c'est
précisément ce qui manque à 97% des perdants des études. P17 et P18 sont respectés
par construction.

### Ce qui est partiel (2)

- **P7 (filtre de régime)** : on MESURE le régime MM200 (Évaluateur) mais aucun agent ne CONDITIONNE ses actions au régime. Le satellite prend des positions virtuelles par tous les temps
- **P3 (stop avant entrée)** : le scoring intraday a des stops/take-profits, mais le briefing ouvre des positions virtuelles sans stop ni taille raisonnée

### Ce qui manque complètement (le trou béant : 6 principes, tous dans la même zone)

**P1, P2, P5, P9, P11, P12 : il n'existe AUCUN moteur de risque.** Le satellite achète
2 000€ fixes par position, quelle que soit la volatilité de la valeur, sans stop
formalisé à l'entrée, sans exigence d'asymétrie, sans limite sectorielle (4 positions
dont 2 banques en ce moment même), sans frein après drawdown.

**Le constat massue de cette recherche** : les grands traders ne parlent presque jamais
d'entrée ou de prédiction. Ils parlent de sortie, de taille et de défense. Notre système
V4 a fait l'inverse : énormément d'intelligence dans la sélection (39 valeurs scorées
4 fois par jour) et zéro dans la gestion. Et la sélection est justement ce qui échoue
(IC négatif). On a construit un tireur myope avec un gros fusil, les grands construisent
des tireurs moyens avec un gilet pare-balles.

### Priorités qui en découlent (pour décision, rien d'automatique)

1. **Risk Engine** (P1+P2+P3+P5+P11+P12) : c'était déjà la Phase 2 de la roadmap V5, jamais construite. Cette recherche la promeut priorité n°1 absolue. Concrètement : un module que le satellite virtuel DOIT traverser avant toute position (taille par volatilité, stop obligatoire, asymétrie minimale, limites sectorielles, frein drawdown)
2. **Filtre de régime actif** (P7) : conditionner les entrées satellite au régime MM200, testable rétroactivement dans le harnais avec nos données existantes
3. **P9/P10 (conviction sizing, pyramidage)** : plus tard, seulement si 1 et 2 prouvent leur valeur en virtuel

---

## 5. Implications pour l'Agent Stratège (Phase C, à valider)

- **Rôle** : l'adjoint d'Arnaud. Une fois par mois, il lit l'état de TOUS les agents (rapports JSON), les confronte aux 20 principes de ce dossier, et produit une page : état de conformité, trou le plus coûteux, UNE proposition d'évolution priorisée avec son protocole de test dans le harnais
- **Ce qu'il n'est PAS** : un prédicteur de marché, un exécutant, un remplaçant du Professeur. Le Professeur juge les résultats mesurés (juge à règles fixes) ; le Stratège conseille sur l'architecture à la lumière des maîtres (conseiller LLM). Les deux rapportent, Arnaud décide
- **Garde-fou** : rien de ce qu'il propose n'entre en prod sans passer la recette (harnais). Le Stratège a le droit de rêver, la recette a le droit de veto
- **Coût** : 1 appel Sonnet/mois, quelques centimes

---

## Sources

- [Chague, De-Losso & Giovannetti — Day Trading for a Living? (SSRN)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3423101)
- [Barber & Odean — Trading is Hazardous to Your Wealth (SSRN)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=219228)
- [Barber, Lee, Liu, Odean — Do Individual Day Traders Make Money? Evidence from Taiwan](https://faculty.haas.berkeley.edu/odean/papers/Day%20Traders/Day%20Trade%20040330.pdf)
- [Meb Faber — Paul Tudor Jones on the 200-Day Moving Average](https://mebfaber.com/2014/11/06/paul-tudor-jones-on-the-200-day-moving-average/)
- [The Original Turtle Trading Rules (PDF intégral)](https://www.tradingwithrayner.com/wp-content/uploads/2014/11/OriginalTurtleRules.pdf)
- [Cornell Capital — Medallion Fund: The Ultimate Counterexample](https://www.cornell-capital.com/blog/2020/02/medallion-fund-the-ultimate-counterexample.html)
- [Renaissance Technologies — Wikipedia (levier, fermeture 2005)](https://en.wikipedia.org/wiki/Renaissance_Technologies)
- [Druckenmiller — The Greatest Lesson I Ever Learned From George Soros](https://acquirersmultiple.com/2017/11/stanley-druckenmiller-the-greatest-lesson-i-ever-learned-from-george-soros/)
- [Schwager — Market Wizards (synthèse des traits communs)](https://www.danielscrivner.com/winning-methods-of-the-market-wizards-common-traits-and-techniques-of-super-traders-and-investors-by-jack-schwager/)
- [AQR — A Century of Evidence on Trend-Following Investing](https://www.aqr.com/Insights/Research/Journal-Article/A-Century-of-Evidence-on-Trend-Following-Investing)
- Zuckerman — The Man Who Solved the Market (2019) ; Bouchaud et al., arXiv 2607.01550 (veille 04/07) ; CLQT, arXiv 2606.29771 (veille 04/07)
