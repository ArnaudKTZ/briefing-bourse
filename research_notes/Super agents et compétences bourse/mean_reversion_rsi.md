# Mean-reversion / RSI isolé en trading systématique multi-jours — État de l'art

## Existe-t-il une littérature académique sérieuse sur l'edge du RSI pris isolément sur actions individuelles à horizon multi-jours ?

### Takeaway
La littérature qui teste le RSI **strictement seul**, avec une méthodologie moderne (coûts de transaction, correction pour tests multiples, out-of-sample), est rare et peu convergente. Les études disponibles (praticiens quant sérieux type Alvarez Quant Trading, ou revues académiques anciennes) trouvent un edge réel mais **faible, instable dans le temps et sensible au choix des seuils/horizons** — pas le consensus propre et robuste qu'on pourrait espérer. Le papier académique le plus rigoureux identifié sur le sujet récent (Darmanin, 2026, voir Q3) ne teste d'ailleurs pas le RSI isolément mais une famille combinée RSI+MACD+Bollinger, ce qui limite fortement ce qu'on peut en tirer pour un RSI pur.

### Cited Findings
- Backtest Alvarez Quant Trading sur les composantes du S&P 500 (2006-2015, prix minimum $5, volume minimum $1M/jour moyen 21j) : 720 combinaisons de paramètres RSI testées (RSI2 <0.5/<1/>99/>99.5, RSI8 <15/<20/>80/>85, RSI14 <25/<30/>70/>75, RSI20 <30/<35/>65/>70), sorties à 5, 10, 21, 63 et 126 jours. 443 des 720 variations affichaient un p-value <5%, mais à horizon 63 jours seules 2 variations dépassaient significativement le baseline, et l'auteur note explicitement que "the edge is not that much bigger than the baseline" et attribue les p-values faibles surtout à la fréquence de trade plutôt qu'à un edge robuste — [Alvarez Quant Trading](https://alvarezquanttrading.com/blog/relative-strength-index-rsi-analysis/)
- Test de seuils RSI(2) de 1 à 50 sur SPY, filtré par SPY > SMA200, de février 1993 à septembre 2026 (33+ ans) : RSI9 ressort comme le seuil le plus performant sur l'échantillon complet (233 trades, 76,8% win rate, gain moyen 0,59%/trade, profit factor 2,59), contre RSI30 classique (613 trades, 70,3% win rate, gain moyen 0,33%/trade, profit factor 1,84). Mais le seuil optimal **change dans le temps** : RSI9 dominant 1993-2004 (profit factor 4,90, 88% gagnants), RSI9 s'affaiblit nettement 2005-2014 (profit factor 1,97), puis RSI14-18 redevient plus performant que RSI9 sur 2015-2026 — [Quantified Strategies](https://quantifiedstrategies.substack.com/p/what-is-the-best-rsi-oversold-level)
- Étude ancienne citée (Poterba & Summers, 1988, Journal of Financial Economics) trouvant une mean-reversion dans les prix des actions à horizon intermédiaire — mention de fond trouvée via résumé de recherche, non vérifiée sur la source primaire — [résultat de recherche secondaire, source primaire non consultée]
- Un article "An investigation of the relative strength index" (Business Perspectives / ResearchGate) existe mais n'a pas pu être consulté (accès 403 / paywall) — [ResearchGate](https://www.researchgate.net/publication/283691105_An_investigation_of_the_relative_strength_index)

### Inferences
- L'instabilité temporelle du seuil optimal (RSI9 vs RSI14-18 selon la décennie) suggère que l'edge RSI "pur" que le projet a trouvé (survente <30 à +1,21 pt en J+5) est probablement réel en tant que phénomène directionnel (sur/sous-réaction à court terme), mais que sa **magnitude précise et le seuil optimal ne sont pas des constantes universelles** — un edge mesuré sur une fenêtre de quelques mois (comme ici depuis le 01/11) doit être revu périodiquement plutôt que figé.
- Le fait que la significativité statistique dans le test Alvarez vienne surtout de la fréquence de trade (beaucoup de trades, peu de "vraie" force) est un avertissement direct pour un edge mesuré à ~1 point : avec 39 valeurs et un historique de plusieurs mois, le nombre de trades peut gonfler artificiellement la confiance statistique sans que l'edge soit économiquement solide.

### Gaps
- Aucune étude trouvée qui teste explicitement RSI(14) en isolation complète (sans combinaison) sur un univers comparable au CAC40 (actions européennes, large caps) avec coûts de transaction modélisés et horizons J+1/J+3/J+5/J+10 précisément alignés sur la méthodologie du projet.
- Pas de source primaire consultée pour Poterba & Summers (1988) ni pour Jegadeesh (1990) / Lehmann (1990) sur le "short-term reversal" — ces papiers sont le socle académique historique du phénomène de mean-reversion à court terme sur actions individuelles, mais je n'ai pas pu les récupérer directement dans cette recherche ; à vérifier séparément si besoin de citer la littérature fondatrice avec précision.
- Pas de papier SSRN ou Journal of Portfolio Management / Journal of Financial Markets identifié spécifiquement et exclusivement sur "RSI isolé, actions individuelles, multi-day" avec chiffres d'edge/Sharpe/win rate vérifiés à la source.

---

## Comment les praticiens reconnus dimensionnent-ils une position sur un signal RSI de survente/surachat ? Y a-t-il un consensus sur l'horizon de sortie optimal ?

### Takeaway
Le praticien de référence (Larry Connors / Cesar Alvarez, "Short Term Trading Strategies That Work") ne sort **jamais sur un nombre de jours fixe** mais sur un signal de retour (RSI qui repasse au-dessus d'un seuil, ou clôture au-dessus d'une moyenne mobile courte) — avec un holding period empirique qui converge systématiquement vers **2 à 7 jours de bourse**, jamais plus. Il n'y a pas de consensus chiffré unique sur "le" horizon optimal, mais une convergence forte de plusieurs sources indépendantes sur une fenêtre très courte (2-4 jours en moyenne, rarement au-delà de 7).

### Cited Findings
- Connors/Alvarez : RSI(2) exploite la "panic selling" qui se résorbe typiquement en 1 à 3 jours ; holding period moyen documenté de 2 à 4 jours (avec win rate 65-75% sur actions au-dessus de leur SMA200), la majorité des trades se résolvant en 2-7 jours de bourse — [Swingfolio](https://swingfolio.com/education/level-6-advanced-strategies/rsi-2-strategy), [MQL5](https://www.mql5.com/en/articles/17636)
- Stratégie "Cumulative RSI" (Connors/Alvarez) testée sur SPY de 1993 à publication (2008) : 88% de trades gagnants, gain moyen 1,26%, holding period moyen de **3,7 jours de bourse** — [MQL5](https://www.mql5.com/en/articles/17636)
- Alvarez Quant Trading, test de sorties à 5/10/21/63/126 jours sur S&P500 (2006-2015) : la sortie à 5 jours est celle qui ressort comme la plus favorable dans la majorité des variations ; à 63 jours l'edge s'évapore presque entièrement — [Alvarez Quant Trading](https://alvarezquanttrading.com/blog/relative-strength-index-rsi-analysis/)
- Connors et Alvarez ont par ailleurs constaté que les stop-loss dégradent souvent la performance des stratégies de trading court-terme (préférence pour une sortie sur signal plutôt que sur stop fixe) — [MQL5](https://www.mql5.com/en/articles/17636)
- Recommandation Alvarez pour un entry plus sélectif : RSI(2) < 1 ou ConnorsRSI < 5 (seuils plus extrêmes que 30) pour des rebonds à plus forte probabilité — [MQL5](https://www.mql5.com/en/articles/17636)

### Inferences
- Le choix du projet de mesurer l'edge RSI à J+1/J+3/J+5/J+10 est bien calibré par rapport à la littérature praticien : l'edge "vrai" (celui qui ne s'évapore pas) semble concentré dans la fenêtre J+1 à J+5, ce qui est cohérent avec le fait que le projet trouve un edge croissant jusqu'à J+5 — mais la littérature suggère de vérifier si l'edge à J+10 commence déjà à se dégrader (sortie trop tardive), par analogie avec la chute observée à 63 jours chez Alvarez.
- Le consensus praticien de sortir **sur signal** (RSI qui repasse au-dessus d'un seuil, ex. 50 ou 70) plutôt que sur un jour calendaire fixe suggère qu'un futur mini-système dédié au RSI pourrait gagner à tester une règle de sortie dynamique (ex. "sortir quand RSI repasse >50") plutôt qu'une sortie à J+5 fixe.

### Gaps
- Aucun chiffre praticien trouvé spécifiquement sur un univers européen/CAC40 — tous les chiffres praticiens cités sont US (SPY, S&P500 constituents).
- Pas de consensus chiffré unique et autoritatif sur "le" nombre de jours optimal — la littérature converge sur une fourchette (2-7 jours) plutôt que sur un chiffre précis.

---

## Le papier "Retail Trader's Ruin" a-t-il un sous-résultat spécifique sur le RSI SEUL ? Est-ce cohérent ou contradictoire avec l'edge RSI isolé trouvé par le projet ?

### Takeaway
**Non — le papier ne teste pas le RSI isolément.** "Retail Trader's Ruin: An Anatomy of Popular Signal Failure" (Adam Darmanin, Hecatus Research, arXiv 2607.20093, 2026) regroupe RSI(14,30/70), MACD(12,26,9) et Bollinger(20,2σ) dans une seule "famille oscillateur" et ne rapporte que des métriques agrégées de cette famille, pas de décomposition indicateur par indicateur. Le papier "réfute" statistiquement la famille oscillateur dans son ensemble, mais ce résultat ne peut **ni confirmer ni contredire directement** l'edge RSI isolé trouvé par le projet sur le CAC40 — et, pris avec les propres résultats du projet (MACD sans edge, Bollinger bruité), il est même plausible que l'échec de la famille agrégée soit tiré vers le bas par MACD et Bollinger plutôt que par le RSI.

### Cited Findings
- Méthodologie : univers NASDAQ-100, 10 331 observations journalières sur la période complète ; coût retail round-trip de 10bps (5bps par jambe) ; benchmark construit en "exposure-time-weighted buy-and-hold quand en position, cash quand flat" ; test statistique par bootstrap stationnaire avec intervalle de confiance à 95% et contrôle du taux de fausses découvertes (Benjamini-Yekutieli) pour corriger les tests multiples — [arXiv 2607.20093](https://arxiv.org/html/2607.20093)
- Les auteurs choisissent explicitement RSI(14,30/70) comme "l'item le plus promu de sa catégorie" pour représenter toute la famille oscillateur, mais ne publient que des métriques combinées RSI+MACD+Bollinger, pas de résultat RSI seul — [arXiv 2607.20093](https://arxiv.org/html/2607.20093)
- Résultat famille oscillateur (porte statistique) : écart de Sharpe vs benchmark, IC à 95% [−0,608 ; −0,175], comparé à un seuil de matérialité δS=0,20 → verdict "REFUTED (significantly negative)" — [arXiv 2607.20093](https://arxiv.org/html/2607.20093)
- Résultat famille oscillateur (porte économique) : écart de CAGR, IC à 95% [−0,149 ; −0,044], comparé à un seuil δR=0,01 → verdict "REFUTED (significantly negative)" — [arXiv 2607.20093](https://arxiv.org/html/2607.20093)
- Porte de survie (probabilité de liquidation à levier 2x) : 0,013 [0,0097 ; 0,0167] — la famille "survit" sur ce critère, mais est déjà réfutée sur les deux critères précédents — [arXiv 2607.20093](https://arxiv.org/html/2607.20093)
- Aucune analyse de sensibilité ou discussion de surapprentissage spécifique aux seuils 30/70 n'est fournie dans le papier (les paramètres sont prédéclarés sans test de robustesse sur le choix du seuil) — [arXiv 2607.20093](https://arxiv.org/html/2607.20093)

### Inferences
- Le CAGR gap négatif (jusqu'à -14,9 points annualisés dans la borne basse de l'IC) pour la famille oscillateur est un écart bien plus large que ce qu'un edge RSI de ~1 point à J+5 pourrait expliquer seul — cela pointe vers MACD et/ou Bollinger comme principaux contributeurs à l'échec, ce qui est **cohérent** avec la propre décomposition du projet (MACD neutralisé, aucun edge constaté).
- Comme le papier ne décompose pas, il est **méthodologiquement incorrect** de citer "Retail Trader's Ruin" comme preuve que le RSI seul ne fonctionne pas — c'est un résultat sur un panier de 3 indicateurs, pas sur le RSI. Le projet devrait être prudent s'il souhaite citer ce papier pour justifier ou réfuter son propre edge RSI : la bonne façon de l'utiliser serait de reproduire la méthodologie du papier (coûts 10bps, bootstrap stationnaire, seuils de matérialité δS/δR) mais appliquée **uniquement** au signal RSI isolé, pour obtenir un résultat réellement comparable.
- Le NASDAQ-100 (tech/croissance, momentum fort) est un univers structurellement différent du CAC40 (plus de valeurs value/cyclique/financières) — même si le papier avait décomposé le RSI seul, la transférabilité du résultat au CAC40 ne serait pas garantie.

### Gaps
- Impossible de savoir si, décomposé, le RSI seul dans l'échantillon NASDAQ-100 de Darmanin aurait un edge positif, neutre ou négatif — cette information n'existe simplement pas dans le papier publié.
- Pas de version antérieure/preprint du papier trouvée qui contiendrait une décomposition indicateur par indicateur en annexe (à vérifier directement dans le PDF complet si une analyse plus poussée est souhaitée — seule la version HTML arXiv a été consultée ici, pas les annexes/suppléments éventuels).

---

## Existe-t-il des études ou pratiques documentées sur le filtrage du signal RSI par le régime de marché ou par secteur ?

### Takeaway
Le filtrage par régime (tendance vs range, souvent via ADX ou position par rapport à une moyenne mobile longue) est une **pratique quant répandue et documentée au niveau praticien/blog**, mais je n'ai trouvé **aucune étude académique rigoureuse** qui teste statistiquement le filtrage de régime appliqué spécifiquement au RSI sur actions individuelles. Le filtrage sectoriel est évoqué dans des sources de qualité inégale (blogs de trading), sans chiffres vérifiables solides.

### Cited Findings
- Pratique standard documentée : ajouter un filtre ADX pour n'autoriser les entrées mean-reversion que lorsque la force directionnelle est faible (ADX < 18-20 = marché range favorable au mean-reversion ; ADX > 25 = marché tendanciel, défavorable) — [FractalCycles](https://fractalcycles.com/guides/market-regime-detection) (source de type guide pratique, non peer-reviewed)
- Le test Alvarez Quant Trading (S&P500, 2006-2015) a explicitement testé un filtre de régime SPX au-dessus/en-dessous de sa SMA200 ; les résultats "à 5 jours" apparaissaient favorables dans la majorité des variations mais **devenaient mitigés une fois filtrés par régime de marché** — [Alvarez Quant Trading](https://alvarezquanttrading.com/blog/relative-strength-index-rsi-analysis/)
- Exemple praticien : système RSI 5 jours (achat RSI<30, vente RSI>70/75/80) appliqué aux Sector SPDRs (ETF sectoriels US) — rentable sur les trois variantes de seuil de sortie testées, avec un drawdown maximum environ un tiers de celui du buy-and-hold — [StockCharts/SystemTrader](https://articles.stockcharts.com/article/articles-arthurhill-2016-07-testing-and-improving-the-5-day-rsi-mean-reversion-system-with-the-sector-spdrs/)
- Affirmations non sourcées académiquement sur une dépendance sectorielle du mean-reversion (Utilities plus mean-reverting, Industrials moins) trouvées sur des sites de contenu trading grand public — qualité de source faible, à traiter comme anecdotique — [sources blog multiples, non citées individuellement par manque de fiabilité]

### Inferences
- Le fait que le filtre de régime (SPX vs SMA200) **dégrade** la clarté des résultats chez Alvarez plutôt que de les améliorer nettement suggère que le filtrage de régime n'est pas une solution miracle et doit être testé empiriquement sur le CAC40 plutôt que supposé bénéfique par défaut.
- Il serait plus rigoureux pour le projet de tester lui-même le filtrage de régime (ex. CAC40 au-dessus/en-dessous de sa MM200, ou VIX/volatilité implicite comme proxy de régime) sur son propre historique plutôt que de s'appuyer sur la littérature existante, qui est soit absente (académique) soit de faible qualité (praticien) sur ce point précis.

### Gaps
- Aucune étude trouvée sur le filtrage sectoriel du RSI avec méthodologie statistique rigoureuse (tests de significativité, correction multiple) sur un large univers d'actions individuelles.
- Aucune étude trouvée appliquant explicitement un filtre de régime au RSI sur un marché européen ou sur le CAC40/indices similaires.

---

## Quels pièges connus (biais de sélection, surapprentissage 30/70, coûts de transaction) sont documentés pour une stratégie à edge aussi faible (~1 point avant frais) ?

### Takeaway
Trois pièges sont solidement documentés et directement pertinents à l'échelle d'edge du projet (~1 point) : (1) le surapprentissage du seuil 30/70 — l'optimum empirique dérive dans le temps et un pic de performance trop précis sur un seuil est un signe classique de bruit ajusté plutôt que de signal réel ; (2) le biais de test multiple — tester beaucoup de combinaisons de seuils/horizons fait apparaître des "significativités" artificielles ; (3) les coûts de transaction, qui dans plusieurs études suffisent à eux seuls à annuler un edge brut de l'ordre de quelques dixièmes de point à ~1 point.

### Cited Findings
- Signature classique de surapprentissage : "un seuil d'entrée RSI de 30 qui backteste à un Sharpe de 1,4, alors que 25 donne 0,3 et 35 donne 0,4, est un pic en aiguille qui est la signature du bruit ajusté, car les effets de marché réels ne sont pas aussi précis" — [article "Backtest Overfitting"](https://obside.com/trading-ai-agents/backtest-overfitting) (source de type blog technique, à utiliser comme heuristique de bon sens plutôt que preuve académique)
- Règle praticienne de prudence citée : limiter l'optimisation à un paramètre par année de données historiques, et viser un ratio minimum de 30 trades par paramètre optimisé, avec un découpage 70% in-sample / 30% out-of-sample — [même source](https://obside.com/trading-ai-agents/backtest-overfitting)
- Dans le test Alvarez Quant Trading, 443 des 720 combinaisons de paramètres RSI affichaient un p-value < 5% — illustration concrète qu'un grand nombre de "résultats significatifs" peut émerger simplement en testant beaucoup de combinaisons, sans que cela traduise un edge économiquement robuste — [Alvarez Quant Trading](https://alvarezquanttrading.com/blog/relative-strength-index-rsi-analysis/)
- Le seuil RSI optimal empirique dérive fortement dans le temps (RSI9 dominant 1993-2004 avec profit factor 4,90 ; nettement plus faible 2005-2014 à 1,97 ; RSI14-18 redevenant supérieur 2015-2026) — preuve directe d'instabilité temporelle du paramètre, pas seulement théorique — [Quantified Strategies](https://quantifiedstrategies.substack.com/p/what-is-the-best-rsi-oversold-level)
- Revue de littérature sur la profitabilité de l'analyse technique : plusieurs études montrent que les coûts de transaction, lorsqu'ils sont correctement modélisés, suffisent à éroder significativement voire annuler le rendement net de stratégies RSI — avec des coûts observés dans certaines études atteignant jusqu'à 0,39% par round-trip, un ordre de grandeur comparable à l'edge brut de ~1 point que mesure le projet — [revue académique via academia.edu](https://www.academia.edu/35696993/What_Do_We_Know_About_the_Profitability_of_Technical_Analysis)
- Le papier "Retail Trader's Ruin" modélise un coût retail round-trip de 10bps ; son verdict "REFUTED" sur la famille oscillateur vient d'un écart de CAGR déjà négatif de -4,4 à -14,9 points annualisés (borne de l'IC 95%) — un écart bien supérieur à ce que 10bps de coûts pourrait expliquer seul, ce qui suggère que dans ce cas précis, l'échec n'est pas principalement dû aux coûts de transaction mais à l'absence d'edge brut de la famille combinée — [arXiv 2607.20093](https://arxiv.org/html/2607.20093)
- Étude indienne citée en revue de littérature : le RSI overbought/oversold "n'a produit aucun rendement positif même avant coûts de transaction", ce qui soutient l'hypothèse d'efficience faible sur ce marché spécifique — [source secondaire via revue académique, marché indien, pas CAC40]

### Inferences
- À ~1 point d'edge brut avant frais, le projet est dans la "zone grise" documentée par la littérature où les coûts de transaction (courtage, spread bid-ask, slippage) peuvent représenter une fraction significative voire la totalité de l'edge — la priorité méthodologique immédiate devrait être de chiffrer précisément le coût round-trip réel du projet (en points, à l'échelle CAC40) et de le comparer directement au +1,21 pt / -0,84 pt mesurés, plutôt que de supposer l'edge "net" sans ce calcul.
- Le fait que le seuil 30/70 ne soit pas universellement optimal dans le temps (dérive documentée chez Quantified Strategies) justifie que le projet traite son edge RSI<30/RSI>=70 actuel comme une mesure **provisoire à revalider périodiquement**, et non comme une constante structurelle à exploiter indéfiniment sans contrôle.
- Avec 39 valeurs testées sur 4 horizons (J+1/J+3/J+5/J+10), le projet a un design proche de celui qui, chez Alvarez, produit un grand nombre de résultats "significatifs" par la seule fréquence de test (443/720) — une bonne pratique serait d'appliquer une correction pour tests multiples (ex. type Benjamini-Yekutieli comme dans Retail Trader's Ruin) avant de conclure à la robustesse de l'edge J+5, même si la cohérence croissante dans le temps observée par le projet est un signal encourageant que cela ne soit pas du pur bruit.

### Gaps
- Aucune étude trouvée qui quantifie précisément, pour un edge RSI de l'ordre de ~1 point sur un horizon de 5 jours, le seuil de coût de transaction à partir duquel l'edge devient net négatif — ce calcul doit être fait par le projet lui-même avec ses propres coûts réels (courtage + spread + slippage estimé sur les 39 valeurs CAC40).
- Pas de méthodologie académique standardisée trouvée spécifiquement pour "combien de tests multiples sont trop" dans le contexte d'un signal unique (RSI) testé sur 4 horizons seulement (par opposition aux centaines de combinaisons chez Alvarez) — la correction multiple est probablement moins critique ici, mais aucune source ne chiffre ce seuil précisément pour un design à 4 horizons.

---

## Synthèse pour la décision du projet (hors structure imposée, lecture rapide)

Points essentiels à retenir pour trancher "mini-système dédié ou composante du score" :

1. **Le "Retail Trader's Ruin" ne peut pas être cité comme preuve contre le RSI isolé** — il teste une famille combinée RSI+MACD+Bollinger, pas le RSI seul. Son usage le plus honnête ici est comme **modèle méthodologique** (coûts 10bps, bootstrap stationnaire, seuils de matérialité δS/δR, benchmark exposure-matched) à appliquer au propre signal RSI isolé du projet pour un test de robustesse plus dur que la mesure d'edge brut actuelle.
2. La littérature praticien (Connors/Alvarez) **converge** sur un horizon de sortie court (2-7 jours, optimum empirique souvent proche de 5 jours), ce qui valide a priori le choix du projet de regarder J+5 comme horizon pivot, mais incite à vérifier si l'edge à J+10 ne commence pas déjà à se dégrader.
3. Le seuil 30/70 n'est **pas une constante universelle** dans la littérature — l'optimum dérive dans le temps et selon les études. Le projet doit traiter son edge actuel comme provisoire et le revalider périodiquement plutôt que de le figer dans un "mini-système" sans mécanisme de réévaluation.
4. À une magnitude d'edge aussi faible (~1 point), les coûts de transaction réels (pas juste supposés) sont le facteur le plus documenté comme capable d'annuler l'edge — c'est probablement la vérification la plus urgente avant d'investir du temps dans un sizing/mini-système dédié.
5. Aucune preuve académique solide trouvée ni pour ni contre un filtrage par régime ou secteur du signal RSI — c'est un terrain où le projet devrait tester lui-même plutôt que de s'appuyer sur la littérature (quasi inexistante en qualité académique sur ce point précis).
