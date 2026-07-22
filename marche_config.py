#!/usr/bin/env python3
"""
Configuration marché partagée — source de vérité unique.
Évite la duplication du dict CAC40 dans chaque agent.
"""

CAC40 = {
    "LVMH":               "MC.PA",
    "TotalEnergies":      "TTE.PA",
    "Hermès":             "RMS.PA",
    "Airbus":             "AIR.PA",
    "Schneider Electric": "SU.PA",
    "L'Oréal":            "OR.PA",
    "Sanofi":             "SAN.PA",
    "BNP Paribas":        "BNP.PA",
    "Air Liquide":        "AI.PA",
    "Safran":             "SAF.PA",
    "Danone":             "BN.PA",
    "Vinci":              "DG.PA",
    "Kering":             "KER.PA",
    "Société Générale":   "GLE.PA",
    "Stellantis":         "STLAM.MI",
    "Saint-Gobain":       "SGO.PA",
    "ArcelorMittal":      "MT",
    "Pernod Ricard":      "RI.PA",
    "Michelin":           "ML.PA",
    "Capgemini":          "CAP.PA",
    "Renault":            "RNO.PA",
    "Legrand":            "LR.PA",
    "Publicis":           "PUB.PA",
    "Bouygues":           "EN.PA",
    "Engie":              "ENGI.PA",
    "Orange":             "ORA.PA",
    "Vivendi":            "VIV.PA",
    "Eurofins Scientific":"ERF.PA",
    "Teleperformance":    "TEP.PA",
    "Alstom":             "ALO.PA",
    "Worldline":          "WLN.PA",
    "Veolia":             "VIE.PA",
    "STMicroelectronics": "STM",
    "Dassault Systèmes":  "DSY.PA",
    "Edenred":            "EDEN.PA",
    "Accor":              "AC.PA",
    "Eurazeo":            "RF.PA",
    "Thales":             "HO.PA",
    "Forvia":             "FRVIA.PA",
}


# Secteur par valeur (source de vérité unique, repris du dict SECTEURS du
# briefing). Utilisé par le Risk Engine pour la limite d'exposition sectorielle
# (principe P11 : pas 3 banques corrélées en même temps).
SECTEUR_PAR_VALEUR = {}
for _secteur, _valeurs in {
    "Luxe":              ["LVMH", "Hermès", "Kering", "L'Oréal", "Pernod Ricard"],
    "Énergie":           ["TotalEnergies", "Engie"],
    "Industrie/Défense": ["Airbus", "Schneider Electric", "Safran", "Vinci", "Saint-Gobain",
                          "Legrand", "ArcelorMittal", "Alstom", "Forvia", "Bouygues", "Thales"],
    "Banques/Finance":   ["BNP Paribas", "Société Générale", "Eurazeo"],
    "Santé":             ["Sanofi", "Air Liquide", "Eurofins Scientific"],
    "Tech":              ["Capgemini", "Dassault Systèmes", "STMicroelectronics", "Worldline"],
    "Télécom/Média":     ["Orange", "Vivendi", "Publicis", "Teleperformance"],
    "Conso/Autre":       ["Danone", "Michelin", "Renault", "Stellantis", "Accor", "Edenred", "Veolia"],
}.items():
    for _v in _valeurs:
        SECTEUR_PAR_VALEUR[_v] = _secteur
