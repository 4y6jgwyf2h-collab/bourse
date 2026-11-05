"""Inflation officielle (indice des prix harmonisé IPCH) depuis l'API publique d'Eurostat.

Jeu de données : PRC_HICP_MINR (ECOICOP 2, depuis 2026), unité RCH_A = taux annuel en %.
Repli sur l'ancien jeu PRC_HICP_MANR si le nouveau ne répond pas.
"""
import json
import urllib.parse
import urllib.request

import pandas as pd

BASE = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
ZONES = {"FR": "France", "EA": "Zone euro", "DE": "Allemagne", "ES": "Espagne", "IT": "Italie"}


def _get(dataset: str, params: list[tuple[str, str]]) -> dict:
    url = BASE + dataset + "?" + urllib.parse.urlencode([("format", "JSON"), ("lang", "fr")] + params)
    req = urllib.request.Request(url, headers={"User-Agent": "bourse-app"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def _vers_tableau(js: dict) -> pd.DataFrame:
    """Convertit une réponse JSON-stat Eurostat en tableau (lignes = mois, colonnes = zones)."""
    ids, tailles = js["id"], js["size"]
    pas = [1] * len(ids)
    for i in range(len(ids) - 2, -1, -1):
        pas[i] = pas[i + 1] * tailles[i + 1]
    dims = {d: js["dimension"][d]["category"]["index"] for d in ids}
    ig, it = ids.index("geo"), ids.index("time")
    lignes = {}
    for cle, val in js.get("value", {}).items():
        k = int(cle)
        pos = [(k // pas[i]) % tailles[i] for i in range(len(ids))]
        # On garde la première modalité des autres dimensions (une seule demandée)
        if any(pos[i] != 0 for i in range(len(ids)) if i not in (ig, it)):
            continue
        geo = next(c for c, j in dims["geo"].items() if j == pos[ig])
        temps = next(c for c, j in dims["time"].items() if j == pos[it])
        lignes.setdefault(temps, {})[geo] = val
    df = pd.DataFrame.from_dict(lignes, orient="index").sort_index()
    df.index = pd.PeriodIndex(df.index, freq="M").to_timestamp()
    return df


def charger_inflation(depuis: str = "2015-01") -> pd.DataFrame:
    """Taux d'inflation annuel (%) par mois et par zone. Lève une exception si Eurostat est injoignable."""
    geos = [("geo", g) for g in ZONES]
    try:
        js = _get("prc_hicp_minr", geos + [("unit", "RCH_A"), ("coicop18", "TOTAL"),
                                           ("sinceTimePeriod", depuis)])
        df = _vers_tableau(js)
        if not df.empty:
            return df.rename(columns=ZONES)
    except Exception:
        pass
    js = _get("prc_hicp_manr", geos + [("coicop", "CP00"), ("sinceTimePeriod", depuis)])
    return _vers_tableau(js).rename(columns=ZONES)


def commentaire(taux: float) -> str:
    if taux < 0:
        return "Les prix baissent (déflation) : rare, souvent signe d'une économie en panne."
    if taux < 1:
        return "Inflation très faible, sous l'objectif de 2 % de la Banque centrale européenne."
    if taux <= 2.5:
        return "Inflation proche de l'objectif de 2 % de la Banque centrale européenne : situation normale."
    if taux <= 4:
        return ("Inflation au-dessus de l'objectif de 2 % : l'argent qui dort perd de sa valeur, "
                "et la BCE peut maintenir des taux d'intérêt élevés.")
    return ("Inflation forte : un livret rapporte souvent moins que la hausse des prix. "
            "Les actions et l'immobilier protègent mieux sur le long terme, les obligations à taux fixe moins bien.")
