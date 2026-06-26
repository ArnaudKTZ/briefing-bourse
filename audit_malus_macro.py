#!/usr/bin/env python3
"""
Audit du malus macro Fear&Greed du V4.

Le V4 applique -10 pts à TOUS les scores quand le Fear&Greed est en peur extrême
(donc rend l'agent défensif, supprime des ACHETER). Question : ce malus améliore-t-il
quelque chose, ou pénalise-t-il pile au mauvais moment ?

Subtilité trouvée à l'inspection : le F&G utilisé (alternative.me) est l'indice
CRYPTO, appliqué à des actions françaises. On teste donc si ce F&G a un lien avec
les rendements FUTURS du CAC 40.

Méthode : pour chaque jour, on regarde le F&G et le rendement du CAC à J+1 et J+5.
On regroupe par niveau de peur. Si la peur extrême précède des rendements POSITIFS,
le malus (qui rend défensif en peur) est CONTRE-PRODUCTIF.
"""

import warnings
warnings.filterwarnings("ignore")

import json
import urllib.request
import numpy as np
import pandas as pd
import yfinance as yf


def fetch_fng_history():
    url = "https://api.alternative.me/fng/?limit=0&format=json"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read())["data"]
    s = {}
    for d in data:
        jour = pd.to_datetime(int(d["timestamp"]), unit="s").normalize()
        s[jour] = int(d["value"])
    return pd.Series(s).sort_index()


def bucket(v):
    if v <= 25:   return "1. Peur extrême (<=25)"
    if v <= 45:   return "2. Peur (26-45)"
    if v <= 55:   return "3. Neutre (46-55)"
    if v <= 75:   return "4. Avidité (56-75)"
    return "5. Avidité extrême (>75)"


if __name__ == "__main__":
    print("Récupération historique Fear&Greed (alternative.me, crypto)...")
    fng = fetch_fng_history()
    print(f"  {len(fng)} jours, du {fng.index[0].date()} au {fng.index[-1].date()}")

    print("Récupération CAC 40...")
    cac = yf.Ticker("^FCHI").history(start=str(fng.index[0].date()))["Close"]
    cac.index = cac.index.tz_localize(None).normalize()

    # Rendements futurs
    ret_1j = cac.pct_change().shift(-1) * 100   # rendement du lendemain
    ret_5j = (cac.shift(-5) / cac - 1) * 100     # rendement à 5 jours

    df = pd.DataFrame({"fng": fng}).join(pd.DataFrame({"r1": ret_1j, "r5": ret_5j}), how="inner").dropna()
    df["niveau"] = df["fng"].apply(bucket)

    print(f"\nÉchantillon aligné : {len(df)} jours\n")
    print(f"{'Niveau de peur':<26} {'N':>5} {'J+1 moy':>9} {'% J+1>0':>8} {'J+5 moy':>9} {'% J+5>0':>8}")
    print("-" * 70)
    for niv in sorted(df["niveau"].unique()):
        g = df[df["niveau"] == niv]
        print(f"{niv:<26} {len(g):>5} {g['r1'].mean():>8.2f}% {(g['r1']>0).mean()*100:>7.0f}% "
              f"{g['r5'].mean():>8.2f}% {(g['r5']>0).mean()*100:>7.0f}%")

    base1, base5 = df["r1"].mean(), df["r5"].mean()
    print("-" * 70)
    print(f"{'Moyenne globale':<26} {len(df):>5} {base1:>8.2f}% {(df['r1']>0).mean()*100:>7.0f}% "
          f"{base5:>8.2f}% {(df['r5']>0).mean()*100:>7.0f}%")

    pe = df[df["fng"] <= 25]
    print("\n" + "=" * 70)
    print("VERDICT")
    print("=" * 70)
    if len(pe) < 20:
        print(f"Peur extrême : seulement {len(pe)} jours, prudence sur la conclusion.")
    print(f"Après peur extrême (<=25) : J+1 = {pe['r1'].mean():+.2f}% (global {base1:+.2f}%), "
          f"J+5 = {pe['r5'].mean():+.2f}% (global {base5:+.2f}%)")
    if pe["r5"].mean() > base5:
        print("→ La peur extrême précède des rendements SUPÉRIEURS à la moyenne.")
        print("  Le malus (qui rend DÉFENSIF en peur) va donc à CONTRE-SENS : il pénalise")
        print("  les achats pile quand le rebond est statistiquement plus probable.")
    else:
        print("→ La peur extrême précède des rendements INFÉRIEURS : le malus défensif se justifie.")
