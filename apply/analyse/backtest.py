"""Backtest simple : on compare une stratégie à « acheter et garder ».

Les positions sont décidées à la clôture et appliquées le lendemain
(pas de lecture du futur). Long uniquement, frais en % par transaction.
"""
import numpy as np
import pandas as pd

STRATEGIES = {
    "Croisement de moyennes (rapide / lente)": "croisement",
    "RSI : acheter en survente, vendre en surachat": "rsi",
    "MACD au-dessus de son signal": "macd",
    "Score global des signaux > seuil": "score",
}


def _position_croisement(df, rapide=20, lente=50):
    r = df["Close"].rolling(rapide).mean()
    l = df["Close"].rolling(lente).mean()
    return (r > l).astype(float)


def _position_rsi(df, bas=30, haut=70):
    pos = pd.Series(np.nan, index=df.index)
    pos[df["rsi"] < bas] = 1.0
    pos[df["rsi"] > haut] = 0.0
    return pos.ffill().fillna(0.0)


def _position_macd(df):
    return (df["macd"] > df["macd_signal"]).astype(float)


def _position_score(df, seuil=15):
    """Recalcule le score des signaux à chaque date (plus lent)."""
    from .signaux import analyser, score
    pos = []
    for i in range(len(df)):
        if i < 2:
            pos.append(0.0)
            continue
        pos.append(1.0 if score(analyser(df.iloc[i - 1:i + 1])) > seuil else 0.0)
    return pd.Series(pos, index=df.index)


def lancer(df: pd.DataFrame, strategie: str, frais_pct: float = 0.1, **params) -> dict:
    if strategie == "croisement":
        pos = _position_croisement(df, params.get("rapide", 20), params.get("lente", 50))
    elif strategie == "rsi":
        pos = _position_rsi(df, params.get("bas", 30), params.get("haut", 70))
    elif strategie == "macd":
        pos = _position_macd(df)
    elif strategie == "score":
        pos = _position_score(df, params.get("seuil", 15))
    else:
        raise ValueError(strategie)

    r = df["Close"].pct_change().fillna(0.0)
    expo = pos.shift(1).fillna(0.0)          # décision d'hier appliquée aujourd'hui
    trades = expo.diff().abs().fillna(expo.abs())
    r_strat = expo * r - trades * frais_pct / 100

    courbe = pd.DataFrame({
        "Stratégie": (1 + r_strat).cumprod(),
        "Acheter et garder": (1 + r).cumprod(),
    })
    return {
        "courbe": courbe,
        "position": expo,
        "stats": {
            "Stratégie": _stats(r_strat, expo, trades),
            "Acheter et garder": _stats(r, pd.Series(1.0, index=r.index), pd.Series(0.0, index=r.index)),
        },
    }


def _stats(r: pd.Series, expo: pd.Series, trades: pd.Series) -> dict:
    cumul = (1 + r).cumprod()
    annees = max(len(r) / 252, 1e-9)
    dd = cumul / cumul.cummax() - 1
    vol = r.std() * np.sqrt(252)
    return {
        "Performance totale": cumul.iloc[-1] - 1,
        "Performance annualisée": cumul.iloc[-1] ** (1 / annees) - 1,
        "Volatilité": vol,
        "Ratio de Sharpe": (r.mean() * 252) / vol if vol > 0 else np.nan,
        "Perte max.": dd.min(),
        "Temps investi": expo.mean(),
        "Nombre d'ordres": int((trades > 0).sum()),
    }
