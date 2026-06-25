#!/usr/bin/env python3
"""
Contrôle de cohérence devise : le mécanisme Dual Momentum se comporte-t-il
pareil en EUR (CW8/ESE, ce que l'agent trade) qu'en USD (proxies du harnais) ?

Réglages FIXES (12 mois, buffer 3%) — ce n'est PAS un test de sur-ajustement
(déjà fait par le harnais walk-forward), juste une comparaison de comportement.
Même période pour les deux (depuis l'existence de l'ESE).
"""

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import yfinance as yf

LOOKBACK, BUFFER, FRAIS, PART_SOCLE = 12, 0.03, 0.001, 0.50


def _ret_ticker(t):
    """Rendements mensuels d'un ticker via Ticker.history (format fiable)."""
    h = yf.Ticker(t).history(period="max")["Close"]
    if h.index.tz is not None:
        h.index = h.index.tz_localize(None)   # aligner EUR (.PA) et US (tz différents)
    return h.resample("ME").last().pct_change()


def mensuel(ticker_or_weights):
    if isinstance(ticker_or_weights, dict):
        rets = {t: _ret_ticker(t) for t in ticker_or_weights}
        df = pd.DataFrame(rets).dropna()
        return sum(ticker_or_weights[t] * df[t] for t in ticker_or_weights)
    return _ret_ticker(ticker_or_weights)


def hybride(world_ret, usa_ret, debut, fin):
    wpx = (1 + world_ret.fillna(0)).cumprod()
    upx = (1 + usa_ret.fillna(0)).cumprod()
    idx = world_ret.index
    pos, rends, switches = None, [], 0
    for i in range(debut, fin):
        mw = wpx.iloc[i-1] / wpx.iloc[i-1-LOOKBACK] - 1
        mu = upx.iloc[i-1] / upx.iloc[i-1-LOOKBACK] - 1
        best, mb = ("USA", mu) if mu >= mw else ("World", mw)
        if mb <= 0:
            cible = "Cash"
        elif pos in ("World", "USA"):
            mp = mu if pos == "USA" else mw
            cible = pos if (mp > 0 and mb < mp + BUFFER) else best
        else:
            cible = best
        r_rot = 0.0 if cible == "Cash" else (usa_ret.iloc[i] if cible == "USA" else world_ret.iloc[i])
        cout = 0.0
        if cible != pos:
            cout, switches = FRAIS, switches + 1
            pos = cible
        rends.append(PART_SOCLE * world_ret.iloc[i] + (1 - PART_SOCLE) * (r_rot - cout))
    return rends, switches


def metr(rends):
    r = np.array(rends); c = np.cumprod(1 + r)
    na = len(r) / 12
    cagr = c[-1] ** (1/na) - 1
    dd = ((c - np.maximum.accumulate(c)) / np.maximum.accumulate(c)).min()
    vol = r.std() * np.sqrt(12)
    return cagr*100, dd*100, ((cagr-0.02)/vol if vol else 0)


def run(nom, world_ret, usa_ret):
    df = pd.DataFrame({"w": world_ret, "u": usa_ret}).dropna()
    w, u = df["w"], df["u"]
    debut = LOOKBACK
    rends, sw = hybride(w, u, debut, len(w))
    bh = list(w.iloc[debut:])
    cg, dd, sh = metr(rends)
    bcg, bdd, bsh = metr(bh)
    print(f"\n=== {nom} ===  (période {df.index[debut].date()} → {df.index[-1].date()})")
    print(f"  Hybride DM   : {cg:6.2f}%/an | chute {dd:6.1f}% | Sharpe {sh:.2f} | {sw} bascules")
    print(f"  World B&H    : {bcg:6.2f}%/an | chute {bdd:6.1f}% | Sharpe {bsh:.2f}")
    print(f"  → Réduction de chute : {dd-bdd:+.1f} pts | écart rendement : {cg-bcg:+.2f} pts")
    return (cg, dd, sh, bcg, bdd, bsh)


if __name__ == "__main__":
    print("Téléchargement EUR (CW8, ESE) et USD (blend, SPY)...")
    eur_w = mensuel("CW8.PA")
    eur_u = mensuel("ESE.PA")
    usd_w = mensuel({"SPY": 0.60, "EFA": 0.30, "EEM": 0.10})
    usd_u = mensuel("SPY")

    # Aligner les deux sur la même fenêtre (intersection, ~depuis ESE 2013)
    debut_commun = max(eur_u.dropna().index[0], usd_u.dropna().index[0])
    eur_w, eur_u = eur_w[eur_w.index >= debut_commun], eur_u[eur_u.index >= debut_commun]
    usd_w, usd_u = usd_w[usd_w.index >= debut_commun], usd_u[usd_u.index >= debut_commun]

    r_eur = run("EUR — ce que l'agent trade (CW8 / ESE)", eur_w, eur_u)
    r_usd = run("USD — ce que le harnais valide (proxies)", usd_w, usd_u)

    print("\n" + "="*60)
    print("VERDICT COHÉRENCE")
    print("="*60)
    meme_signe_dd = (r_eur[1]-r_eur[4]) > 0 and (r_usd[1]-r_usd[4]) > 0
    print(f"Réduction de chute dans les DEUX devises : {'OUI' if meme_signe_dd else 'NON'}")
    print(f"Sharpe hybride EUR {r_eur[2]:.2f} vs USD {r_usd[2]:.2f} (proche = mécanisme stable)")
    print("Si le comportement (airbag + relation au buy&hold) est semblable,")
    print("la validation USD est transposable en EUR. Sinon, à creuser.")
