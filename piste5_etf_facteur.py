#!/usr/bin/env python3
"""
Piste 5 — Remplacer le satellite stock-picking par 2 ETF facteur PEA
(BNP Paribas Easy Quality Europe + Low Vol Europe), en buy & hold.

Origine (recherche du 11/10, research_notes/Evolutions agent bourse PEA/
etf_facteurs_pea.md) : le satellite stock-picking a un edge net négatif
confirmé par 3 mesures indépendantes depuis juillet (Évaluateur, Shadow,
backtest momentum+qualité) et par la littérature ("Retail Trader's Ruin").
Deux ETF facteur sont PEA-éligibles aujourd'hui et documentés comme
résilients en krach (MSCI) :
  - BNP Paribas Easy Quality Europe UCITS ETF  (ISIN LU1377382103, ticker
    Euronext Paris EQUA, TER 0,31%)
  - BNP Paribas Easy Low Vol Europe UCITS ETF  (ISIN LU1377381717, ticker
    Euronext Paris EVOE, TER 0,31%)
Aucun paramètre à optimiser ici : c'est du buy & hold pur, zéro trading actif,
cohérent avec la philosophie déjà actée. On compare simplement leur
historique réel (depuis le lancement du fonds, juin 2016) et sur la fenêtre
exacte où le satellite a tourné (depuis le 19/06/2026), au CAC 40 et au
satellite lui-même.

RÉSERVE DÉJÀ POSÉE PAR LA RECHERCHE : il n'existe aucune version "World" ou
"USA" de ces facteurs éligible PEA, seulement une version 100% Europe. Ce
n'est donc pas une substitution neutre du satellite CAC40 par un "satellite
indiciel" : c'est l'AJOUT d'une surpondération Europe par-dessus un cœur
World/USA, une décision d'allocation géographique à assumer, pas une
neutralité.

Ne touche à rien en prod. Sortie : console + piste5_etf_facteur_resultats.json.
"""

import warnings
warnings.filterwarnings("ignore")

import json
import numpy as np
import pandas as pd
import yfinance as yf

TICKERS = {"Quality Europe (EQUA)": "EQUA.PA", "Low Vol Europe (EVOE)": "EVOE.PA",
           "CAC 40": "^FCHI"}
DATE_SATELLITE_DEPART = "2026-06-19"   # inception réelle du satellite virtuel
SATELLITE_PERF_PCT    = -22.55         # (7744.79 / 10000 - 1) * 100, valeur du 28/10


def charger():
    data = yf.download(list(TICKERS.values()), start="2016-01-01",
                        auto_adjust=True, progress=False)["Close"]
    data = data.rename(columns={v: k for k, v in TICKERS.items()})
    return data.dropna(how="all")


def metriques(serie):
    s = serie.dropna()
    n_annees = (s.index[-1] - s.index[0]).days / 365.25
    if n_annees <= 0:
        return None
    total_ret = s.iloc[-1] / s.iloc[0] - 1
    cagr = (1 + total_ret) ** (1 / n_annees) - 1 if n_annees >= 1 else total_ret
    rendements = s.pct_change().dropna()
    pic = s.cummax()
    dd = (s - pic) / pic
    vol = rendements.std() * np.sqrt(252)
    sharpe = (cagr - 0.02) / vol if vol > 0 else 0
    return {
        "depuis": str(s.index[0].date()), "jusqu_a": str(s.index[-1].date()),
        "n_annees": round(n_annees, 2),
        "rendement_total_pct": round(float(total_ret) * 100, 2),
        "cagr_pct": round(float(cagr) * 100, 2),
        "max_drawdown_pct": round(float(dd.min()) * 100, 1),
        "vol_pct": round(float(vol) * 100, 1),
        "sharpe": round(float(sharpe), 2),
    }


if __name__ == "__main__":
    print("Téléchargement EQUA.PA, EVOE.PA, ^FCHI...")
    prix = charger()
    print(f"Données : {prix.index[0].date()} → {prix.index[-1].date()}\n")

    resultats = {}

    print("="*88)
    print("DEPUIS LE LANCEMENT DU FONDS (juin 2016, ~10 ans)".center(88))
    print("="*88)
    # Blend 50/50 rééquilibré mensuellement (approximé ici en quotidien, l'écart est négligeable)
    px_blend = prix[["Quality Europe (EQUA)", "Low Vol Europe (EVOE)"]].dropna()
    rr = px_blend.pct_change().fillna(0)
    val = [100.0]
    for _, row in rr.iloc[1:].iterrows():
        val.append(val[-1] * (1 + 0.5 * row.iloc[0] + 0.5 * row.iloc[1]))
    blend_serie = pd.Series(val, index=px_blend.index, name="Blend 50/50 Quality+LowVol")

    for nom in list(TICKERS) + ["Blend 50/50 Quality+LowVol"]:
        serie = blend_serie if nom == "Blend 50/50 Quality+LowVol" else prix[nom]
        m = metriques(serie)
        resultats[f"depuis_2016__{nom}"] = m
        print(f"{nom:32} CAGR {m['cagr_pct']:>6.2f}%  PireChute {m['max_drawdown_pct']:>6.1f}%  "
              f"Vol {m['vol_pct']:>5.1f}%  Sharpe {m['sharpe']:>5.2f}")

    print("\n" + "="*88)
    print(f"DEPUIS L'INCEPTION DU SATELLITE ({DATE_SATELLITE_DEPART}, fenêtre exacte)".center(88))
    print("="*88)
    fenetre = prix.loc[DATE_SATELLITE_DEPART:]
    for nom in TICKERS:
        serie = fenetre[nom].dropna()
        if len(serie) < 2:
            continue
        perf = (serie.iloc[-1] / serie.iloc[0] - 1) * 100
        dd = ((serie - serie.cummax()) / serie.cummax()).min() * 100
        resultats[f"fenetre_satellite__{nom}"] = {"perf_pct": round(float(perf), 2),
                                                     "max_drawdown_pct": round(float(dd), 1)}
        print(f"{nom:32} Perf {perf:>+7.2f}%   PireChute {dd:>6.1f}%")
    print(f"{'Satellite stock-picking (réel)':32} Perf {SATELLITE_PERF_PCT:>+7.2f}%   "
          f"PireChute  -27.8%  (circuit-breaker actif depuis le 11/10)")
    resultats["fenetre_satellite__Satellite (réel)"] = {
        "perf_pct": SATELLITE_PERF_PCT, "max_drawdown_pct": -27.8}
    print("="*88)

    print("\nRéserve à garder en tête : aucune version World/USA de ces facteurs")
    print("n'est éligible PEA, seulement une version 100% Europe. Les adopter ajoute")
    print("une surpondération Europe au-dessus du cœur World/USA, ce n'est pas une")
    print("neutralité géographique.")

    with open("piste5_etf_facteur_resultats.json", "w", encoding="utf-8") as f:
        json.dump(resultats, f, ensure_ascii=False, indent=2)
    print("\nRésultats détaillés sauvegardés dans piste5_etf_facteur_resultats.json")
