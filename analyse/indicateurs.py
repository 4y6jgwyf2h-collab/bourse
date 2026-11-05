"""Indicateurs techniques classiques, calculés avec pandas uniquement."""
import numpy as np
import pandas as pd


def sma(serie: pd.Series, n: int) -> pd.Series:
    """Moyenne mobile simple."""
    return serie.rolling(n, min_periods=n).mean()


def ema(serie: pd.Series, n: int) -> pd.Series:
    """Moyenne mobile exponentielle."""
    return serie.ewm(span=n, adjust=False, min_periods=n).mean()


def rsi(serie: pd.Series, n: int = 14) -> pd.Series:
    """Relative Strength Index (méthode de Wilder), entre 0 et 100."""
    delta = serie.diff()
    hausse = delta.clip(lower=0)
    baisse = -delta.clip(upper=0)
    moy_h = hausse.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    moy_b = baisse.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rs = moy_h / moy_b.replace(0, np.nan)
    out = 100 - 100 / (1 + rs)
    # Aucune baisse sur la période : RSI = 100
    out = out.where(moy_b != 0, 100.0)
    return out.where(moy_h.notna())


def macd(serie: pd.Series, rapide: int = 12, lente: int = 26, signal: int = 9) -> pd.DataFrame:
    ligne = ema(serie, rapide) - ema(serie, lente)
    sig = ligne.ewm(span=signal, adjust=False).mean()
    return pd.DataFrame({"macd": ligne, "macd_signal": sig, "macd_hist": ligne - sig})


def bollinger(serie: pd.Series, n: int = 20, k: float = 2.0) -> pd.DataFrame:
    milieu = sma(serie, n)
    ecart = serie.rolling(n, min_periods=n).std()
    return pd.DataFrame({
        "bb_milieu": milieu,
        "bb_haut": milieu + k * ecart,
        "bb_bas": milieu - k * ecart,
    })


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    """Average True Range : mesure de la volatilité en unités de prix."""
    prec = df["Close"].shift()
    tr = pd.concat([
        df["High"] - df["Low"],
        (df["High"] - prec).abs(),
        (df["Low"] - prec).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def ajouter_indicateurs(df: pd.DataFrame) -> pd.DataFrame:
    """Retourne une copie du DataFrame OHLCV enrichie de tous les indicateurs."""
    out = df.copy()
    c = out["Close"]
    out["sma20"] = sma(c, 20)
    out["sma50"] = sma(c, 50)
    out["sma200"] = sma(c, 200)
    out["rsi"] = rsi(c, 14)
    out = out.join(macd(c)).join(bollinger(c))
    out["atr"] = atr(out)
    out["vol_moy20"] = out["Volume"].rolling(20, min_periods=20).mean()
    out["rendement"] = c.pct_change()
    return out
