#!/usr/bin/env python3
"""
Piste 6 — Ajouter de l'or à l'assurance vie : actions Monde / fonds euros / or.

Origine (Veille, digest du 31/10, lu le 15/11) : "Simple Portfolios that
Deliver Consistent Decent Returns" (arXiv 2610.36491). Sur des ETF américains
en dollars (2005-2025), un tiers actions / un tiers obligations / un tiers or
obtient un rendement par unité de risque de 0,68 contre 0,52 pour le 60/40,
et les auteurs concluent que "la répartition exacte compte moins que le fait
d'avoir les trois". Réserves de l'article lui-même : portefeuilles choisis en
regardant le passé, univers américain, rien pour un épargnant en euros.

Question posée ici, en euros, pour le cas réel d'Arnaud (assurance vie
BoursoVie : ETF Monde + fonds euros) : l'or apporte-t-il quelque chose de
plus que le simple dosage actions / fonds euros ?

CRITÈRE FIXÉ AVANT DE VOIR LES RÉSULTATS (15/11) :
  Le fonds euros ne baisse jamais. On peut donc toujours réduire le risque
  d'un portefeuille actions en mettant plus de fonds euros. L'or ne mérite sa
  place que s'il fait MIEUX que ce réglage gratuit. Donc :
    VALIDÉ  si, à volatilité égale, le 1/3-1/3-1/3 a un rendement annuel
            supérieur au mélange Monde / fonds euros, sur CHACUNE des deux
            moitiés de la période, ET une pire chute pas plus profonde.
    REJETÉ  sinon.
  Un seul portefeuille candidat (celui de l'article), aucun poids optimisé.
  Les variantes 10% et 20% d'or sont affichées pour information seulement.

Hypothèses :
  - Actions Monde : ETF ACWI (dollars, depuis mars 2008) converti en euros.
    Choisi plutôt que CW8.PA (2009) pour inclure la crise de 2008.
  - Or : ETF GLD (dollars) converti en euros.
  - Fonds euros : pas de cours. Taux moyens annuels du marché français,
    nets de frais de gestion, avant prélèvements sociaux. Valeurs approchées
    de mémoire (France Assureurs), pas le taux d'Euro Exclusif en particulier.
  - Frais de gestion du contrat sur les unités de compte : 0,75 %/an sur
    l'ETF et sur l'or. Arbitrages gratuits (cas BoursoVie).
  - Rééquilibrage une fois par an, début janvier. Pas de versements.
  - Fiscalité ignorée (identique pour toutes les variantes dans le contrat).

Ne touche à rien en prod. Sortie : console + piste6_trois_poches_resultats.json.
"""
import json
import warnings

import numpy as np
import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")

TAUX_FONDS_EUROS = {
    2008: 4.0, 2009: 3.6, 2010: 3.4, 2011: 3.0, 2012: 2.9, 2013: 2.8, 2014: 2.5,
    2015: 2.3, 2016: 1.9, 2017: 1.8, 2018: 1.8, 2019: 1.4, 2020: 1.3, 2021: 1.3,
    2022: 2.0, 2023: 2.6, 2024: 2.6, 2025: 2.6, 2026: 2.6,
}
FRAIS_UC = 0.0075
DEBUT = "2008-04-01"

PORTEFEUILLES = {
    "100% Monde":                   {"monde": 1.0},
    "70/30 Monde/fonds euros":      {"monde": 0.7, "euro": 0.3},
    "50/50 Monde/fonds euros":      {"monde": 0.5, "euro": 0.5},
    "1/3 Monde, 1/3 fonds euros, 1/3 or": {"monde": 1/3, "euro": 1/3, "or": 1/3},
    "60/30/10 (10% d'or)":          {"monde": 0.6, "euro": 0.3, "or": 0.1},
    "50/30/20 (20% d'or)":          {"monde": 0.5, "euro": 0.3, "or": 0.2},
}
CANDIDAT = "1/3 Monde, 1/3 fonds euros, 1/3 or"


def charger():
    def close(t):
        s = yf.Ticker(t).history(period="max", auto_adjust=True)["Close"].dropna()
        s.index = s.index.tz_localize(None).normalize()
        return s
    acwi, gld, fx = close("ACWI"), close("GLD"), close("EURUSD=X")
    df = pd.concat({"acwi": acwi, "gld": gld, "fx": fx}, axis=1).ffill().dropna()
    df = df[df.index >= DEBUT]
    px = pd.DataFrame({"monde": df["acwi"] / df["fx"], "or": df["gld"] / df["fx"]})
    r = px.pct_change().fillna(0) - FRAIS_UC / 252
    taux = pd.Series([TAUX_FONDS_EUROS[d.year] / 100 for d in r.index], index=r.index)
    r["euro"] = (1 + taux) ** (1 / 252) - 1
    return r


def simuler(r, poids):
    """Valeur d'1 € investi, rééquilibré au 1er jour de bourse de chaque année."""
    cles = list(poids)
    w = np.array([poids[k] for k in cles])
    parts = w.copy()
    valeurs, annee = [], r.index[0].year
    for d, ligne in r[cles].iterrows():
        if d.year != annee:
            parts = w * parts.sum()
            annee = d.year
        parts = parts * (1 + ligne.values)
        valeurs.append(parts.sum())
    return pd.Series(valeurs, index=r.index)


def mesures(v):
    ans = (v.index[-1] - v.index[0]).days / 365.25
    rdt = (v.iloc[-1] / v.iloc[0]) ** (1 / ans) - 1
    vol = v.pct_change().dropna().std() * np.sqrt(252)
    chute = (v / v.cummax() - 1).min()
    annuels = v.resample("YE").last().pct_change().dropna()
    return {"rendement_annuel": round(rdt * 100, 2), "volatilite": round(vol * 100, 2),
            "pire_chute": round(chute * 100, 1),
            "pire_annee": round(annuels.min() * 100, 1) if len(annuels) else None,
            "rendement_par_risque": round(rdt / vol, 2) if vol else None}


def melange_meme_risque(r, vol_cible):
    """Part d'actions du mélange Monde / fonds euros qui a la même volatilité."""
    meilleur = None
    for pct in range(0, 101):
        v = simuler(r, {"monde": pct / 100, "euro": 1 - pct / 100})
        ecart = abs(mesures(v)["volatilite"] - vol_cible)
        if meilleur is None or ecart < meilleur[0]:
            meilleur = (ecart, pct, v)
    return meilleur[1], meilleur[2]


def comparer_a_risque_egal(r, nom):
    cand = simuler(r, PORTEFEUILLES[CANDIDAT])
    mc = mesures(cand)
    pct, ref = melange_meme_risque(r, mc["volatilite"])
    mr = mesures(ref)
    ok = mc["rendement_annuel"] > mr["rendement_annuel"] and mc["pire_chute"] >= mr["pire_chute"]
    print(f"\n  {nom} ({r.index[0].date()} -> {r.index[-1].date()})")
    print(f"    Trois poches            : {mc['rendement_annuel']:+.2f} %/an, volatilité {mc['volatilite']:.1f} %, pire chute {mc['pire_chute']:.1f} %")
    print(f"    {pct}% Monde + {100 - pct}% fonds euros : {mr['rendement_annuel']:+.2f} %/an, volatilité {mr['volatilite']:.1f} %, pire chute {mr['pire_chute']:.1f} %")
    print(f"    -> {'OK' if ok else 'ÉCHEC'} (écart {mc['rendement_annuel'] - mr['rendement_annuel']:+.2f} pt/an)")
    return {"periode": nom, "trois_poches": mc, "melange_meme_risque": {"part_monde_pct": pct, **mr}, "ok": bool(ok)}


if __name__ == "__main__":
    r = charger()
    print(f"Piste 6 — trois poches, en euros, {r.index[0].date()} -> {r.index[-1].date()} ({len(r)} séances)")

    print("\nVue d'ensemble (période complète) :")
    print(f"  {'Portefeuille':<38}{'Rdt/an':>8}{'Volat.':>8}{'Pire chute':>12}{'Pire année':>12}{'Rdt/risque':>12}")
    tableau = {}
    for nom, poids in PORTEFEUILLES.items():
        m = mesures(simuler(r, poids))
        tableau[nom] = m
        print(f"  {nom:<38}{m['rendement_annuel']:>7.2f}%{m['volatilite']:>7.1f}%{m['pire_chute']:>11.1f}%{m['pire_annee']:>11.1f}%{m['rendement_par_risque']:>12.2f}")

    print("\nRendement annuel de chaque poche seule :")
    for k in ["monde", "or", "euro"]:
        print(f"  {k:<6} {mesures(simuler(r, {k: 1.0}))['rendement_annuel']:+.2f} %/an")

    milieu = r.index[len(r) // 2]
    print("\nCRITÈRE — à risque égal, les trois poches rapportent-elles plus ?")
    tests = [comparer_a_risque_egal(r[r.index < milieu], "1re moitié"),
             comparer_a_risque_egal(r[r.index >= milieu], "2e moitié"),
             comparer_a_risque_egal(r, "Période complète (information)")]
    valide = tests[0]["ok"] and tests[1]["ok"]
    print(f"\nVERDICT : {'VALIDÉ' if valide else 'REJETÉ'} (critère : OK sur les deux moitiés)")

    # Robustesse : toutes les fenêtres de 5 ans glissantes (pas d'un mois)
    cand, n = simuler(r, PORTEFEUILLES[CANDIDAT]), 0
    ref = simuler(r, {"monde": tests[2]["melange_meme_risque"]["part_monde_pct"] / 100,
                      "euro": 1 - tests[2]["melange_meme_risque"]["part_monde_pct"] / 100})
    debuts = pd.date_range(r.index[0], r.index[-1] - pd.DateOffset(years=5), freq="MS")
    gagne, moins_de_chute, ecarts = 0, 0, []
    for d in debuts:
        f = d + pd.DateOffset(years=5)
        a, b = cand[(cand.index >= d) & (cand.index <= f)], ref[(ref.index >= d) & (ref.index <= f)]
        n += 1
        ea = ((a.iloc[-1] / a.iloc[0]) ** 0.2 - (b.iloc[-1] / b.iloc[0]) ** 0.2) * 100
        ecarts.append((ea, d))
        gagne += ea > 0
        moins_de_chute += (a / a.cummax() - 1).min() >= (b / b.cummax() - 1).min()
    print(f"Fenêtres de 5 ans glissantes : trois poches devant en rendement dans {gagne}/{n} cas ({gagne / n * 100:.0f} %)")
    print(f"  pire chute moins profonde dans {moins_de_chute}/{n} cas ({moins_de_chute / n * 100:.0f} %)")
    pire, meilleur = min(ecarts), max(ecarts)
    print(f"  écart de rendement annuel : médiane {np.median([e for e, _ in ecarts]):+.2f} pt, "
          f"pire {pire[0]:+.2f} pt (départ {pire[1].date()}), meilleur {meilleur[0]:+.2f} pt (départ {meilleur[1].date()})")
    perdantes = sorted(d for e, d in ecarts if e <= 0)
    if perdantes:
        print(f"  fenêtres perdantes : départs entre {perdantes[0].date()} et {perdantes[-1].date()}")

    with open("piste6_trois_poches_resultats.json", "w", encoding="utf-8") as f:
        json.dump({"date": pd.Timestamp.today().date().isoformat(),
                   "periode": [str(r.index[0].date()), str(r.index[-1].date())],
                   "tableau": tableau, "tests_risque_egal": tests,
                   "fenetres_5_ans": {"gagnees_rendement": int(gagne), "moins_de_chute": int(moins_de_chute), "total": n,
                                      "ecart_median_pt": round(float(np.median([e for e, _ in ecarts])), 2),
                                      "ecart_pire_pt": round(float(pire[0]), 2), "ecart_meilleur_pt": round(float(meilleur[0]), 2)},
                   "verdict": "VALIDÉ" if valide else "REJETÉ"}, f, ensure_ascii=False, indent=2)
