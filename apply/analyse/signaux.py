"""Signaux d'aide à la décision.

Chaque règle donne un vote entre -2 (fortement baissier) et +2 (fortement haussier)
avec une explication en clair. Le score global est la somme ramenée entre -100 et +100.
Ce n'est pas une recommandation : c'est une synthèse lisible des indicateurs.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class Signal:
    famille: str
    vote: int          # -2 .. +2
    explication: str


def _ok(*valeurs) -> bool:
    return all(v is not None and not (isinstance(v, float) and np.isnan(v)) for v in valeurs)


def analyser(df: pd.DataFrame) -> list[Signal]:
    """Analyse la dernière bougie d'un DataFrame enrichi par ajouter_indicateurs()."""
    if len(df) < 2:
        return []
    d, p = df.iloc[-1], df.iloc[-2]
    c = d["Close"]
    s: list[Signal] = []

    # Tendance de fond : prix vs moyenne 200 jours
    if _ok(d["sma200"]):
        if c > d["sma200"]:
            s.append(Signal("Tendance", 1, f"Le cours ({c:.2f}) est au-dessus de sa moyenne 200 jours ({d['sma200']:.2f}) : tendance de fond haussière."))
        else:
            s.append(Signal("Tendance", -1, f"Le cours ({c:.2f}) est sous sa moyenne 200 jours ({d['sma200']:.2f}) : tendance de fond baissière."))

    # Croisement 50 / 200 (golden / death cross)
    if _ok(d["sma50"], d["sma200"], p["sma50"], p["sma200"]):
        if p["sma50"] <= p["sma200"] and d["sma50"] > d["sma200"]:
            s.append(Signal("Tendance", 2, "Croisement doré : la moyenne 50 jours vient de passer au-dessus de la 200 jours."))
        elif p["sma50"] >= p["sma200"] and d["sma50"] < d["sma200"]:
            s.append(Signal("Tendance", -2, "Croisement de la mort : la moyenne 50 jours vient de passer sous la 200 jours."))
        elif d["sma50"] > d["sma200"]:
            s.append(Signal("Tendance", 1, "La moyenne 50 jours est au-dessus de la 200 jours (configuration haussière)."))
        else:
            s.append(Signal("Tendance", -1, "La moyenne 50 jours est sous la 200 jours (configuration baissière)."))

    # Moyen terme : prix vs moyenne 20 jours
    if _ok(d["sma20"]):
        if c > d["sma20"]:
            s.append(Signal("Court terme", 1, f"Le cours est au-dessus de sa moyenne 20 jours ({d['sma20']:.2f})."))
        else:
            s.append(Signal("Court terme", -1, f"Le cours est sous sa moyenne 20 jours ({d['sma20']:.2f})."))

    # RSI
    if _ok(d["rsi"]):
        r = d["rsi"]
        if r < 30:
            s.append(Signal("Momentum", 2, f"RSI à {r:.0f} : zone de survente, un rebond est possible."))
        elif r > 70:
            s.append(Signal("Momentum", -2, f"RSI à {r:.0f} : zone de surachat, risque de correction."))
        elif r >= 50:
            s.append(Signal("Momentum", 1 if r < 65 else 0, f"RSI à {r:.0f} : momentum plutôt positif."))
        else:
            s.append(Signal("Momentum", -1 if r > 35 else 0, f"RSI à {r:.0f} : momentum plutôt négatif."))

    # MACD
    if _ok(d["macd"], d["macd_signal"], p["macd"], p["macd_signal"]):
        if p["macd"] <= p["macd_signal"] and d["macd"] > d["macd_signal"]:
            s.append(Signal("Momentum", 2, "Le MACD vient de croiser sa ligne de signal à la hausse."))
        elif p["macd"] >= p["macd_signal"] and d["macd"] < d["macd_signal"]:
            s.append(Signal("Momentum", -2, "Le MACD vient de croiser sa ligne de signal à la baisse."))
        elif d["macd"] > d["macd_signal"]:
            s.append(Signal("Momentum", 1, "Le MACD est au-dessus de sa ligne de signal."))
        else:
            s.append(Signal("Momentum", -1, "Le MACD est sous sa ligne de signal."))

    # Bollinger
    if _ok(d["bb_haut"], d["bb_bas"]):
        if c < d["bb_bas"]:
            s.append(Signal("Volatilité", 1, "Le cours est sous la bande de Bollinger basse : excès de baisse à court terme."))
        elif c > d["bb_haut"]:
            s.append(Signal("Volatilité", -1, "Le cours est au-dessus de la bande de Bollinger haute : excès de hausse à court terme."))
        else:
            larg = (d["bb_haut"] - d["bb_bas"]) / d["bb_milieu"] * 100
            s.append(Signal("Volatilité", 0, f"Le cours est dans les bandes de Bollinger (largeur {larg:.1f} %)."))

    # Volume
    if _ok(d["vol_moy20"]) and d["vol_moy20"] > 0:
        ratio = d["Volume"] / d["vol_moy20"]
        if ratio > 1.5:
            sens = 1 if c >= p["Close"] else -1
            mot = "hausse" if sens > 0 else "baisse"
            s.append(Signal("Volume", sens, f"Volume {ratio:.1f}× supérieur à la moyenne sur une séance de {mot} : mouvement confirmé."))

    return s


def score(signaux: list[Signal]) -> int:
    """Score entre -100 et +100."""
    if not signaux:
        return 0
    total = sum(x.vote for x in signaux)
    maxi = 2 * len(signaux)
    return int(round(100 * total / maxi))


def verdict(sc: int) -> tuple[str, str]:
    """Libellé et couleur associés au score."""
    if sc >= 50:
        return "Fortement haussier", "#1a9850"
    if sc >= 15:
        return "Plutôt haussier", "#66bd63"
    if sc > -15:
        return "Neutre", "#888888"
    if sc > -50:
        return "Plutôt baissier", "#f46d43"
    return "Fortement baissier", "#d73027"


def niveaux_risque(df: pd.DataFrame, mult_atr: float = 2.0) -> dict:
    """Propose un stop et un objectif à partir de l'ATR (volatilité)."""
    d = df.iloc[-1]
    if not _ok(d["atr"]):
        return {}
    c, a = d["Close"], d["atr"]
    return {
        "stop": c - mult_atr * a,
        "objectif": c + 2 * mult_atr * a,
        "atr_pct": a / c * 100,
    }


def statistiques(df: pd.DataFrame) -> dict:
    r = df["Close"].pct_change().dropna()
    if r.empty:
        return {}
    cumul = (1 + r).cumprod()
    dd = cumul / cumul.cummax() - 1
    def perf(n):
        return df["Close"].iloc[-1] / df["Close"].iloc[-n - 1] - 1 if len(df) > n else np.nan
    return {
        "Perf. 1 mois": perf(21),
        "Perf. 3 mois": perf(63),
        "Perf. 1 an": perf(252),
        "Volatilité annualisée": r.std() * np.sqrt(252),
        "Perte max. (drawdown)": dd.min(),
    }
