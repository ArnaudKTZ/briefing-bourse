#!/usr/bin/env python3
"""
Audit du malus VIX du V4 (même méthode que l'audit Fear&Greed du 26/06).

Le V4 applique un malus global à TOUS les scores selon le VIX :
-20 pts si VIX > 35, -12 si > 25, -5 si > 20 (briefing + scoring intraday).
Question : un VIX élevé prédit-il des rendements CAC 40 futurs plus faibles
(malus justifié), ou au contraire des rebonds (malus contre-productif) ?

Deux subtilités par rapport à l'audit F&G :
  - Le VIX est la volatilité implicite du S&P 500, appliquée ici à des actions
    françaises. On teste donc son lien avec les rendements FUTURS du CAC.
  - Le malus est aussi une protection RISQUE, pas seulement un pari sur le
    rendement : on mesure donc aussi la volatilité réalisée par bucket et le
    ratio rendement/volatilité (un malus peut se justifier par le risque même
    si le rendement moyen est positif).

Méthode : pour chaque jour depuis 2000, VIX de clôture → rendement CAC à
J+1 et J+5, regroupé par bucket calé sur les seuils du malus (20 / 25 / 35).
Sous-période 2015+ affichée aussi (les régimes de volatilité changent).
"""

import warnings
warnings.filterwarnings("ignore")

import pandas as pd
import yfinance as yf


BUCKETS = [
    (0,  20,  "1. VIX <= 20 (pas de malus)"),
    (20, 25,  "2. VIX 20-25 (malus -5)"),
    (25, 35,  "3. VIX 25-35 (malus -12)"),
    (35, 999, "4. VIX > 35 (malus -20)"),
]


def bucket(v):
    for lo, hi, label in BUCKETS:
        if lo < v <= hi:
            return label
    return BUCKETS[0][2]


def tableau(df, titre):
    print(f"\n{titre} — {len(df)} jours alignés")
    print(f"{'Bucket':<30} {'N':>5} {'J+1 moy':>9} {'% J+1>0':>8} {'J+5 moy':>9} {'% J+5>0':>8} {'Vol J+5':>8} {'Rdt/Vol':>8}")
    print("-" * 92)
    for _, _, label in BUCKETS:
        g = df[df["niveau"] == label]
        if g.empty:
            continue
        vol5 = g["r5"].std()
        ratio = g["r5"].mean() / vol5 if vol5 else float("nan")
        print(f"{label:<30} {len(g):>5} {g['r1'].mean():>8.2f}% {(g['r1']>0).mean()*100:>7.0f}% "
              f"{g['r5'].mean():>8.2f}% {(g['r5']>0).mean()*100:>7.0f}% {vol5:>7.2f}% {ratio:>8.3f}")
    vol5 = df["r5"].std()
    print("-" * 92)
    print(f"{'Moyenne globale':<30} {len(df):>5} {df['r1'].mean():>8.2f}% {(df['r1']>0).mean()*100:>7.0f}% "
          f"{df['r5'].mean():>8.2f}% {(df['r5']>0).mean()*100:>7.0f}% {vol5:>7.2f}% {df['r5'].mean()/vol5:>8.3f}")


if __name__ == "__main__":
    print("Récupération VIX et CAC 40 depuis 2000...")
    vix = yf.Ticker("^VIX").history(start="2000-01-01")["Close"]
    cac = yf.Ticker("^FCHI").history(start="2000-01-01")["Close"]
    vix.index = vix.index.tz_localize(None).normalize()
    cac.index = cac.index.tz_localize(None).normalize()

    # Rendements CAC futurs : le VIX de clôture US du jour J est connu avant
    # l'ouverture de Paris à J+1 — c'est bien l'information dont dispose le
    # briefing de 7h. On mesure donc CAC de J+1 en avant.
    ret_1j = cac.pct_change().shift(-1) * 100
    ret_5j = (cac.shift(-5) / cac - 1) * 100

    df = (pd.DataFrame({"vix": vix})
          .join(pd.DataFrame({"r1": ret_1j, "r5": ret_5j}), how="inner")
          .dropna())
    df["niveau"] = df["vix"].apply(bucket)

    tableau(df, "PÉRIODE COMPLÈTE (2000+)")
    tableau(df[df.index >= "2015-01-01"], "SOUS-PÉRIODE RÉCENTE (2015+)")

    base5 = df["r5"].mean()
    haut  = df[df["vix"] > 25]
    print("\n" + "=" * 92)
    print("VERDICT")
    print("=" * 92)
    print(f"Après VIX > 25 (malus -12/-20) : J+5 = {haut['r5'].mean():+.2f}% "
          f"(global {base5:+.2f}%), vol J+5 = {haut['r5'].std():.2f}% (global {df['r5'].std():.2f}%)")
    if haut["r5"].mean() > base5:
        print("→ Rendement : un VIX élevé précède des rendements SUPÉRIEURS à la moyenne.")
        print("  Comme le F&G, le malus pénalise les achats pile quand le rebond est probable.")
    else:
        print("→ Rendement : un VIX élevé précède des rendements INFÉRIEURS : malus justifié côté rendement.")
    ratio_haut = haut["r5"].mean() / haut["r5"].std()
    ratio_bas  = df[df["vix"] <= 20]["r5"].mean() / df[df["vix"] <= 20]["r5"].std()
    print(f"→ Risque : rendement/volatilité à J+5 = {ratio_haut:.3f} en VIX > 25 "
          f"vs {ratio_bas:.3f} en VIX <= 20.")
    print("  Si le ratio en VIX élevé est nettement plus faible, le malus reste défendable")
    print("  comme protection risque même avec un rendement moyen supérieur.")
