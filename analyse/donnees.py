"""Chargement des cours : Yahoo Finance, fichier CSV, ou données de démonstration."""
import numpy as np
import pandas as pd

COLONNES = ["Open", "High", "Low", "Close", "Volume"]

# Catalogue de symboles (format Yahoo Finance), classés par catégorie
CATALOGUE = {
    "Indices": {
        "CAC 40": "^FCHI", "SBF 120": "^SBF120", "Euro Stoxx 50": "^STOXX50E", "DAX (Allemagne)": "^GDAXI",
        "FTSE 100 (Royaume-Uni)": "^FTSE", "IBEX 35 (Espagne)": "^IBEX", "FTSE MIB (Italie)": "FTSEMIB.MI",
        "AEX (Pays-Bas)": "^AEX", "SMI (Suisse)": "^SSMI", "S&P 500": "^GSPC", "Nasdaq 100": "^NDX",
        "Nasdaq Composite": "^IXIC", "Dow Jones": "^DJI", "Russell 2000": "^RUT", "VIX (volatilité)": "^VIX",
        "Nikkei 225 (Japon)": "^N225", "Hang Seng (Hong Kong)": "^HSI", "Shanghai Composite": "000001.SS",
        "Sensex (Inde)": "^BSESN", "KOSPI (Corée)": "^KS11", "ASX 200 (Australie)": "^AXJO",
        "TSX (Canada)": "^GSPTSE", "Bovespa (Brésil)": "^BVSP",
    },
    "Actions françaises": {
        "LVMH": "MC.PA", "Hermès": "RMS.PA", "L'Oréal": "OR.PA", "TotalEnergies": "TTE.PA", "Air Liquide": "AI.PA",
        "Sanofi": "SAN.PA", "Airbus": "AIR.PA", "Schneider Electric": "SU.PA", "Safran": "SAF.PA",
        "BNP Paribas": "BNP.PA", "AXA": "CS.PA", "Crédit Agricole": "ACA.PA", "Société Générale": "GLE.PA",
        "Vinci": "DG.PA", "EssilorLuxottica": "EL.PA", "Kering": "KER.PA", "Danone": "BN.PA",
        "Pernod Ricard": "RI.PA", "Stellantis": "STLAP.PA", "Renault": "RNO.PA", "Michelin": "ML.PA",
        "Orange": "ORA.PA", "Capgemini": "CAP.PA", "Dassault Systèmes": "DSY.PA", "Thales": "HO.PA",
        "Saint-Gobain": "SGO.PA", "Engie": "ENGI.PA", "Veolia": "VIE.PA", "Carrefour": "CA.PA", "Accor": "AC.PA",
    },
    "Actions américaines": {
        "Apple": "AAPL", "Microsoft": "MSFT", "Nvidia": "NVDA", "Amazon": "AMZN", "Alphabet (Google)": "GOOGL",
        "Meta (Facebook)": "META", "Tesla": "TSLA", "Broadcom": "AVGO", "AMD": "AMD", "Netflix": "NFLX",
        "Berkshire Hathaway": "BRK-B", "JPMorgan": "JPM", "Visa": "V", "Coca-Cola": "KO",
        "Johnson & Johnson": "JNJ", "Walmart": "WMT", "McDonald's": "MCD", "Disney": "DIS",
    },
    "Actions européennes": {
        "ASML": "ASML.AS", "SAP": "SAP.DE", "Siemens": "SIE.DE", "Nestlé": "NESN.SW", "Roche": "ROG.SW",
        "Novo Nordisk": "NOVO-B.CO", "Shell": "SHEL.L", "AstraZeneca": "AZN.L", "Ferrari": "RACE.MI",
    },
    "ETF": {
        "Amundi MSCI World (CW8)": "CW8.PA", "Amundi PEA Monde (EWLD)": "EWLD.PA",
        "BNP S&P 500 (ESE)": "ESE.PA", "Amundi PEA Nasdaq-100 (PANX)": "PANX.PA", "Amundi CAC 40 (CAC)": "CAC.PA",
        "Amundi Marchés émergents (AEEM)": "AEEM.PA", "iShares Core MSCI World (IWDA)": "IWDA.AS",
        "Vanguard FTSE All-World (VWCE)": "VWCE.DE", "SPDR S&P 500 (SPY)": "SPY", "Invesco Nasdaq 100 (QQQ)": "QQQ",
    },
    "Cryptomonnaies": {
        "Bitcoin (EUR)": "BTC-EUR", "Ethereum (EUR)": "ETH-EUR", "Solana (EUR)": "SOL-EUR", "XRP (EUR)": "XRP-EUR",
        "BNB (EUR)": "BNB-EUR", "Cardano (EUR)": "ADA-EUR", "Dogecoin (EUR)": "DOGE-EUR", "Bitcoin (USD)": "BTC-USD",
    },
    "Matières premières": {
        "Or": "GC=F", "Argent": "SI=F", "Pétrole Brent": "BZ=F", "Pétrole WTI": "CL=F", "Gaz naturel": "NG=F",
        "Cuivre": "HG=F", "Blé": "ZW=F",
    },
    "Devises et taux": {
        "EUR/USD": "EURUSD=X", "EUR/GBP": "EURGBP=X", "EUR/CHF": "EURCHF=X", "EUR/JPY": "EURJPY=X",
        "GBP/USD": "GBPUSD=X", "USD/JPY": "JPY=X", "Taux US 10 ans": "^TNX",
    },
}
EXEMPLES = {nom: sym for cat in CATALOGUE.values() for nom, sym in cat.items()}

# Unités de temps : intervalle Yahoo -> périodes autorisées par Yahoo
UNITES = {
    "1 minute": ("1m", ["1d", "5d", "7d"]),
    "5 minutes": ("5m", ["1d", "5d", "1mo", "60d"]),
    "15 minutes": ("15m", ["1d", "5d", "1mo", "60d"]),
    "1 heure": ("1h", ["5d", "1mo", "3mo", "6mo", "1y", "2y"]),
    "Jour": ("1d", ["1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "max"]),
    "Semaine": ("1wk", ["1y", "2y", "5y", "10y", "max"]),
    "Mois": ("1mo", ["5y", "10y", "max"]),
}
NOMS_PERIODES = {"1d": "1 jour", "5d": "5 jours", "7d": "7 jours", "1mo": "1 mois", "60d": "60 jours",
                 "3mo": "3 mois", "6mo": "6 mois", "1y": "1 an", "2y": "2 ans", "5y": "5 ans",
                 "10y": "10 ans", "max": "Tout l'historique"}


def rechercher(texte: str) -> list[dict]:
    """Recherche un actif par son nom sur Yahoo Finance."""
    try:
        import yfinance as yf
        res = yf.Search(texte, max_results=12, news_count=0).quotes
    except Exception:
        return []
    out = []
    for q in res:
        sym = q.get("symbol")
        if not sym:
            continue
        nom = q.get("longname") or q.get("shortname") or sym
        out.append({"symbole": sym, "nom": nom, "place": q.get("exchDisp") or q.get("exchange") or "",
                    "type": q.get("typeDisp") or q.get("quoteType") or ""})
    return out


def prix_direct(symbole: str) -> dict:
    """Dernier prix connu (peut être différé selon la place de cotation)."""
    try:
        import yfinance as yf
        fi = yf.Ticker(symbole).fast_info
        return {"prix": float(fi["last_price"]), "veille": float(fi["previous_close"]),
                "devise": fi.get("currency") if hasattr(fi, "get") else None}
    except Exception:
        return {}


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


def infos_brutes(symbole: str) -> dict:
    """Toutes les infos Yahoo (fondamentaux), dictionnaire vide en cas d'échec."""
    try:
        import yfinance as yf
        return dict(yf.Ticker(symbole).info or {})
    except Exception:
        return {}


def charger_csv(fichier) -> pd.DataFrame:
    """CSV avec une colonne date et des colonnes Open, High, Low, Close (Volume optionnel)."""
    df = pd.read_csv(fichier, sep=None, engine="python")
    col_date = next((c for c in df.columns if c.lower() in ("date", "datetime", "time")), df.columns[0])
    df = df.set_index(col_date)
    return _nettoyer(df)


def donnees_demo(jours: int = 600, graine: int = 42, vol: float = 0.017, derive_moy: float = 0.0006) -> pd.DataFrame:
    """Série synthétique (marche aléatoire avec tendances) pour tester sans connexion."""
    rng = np.random.default_rng(graine)
    dates = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=jours)
    derive = np.repeat(rng.normal(derive_moy, 0.0015, jours // 60 + 1), 60)[:jours]
    rend = rng.normal(derive, vol)
    close = 100 * np.exp(np.cumsum(rend))
    open_ = close * (1 + rng.normal(0, 0.005, jours))
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.008, jours)))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.008, jours)))
    vol = rng.integers(800_000, 3_000_000, jours)
    return pd.DataFrame({"Open": open_, "High": high, "Low": low, "Close": close, "Volume": vol},
                        index=dates)
