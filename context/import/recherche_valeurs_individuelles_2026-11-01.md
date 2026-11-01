# Recherche valeurs individuelles — 01/11/2026

> Décision en attente d'Arnaud ("garde sous le coude"). Pas d'automatisation,
> pas de lien avec les agents du repo. Recherche ponctuelle via les skills
> `quality-screen` + `investment-checklist` (pack ai-berkshire), suite à la
> validation du facteur Quality/Low Vol Europe (ETF) dans l'audit du 29/10.

## Contexte

Objectif : voir si une approche fondamentale (sélection d'actions individuelles
façon Buffett/qualité) identifie des candidats solides à détenir en direct
plusieurs années, en complément des ETF facteur Quality Europe (EQUA.PA) et
Low Vol Europe (EVOE.PA) déjà recommandés pour le cœur PEA.

Candidats testés : **L'Oréal (OR.PA)**, **Air Liquide (AI.PA)**, **LVMH (MC.PA)**.

## Étape 1 — Filtrage qualité (7 indicateurs, `quality-screen`)

| Entreprise | ROE 10a | FCF 5a | Couv. intérêts | Marge brute | OCF/RN | Marge nette | Dilution 5a | Résultat |
|---|---|---|---|---|---|---|---|---|
| L'Oréal | 16,9% | +30,6 Md€ | ~38x | ~73% | 1,30x | 13,8% | -4,7% (rachats) | Passe sans réserve |
| Air Liquide | 12,6% | +13,5 Md€ | ~13x | ~59% | 2,0x | 11,0% | +0,8% (stable) | Passe sans réserve |
| LVMH | 20,5% | +67,5 Md€ | ~21x | ~67% | 1,45x | 14,3% | -1,4% (rachats) | Passe sans réserve |

Les trois passent sans exemption. Rappel du skill : ça élimine les mauvaises,
ça ne prouve pas les bonnes (pas de jugement sur le prix).

## Étape 2 — Checklist Buffett 6 points (`investment-checklist`)

Valorisations vérifiées avec l'outil `financial_rigor.py` du pack (pas de calcul
à la main). Prix et données du 01/11/2026 (yfinance + recherche web croisée).

| Entreprise | Compétence | Bonne affaire | Moat | Management | Marge de sécurité | Verdict |
|---|---|---|---|---|---|---|
| L'Oréal | ★★★★★ | ★★★★☆ | ★★★★☆ | ★★★★☆ | ★★☆☆☆ | 5/6, bloque sur le prix |
| Air Liquide | ★★★★★ | ★★★☆☆ | ★★★★★ | ★★★★☆ | ★★☆☆☆ | 5/6, bloque sur le prix |
| LVMH | ★★★★★ | ★★★★★ | ★★★★☆ | ★★★★☆ | ★★★★☆ | **6/6** |

### Valorisation actuelle (01/11/2026)

| | Prix | PE (TTM) | P/FCF | FCF yield | Div. yield |
|---|---|---|---|---|---|
| L'Oréal | 436,95€ | 37,1x | 32,5x | 3,07% | 1,65% |
| Air Liquide | 180,90€ | 32,6x | 43,2x | 2,32% | 1,86% |
| LVMH | 387,00€ | 17,8x | 13,3x | 7,50% | 3,36% |

### Trois scénarios à 5 ans (outil `three-scenario`)

| | Optimiste | Central | Pessimiste |
|---|---|---|---|
| L'Oréal (croissance 8/5/1%, PE sortie 35/30/25x) | +38,6% | +3,2% | -29,2% |
| Air Liquide (croissance 8/6/2%, PE sortie 30/26/20x) | +35,2% | +6,7% | -32,3% |
| LVMH (croissance 10/5/-2%, PE sortie 25/20/15x) | +126,4% | +43,5% | -23,8% |

## Conclusion du 01/11

- **L'Oréal et Air Liquide** : excellentes entreprises (moat fort, management
  solide), mais prix actuel sans marge de sécurité. Scénario central quasi
  plat sur 5 ans. À suivre, pas à acheter à ce niveau.
- **LVMH** : seule à passer les 6 points sans réserve. Le marché boude le
  luxe (Chine molle) ce qui a compressé son PE de ~25-30x historique à 17,8x,
  alors que les fondamentaux (ROE 20,5%, FCF yield 7,5%) restent excellents.
  Scénario central +43,5%/5 ans, scénario pessimiste plus doux (-23,8%) que
  le scénario CENTRAL des deux autres. Risque à noter : succession Bernard
  Arnault (âge, gouvernance familiale).
- Aucune décision prise. Pas de capital réel engagé, pas de ligne de code
  modifiée. Reprendre cette note si/quand la décision mûrit (vérifier que le
  contexte luxe n'a pas changé entre-temps avant d'agir sur ces chiffres).
