"""Outils pour l'investissement long terme.

- note_fondamentale : lit les ratios d'une entreprise et les explique simplement
- historique_long : rendement annuel moyen, pires baisses, temps de récupération
- simuler_dca : investissement d'une somme fixe chaque mois sur l'historique réel
- projeter : projection d'une épargne selon plusieurs taux de rendement

Aide à la réflexion uniquement : ce n'est pas un conseil en investissement.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd


# --------------------------------------------------------------------- Fondamentaux
@dataclass
class Critere:
    pilier: str
    nom: str
    valeur: str
    vote: int          # -2 .. +2
    explication: str


PILIERS = ["Valorisation", "Rentabilité", "Solidité financière", "Croissance", "Dividende"]


def _f(info, *cles):
    for k in cles:
        v = info.get(k)
        if isinstance(v, (int, float)) and not (isinstance(v, float) and np.isnan(v)):
            return float(v)
    return None


def _p(x, d=1):
    return f"{x * 100:.{d}f} %"


def rendement_dividende(info: dict):
    """Rendement en fraction (0.03 = 3 %), robuste aux changements d'unité de Yahoo."""
    prix = _f(info, "currentPrice", "regularMarketPrice", "previousClose")
    taux = _f(info, "dividendRate", "trailingAnnualDividendRate")
    if prix and taux is not None:
        return taux / prix
    dy = _f(info, "dividendYield")
    if dy is None:
        return None
    return dy / 100 if dy > 0.3 else dy


def est_entreprise(info: dict) -> bool:
    return (info.get("quoteType") or "").upper() == "EQUITY"


def note_fondamentale(info: dict) -> list[Critere]:
    c: list[Critere] = []
    financiere = (info.get("sector") or "") in ("Financial Services",)

    # Valorisation
    per = _f(info, "trailingPE")
    eps = _f(info, "trailingEps")
    if per is None and eps is not None and eps <= 0:
        c.append(Critere("Valorisation", "PER", "négatif", -2,
                         "L'entreprise a perdu de l'argent sur les 12 derniers mois : pas de bénéfice pour justifier le prix."))
    elif per is not None:
        if per < 12:
            v, t = 2, "bon marché : tu paies moins de 12 ans de bénéfices actuels."
        elif per < 20:
            v, t = 1, "raisonnable, proche de la moyenne historique des marchés (15-20)."
        elif per < 30:
            v, t = 0, "un peu cher : le marché attend de la croissance."
        elif per < 45:
            v, t = -1, "cher : il faudra une forte croissance des bénéfices pour le justifier."
        else:
            v, t = -2, "très cher : beaucoup d'optimisme est déjà dans le prix."
        c.append(Critere("Valorisation", "PER", f"{per:.1f}", v, f"Le cours vaut {per:.0f} fois le bénéfice annuel, {t}"))
    peg = _f(info, "pegRatio", "trailingPegRatio")
    if peg is not None and peg > 0:
        v = 1 if peg < 1 else (-1 if peg > 2.5 else 0)
        c.append(Critere("Valorisation", "PEG", f"{peg:.2f}", v,
                         "PER rapporté à la croissance attendue. Sous 1, le prix semble modeste au regard de la croissance ; "
                         "au-dessus de 2,5 il paraît élevé."))

    # Rentabilité
    roe = _f(info, "returnOnEquity")
    if roe is not None:
        v = 2 if roe > .20 else 1 if roe > .12 else 0 if roe > .05 else -1 if roe > 0 else -2
        c.append(Critere("Rentabilité", "Rentabilité des capitaux (ROE)", _p(roe), v,
                         f"Pour 100 € apportés par les actionnaires, l'entreprise gagne {roe * 100:.0f} € par an. "
                         "Au-dessus de 15 %, c'est le signe d'un avantage concurrentiel."))
    marge = _f(info, "profitMargins")
    if marge is not None:
        v = 2 if marge > .20 else 1 if marge > .10 else 0 if marge > .03 else -1 if marge > 0 else -2
        c.append(Critere("Rentabilité", "Marge nette", _p(marge), v,
                         f"Sur 100 € de ventes, il reste {marge * 100:.0f} € de bénéfice. Une marge élevée protège en cas de coup dur."))

    # Solidité financière
    dte = _f(info, "debtToEquity")
    if dte is not None and not financiere:
        r = dte / 100
        v = 2 if r < .5 else 1 if r < 1 else 0 if r < 2 else -1 if r < 3 else -2
        c.append(Critere("Solidité financière", "Dette / capitaux propres", f"{r:.2f}", v,
                         f"La dette représente {r:.1f} fois les capitaux propres. Plus c'est bas, mieux l'entreprise "
                         "traverse les crises et la hausse des taux."))
    cr = _f(info, "currentRatio")
    if cr is not None and not financiere:
        v = 1 if cr > 1.5 else -1 if cr < 1 else 0
        c.append(Critere("Solidité financière", "Liquidité (current ratio)", f"{cr:.2f}", v,
                         "Ce que l'entreprise possède à court terme divisé par ce qu'elle doit à court terme. "
                         "Sous 1, elle pourrait manquer de trésorerie."))
    fcf = _f(info, "freeCashflow")
    if fcf is not None:
        c.append(Critere("Solidité financière", "Flux de trésorerie libre", "positif" if fcf > 0 else "négatif",
                         1 if fcf > 0 else -1,
                         "L'argent qui reste une fois les investissements payés. Positif, il finance dividendes, "
                         "rachats d'actions et désendettement." if fcf > 0 else
                         "L'entreprise consomme plus d'argent qu'elle n'en génère : elle doit s'endetter ou lever des fonds."))

    # Croissance
    rg = _f(info, "revenueGrowth")
    if rg is not None:
        v = 2 if rg > .10 else 1 if rg > .03 else 0 if rg > -.02 else -1
        c.append(Critere("Croissance", "Croissance du chiffre d'affaires", _p(rg), v,
                         "Évolution des ventes sur un an. Une entreprise qui vend plus chaque année a plus de chances "
                         "de voir sa valeur grandir."))
    eg = _f(info, "earningsGrowth")
    if eg is not None:
        v = 1 if eg > .10 else -1 if eg < -.10 else 0
        c.append(Critere("Croissance", "Croissance des bénéfices", _p(eg), v,
                         "Évolution des bénéfices sur un an. À long terme, le cours suit les bénéfices."))

    # Dividende
    dy = rendement_dividende(info)
    payout = _f(info, "payoutRatio")
    if dy is not None and dy > 0:
        v = 1 if dy > .025 else 0
        if dy > .08:
            v, extra = -1, " Un rendement aussi élevé signale souvent un dividende menacé ou un cours en forte baisse."
        else:
            extra = ""
        c.append(Critere("Dividende", "Rendement du dividende", _p(dy, 2), v,
                         f"Chaque année, l'entreprise verse environ {dy * 100:.1f} % du prix de l'action.{extra}"))
        if payout is not None:
            v = 1 if 0 < payout < .7 else -1 if payout > 1 else 0
            c.append(Critere("Dividende", "Part des bénéfices distribuée", _p(payout, 0), v,
                             "Au-dessus de 100 %, l'entreprise verse plus qu'elle ne gagne, ce qui n'est pas tenable. "
                             "Entre 30 et 70 %, le dividende est en général bien couvert."))
    elif dy is not None:
        c.append(Critere("Dividende", "Rendement du dividende", "aucun", 0,
                         "Pas de dividende : l'entreprise réinvestit tous ses bénéfices. Ce n'est ni bon ni mauvais en soi."))
    return c


def notes_par_pilier(criteres: list[Critere]) -> dict:
    """Note sur 10 par pilier (None si pas de donnée) + note globale."""
    out = {}
    for p in PILIERS:
        votes = [x.vote for x in criteres if x.pilier == p]
        out[p] = round(5 + 2.5 * np.mean(votes), 1) if votes else None
    vals = [v for k, v in out.items() if v is not None and k != "Dividende"]
    out["Globale"] = round(float(np.mean(vals)), 1) if vals else None
    return out


def infos_demo() -> dict:
    """Fondamentaux fictifs pour le mode démo."""
    return {"quoteType": "EQUITY", "longName": "Exemple SA (fictif)", "sector": "Industrials",
            "trailingPE": 17.5, "pegRatio": 1.6, "returnOnEquity": 0.17, "profitMargins": 0.11,
            "debtToEquity": 65.0, "currentRatio": 1.4, "freeCashflow": 1.2e9, "revenueGrowth": 0.06,
            "earningsGrowth": 0.09, "currentPrice": 100.0, "dividendRate": 2.8, "payoutRatio": 0.48}


# --------------------------------------------------------------------- Historique
def _cagr(serie: pd.Series) -> float:
    ans = (serie.index[-1] - serie.index[0]).days / 365.25
    return (serie.iloc[-1] / serie.iloc[0]) ** (1 / ans) - 1 if ans > 0.5 else np.nan


def _periodes_par_an(s: pd.Series) -> int:
    ecart = pd.Series(s.index).diff().dt.days.median()
    return 252 if ecart <= 3 else 52 if ecart <= 8 else 12


def historique_long(close: pd.Series) -> dict:
    close = close.dropna()
    fin = close.index[-1]
    res = {"Depuis le début": _cagr(close)}
    for n in (3, 5, 10, 20):
        s = close[close.index >= fin - pd.DateOffset(years=n)]
        if (s.index[0] - (fin - pd.DateOffset(years=n))).days < 20:
            res[f"Sur {n} ans"] = _cagr(s)
    pic = close.cummax()
    dd = close / pic - 1
    creux = dd.idxmin()
    date_pic = close[:creux].idxmax()
    apres = close[creux:]
    retour = apres[apres >= close[date_pic]]
    recup = (retour.index[0] - date_pic).days / 365.25 if len(retour) else None
    annuel = close.resample("YE").last()
    annuel = pd.concat([close.iloc[:1], annuel]).pct_change().dropna()
    annuel.index = annuel.index.year
    annuel = annuel[~annuel.index.duplicated(keep="last")]
    # Part des périodes de 5 ans gagnantes
    mensuel = close.resample("ME").last()
    r5 = (mensuel / mensuel.shift(60) - 1).dropna()
    r_j = close.pct_change().dropna()
    return {
        "cagr": res,
        "volatilite": r_j.std() * np.sqrt(_periodes_par_an(close)),
        "drawdown": dd.min(),
        "date_pic": date_pic,
        "date_creux": creux,
        "recuperation_ans": recup,
        "annees": annuel,
        "pct_5ans_gagnants": (r5 > 0).mean() if len(r5) else None,
        "pire_5ans": r5.min() if len(r5) else None,
        "drawdown_serie": dd,
    }


def rendements_glissants(close: pd.Series, ans: int = 10) -> pd.Series:
    """Rendement annualisé de chaque période de `ans` années (pas mensuel)."""
    m = close.dropna().resample("ME").last()
    r = (m / m.shift(12 * ans)) ** (1 / ans) - 1
    return r.dropna()


def taux_depuis_historique(close: pd.Series, plafond: float = 0.12) -> dict | None:
    """Taux central = rendement annuel des 10 dernières années (ou de tout l'historique s'il est plus court).
    Pessimiste / optimiste = 10e et 90e centiles des périodes de 10 ans passées si l'historique le permet."""
    close = close.dropna()
    ans_dispo = (close.index[-1] - close.index[0]).days / 365.25
    if ans_dispo < 3:
        return None
    h = historique_long(close)["cagr"]
    base, libelle = (h["Sur 10 ans"], "10 dernières années") if "Sur 10 ans" in h else \
        (h["Depuis le début"], f"{ans_dispo:.0f} dernières années")
    central = float(np.clip(base, -0.05, plafond))
    gl = rendements_glissants(close, 10)
    if len(gl) >= 60:  # au moins 5 ans de périodes de 10 ans
        p10, p90 = float(gl.quantile(0.10)), float(gl.quantile(0.90))
        pess = float(np.clip(p10, -0.05, central - 0.02))
        opt = float(np.clip(p90, central + 0.02, plafond + 0.04))
        methode = ("Pessimiste et optimiste : les 10 % moins bonnes et les 10 % meilleures périodes de 10 ans "
                   f"de son histoire ({p10 * 100:.1f} % et {p90 * 100:.1f} % par an)")
        methode += ", ramenées dans une fourchette réaliste." if (pess != p10 or opt != p90) else "."
    else:
        pess, opt = max(central - 0.03, -0.05), central + 0.03
        methode = "Historique trop court pour mesurer les meilleures et pires périodes : on retient ± 3 points."
    return {"brut": float(base), "central": central, "pessimiste": pess, "optimiste": opt,
            "plafonne": base > plafond, "libelle": libelle, "methode": methode}


# --------------------------------------------------------------------- DCA
def simuler_dca(close: pd.Series, mensualite: float, debut: pd.Timestamp, frais_pct: float = 0.0) -> dict:
    s = close[close.index >= debut].dropna()
    if len(s) < 2:
        raise ValueError("Pas assez d'historique pour cette date de début.")
    dates_achat = s.groupby([s.index.year, s.index.month]).head(1).index
    parts = pd.Series(0.0, index=s.index)
    verse = pd.Series(0.0, index=s.index)
    for d in dates_achat:
        parts[d] += mensualite * (1 - frais_pct / 100) / s[d]
        verse[d] += mensualite
    parts, verse = parts.cumsum(), verse.cumsum()
    valeur = parts * s
    total = verse.iloc[-1]
    # Comparaison : tout investir au début
    unique = total * (1 - frais_pct / 100) * s / s.iloc[0]
    flux = [(-mensualite, d) for d in dates_achat] + [(valeur.iloc[-1], s.index[-1])]
    return {
        "courbe": pd.DataFrame({"Valeur du portefeuille": valeur, "Total versé": verse,
                                "Tout investi au début": unique}),
        "verse": total,
        "valeur": valeur.iloc[-1],
        "nb_mois": len(dates_achat),
        "taux_annuel": _xirr(flux),
        "valeur_unique": unique.iloc[-1],
        "pire_moment": (valeur / verse - 1)[verse > 0].min(),
    }


def _xirr(flux) -> float:
    t0 = flux[0][1]
    ts = np.array([(d - t0).days / 365.25 for _, d in flux])
    cf = np.array([m for m, _ in flux])

    def vna(r):
        return np.sum(cf / (1 + r) ** ts)
    bas, haut = -0.99, 5.0
    if vna(bas) * vna(haut) > 0:
        return np.nan
    for _ in range(200):
        mil = (bas + haut) / 2
        if vna(bas) * vna(mil) <= 0:
            haut = mil
        else:
            bas = mil
    return (bas + haut) / 2


# --------------------------------------------------------------------- Projection
def projeter(capital: float, mensualite: float, annees: int, taux: float, inflation: float = 0.0) -> pd.DataFrame:
    """Projection mois par mois (versements en début de mois)."""
    rm = (1 + taux) ** (1 / 12) - 1
    im = (1 + inflation) ** (1 / 12) - 1
    v, verse, lignes = capital, capital, []
    for m in range(annees * 12 + 1):
        if m:
            v = (v + mensualite) * (1 + rm)
            verse += mensualite
        if m % 12 == 0:
            lignes.append({"Année": m // 12, "Valeur": v, "Versé": verse,
                           "Valeur en euros d'aujourd'hui": v / (1 + im) ** m})
    return pd.DataFrame(lignes).set_index("Année")
