# Workspace History

> Journal chronologique de toutes les sessions et décisions importantes.
> Le plus récent en haut. Mis à jour automatiquement par Claude.
>
> **Comment ça marche :** Quand je lance la commande `/update` après une session importante, ou quand je raconte un changement significatif, Claude ajoute une entrée ici automatiquement. Je n'ai pas à écrire ce fichier manuellement.

---

## 2026-07-16

### Incident briefing muet 15-16/07 : NaN profond réparé, briefing rétabli

- Alerte Watchdog reçue par Arnaud : pas de briefing le 16/07 (dernier : 14/07). Diagnostic : la fermeture de la position BNP Paribas le 14/07 à 7h01 (signal ÉVITER) s'est faite sur un cours NaN (bougie Yahoo incomplète) → pnl NaN → **capital contaminé en NaN**. Le garde-fou anti-chiffres-faux du briefing (01/07) a alors correctement bloqué les briefings des 15 et 16/07 (alertes envoyées à la place). La réparation du 15/07 n'avait nettoyé que l'historique de valeur, pas le capital ni le trade
- Réparation honnête : sortie BNP reconstituée à la dernière clôture valide avant la sortie (100,92 € le 13/07, exactement ce que le code corrigé aurait utilisé), pnl -0,28%, capital recalculé depuis l'état git d'avant fermeture (1940,62 + produit net = 3848,51 €). Note de réparation tracée dans le trade. Plus aucun NaN dans le fichier (scan récursif)
- Ceinture-bretelles ajoutée dans scoring_intraday.py : jamais fermer une position sur un cours invalide (en plus du dropna du 15/07)
- Briefing du 16/07 relancé manuellement : envoyé avec succès, pipeline complet. Le portefeuille a repris son fonctionnement normal (2 ouvertures virtuelles avec le capital libéré : Hermès + BNP, 5/5 positions, valeur 9 890,93 €)
- Améliorations retenues de l'incident : le message d'alerte du briefing disait "0/39 valeurs sans données" (raison erronée, c'était le portefeuille qui était invalide) — à préciser un jour ; le briefing du 15/07 est définitivement perdu (pas de recos ce jour-là dans performance.json)

---

## 2026-07-15

### Agent Stratège créé + dossier méthodes des grands traders + fix NaN scoring

- Demande d'Arnaud : étudier les méthodes des grands traders millionnaires et créer un agent "Loup de Wall Street" qui manage les autres et le conseille. Cadrage honnête accepté : pas un super-prédicteur (97% des day traders persistants perdent, étude brésilienne ; <1% d'edge fiable à Taïwan), mais un Stratège qui audite la flotte contre les méthodes documentées des maîtres
- **Recherche profonde sourcée** (context/import/methodes_grands_traders.md) : Simons/Medallion (66%/an brut avec 50,75% de réussite seulement), Tudor Jones (MM200, losers average losers, 5:1), Soros/Druckenmiller (sizing par conviction), Turtles (règles publiques complètes : 2%/trade, unités de volatilité), O'Neil/Minervini, Schwager, Livermore (mort ruiné), contre-poids académique (Brésil/Taïwan/Barber-Odean) et validation AQR du trend lent (positif chaque décennie depuis 1880). **20 principes codifiés testables (P1-P20)**
- **Audit de la flotte intégré** : forts sur 7 principes (mesure, discipline, poches étanches), trou béant = AUCUN moteur de risque (P1/P2/P5/P9/P11/P12 absents : taille fixe 2000€, pas de stop à l'entrée, pas de limite sectorielle, pas de frein drawdown). Constat : les grands parlent de gestion, jamais de prédiction ; notre V4 a fait l'inverse. Priorité n°1 qui en sort : le Risk Engine (Phase 2 V5 jamais construite)
- **Agent Stratège en prod** (agent_stratege.py, workflow stratege.yml, le 4 du mois 18h, job cron-job.org créé) : collecte les faits chiffrés de toute la flotte en Python (drawdowns, concentration, edge net, IC, coûts), les confronte aux 20 principes, produit une page de conseil + UNE proposition avec protocole de test. 1 appel Sonnet 4.6/mois. Gouvernance : conseille seulement, jamais de signal marché, le Professeur reste juge, la recette garde le veto, Arnaud décide. Spec mise à jour (carte, trombinoscope "le coach qui a étudié tous les champions", B.15/B.16)
- **Les 8 anciens jobs cron-job.org recalés aux heures nominales** (ils tournaient 2h trop tôt depuis le 24/06) : Briefing 5h→7h, News 4h45→6h45, Watchdog 5h30→7h30, Espion lundi 4h15→6h15, Scoring 7h/9h30/12h/14h→9h/11h30/14h/16h (heures de marché retrouvées). Fuseau Europe/Paris par job, donc l'heure d'hiver ne décalera plus rien. Vérifié job par job puis sur la liste rechargée. Dès demain le briefing arrive à 7h
- **Incident réparé au passage** : le scoring du 14/07 a écrit une valeur NaN dans l'historique du satellite (bougie Yahoo incomplète, même famille que l'incident du 01/07 mais dans le chemin scoring). Fix : filtrage des Close NaN dans scorer_action + garde-fou à l'écriture de la valeur portefeuille (jamais de NaN persisté). Point du 14/07 retiré de l'historique (valeur réelle inconnue). Le Stratège est lui-même blindé contre les NaN

---

## 2026-07-13

### Bilan Agent Bourse + edge net de frais + critères du 22/07 figés

- Bilan complet demandé par Arnaud, chiffres au 13/07 : cœur DM +2,3% (10 232 €, poche USA maintenue grâce au buffer 3%), satellite -1,0% (9 899 €, 2 trades gagnants sur 12 clos, 202 € de frais cumulés soit 2% du capital)
- Convergence des trois juges contre le satellite : Shadow (alertes NUISIBLES, -1,71 pt sous CAC net à J+5), Évaluateur (IC -0,050 avec 25% de jours positifs, le score classe à l'envers, bucket 85+ pire que 75-84), Professeur (Briefing V4 noté E, précision 43,5% en baisse)
- Infra saine : data quality 0 erreur depuis le 06/07, watchdog OK, coûts API 1,55 $ au total. Repo local resynchronisé (était 38 commits derrière)
- Piste rituelle implémentée : **edge NET de frais dans l'Évaluateur** (péage 1% aller-retour déduit, aligné Shadow/scoring). Colonne "Edge NET" dans l'email, champ edge_net dans le JSON, verdict exprimé en net. Vérifié en local : edge brut +0,04 pt à J+5 = -0,96 pt net, "perdant en réel". ÉVITER laissés en brut (ne pas acheter ne coûte rien)
- **Critères du bilan 22/07 figés à froid** (ECHEANCES.md + spec) : IC ≤ 0 OU edge net ≤ 0 → satellite 100% virtuel et effort sur Phase 1 V5 ; IC ≥ +0,03 ET edge net > 0 → candidat budget réel réduit ; entre les deux → re-bilan 22/08. Trajectoire au 13/07 = gel virtuel + Phase 1 V5
- Spec mise à jour : annexe B.7 (analogie salaire brut/net), carte Évaluateur, rendez-vous 22/07 avec la grille figée
- **Crypto Dual Momentum lancé en production** (décision Arnaud) : agent_crypto_dm.py + workflow crypto_dm.yml (1er du mois 8h15, après le DM actions). Réglages strictement fidèles au backtest validé : rotation pure BTC/ETH, lookback 12 FIXE, refuge stablecoin, frais 0,5%/rotation, décision sur clôtures de fin de mois (pas de look-ahead), SOL exclu. Portefeuille virtuel 1 000 $ vs B&H BTC. Noté par le Professeur chaque dimanche (evaluer_crypto_dm). Premier signal réel : BTC -45% et ETH -37% sur 12 mois → refuge stablecoin d'entrée, l'airbag s'active dès le lancement (bear market crypto en cours). Note fiscale dans l'email de rotation : passer par un stablecoin plutôt que par des euros évite de cristalliser la flat tax (crypto→crypto non imposable, art. 150 VH bis). Spec mise à jour (carte agent, trombinoscope A.3, B.1 troisième poche, roadmap). Job cron-job.org à créer (comme Dividendes)
- **Jobs cron-job.org créés via Chrome** (session d'Arnaud) : Dividendes (lundi 8h05 Paris) et Crypto DM (1er du mois 8h15 Paris), par clonage d'un job existant (les en-têtes avec le token GitHub sont copiés côté serveur, jamais manipulés). Tests 204 pour les deux, configuration revérifiée après rechargement complet. 12 jobs actifs. Le test Dividendes a utilement envoyé le rapport du lundi (le cron GitHub n'avait pas tourné ce matin, dernier run planifié le 06/07). Constat au passage : les jobs du 24/06 (Briefing, News, Scoring, Espion, Watchdog) tournent 2h plus tôt que l'heure nominale (d'où le briefing à 5h), ceux créés depuis le 02/07 sont à l'heure Paris exacte. Token GitHub des jobs : expire le 23/06/2027, échéance de renouvellement notée
- Toujours en attente de décision Arnaud : les trois décisions du 02/08 (alertes, poids News/Espion, budget satellite)

---

## 2026-07-02

### Audit complet Agent Bourse + réparation de 3 bugs critiques

- Audit complet du projet demandé par Arnaud (agents, workflows, scoring, données, coûts) : verdict 6/10, architecture saine mais bugs critiques découverts
- Bug critique 1 : les stats de précision étaient empoisonnées — le 01/07 les recos du 30/06 ont été jugées contre des prix NaN (NaN est truthy en Python, le garde "not prix" ne le filtrait pas), et la relance du briefing à 13h53 a compté la même journée en double
- Réparation : stats recalculées depuis zéro sur l'historique propre — 305 → 211 échantillons, précision réelle 42.7% (ACHETER 40.8%, ÉVITER 46.4%). Garde _prix_valide() ajouté dans les deux boucles d'évaluation
- Bug critique 2 : les trades intraday n'ont jamais existé — scoring_intraday.yml ne commitait pas portefeuille_virtuel.json, chaque décision intraday (stop-loss, take-profit, achats 80+) était perdue à chaque run. Même bug sur dual_momentum.yml (rééquilibrage mensuel du 01/07 perdu, point de valorisation 10136.94€ restauré) et briefing_bourse.yml (costs_log.json jamais commité, coûts Opus invisibles du rapport hebdo)
- Bug majeur 3 : tous les workflows poussaient avec "|| true" sans se resynchroniser — un push rejeté = données silencieusement perdues. git pull --rebase ajouté avant chaque push dans les 8 workflows
- Constat stratégique : précision ACHETER sous 50% + frais ~1% par aller-retour = le satellite détruit de la valeur en l'état. Points forts confirmés : Dual Momentum backtesté (le plus solide), agent Professeur avec garde-fou méta, séparation cœur/satellite
- Décision Arnaud : modèle V4 laissé en observation, mais alertes email achat/vente suspendues 1 mois (flag ALERTES_EMAIL_ACTIVES dans scoring_intraday.py), en reparler ~02/08 (rappel programmé). Pas de reprise automatique
- Agent Shadow créé (vendredi 18h35) : contrefactuel des alertes suspendues — rejoue chaque alerte (2000€, frais inclus, sortie J+1/J+3/J+5) vs CAC. Journal permanent shadow_alertes.json alimenté par le scoring. Premier verdict sur les alertes réelles du 26/06-02/07 : NUISIBLES (-1.73% net à J+1, 21% gagnantes, -2.4 pts sous le CAC à J+3)
- Agent Évaluateur créé (samedi 7h35) : mesure multi-horizons rétroactive — rendement ACHETER/ÉVITER à J+1/J+3/J+5/J+10 vs l'univers CAC40 le même jour (vrai benchmark) + buckets de score. Premier verdict : ACHETER +0.70 pts vs univers à J+5 et ÉVITER utiles, MAIS edge < frais et le score ne discrimine pas (bucket 85+ fait pire que 75-84)
- Jobs cron-job.org créés pour Shadow et Evaluateur (Claude a pris la main sur Chrome, jobs testés 204, workflows GitHub vérifiés en succès). 10 jobs actifs au total
- Décision en suspens (à trancher par Arnaud le 02/08) : réactivation des alertes + réduire ou non le budget par position du satellite (2000€ → 500€ ?)
- Idées reportées avec raisons : Agent Dividendes PEA (quick win, n'importe quand), Agent Patrimoine global (session dédiée avec données réelles), Crypto Dual Momentum (après bilan 22/07, via harnais)
- Spec mise à jour : docs/Architecture_Agent_Bourse_V5.html reflète tout (agents Shadow/Évaluateur, suspension, fiabilité données, persistance CI, rendez-vous 22/07 et 02/08)
- Destinataires des 4 rapports hebdo (Professeur, Veille, Shadow, Évaluateur) fixés en dur à zoho + xtrem111, secret DESTINATAIRES_HEBDO retiré des workflows
- Audit de contribution News/Espion (demandé par Arnaud, question "agents trop légers ?") : mesure rétroactive depuis git (312 obs News, 117 Espion) des rendements forward vs univers CAC40. Constat : le sentiment News n'a aucun edge positif tel que pondéré (signal penchant à l'envers, bucket négatif surperforme), bonus Espion non mesurable (données institutionnelles Yahoo vides sur les .PA). Le vrai problème n'était pas la légèreté mais l'absence de mesure (Professeur les notait [C] depuis le début)
- Décision : POIDS_NEWS et POIDS_ESPION mis à 0 (briefing + intraday), constantes réversibles. Collecte maintenue, seul le poids dans le score coupé. Retest ~02/08 intégré au rappel programmé
- Idées reportées mises à jour : muscler News/Espion seulement si le retest montre un edge (ne jamais enrichir un agent non mesuré)

---

## 2026-07-01

### Fix NaN briefing + garde-fou anti-chiffres-faux + log qualité données

- Briefing du matin rempli de "nan" : Yahoo Finance a renvoyé une dernière bougie incomplète (Close = NaN) sur la quasi-totalité des valeurs Euronext Paris (.PA) à 7h, seules les valeurs non-.PA (STMicro, ArcelorMittal, Stellantis) avaient un prix valide
- Fix : filtrage des lignes Close NaN avant lecture du dernier cours dans recuperer_donnees_action et recuperer_indice_cac (retombe sur le dernier cours valide connu)
- Garde-fou ajouté : si la valeur du portefeuille est NaN malgré tout, email d'alerte court à la place du briefing normal (pas de chiffres faux envoyés), historique non pollué, dernière valeur connue conservée
- Journalisation qualité données : data_quality_log.json (log glissant ~3 mois) trace combien de valeurs sont sans données à chaque run — servira à décider si la diversification des sources (V5 phase 4, octobre) doit être avancée
- Piste d'amélioration proposée et retenue : transformer les échecs silencieux en échecs visibles

---

## 2026-06-24

### Fiabilisation V4 + Roadmap V5 validée + idées futures

- GitHub Actions cron défaillant ce matin : aucun workflow déclenché automatiquement
- Solution : cron-job.org mis en place (gratuit, externe) — 8 jobs créés pour déclencher tous les workflows via API GitHub à heure fixe
- Token GitHub Personal Access Token créé (scope workflow) et configuré dans cron-job.org
- Email V3 → V4 : sujet corrigé dans briefing_bourse_v3.py
- Analyse du briefing du jour : précision 36.5%, Vinci 99/100, BNP 93/100, Danone 89/100
- Analyse de la spec V5 rédigée par l'architecte logiciel d'Arnaud — validée et capitalisée
- Roadmap V5 complète définie en 4 phases (juillet → octobre 2026)
- Tableau portefeuille PWA amélioré : quantité, prix achat, cours actuel, valeur position, gain/perte
- Idée future validée : "Bon de commande PWA" — notification push + ordre complet (valeur, quantité, prix limite, stop loss, take profit) pour chaque signal achat/vente, 1 clic pour valider sur Boursobank
- Idée future validée : passage d'ordres semi-automatique intraday — alertes stop loss / take profit / signal retourné avec bon de commande push en cours de journée
- Document architecture à refaire en V5 avec toutes les nouvelles fonctionnalités
- Document Architecture_Agent_Bourse_V5.html créé avec : V4 en prod, 4 couches V5, nouveaux agents, bon de commande PWA, séquencement complet, roadmap 4 phases, critères de succès, 15 évolutions du cœur des agents existants
- Principe établi : à chaque session Arnaud peut demander "challenge les agents" pour générer de nouvelles idées d'amélioration basées sur les données réelles
- Phase 1 (22 juillet) : Data Quality + Feature Engine + Score Engine 4 sous-scores + auto-apprentissage
- Phase 2 (août) : Risk Engine + Briefing V5 + Alerteur V5 + Watchdog V5
- Phase 3 (septembre) : Backtest / Walk-forward / Calibration
- Phase 4 (octobre) : Agent Macro+ + Agent Insider + diversification sources (plus Yahoo seul)
- Point faible identifié : toutes les données viennent de Yahoo Finance uniquement — risque de panne et données fondamentales en retard
- Décision : garder Yahoo pour cours intraday, diversifier pour fondamentaux et news en V5

---

## 2026-06-23

### PWA iPhone + corrections critiques + conformité V4

- Clé API Anthropic révoquée automatiquement par GitHub (était dans le code git avant migration secrets) — nouvelle clé créée et mise en place dans GitHub Secrets
- PWA iPhone opérationnelle : installée sur écran d'accueil, notifications activées, PIN de sécurité
- Rendu Markdown dans le briefing PWA : tableaux avec vraies colonnes, titres colorés, ACHETER/ÉVITER/SURVEILLER en vert/rouge/jaune, Haussier/Baissier colorés
- Portefeuille virtuel visible dans les deux écrans (Scores ET Briefing) via cache global
- Portefeuille remonté en haut de la vue Scores (juste après les macros)
- Service worker passé en v4 pour forcer l'invalidation du cache Safari
- Vérification conformité specs V4 : tous les agents conformes (Briefing, Scoring intraday 4x/jour, News 3x/jour, Espion lundi 6h15, Watchdog 7h30)
- Repo sécurisé : aucune donnée sensible dans les fichiers, tout dans GitHub Secrets
- Prochaine échéance : bilan + auto-apprentissage agents secondaires le 22 juillet

### Agent Bourse V4 — Architecture multi-agents finalisée

- Architecture V4 en production : 5 agents actifs (Briefing, Scoring intraday, News, Espion, Watchdog)
- Briefing email enrichi : portefeuille virtuel intégré, narration sectorielle, alertes détaillées, auto-réflexion sur la précision
- Scoring intraday passé à 4x/jour avec rotation sectorielle ETF en temps réel
- Document d'architecture créé et téléchargeable (rôles, séquencement, flux de données)
- Décision : auto-apprentissage des agents secondaires reporté au 22 juillet (pas assez de données)
- Agents en réserve identifiés : Agent Macro+ et Agent Insider
- Niveau agent estimé : 8/10
- Précision actuelle : 50% (base de départ, s'affinera avec le temps)

---

## 2026-06-19

### Agent bourse V3 — Tests et décision stratégique

- V3 confirmée en production sur GitHub Actions (coche verte, run réussi)
- Portefeuille virtuel : frais de courtage et dividendes volontairement exclus pour l'instant
- Décision : laisser tourner 3-4 semaines avant toute amélioration du modèle
- Bilan prévu fin juillet pour analyser l'historique de performance et décider des évolutions

---

## 2026-06-19

### Mise en place du briefing bourse automatique

- Ouverture d'un PEA : stratégie mixte ETFs long terme (CAC 40, MSCI World, S&P 500) + actions court/moyen terme
- Watchlist : les 40 valeurs du CAC 40
- Routine Claude configurée : briefing quotidien lundi-vendredi à 8h dans la section Routines
- Script Python créé (briefing_bourse.py) : appel API Claude + envoi email via Zoho SMTP
- GitHub Actions configuré : exécution automatique dans le cloud, Mac éteint ou allumé
- Destinataires : xtrem111team@gmail.com + ferrey83400@gmail.com
- Comptes créés : GitHub (ArnaudKTZ), dépôt privé briefing-bourse
- Section dividendes de la semaine tous les lundis, top 3 opportunités chaque jour

---

## 2026-06-19

### Projet solaire piscine - étude et recherche

- Dimensionnement : pompe PPB 0,75 CV (~550W), besoin ~1 200W de panneaux pour couvrir la filtration
- Objectif élargi : couvrir la pompe piscine ET réduire la facture EDF globalement
- Techno retenue : monocristallin, micro-onduleurs (meilleurs que onduleur central pour toiture)
- Kit visé : plug-and-play ~3 000W pour toiture
- Sites fiables identifiés : Sunethic (meilleur SAV, panneaux français Voltec), La Boutique Solaire et Upwatt (micro-onduleurs Hoymiles), PVDF
- Marques panneaux fiables : Longi Solar (référence mondiale), Voltec (français)
- Points de vigilance : déclaration préalable en mairie requise (>3 kWc), vérifier fixations toiture incluses

---

## 2026-06-19

### Évolutions AT26_Newsletter — Avancement planning & UX

- Refonte complète de l'onglet "Bilan hebdomadaire" renommé "Avancement planning"
- Intégration du fichier Excel Planning AT26 COVIE : extraction des dates de début/fin par tâche (niveau 6) pour 37 locaux
- Courbe d'avancement prévisionnel par local et globale (profil actif) basée sur les durées réelles du planning Excel
- Superposition courbe réelle vs prévisionnelle : snapshot automatique à chaque "Publier" avec la date de la NL (pas la date du jour), stocké dans history-{pid} du JSON réseau
- Caractéristiques locaux affichées sur chaque mini-graphique (surface + type)
- Titre du graphique global dynamique avec le nom du profil ouvert
- Refonte du login en 2 étapes : validation profil/mdp puis chargement obligatoire du dossier réseau avant entrée dans l'app (avec option "Continuer sans réseau")
- Sélecteur NL : ajout d'un date picker synchronisé bidirectionnellement avec le numéro de NL
- Bloc Actions de "Saisie des données" rendu sticky (toujours visible au scroll)
- Suppression des lignes N/A dans Planning & avancement pour tous les profils

---

## 2026-06-16

### Evolution majeure AT26_Newsletter — Profils, PDF, UX

- Fusion Arnaud + Matthieu en un seul profil "Hyg. & San." avec fichier JSON partagé (storageId hygiene)
- Redistribution des périmètres : Houari devient "Postes Lot 1&2" (13 locaux), Angélique devient "Postes Lot 3&4" (7 locaux), WPM inchangé
- 33 locaux vérifiés, zéro oubli, zéro doublon
- Générateur PDF jsPDF ajouté (téléchargement direct sans dialog Firefox)
- Sauvegarde auto localStorage à chaque changement d'onglet
- Bannière rouge "données non publiées" avec bouton Publier maintenant
- Dropdown travaux : option "— Aucun travaux —" pour remettre à vide
- Bouton "Vider" par local pour effacer tous les champs d'un local

---

## 2026-06-15

### Audit complet KTZ71.com

- Audit technique : WordPress + WooCommerce, dernière mise à jour janvier 2022, 6 annonces périmées
- Problèmes critiques identifiés : mentions légales absentes (404), e-garage 404, email personnel exposé dans les fiches, fiches annonces vides (pas de prix, une photo, zéro caractéristiques)
- Problèmes majeurs : parcours UX cassé, zéro preuve sociale, contenu éditorial absent, pages orphelines indexées
- Plan d'action établi : 15 étapes classées par criticité (stratégie, légal, technique, contenu, design)
- Mentions légales rédigées, en attente des informations à compléter (adresse, hébergeur, statut)
- Prochaines étapes : compléter les mentions légales, rédiger la politique RGPD, corriger la page e-garage, refaire les fiches annonces

### Migration Firefox + Export PDF — AT26_Newsletter_v2_6_18

- Adaptation de la newsletter pour Firefox (PC de travail Naval Group, sans droits admin)
- Remplacement du File System Access API (non supporté Firefox) par un système import/export JSON
- Chargement des données réseau au démarrage via sélection de dossier (webkitdirectory)
- Sauvegarde automatique en localStorage à chaque action
- Bouton "Publier" pour exporter le JSON du profil vers le dossier réseau partagé
- Bouton "↺ Sync" pour recharger les données de tous les profils depuis le réseau
- Alerte à la fermeture si données non publiées
- Remplacement de l'export PDF html2canvas (page blanche sur Firefox) par window.print() natif
- Création du PowerPoint de présentation utilisateur : COVIE_AT26_Guide_Utilisateur.pptx (17 slides)

### Développement AT26_Newsletter — Suivi OTs + dossier partagé réseau

- Calendrier étendu de N°021 à N°072 (fin chantier 10/11/2026)
- Ajout File System Access API : un fichier JSON par profil sur dossier réseau partagé, zéro risque d'écrasement entre RLT
- Bouton ↺ Sync pour recharger les données de tous les profils
- Nouveau menu "Suivi des OTs" : chargement Excel, filtre CDG-AT26-00 sur colonne E (Arrêt), tableau avec statuts colorés, persistance par profil
- Corrections : bug de layout (page hors du .main), variables manquantes, colonne de filtrage corrigée de F vers E

---

## 2026-06-12

### Installation initiale de Lewis

- Workspace personnalisé pour Arnaud, basé à Six-Fours-les-Plages (Var)
- Profil principal : Employé, ingénieur en mécanique
- Activité : Responsable de travaux chez Naval Group, maintenance des bateaux de la Marine Nationale
- Objectifs court terme identifiés : promotion professionnelle (communication hiérarchie) + lancement projet personnel (bourse / véhicules d'exception)
- Vision long terme : tripler les revenus sur 1 à 3 ans
- Projets actifs au démarrage : projet personnel en cours de définition (bourse + KTZ71.com), promotion Naval Group
- Domaine d'aide prioritaire : productivité et organisation au quotidien
- Style de communication choisi : direct et sans fioritures
