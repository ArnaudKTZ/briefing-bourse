# Workspace History

> Journal chronologique de toutes les sessions et décisions importantes.
> Le plus récent en haut. Mis à jour automatiquement par Claude.
>
> **Comment ça marche :** Quand je lance la commande `/update` après une session importante, ou quand je raconte un changement significatif, Claude ajoute une entrée ici automatiquement. Je n'ai pas à écrire ce fichier manuellement.

---

## 2026-06-24

### Fiabilisation V4 + Roadmap V5 validée

- GitHub Actions cron défaillant ce matin : aucun workflow déclenché automatiquement
- Solution : cron-job.org mis en place (gratuit, externe) — 8 jobs créés pour déclencher tous les workflows via API GitHub à heure fixe
- Token GitHub Personal Access Token créé (scope workflow) et configuré dans cron-job.org
- Email V3 → V4 : sujet corrigé dans briefing_bourse_v3.py
- Analyse du briefing du jour : précision 36.5%, Vinci 99/100, BNP 93/100, Danone 89/100
- Analyse de la spec V5 rédigée par l'architecte logiciel d'Arnaud — validée et capitalisée
- Roadmap V5 complète définie en 4 phases (juillet → octobre 2026)
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
