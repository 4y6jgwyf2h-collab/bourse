"""Chargement des cours : Yahoo Finance, fichier CSV, ou données de démonstration."""
import numpy as np
import pandas as pd

COLONNES = ["Open", "High", "Low", "Close", "Volume"]

# Quelques symboles pour démarrer (format Yahoo Finance)
EXEMPLES = {
    "Apple": "AAPL",
    "Microsoft": "MSFT",
    "Nvidia": "NVDA",
    "LVMH": "MC.PA",
    "TotalEnergies": "TTE.PA",
    "Air Liquide": "AI.PA",
    "CAC 40": "^FCHI",
    "S&P 500": "^GSPC",
    "ETF MSCI World (CW8)": "CW8.PA",
    "Bitcoin (EUR)": "BTC-EUR",
    "Ethereum (EUR)": "ETH-EUR",
    "Or": "GC=F",
    "EUR/USD": "EURUSD=X",
}


def _nettoyer(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.rename(columns={c: c.capitalize() for c in df.columns})
    manquantes = [c for c in COLONNES if c not in df.columns]
    if "Volume" in manquantes:
        df["Volume"] = 0
        manquantes.remove("Volume")
    if manquantes:
        raise ValueError(f"Colonnes manquantes : {', '.join(manquantes)}")
    df = df[COLONNES].apply(pd.to_numeric, errors="coerce").dropna(subset=["Close"])
    df.index = pd.to_datetime(df.index)
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    return df.sort_index()


def charger_yahoo(symbole: str, periode: str = "2y", intervalle: str = "1d") -> pd.DataFrame:
    import yfinance as yf

    df = yf.download(symbole, period=periode, interval=intervalle,
                     auto_adjust=True, progress=False)
    if df is None or df.empty:
        raise ValueError(f"Aucune donnée pour « {symbole} ». Vérifie le symbole ou ta connexion.")
    return _nettoyer(df)


def infos_yahoo(symbole: str) -> dict:
    """Infos fondamentales de base (peut échouer silencieusement)."""
    try:
        import yfinance as yf
        info = yf.Ticker(symbole).info or {}
    except Exception:
        return {}
    cles = {
        "longName": "Nom", "sector": "Secteur", "currency": "Devise",
        "marketCap": "Capitalisation", "trailingPE": "PER", "forwardPE": "PER estimé",
        "dividendYield": "Rendement dividende", "beta": "Bêta",
        "fiftyTwoWeekHigh": "Plus haut 52 sem.", "fiftyTwoWeekLow": "Plus bas 52 sem.",
    }
    return {lib: info[k] for k, lib in cles.items() if info.get(k) is not None}


def charger_csv(fichier) -> pd.DataFrame:
    """CSV avec une colonne date et des colonnes Open, High, Low, Close (Volume optionnel)."""
    df = pd.read_csv(fichier, sep=None, engine="python")
    col_date = next((c for c in df.columns if c.lower() in ("date", "datetime", "time")), df.columns[0])
    df = df.set_index(col_date)
    return _nettoyer(df)


def donnees_demo(jours: int = 600, graine: int = 42) -> pd.DataFrame:
    """Série synthétique (marche aléatoire avec tendances) pour tester sans connexion."""
    rng = np.random.default_rng(graine)
    dates = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=jours)
    derive = np.repeat(rng.normal(0.0006, 0.0015, jours // 60 + 1), 60)[:jours]
    rend = rng.normal(derive, 0.017)
    close = 100 * np.exp(np.cumsum(rend))
    open_ = close * (1 + rng.normal(0, 0.005, jours))
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.008, jours)))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.008, jours)))
    vol = rng.integers(800_000, 3_000_000, jours)
    return pd.DataFrame({"Open": open_, "High": high, "Low": low, "Close": close, "Volume": vol},
                        index=dates)
