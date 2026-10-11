#!/usr/bin/env python3
"""
Piste 2 — Signal canari découplé (DAA, Keller & Keuning) sur le cœur Dual Momentum.

Origine (recherche du 11/10, research_notes/Evolutions agent bourse PEA/
dual_momentum_extensions.md) : le projet a déjà testé et rejeté DEUX FOIS les
émergents comme 3e classe d'actif DÉTENUE (ils aggravent la pire chute). La
littérature sur la "Defensive Asset Allocation" (Keller & Keuning, SSRN
3212862) pose une question différente et jamais testée ici : la valeur des
émergents comme SIGNAL D'ALERTE PRÉCOCE, sans jamais les détenir. Leur
"univers canari" original est EEM (émergents) + AGG (obligataire agrégé) ;
on reprend les deux, bien qu'on ne détienne ni l'un ni l'autre (aucun ETF
obligataire n'est éligible PEA actuellement) — le canari n'est JAMAIS un
actif acheté, seulement un thermomètre.

Mécanisme (posé a priori, repris tel que publié, AUCUN paramètre optimisé
sur nos données) :
  - n = nombre d'actifs canari (EEM, IEF) dont le momentum 12 mois est <= 0
        (0, 1 ou 2)
  - fraction_refuge_canari = n / 2   (0%, 50%, 100%)
  - Si la règle normale du cœur (momentum absolu World/USA) dit déjà "Cash" :
        rien ne change, on est déjà 100% défensif.
  - Sinon (la règle normale veut investir dans World ou USA) :
        (1 - fraction_refuge_canari) va dans l'actif choisi,
        fraction_refuge_canari va au monétaire (même refuge que le live,
        AUCUN nouvel actif détenu).

Reproduit EXACTEMENT la recette live post-08/09 (piste1_bridage_pea.py,
agent_dual_momentum.py) comme bras A : rotatif {World, USA}, refuge monétaire
(2%/an, pas 0%), socle 0%, anti-whipsaw +3%, frais 0,1% sur la fraction qui
bouge. Le bras B est identique, canari en plus.

CRITÈRE DE VALIDATION FIXÉ AVANT DE LANCER LE TEST (pour ne pas le choisir
après coup) : le canari n'est qu'un airbag de plus, pas un moteur de
rendement — on l'adopte en virtuel SEULEMENT s'il réduit la pire chute d'au
moins 2 points ET ne coûte pas plus d'1 point de rendement annuel. Sinon on
le documente comme négatif et on n'implémente rien.

LIMITE ASSUMÉE : aucune publication identifiée ne teste un canari sur un
univers investi à seulement 2 actifs (voir recherche du 11/10) — c'est une
extrapolation du concept DAA, pas une réplication d'un résultat publié.

Ne touche à rien en prod. Sortie : console + piste2_canari_resultats.json.
"""

import warnings
warnings.filterwarnings("ignore")

import json
import numpy as np
import pandas as pd
import yfinance as yf

LOOKBACK      = 12
FRAIS         = 0.001    # 0,1% par changement de la poche rotative (comme piste1)
BUFFER        = 0.03     # anti-whipsaw +3% (identique au live)
CAP           = 10000.0
TAUX_MONETAIRE = 0.02    # refuge monétaire, ~2%/an (identique à agent_dual_momentum.py)

TICKERS = ["SPY", "EFA", "EEM", "IEF"]           # USA, dév ex-US, émergents (canari), oblig (canari)
POIDS_WORLD = {"SPY": 0.60, "EFA": 0.30, "EEM": 0.10}
CANARIS = ["EEM", "IEF"]


def charger():
    px = yf.download(TICKERS, start="2003-01-01", auto_adjust=True, progress=False)["Close"]
    mens = px.resample("ME").last().dropna(how="all")
    rr = mens[list(POIDS_WORLD)].pct_change().fillna(0)
    poids = np.array([POIDS_WORLD[c] for c in POIDS_WORLD])
    world = [100.0]
    for _, row in rr.iloc[1:].iterrows():
        world.append(world[-1] * (1 + float(np.dot(poids, row[list(POIDS_WORLD)].values))))
    mens["WORLD"] = world
    return mens.dropna()


def moteur(prix, avec_canari):
    """Rotatif {WORLD, SPY}, refuge monétaire (2%/an), socle 0%, anti-whipsaw +3%.
    Si avec_canari, module la fraction investie selon la breadth EEM/IEF (DAA)."""
    rotatif = ["WORLD", "SPY"]
    rends = prix.pct_change()
    mom   = prix.pct_change(LOOKBACK)
    dates = prix.index[LOOKBACK:]

    valeur, position, nb_trades, cash_frac_prec = CAP, None, 0, 0.0
    courbe = {}
    journal = []

    for i, date in enumerate(dates):
        date_prec = dates[i-1] if i > 0 else date
        m = mom.loc[date_prec, rotatif]
        best = m.idxmax(); mbest = m[best]

        if mbest <= 0:
            cible = "CASH"
        elif (position in rotatif and m[position] > 0
              and mbest < m[position] + BUFFER):
            cible = position
        else:
            cible = best

        # Fraction canari (信号 seul, EEM/IEF jamais détenus)
        if avec_canari and cible != "CASH":
            m_canari = mom.loc[date_prec, CANARIS]
            n_neg = int((m_canari <= 0).sum())
            frac_refuge = n_neg / len(CANARIS)
        else:
            frac_refuge = 0.0

        frac_risque = 1.0 - frac_refuge

        # Rendement du mois : fraction risquée sur l'actif détenu + fraction
        # cash sur le monétaire (intérêts mensuels, pas 0%)
        if position is not None and position != "CASH" and i > 0:
            r_risque = rends.loc[date, position]
            r_risque = 0.0 if np.isnan(r_risque) else r_risque
        else:
            r_risque = 0.0
        r_cash = TAUX_MONETAIRE / 12
        # La fraction détenue hier (cash_frac_prec) détermine le rendement de CE mois,
        # avant tout rééquilibrage (pas de look-ahead sur la décision du mois)
        valeur *= (1 + (1 - cash_frac_prec) * r_risque + cash_frac_prec * r_cash)

        # Rééquilibrage (frais sur le changement d'actif ET sur le changement
        # de fraction canari, les deux bougent du capital)
        changement = (cible != position) or (abs(frac_refuge - cash_frac_prec) > 1e-9)
        if changement:
            # frais proportionnels au capital qui change de case réellement
            delta = abs(frac_refuge - cash_frac_prec) + (1.0 if cible != position else 0.0) * frac_risque
            valeur *= (1 - FRAIS * min(delta, 1.0))
            if cible != position:
                nb_trades += 1
            position = cible if cible != "CASH" else position  # mémorise le dernier actif risqué visé
            journal.append((str(date.date()), cible, round(float(frac_refuge)*100)))

        cash_frac_prec = frac_refuge if cible != "CASH" else 1.0
        courbe[str(date.date())] = round(valeur, 2)

    return courbe, nb_trades, journal


def buy_hold(prix, col):
    p = prix[col].dropna()
    p = p.loc[p.index[LOOKBACK]:]
    base = p.iloc[0]
    return {str(d.date()): round(CAP * v / base, 2) for d, v in p.items()}


def metriques(courbe):
    vals = np.array(list(courbe.values()))
    dts = list(courbe.keys())
    n = (pd.to_datetime(dts[-1]) - pd.to_datetime(dts[0])).days / 365.25
    cagr = (vals[-1] / vals[0]) ** (1 / n) - 1
    pic = np.maximum.accumulate(vals)
    max_dd = ((vals - pic) / pic).min()
    r = np.diff(vals) / vals[:-1]
    vol = r.std() * np.sqrt(12)
    sharpe = (cagr - 0.02) / vol if vol > 0 else 0
    return {"final": round(float(vals[-1])), "cagr": round(float(cagr) * 100, 2),
            "dd": round(float(max_dd) * 100, 1), "vol": round(float(vol) * 100, 1),
            "sharpe": round(float(sharpe), 2), "ans": round(n, 1)}


if __name__ == "__main__":
    prix = charger()
    print(f"Données : {prix.index[0].date()} → {prix.index[-1].date()} ({len(prix)} mois)\n")

    courbe_a, nt_a, journal_a = moteur(prix, avec_canari=False)
    courbe_b, nt_b, journal_b = moteur(prix, avec_canari=True)

    m_a = metriques(courbe_a)
    m_b = metriques(courbe_b)
    m_world = metriques(buy_hold(prix, "WORLD"))

    print("="*92)
    print(f"{'':32}{'Valeur':>10}{'CAGR':>9}{'PireChute':>11}{'Vol':>8}{'Sharpe':>8}{'Trades/an':>11}")
    print("-"*92)
    for nom, m, nt in [("A — Live actuel (sans canari)", m_a, nt_a),
                       ("B — Avec canari EEM/IEF", m_b, nt_b),
                       ("World buy & hold", m_world, 0)]:
        tpy = f"{nt/m['ans']:.1f}" if nt else "-"
        print(f"{nom:32}{m['final']:>10}{m['cagr']:>8.2f}%{m['dd']:>10.1f}%"
              f"{m['vol']:>7.1f}%{m['sharpe']:>8.2f}{tpy:>11}")
    print("="*92)

    delta_dd   = m_b["dd"] - m_a["dd"]      # positif = pire chute moins profonde
    delta_cagr = m_b["cagr"] - m_a["cagr"]
    passe = (delta_dd >= 2.0) and (delta_cagr >= -1.0)
    verdict = (
        f"Canari EEM/IEF : pire chute {m_a['dd']}% -> {m_b['dd']}% "
        f"({'+' if delta_dd>=0 else ''}{round(delta_dd,2)} pts). "
        f"CAGR {m_a['cagr']}% -> {m_b['cagr']}% ({'+' if delta_cagr>=0 else ''}{round(delta_cagr,2)} pts/an). "
        f"Critère fixé a priori (DD >= +2 pts ET CAGR >= -1 pt) : {'PASSE' if passe else 'NE PASSE PAS'}."
    )
    print("\n" + verdict)

    print("\nDerniers déclenchements du canari (date, cible, % refuge canari) :")
    declenchements = [j for j in journal_b if j[2] > 0][-8:]
    for d in declenchements or ["aucun déclenchement sur toute la période"]:
        print(f"  {d}")

    resultats = {
        "periode": f"{prix.index[0].date()} → {prix.index[-1].date()}",
        "sans_canari": m_a,
        "avec_canari": m_b,
        "world_buy_hold": m_world,
        "nb_trades_sans_canari": nt_a,
        "nb_trades_avec_canari": nt_b,
        "delta_drawdown_pts": round(delta_dd, 2),
        "delta_cagr_pts": round(delta_cagr, 2),
        "critere_passe": passe,
        "verdict": verdict,
        "limite_assumee": (
            "Aucune publication ne teste un canari (breadth 2 actifs) sur un "
            "univers investi a seulement 2 actifs (World/USA) : extrapolation "
            "du concept DAA, pas replication d'un resultat publie."
        ),
    }
    with open("piste2_canari_resultats.json", "w", encoding="utf-8") as f:
        json.dump(resultats, f, ensure_ascii=False, indent=2)
    print("\nRésultats détaillés sauvegardés dans piste2_canari_resultats.json")
