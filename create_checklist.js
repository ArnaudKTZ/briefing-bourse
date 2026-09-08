const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  AlignmentType, HeadingLevel, BorderStyle, WidthType, ShadingType,
  LevelFormat, PageNumber, Header, Footer
} = require('docx');
const fs = require('fs');

const teal = "1A7A6E";
const lightTeal = "E8F5F3";
const orange = "E67E22";
const lightOrange = "FEF9F5";
const gray = "F5F5F5";

const border = { style: BorderStyle.SINGLE, size: 1, color: "DDDDDD" };
const borders = { top: border, bottom: border, left: border, right: border };
const noBorder = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
const noBorders = { top: noBorder, bottom: noBorder, left: noBorder, right: noBorder };

function heading1(text) {
  return new Paragraph({
    children: [new TextRun({ text, bold: true, size: 28, color: "FFFFFF", font: "Arial" })],
    spacing: { before: 300, after: 200 },
    shading: { fill: teal, type: ShadingType.CLEAR },
    indent: { left: 200, right: 200 },
  });
}

function heading2(text) {
  return new Paragraph({
    children: [new TextRun({ text, bold: true, size: 24, color: teal, font: "Arial" })],
    spacing: { before: 280, after: 100 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: teal } },
  });
}

function durationLine(text) {
  return new Paragraph({
    children: [
      new TextRun({ text: "⏱ ", size: 20, font: "Arial" }),
      new TextRun({ text, size: 20, bold: true, color: "555555", font: "Arial", italics: true }),
    ],
    spacing: { before: 60, after: 60 },
    shading: { fill: "F0F0F0", type: ShadingType.CLEAR },
    indent: { left: 200 },
  });
}

function checkItem(text) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  const runs = parts.map(part => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return new TextRun({ text: part.slice(2, -2), bold: true, size: 20, font: "Arial" });
    }
    return new TextRun({ text: part, size: 20, font: "Arial" });
  });
  return new Paragraph({
    numbering: { reference: "checkboxes", level: 0 },
    children: runs,
    spacing: { before: 40, after: 40 },
  });
}

function warningBox(items) {
  const children = [
    new Paragraph({
      children: [new TextRun({ text: "⚠️  Points de vigilance", bold: true, size: 20, color: "7D3C00", font: "Arial" })],
      spacing: { before: 60, after: 60 },
    }),
    ...items.map(item => new Paragraph({
      numbering: { reference: "warnings", level: 0 },
      children: [new TextRun({ text: item, size: 19, color: "5D4037", font: "Arial" })],
      spacing: { before: 30, after: 30 },
    }))
  ];
  return new Table({
    width: { size: 9026, type: WidthType.DXA },
    columnWidths: [9026],
    rows: [new TableRow({ children: [new TableCell({
      borders,
      width: { size: 9026, type: WidthType.DXA },
      shading: { fill: "FFF3E0", type: ShadingType.CLEAR },
      margins: { top: 100, bottom: 100, left: 200, right: 200 },
      children,
    })] })]
  });
}

function spacer() {
  return new Paragraph({ children: [new TextRun("")], spacing: { before: 80, after: 0 } });
}

const doc = new Document({
  numbering: {
    config: [
      {
        reference: "checkboxes",
        levels: [{
          level: 0,
          format: LevelFormat.BULLET,
          text: "☐",
          alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 500, hanging: 300 } } }
        }]
      },
      {
        reference: "warnings",
        levels: [{
          level: 0,
          format: LevelFormat.BULLET,
          text: "–",
          alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 400, hanging: 200 } } }
        }]
      },
    ]
  },
  sections: [{
    properties: {
      page: {
        size: { width: 11906, height: 16838 },
        margin: { top: 1000, right: 1000, bottom: 1000, left: 1000 }
      }
    },
    headers: {
      default: new Header({ children: [
        new Paragraph({
          children: [
            new TextRun({ text: "Checklist Montage — Piscine Magnelis Océane", bold: true, size: 18, color: teal, font: "Arial" }),
            new TextRun({ text: "     |     2 jours – 2 personnes – Sans volet immergé", size: 18, color: "888888", font: "Arial" }),
          ],
          border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: teal } },
        })
      ]})
    },
    footers: {
      default: new Footer({ children: [
        new Paragraph({
          children: [
            new TextRun({ text: "Notice officielle Piscine Discount     |     Page ", size: 16, color: "AAAAAA", font: "Arial" }),
            new TextRun({ children: [PageNumber.CURRENT], size: 16, color: "AAAAAA", font: "Arial" }),
          ],
          alignment: AlignmentType.CENTER,
          border: { top: { style: BorderStyle.SINGLE, size: 2, color: "DDDDDD" } },
        })
      ]})
    },
    children: [
      // TITRE
      new Paragraph({
        children: [new TextRun({ text: "CHECKLIST MONTAGE", bold: true, size: 52, color: teal, font: "Arial" })],
        alignment: AlignmentType.CENTER,
        spacing: { before: 200, after: 100 },
      }),
      new Paragraph({
        children: [new TextRun({ text: "Piscine Acier Magnelis Océane — Piscine Discount", size: 26, color: "555555", font: "Arial" })],
        alignment: AlignmentType.CENTER,
        spacing: { before: 0, after: 60 },
      }),
      new Paragraph({
        children: [new TextRun({ text: "⏱ Durée totale : 5-6 semaines (6 jours de travail + séchages)     |     👥 2 personnes minimum", size: 20, color: "FFFFFF", bold: true, font: "Arial" })],
        alignment: AlignmentType.CENTER,
        spacing: { before: 100, after: 200 },
        shading: { fill: teal, type: ShadingType.CLEAR },
        indent: { left: 100, right: 100 },
      }),

      // AVANT DE COMMENCER
      heading1("AVANT DE COMMENCER"),
      checkItem("Vérifier que la liste du matériel est complète (sortir toutes les pièces, les regrouper par type et les compter)"),
      checkItem("Prévoir un **électricien qualifié** pour les branchements électriques"),
      checkItem("Vérifier que l'alimentation en eau est suffisante"),
      checkItem("Choisir un jour ensoleillé, **sans grand vent**"),
      checkItem("Prévoir le **dispositif différentiel 30 mA** sur l'alimentation de la pompe"),
      spacer(),
      new Paragraph({
        children: [new TextRun({ text: "Outils : perceuse à percussion, disqueuse, marteau, aspirateur, clé 17, mètre ruban, cordex, tournevis, tire-fil électricien, clés à cliquet 13/17/24, niveau, scie à métaux, cutter, ciseaux", size: 18, color: "555555", italics: true, font: "Arial" })],
        spacing: { before: 60, after: 100 },
        shading: { fill: gray, type: ShadingType.CLEAR },
        indent: { left: 200 },
      }),

      // ETAPE 01
      heading2("ÉTAPE 01 — TERRASSEMENT"),
      durationLine("Durée estimée : 1 demi-journée (avec mini-pelle)"),
      checkItem("Creuser **minimum 1m de plus** que les dimensions de la piscine en long et en large"),
      checkItem("Profondeur = hauteur des panneaux (1m50) + hauteur de la dalle (15 à 20 cm)"),
      spacer(),
      warningBox([
        "Vérifier le plan de masse avant de creuser (fils électriques, canalisations enterrées)",
        "Prévoir l'évacuation des déblais (volume important)",
        "S'assurer que le fond est parfaitement horizontal avant de continuer",
      ]),

      // ETAPE 02
      heading2("ÉTAPE 02 — MISE EN PLACE DE LA BONDE DE FOND ET CANALISATION"),
      durationLine("Durée estimée : 1h"),
      checkItem("Installer la bonde de fond **au centre de la dalle** (niveau 0 du radier)"),
      checkItem("Raccorder le tuyau à la bonde avec le raccord fourni dans le kit plomberie"),
      checkItem("Sceller la bonde de fond avec du mortier"),
      checkItem("Poser un **scotch de protection** sur la bonde avant de couler la dalle"),
      spacer(),
      warningBox([
        "La bonde doit être exactement au niveau 0 du radier fini — trop haute ou trop basse = problème sous le liner",
        "Ne pas oublier le scotch de protection avant coulage : impossible à nettoyer après",
        "Vérifier l'étanchéité du raccord tuyau/bonde avant de couler",
      ]),

      // ETAPE 03
      heading2("ÉTAPE 03 — MISE EN PLACE DU TREILLIS SOUDÉ"),
      durationLine("Durée estimée : 1h"),
      checkItem("Positionner le treillis soudé au fond du terrassement"),
      checkItem("Le surélever sur des cales pour qu'il se trouve **au milieu de la dalle**"),
      spacer(),
      warningBox([
        "Le treillis doit être surélevé sur des cales, pas posé à plat — sinon il ne renforce pas la dalle",
        "Découper proprement aux angles pour que le treillis s'adapte à la forme du bassin",
      ]),

      // ETAPE 04
      heading2("ÉTAPE 04 — COULAGE DALLE BÉTON"),
      durationLine("Durée estimée : 1 journée + 15 à 20 jours de séchage obligatoire"),
      checkItem("Couler la dalle béton dosée à **350 kg/m3**"),
      checkItem("Épaisseur entre **15 et 20 cm** (béton autonivelant possible)"),
      checkItem("Laisser sécher **15 à 20 jours** — ne pas poursuivre avant"),
      spacer(),
      warningBox([
        "Respecter impérativement le dosage 350 kg/m3",
        "La dalle doit être parfaitement plane — tout défaut se répercute sur les panneaux",
        "Attendre impérativement le séchage complet avant de reprendre — une dalle pas sèche se fissure",
      ]),

      // ETAPE 05
      heading2("ÉTAPE 05 — TRAÇAGE AU SOL"),
      durationLine("Durée estimée : 30 min"),
      checkItem("Repérer les 4 angles (A1, A2, A3, A4) selon les dimensions intérieures du bassin"),
      checkItem("Mesurer les 2 diagonales et ajuster jusqu'à ce que **D1 = D2** (parfaitement carré)"),
      checkItem("Tracer les contours à l'aide du cordex"),
      spacer(),
      warningBox([
        "Étape la plus critique : si le traçage est faux, les panneaux ne s'assembleront pas",
        "Vérifier les diagonales plusieurs fois avant de tracer",
        "Prendre les dimensions INTÉRIEURES du bassin, pas extérieures",
      ]),

      // ETAPE 06
      heading2("ÉTAPE 06 — MONTAGE DES PANNEAUX"),
      durationLine("Durée estimée : 3 à 4h"),
      checkItem("Commencer par un angle, assembler les panneaux avec vis + écrous M10"),
      checkItem("Respecter la nomenclature selon la dimension du bassin (skimmer et buses aux bons emplacements)"),
      checkItem("Vérifier la verticalité et l'alignement par rapport au traçage"),
      spacer(),
      warningBox([
        "Bien identifier les panneaux avant de commencer (skimmer, buse, plein) — une erreur = tout démonter",
        "Ne pas serrer les vis définitivement tout de suite : ajuster l'ensemble d'abord",
        "Vérifier régulièrement la verticalité au niveau",
      ]),

      // ETAPE 07
      heading2("ÉTAPE 07 — FIXATION AU SOL"),
      durationLine("Durée estimée : 1h30"),
      checkItem("Aligner la face intérieure du panneau sur le traçage"),
      checkItem("Avec le foret béton de 12, traverser le trou pré-percé du panneau puis percer la dalle"),
      checkItem("Aspirer la poussière avant mise en place de la cheville"),
      checkItem("Fixer avec cheville M12x50 + tirefond M10x50 + rondelle M10"),
      spacer(),
      warningBox([
        "Aspirer impérativement la poussière avant de poser la cheville — sinon ancrage insuffisant",
        "Vérifier l'alignement sur le traçage avant de percer (impossible de corriger après)",
      ]),

      // ETAPE 08
      heading2("ÉTAPE 08 — FIXATION JAMBES DE FORCE"),
      durationLine("Durée estimée : 2h"),
      checkItem("Fixer le haut des jambes de force au panneau vertical (2ème trou en partant du haut)"),
      checkItem("**Pas de jambes de force dans les angles**"),
      checkItem("Vérifier la verticalité et l'alignement des panneaux avant de visser au sol"),
      checkItem("Fixer les jambes de force sur la dalle béton"),
      spacer(),
      warningBox([
        "Vérifier la verticalité AVANT de fixer les jambes — c'est le dernier moment pour corriger",
        "Ne pas oublier de jambes de force : elles maintiennent la structure contre la pression de l'eau et du remblai",
      ]),

      // ETAPE 09
      heading2("ÉTAPE 09 — MONTAGE DES PROFILÉS DE FIXATION DE LINER"),
      durationLine("Durée estimée : 1h"),
      checkItem("Vérifier la longueur des profilés d'accrochage Hung, recouper à la scie à métaux si besoin"),
      checkItem("Fixer les profilés par-dessus à l'aide des vis autoforeuses"),
      spacer(),
      warningBox([
        "Les profilés doivent être continus sur tout le pourtour — un trou = liner qui peut décrocher",
        "Dégraisser les bords des coupes à la scie à métaux pour éviter de déchirer le liner",
      ]),

      // ETAPE 10
      heading2("ÉTAPE 10 — POSE DU SKIMMER"),
      durationLine("Durée estimée : 30 min"),
      checkItem("Passer le skimmer dans l'emplacement prévu"),
      checkItem("Le fixer par l'intérieur avec les vis de préfixation fournies"),
      spacer(),
      warningBox([
        "Fixation provisoire à cette étape — le skimmer sera bridé définitivement après le liner (étape 21)",
        "Ne pas serrer à fond",
      ]),

      // ETAPE 11
      heading2("ÉTAPE 11 — POSE DES PIÈCES À SCELLER"),
      durationLine("Durée estimée : 30 min"),
      checkItem("Passer les pièces à sceller (buses de refoulement, prise balai) dans les emplacements prévus"),
      checkItem("Les bloquer par l'arrière à l'aide de l'écrou"),
      spacer(),
      warningBox([
        "Fixation provisoire — le bridage définitif se fait après le liner (étape 21)",
        "Vérifier que les pièces sont bien orientées (sens de passage de l'eau)",
      ]),

      // ETAPE 12
      heading2("ÉTAPE 12 — MONTAGE DU PASSE CÂBLE PROJECTEUR"),
      durationLine("Durée estimée : 30 min"),
      checkItem("Coller l'ensemble PVC courbe grand rayon sur la prise balai"),
      checkItem("Coller la boîte de connexion en alignant le haut avec la finition choisie (margelles...)"),
      spacer(),
      warningBox([
        "Aligner le haut de la boîte de connexion avec la hauteur définitive de la margelle",
        "La colle PVC prend vite : bien positionner avant de coller",
      ]),

      // ETAPE 13
      heading2("ÉTAPE 13 — RACCORDEMENT DES BUSES À LA POMPE"),
      durationLine("Durée estimée : 2h"),
      checkItem("Raccorder buses de refoulement, prise balai et skimmer au local technique selon le schéma"),
      spacer(),
      warningBox([
        "Respecter le schéma de raccordement de la notice — ne pas improviser l'ordre des connexions",
        "Utiliser du tuyau souple entre la piscine et le local technique pour absorber les vibrations",
        "Prévoir des longueurs suffisantes avant de coller (impossible de rallonger après)",
      ]),

      // ETAPE 14
      heading2("ÉTAPE 14 — RACCORDEMENT DANS LE LOCAL TECHNIQUE"),
      durationLine("Durée estimée : 2h + intervention électricien"),
      checkItem("Raccorder l'ensemble dans le local technique selon le schéma électrique/hydraulique"),
      checkItem("Câble pompe : **3 fils 1,5 mm²** vers alimentation"),
      checkItem("Projecteur : **câble 2 conducteurs minimum 16 mm²** via coffret électrique (transformateur)"),
      spacer(),
      warningBox([
        "La partie électrique DOIT être réalisée par un électricien qualifié — obligatoire pour la garantie et la sécurité",
        "Respecter les sections de câbles indiquées (sous-dimensionner = risque incendie)",
        "Prévoir le différentiel 30 mA en amont",
      ]),

      // ETAPE 15
      heading2("ÉTAPE 15 — POSE DU FEUTRE"),
      durationLine("Durée estimée : 1h30"),
      checkItem("Appliquer la colle à feutre sur toutes les parois en formant un Z tous les mètres environ"),
      checkItem("Coller principalement le haut et les jointures"),
      checkItem("Découper soigneusement le feutre autour de toutes les pièces à sceller"),
      spacer(),
      warningBox([
        "Bien découper autour des pièces à sceller sans les masquer",
        "Éviter les plis dans les angles : couper en onglet pour que le feutre soit plat",
        "Ne pas lésiner sur la colle en haut des panneaux : c'est là que le feutre se décolle le plus souvent",
      ]),

      // ETAPE 16
      heading2("ÉTAPE 16 — POSE DES JOINTS DES PIÈCES À SCELLER"),
      durationLine("Durée estimée : 30 min"),
      checkItem("Coller les joints sur la face avant des pièces à sceller (buses de refoulement, prise balai, skimmer)"),
      spacer(),
      warningBox([
        "Bien centrer les joints sur les pièces",
        "C'est ce qui assure l'étanchéité entre la pièce et le liner — une mauvaise pose = fuite garantie",
      ]),

      // ETAPE 17
      heading2("ÉTAPE 17 — POSITIONNEMENT DU LINER"),
      durationLine("Durée estimée : 1h (2 personnes minimum)"),
      checkItem("Déployer le liner à l'intérieur de la piscine"),
      checkItem("Le centrer correctement avant de le fixer"),
      spacer(),
      warningBox([
        "Faire cette étape par temps chaud : le liner est plus souple et plus facile à positionner",
        "Ne jamais tirer brutalement sur le liner — il se déchire",
        "Ne pas marcher avec des chaussures à l'intérieur pendant la pose",
        "Vérifier le centrage sur les 4 côtés avant de fixer quoi que ce soit",
      ]),

      // ETAPE 18
      heading2("ÉTAPE 18 — FIXATION DU LINER"),
      durationLine("Durée estimée : 1h"),
      checkItem("En commençant par un angle, fixer le liner dans le profil d'accrochage Hung sur tout le tour"),
      spacer(),
      warningBox([
        "Travailler en alternant les côtés opposés pour éviter les plis (ne pas finir un côté entier avant l'autre)",
        "Vérifier qu'il n'y a pas de pli sur le fond avant de finaliser la fixation en haut",
      ]),

      // ETAPE 19
      heading2("ÉTAPE 19 — BRIDAGE BONDE DE FOND"),
      durationLine("Durée estimée : 30 min"),
      checkItem("**S'assurer que le liner est parfaitement en place** avant cette étape"),
      checkItem("Repérer les trous de la bonde à travers le liner, positionner le joint et la bride"),
      checkItem("Fixer la bride avec les vis inox"),
      checkItem("Fixer le cache"),
      spacer(),
      warningBox([
        "Ne pas découper le liner avant que la bride soit en place et vissée",
        "Serrer en croix pour assurer une pression uniforme du joint",
        "Vérifier l'étanchéité après les premiers centimètres d'eau",
      ]),

      // ETAPE 20
      heading2("ÉTAPE 20 — REMBLAI LORS DU REMPLISSAGE"),
      durationLine("Durée estimée : demi-journée (selon débit)"),
      checkItem("Remplir la piscine d'eau ET remblayer **simultanément** avec du gravier concassé petite granulométrie"),
      checkItem("Remblayer à mesure que l'eau monte (même hauteur intérieur/extérieur)"),
      checkItem("**Arrêter le remplissage avant que l'eau n'atteigne les pièces à sceller**"),
      spacer(),
      warningBox([
        "CRITIQUE : le remblai et le remplissage doivent progresser au même rythme — décalage = déformation des panneaux",
        "Utiliser UNIQUEMENT du gravier concassé (pas de terre, pas de sable) — obligatoire pour le drainage",
        "Remblayer avec de la terre annule la garantie",
      ]),

      // ETAPE 21
      heading2("ÉTAPE 21 — BRIDAGE DES PIÈCES À SCELLER"),
      durationLine("Durée estimée : 1h"),
      checkItem("Repérer les trous des pièces à sceller à travers le liner, visser la bride d'étanchéité"),
      checkItem("Répéter sur l'ensemble des buses et sur le skimmer"),
      checkItem("Découper délicatement au cutter l'intérieur de chaque pièce à sceller"),
      spacer(),
      warningBox([
        "Couper au cutter avec précision : trop petit = flux limité, trop grand = risque de fuite",
        "Serrer en croix, progressivement",
        "Vérifier l'étanchéité de chaque pièce avant de passer à la suivante",
      ]),

      // ETAPE 22
      heading2("ÉTAPE 22 — MONTAGE DU PROJECTEUR"),
      durationLine("Durée estimée : 30 min"),
      checkItem("Passer le tire-fil de l'extérieur vers l'intérieur"),
      checkItem("Côté intérieur, accrocher le câble du projecteur au tire-fil"),
      checkItem("Côté extérieur, tirer sur le tire-fil"),
      checkItem("Fixer le projecteur en le vissant dans la prise balai"),
      spacer(),
      warningBox([
        "Vérifier que le câble du projecteur n'est pas endommagé avant installation",
        "Le raccordement électrique final doit être fait par l'électricien (basse tension via transformateur)",
      ]),

      // ETAPE 23
      heading2("ÉTAPE 23 — REMPLISSAGE DU BASSIN"),
      durationLine("Durée estimée : selon volume (plusieurs heures à une nuit)"),
      checkItem("Finir de remblayer la périmétrie avec le gravier"),
      checkItem("**Arrêter à 20 cm du haut**"),
      spacer(),
      warningBox([
        "Surveiller le liner pendant le remplissage final — ajuster les plis tant que l'eau est encore basse",
        "Surveiller les raccords plomberie pour détecter toute fuite",
      ]),

      // ETAPE 24
      heading2("ÉTAPE 24 — CEINTURE BÉTON"),
      durationLine("Durée estimée : 1 journée + 7 jours de séchage minimum"),
      checkItem("Préparer le coffrage et le treillis pour la ceinture béton"),
      checkItem("Couler une ceinture béton d'une **largeur minimum de 30 cm**"),
      spacer(),
      warningBox([
        "Largeur minimum 30 cm impérative pour supporter les margelles",
        "La ceinture doit être parfaitement de niveau pour que les margelles soient droites",
        "Inclure le treillis dans la ceinture pour éviter les fissures",
      ]),

      // ETAPE 25
      heading2("ÉTAPE 25 — FIXATION DES MARGELLES D'HABILLAGE"),
      durationLine("Durée estimée : 1 journée"),
      checkItem("Coller les margelles de finition grès cérame sur les margelles acier"),
      checkItem("Prévoir un **débord intérieur d'environ 10 mm**"),
      spacer(),
      warningBox([
        "Utiliser une colle spéciale margelle adaptée à l'extérieur et à l'humidité",
        "Le débord de 10 mm vers l'intérieur cache le haut du liner et évite les infiltrations",
        "Prévoir les joints entre margelles dès le départ (espacement régulier)",
      ]),

      spacer(),
      new Paragraph({
        children: [new TextRun({ text: "Notice officielle Piscine Discount — Magnelis Océane — Sans volet immergé", size: 16, color: "AAAAAA", italics: true, font: "Arial" })],
        alignment: AlignmentType.CENTER,
        spacing: { before: 200 },
      }),
    ]
  }]
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync("/Users/arnaudkuntz/Downloads/Checklist_Piscine_Oceane.docx", buffer);
  console.log("✅ Fichier créé : Checklist_Piscine_Oceane.docx");
});
