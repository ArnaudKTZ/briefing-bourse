#!/usr/bin/env python3
"""
Analyse de stabilité du classement du score (piste d'amélioration du 11/08).

Question posée : le score range-t-il les valeurs de façon STABLE dans le temps ?
Enjeu : toute la thèse du Risk Engine repose sur "concentrer sur le top-3 par
score". Si le classement se réorganise à chaque run (score bruité), le top-3
change tout le temps → rotation forte → frais → et surtout la "conviction" du
top-3 n'a aucune fondation.

Deux mesures, uniquement sur données déjà collectées (performance.json) :
  1) Autocorrélation des rangs à lag 1 jour et lag ~5 jours (une semaine de
     bourse). Spearman = Pearson sur les rangs (pas de scipy dans le CI).
     Proche de 1 = classement stable ; proche de 0 = classement qui se
     réorganise au hasard ; négatif = classement qui s'inverse.
  2) Persistance du top-3 : recouvrement (Jaccard) du trio de tête d'une
     semaine à la suivante, et taux de survie d'une valeur du top-3.

Sortie : console + score_stabilite_resultats.json.
Ne modifie rien, ne décide rien. Alimente la recette du 22/08.
"""

import json
import datetime

FICHIER_PERF = "performance.json"
LAG_SEMAINE = 5  # jours de bourse ~ une semaine


def charger_scores_par_jour():
    """Retourne une liste (date, {valeur: score}) triée par date croissante."""
    d = json.load(open(FICHIER_PERF, encoding="utf-8"))
    hist = d.get("historique", {})
    jours = []
    for date_str in sorted(hist.keys()):
        valeurs = hist[date_str]
        if not isinstance(valeurs, dict):
            continue
        scores = {}
        for nom, info in valeurs.items():
            if isinstance(info, dict) and isinstance(info.get("score"), (int, float)):
                scores[nom] = float(info["score"])
        if len(scores) >= 10:  # coupe transversale exploitable
            jours.append((date_str, scores))
    return jours


def rangs(valeurs_par_nom, noms):
    """Rangs moyens (gestion des ex aequo) pour la liste ordonnée `noms`."""
    paires = sorted(noms, key=lambda n: valeurs_par_nom[n])
    rang = {}
    i = 0
    n = len(paires)
    while i < n:
        j = i
        while j + 1 < n and valeurs_par_nom[paires[j + 1]] == valeurs_par_nom[paires[i]]:
            j += 1
        rang_moyen = (i + j) / 2.0 + 1.0  # rangs 1..n, moyenne sur les ex aequo
        for k in range(i, j + 1):
            rang[paires[k]] = rang_moyen
        i = j + 1
    return rang


def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = sum((x - mx) ** 2 for x in xs) ** 0.5
    dy = sum((y - my) ** 2 for y in ys) ** 0.5
    if dx == 0 or dy == 0:
        return None
    return num / (dx * dy)


def spearman(scores_a, scores_b):
    """Spearman entre deux coupes, sur les valeurs communes."""
    communs = sorted(set(scores_a) & set(scores_b))
    if len(communs) < 3:
        return None, len(communs)
    ra = rangs(scores_a, communs)
    rb = rangs(scores_b, communs)
    return pearson([ra[n] for n in communs], [rb[n] for n in communs]), len(communs)


def top_k(scores, k=3):
    return set(sorted(scores, key=lambda n: -scores[n])[:k])


def jaccard(a, b):
    u = a | b
    return len(a & b) / len(u) if u else None


def main():
    jours = charger_scores_par_jour()
    if len(jours) < LAG_SEMAINE + 1:
        print(f"Pas assez de jours ({len(jours)}) pour l'analyse.")
        return

    dates = [d for d, _ in jours]
    print(f"Analyse de stabilité du classement — {len(jours)} coupes du {dates[0]} au {dates[-1]}\n")

    # 1) Autocorrélation des rangs à lag 1 et lag ~1 semaine
    resultats = {"date": datetime.date.today().isoformat(),
                 "n_coupes": len(jours), "debut": dates[0], "fin": dates[-1]}
    for lag, libelle in [(1, "lag 1 jour"), (LAG_SEMAINE, f"lag {LAG_SEMAINE} jours (~1 semaine)")]:
        rhos = []
        for i in range(len(jours) - lag):
            rho, n = spearman(jours[i][1], jours[i + lag][1])
            if rho is not None:
                rhos.append(rho)
        if rhos:
            moy = sum(rhos) / len(rhos)
            mini, maxi = min(rhos), max(rhos)
            pct_faible = 100.0 * sum(1 for r in rhos if r < 0.5) / len(rhos)
            print(f"Rang-autocorrélation {libelle:24} : moyenne {moy:+.3f}  "
                  f"(min {mini:+.2f}, max {maxi:+.2f}, n={len(rhos)})  "
                  f"| {pct_faible:.0f}% des paires sous 0.5")
            resultats[f"autocorr_lag{lag}"] = {
                "moyenne": round(moy, 3), "min": round(mini, 3),
                "max": round(maxi, 3), "n": len(rhos),
                "pct_sous_0_5": round(pct_faible, 1)}

    # 2) Persistance du top-3 semaine à semaine
    print()
    overlaps = []
    survies = []
    for i in range(0, len(jours) - LAG_SEMAINE, LAG_SEMAINE):
        a = top_k(jours[i][1], 3)
        b = top_k(jours[i + LAG_SEMAINE][1], 3)
        j = jaccard(a, b)
        survie = len(a & b)  # combien du trio survivent une semaine
        overlaps.append(j)
        survies.append(survie)
    if overlaps:
        moy_j = sum(overlaps) / len(overlaps)
        moy_s = sum(survies) / len(survies)
        print(f"Persistance top-3 (semaine à semaine) : Jaccard moyen {moy_j:.2f}, "
              f"survie moyenne {moy_s:.2f}/3 valeurs  (n={len(overlaps)} transitions)")
        resultats["top3"] = {"jaccard_moyen": round(moy_j, 3),
                             "survie_moyenne_sur_3": round(moy_s, 3),
                             "n_transitions": len(overlaps)}

    # Lecture guidée
    print("\n── Lecture ─────────────────────────────────────────────")
    a5 = resultats.get(f"autocorr_lag{LAG_SEMAINE}", {}).get("moyenne")
    if a5 is not None:
        if a5 >= 0.6:
            verdict = ("classement STABLE d'une semaine à l'autre : la concentration "
                       "top-3 du Risk Engine repose sur un socle solide.")
        elif a5 >= 0.3:
            verdict = ("stabilité MOYENNE : le top-3 a un sens mais tourne pas mal, "
                       "surveiller la rotation/frais côté Risk Engine.")
        else:
            verdict = ("classement INSTABLE : le score se réorganise presque au hasard "
                       "d'une semaine à l'autre, la 'conviction' top-3 est fragile. "
                       "Signal à porter à la recette du 22/08.")
        print(verdict)
        resultats["verdict"] = verdict

    json.dump(resultats, open("score_stabilite_resultats.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("\nRésultats écrits dans score_stabilite_resultats.json")


if __name__ == "__main__":
    main()
