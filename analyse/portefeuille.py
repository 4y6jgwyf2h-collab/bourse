"""Construction et analyse d'un portefeuille.

Aide à la réflexion uniquement : ce n'est pas un conseil en investissement personnalisé.
"""
import json
import os

import numpy as np
import pandas as pd

# --------------------------------------------------------------------- Profil
QUESTIONS = {
    "horizon": ("Dans combien de temps pourrais-tu avoir besoin de cet argent ?",
                ["Moins de 3 ans", "3 à 5 ans", "5 à 10 ans", "Plus de 10 ans"]),
    "baisse": ("Ton placement perd 30 % en quelques mois. Que fais-tu ?",
               ["Je vends tout", "Je vends une partie", "J'attends sans rien faire", "J'en rachète"]),
    "objectif": ("Quel est ton objectif principal ?",
                 ["Ne pas perdre d'argent", "Battre un peu l'inflation", "Faire grossir mon capital",
                  "Le maximum de rendement, quitte à prendre des risques"]),
    "experience": ("Ton expérience de la bourse ?",
                   ["Aucune", "Quelques placements", "J'investis depuis plusieurs années"]),
}

PROFILS = {
    "Prudent": "Tu privilégies la sécurité. Les baisses fortes te seraient difficiles à vivre.",
    "Équilibré": "Tu acceptes des baisses modérées en échange d'un meilleur rendement à long terme.",
    "Dynamique": "Tu vises la croissance sur le long terme et tu peux traverser des baisses importantes.",
    "Offensif": "Tu cherches le rendement maximal et tu acceptes des baisses de 40 à 50 % en cours de route.",
}

# Répartition cible par classe d'actifs (en %)
ALLOCATIONS = {
    "Prudent":   {"Épargne sécurisée": 50, "Obligations": 25, "Actions monde": 17, "Actions émergentes": 3, "Or": 5, "Crypto": 0},
    "Équilibré": {"Épargne sécurisée": 25, "Obligations": 20, "Actions monde": 42, "Actions émergentes": 8, "Or": 5, "Crypto": 0},
    "Dynamique": {"Épargne sécurisée": 10, "Obligations": 10, "Actions monde": 60, "Actions émergentes": 12, "Or": 5, "Crypto": 3},
    "Offensif":  {"Épargne sécurisée": 5, "Obligations": 0, "Actions monde": 70, "Actions émergentes": 15, "Or": 5, "Crypto": 5},
}

# Exemple de support pour chaque classe (symbole Yahoo utilisé aussi pour la simulation)
SUPPORTS = {
    "Épargne sécurisée": ("Livret A / LDDS, fonds euros d'assurance-vie", None),
    "Obligations": ("ETF obligations d'État zone euro (ex. Xtrackers Eurozone Government Bond)", "XGLE.DE"),
    "Actions monde": ("ETF MSCI World (ex. Amundi PEA Monde EWLD, Amundi MSCI World CW8)", "CW8.PA"),
    "Actions émergentes": ("ETF marchés émergents (ex. Amundi PEA Emerging AEEM)", "AEEM.PA"),
    "Or": ("ETC or physique (ex. Xetra-Gold 4GLD)", "4GLD.DE"),
    "Crypto": ("Bitcoin (petite part uniquement)", "BTC-EUR"),
}
TAUX_SECURISE = 0.02  # rendement annuel supposé de l'épargne sécurisée pour la simulation

COULEURS = {"Épargne sécurisée": "#9e9e9e", "Obligations": "#4e79a7", "Actions monde": "#2962ff",
            "Actions émergentes": "#76b7b2", "Actions": "#2962ff", "ETF actions": "#59a14f", "Or": "#e2b33c",
            "Crypto": "#f28e2b", "Autre": "#b07aa1", "Indice": "#bab0ac"}


def profil(reponses: dict) -> str:
    pts = sum(reponses.values())
    if reponses.get("horizon", 3) == 0:
        return "Prudent"
    if pts <= 3:
        return "Prudent"
    if pts <= 6:
        return "Équilibré"
    if pts <= 8:
        return "Dynamique"
    return "Offensif"


def repartition(nom_profil: str, montant: float) -> pd.DataFrame:
    alloc = ALLOCATIONS[nom_profil]
    lignes = [{"Classe d'actifs": k, "Part (%)": v, "Montant (€)": montant * v / 100,
               "Exemple de support": SUPPORTS[k][0]} for k, v in alloc.items() if v > 0]
    return pd.DataFrame(lignes)


# --------------------------------------------------------------------- Simulation
def simuler(prix: dict[str, pd.Series], poids: dict[str, float], taux_fixe: dict[str, float] | None = None) -> pd.Series:
    """Valeur d'un portefeuille de 100 rééquilibré chaque mois.

    prix : {nom: série de cours}, poids : {nom: poids en fraction}, taux_fixe : {nom: rendement annuel constant}.
    """
    taux_fixe = taux_fixe or {}
    series = {k: v.dropna() for k, v in prix.items() if k in poids and v is not None and len(v.dropna()) > 20}
    if not series:
        raise ValueError("Aucune donnée de cours disponible.")
    df = pd.DataFrame(series)
    df.index = pd.to_datetime(df.index).normalize()
    df = df[~df.index.duplicated()].sort_index()
    debut = max(df[c].first_valid_index() for c in df.columns)
    df = df[df.index >= debut].ffill().dropna()
    r = df.pct_change().fillna(0.0)
    jours = df.index.to_series().diff().dt.days.fillna(0)
    for k, t in taux_fixe.items():
        if k in poids:
            r[k] = (1 + t) ** (jours / 365.25) - 1
    tot = sum(poids[k] for k in r.columns)
    w = pd.Series({k: poids[k] / tot for k in r.columns})
    valeurs, v, wc = [], 100.0, w.copy()
    mois = None
    for d, ligne in r.iterrows():
        if mois is not None and d.month != mois:
            wc = w.copy()  # rééquilibrage mensuel
        mois = d.month
        rj = float((wc * ligne).sum())
        v *= 1 + rj
        wc = wc * (1 + ligne) / (1 + rj)
        valeurs.append(v)
    return pd.Series(valeurs, index=r.index)


def stats_courbe(c: pd.Series) -> dict:
    r = c.pct_change().dropna()
    ans = (c.index[-1] - c.index[0]).days / 365.25
    dd = c / c.cummax() - 1
    vol = r.std() * np.sqrt(252)
    perf_an = (c.iloc[-1] / c.iloc[0]) ** (1 / ans) - 1 if ans > 0.3 else np.nan
    return {"Performance totale": c.iloc[-1] / c.iloc[0] - 1, "Performance annualisée": perf_an,
            "Volatilité": vol, "Pire baisse": dd.min(), "Années simulées": ans}


# --------------------------------------------------------------------- Analyse
def classer(info: dict, symbole: str) -> str:
    t = (info.get("quoteType") or "").upper()
    nom = " ".join(str(info.get(k) or "") for k in ("longName", "shortName", "category")).lower()
    if t == "CRYPTOCURRENCY" or symbole.endswith(("-EUR", "-USD")):
        return "Crypto"
    if "gold" in nom or " or " in f" {nom} " or symbole in ("GC=F", "4GLD.DE"):
        return "Or"
    if t in ("ETF", "MUTUALFUND"):
        if any(m in nom for m in ("bond", "oblig", "govt", "treasury", "aggregate", "credit")):
            return "Obligations"
        return "ETF actions"
    if t == "EQUITY":
        return "Actions"
    if t == "INDEX":
        return "Indice"
    return "Autre"


def diagnostic(lignes: pd.DataFrame, rendements: pd.DataFrame | None) -> tuple[float, list[tuple[int, str]]]:
    """Note de diversification sur 10 et liste de remarques (gravité -1 / 0 / +1, texte).

    lignes : colonnes Symbole, Nom, Montant, Classe, Secteur.
    """
    rem: list[tuple[int, str]] = []
    note = 10.0
    total = lignes["Montant"].sum()
    p = lignes.set_index("Symbole")["Montant"] / total
    par_classe = lignes.groupby("Classe")["Montant"].sum() / total

    top = p.idxmax()
    if p.max() > 0.40 and lignes.loc[lignes["Symbole"] == top, "Classe"].iloc[0] == "Actions":
        note -= 3
        rem.append((-1, f"**{top}** pèse {p.max() * 100:.0f} % du portefeuille. Si cette seule entreprise chute, "
                        "tout ton portefeuille en souffre. Au-delà de 10 à 15 % sur une action, le risque devient élevé."))
    elif p.max() > 0.20 and lignes.loc[lignes["Symbole"] == top, "Classe"].iloc[0] == "Actions":
        note -= 1.5
        rem.append((0, f"**{top}** pèse {p.max() * 100:.0f} % du portefeuille : c'est une position importante "
                       "pour une seule entreprise."))

    n_actions = int((lignes["Classe"] == "Actions").sum())
    part_actions = par_classe.get("Actions", 0)
    part_etf = par_classe.get("ETF actions", 0)
    if part_actions > 0.5 and n_actions < 10 and part_etf < 0.2:
        note -= 2
        rem.append((-1, f"Tes actions en direct représentent {part_actions * 100:.0f} % du portefeuille, réparties sur "
                        f"seulement {n_actions} entreprise(s). Un ETF monde t'exposerait à plus de 1 500 entreprises "
                        "en une seule ligne."))
    if part_etf >= 0.4:
        rem.append((1, f"Les ETF actions représentent {part_etf * 100:.0f} % du portefeuille : bonne base diversifiée "
                       "et peu coûteuse."))

    crypto = par_classe.get("Crypto", 0)
    if crypto > 0.10:
        note -= 2
        rem.append((-1, f"Les cryptomonnaies pèsent {crypto * 100:.0f} %. Elles ont déjà perdu 70 à 80 % plusieurs "
                        "fois : on conseille généralement de ne pas dépasser 5 à 10 %."))
    elif crypto > 0:
        rem.append((0, f"Crypto : {crypto * 100:.0f} %, une part limitée, c'est raisonnable."))

    secteurs = lignes[lignes["Classe"] == "Actions"].groupby("Secteur")["Montant"].sum() / total
    secteurs = secteurs.drop(labels=["", "Inconnu"], errors="ignore")
    if len(secteurs) and secteurs.max() > 0.35:
        note -= 1.5
        rem.append((-1, f"Le secteur **{secteurs.idxmax()}** représente {secteurs.max() * 100:.0f} % du portefeuille. "
                        "Un choc sur ce secteur toucherait beaucoup de tes lignes en même temps."))

    if rendements is not None and rendements.shape[1] >= 2:
        corr = rendements.corr().values
        moy = corr[np.triu_indices_from(corr, 1)].mean()
        if moy > 0.7:
            note -= 1.5
            rem.append((-1, f"Tes lignes évoluent presque toutes ensemble (corrélation moyenne {moy:.2f}). "
                            "Elles ne se protègent pas entre elles quand le marché baisse."))
        elif moy < 0.4:
            rem.append((1, f"Tes lignes évoluent assez différemment les unes des autres (corrélation moyenne "
                           f"{moy:.2f}) : c'est le principe même de la diversification."))

    if par_classe.get("Obligations", 0) == 0 and par_classe.get("Or", 0) == 0:
        rem.append((0, "Aucune obligation ni or : rien n'amortit les baisses de la bourse. Ça peut convenir "
                       "à un profil dynamique avec un long horizon et une épargne de précaution à côté."))
    if len(lignes) == 1:
        note -= 3
        rem.append((-1, "Une seule ligne : tout dépend d'un seul actif."))
    return max(0.0, min(10.0, note)), rem


# --------------------------------------------------------------------- Sauvegarde
FICHIER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "mon_portefeuille.json")
EXEMPLE = [{"Symbole": "CW8.PA", "Montant": 4000.0}, {"Symbole": "MC.PA", "Montant": 1500.0},
           {"Symbole": "AI.PA", "Montant": 1000.0}, {"Symbole": "TTE.PA", "Montant": 800.0},
           {"Symbole": "BTC-EUR", "Montant": 500.0}]


def charger_portefeuille() -> list[dict]:
    try:
        with open(FICHIER, encoding="utf-8") as f:
            data = json.load(f)
        return [d for d in data if d.get("Symbole")]
    except Exception:
        return list(EXEMPLE)


def enregistrer_portefeuille(lignes: list[dict]) -> None:
    with open(FICHIER, "w", encoding="utf-8") as f:
        json.dump(lignes, f, ensure_ascii=False, indent=2)
