"""Bourse — aide à l'analyse des marchés.

Lancer avec :  streamlit run app.py
Outil pédagogique d'aide à la réflexion : ce n'est pas un conseil en investissement.
"""
import datetime as dt

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from analyse import backtest, donnees, indicateurs, signaux
import onglet_long_terme
import onglet_economie
import onglet_portefeuille

st.set_page_config(page_title="Bourse — analyse", page_icon="📈", layout="wide")

AVERTISSEMENT = ("⚠️ Outil d'aide à l'analyse uniquement. Les signaux sont calculés mécaniquement "
                 "à partir des cours passés et ne constituent pas un conseil en investissement. "
                 "Les performances passées ne préjugent pas des performances futures.")


def pct(x):
    return "—" if pd.isna(x) else f"{x * 100:+.1f} %"


@st.cache_data(ttl=900, show_spinner=False)
def charger(source, symbole, periode, intervalle):
    if source == "demo":
        return donnees.donnees_demo()
    if source == "demo_long":
        return donnees.donnees_demo(jours=3900, graine=19, vol=0.011, derive_moy=0.0004)
    return donnees.charger_yahoo(symbole, periode, intervalle)


@st.cache_data(ttl=20, show_spinner=False)
def charger_rapide(symbole, periode, intervalle):
    """Version à durée de cache courte, pour l'intraday et l'actualisation automatique."""
    return donnees.charger_yahoo(symbole, periode, intervalle)


@st.cache_data(ttl=10, show_spinner=False)
def prix_direct(symbole):
    return donnees.prix_direct(symbole)


@st.cache_data(ttl=3600, show_spinner=False)
def rechercher(texte):
    return donnees.rechercher(texte)


@st.cache_data(ttl=3600, show_spinner=False)
def infos(symbole):
    return donnees.infos_yahoo(symbole)


@st.cache_data(ttl=3600, show_spinner=False)
def infos_brutes(symbole):
    return donnees.infos_brutes(symbole)


# ---------------------------------------------------------------- Barre latérale
with st.sidebar:
    st.header("📈 Bourse")
    espace = st.radio("Espace", ["📈 Analyser un actif", "💼 Mon portefeuille", "🌍 Économie"],
                      label_visibility="collapsed")
    st.divider()
    sources = ["Yahoo Finance", "Fichier CSV", "Démo (hors ligne)"] if espace.startswith("📈") \
        else ["Yahoo Finance", "Démo (hors ligne)"]
    source = st.radio("Source des données", sources)
    symbole, df_brut = None, None
    periode, intervalle = "2y", "1d"
    auto, delai = False, 60

    if not espace.startswith("📈"):
        pass
    elif source == "Yahoo Finance":
        mode = st.radio("Choisir l'actif", ["Liste", "Recherche par nom", "Symbole"], horizontal=True)
        if mode == "Liste":
            cat = st.selectbox("Catégorie", list(donnees.CATALOGUE))
            nom_actif = st.selectbox("Actif", list(donnees.CATALOGUE[cat]))
            symbole = donnees.CATALOGUE[cat][nom_actif]
        elif mode == "Recherche par nom":
            texte = st.text_input("Nom de l'entreprise, de l'indice…", "Michelin")
            resultats = rechercher(texte) if len(texte.strip()) >= 2 else []
            if resultats:
                r = st.selectbox("Résultats", resultats,
                                 format_func=lambda q: f"{q['nom']} · {q['symbole']} · {q['place']} {q['type']}")
                symbole = r["symbole"]
            else:
                st.caption("Aucun résultat pour l'instant.")
                symbole = "AAPL"
        else:
            symbole = st.text_input("Symbole Yahoo", "AAPL",
                                    help="Ex. AAPL, MC.PA (Paris), BTC-EUR, ^FCHI. "
                                         "Cherche le symbole sur finance.yahoo.com.").strip().upper()
        unite = st.selectbox("Unité de temps (une bougie =)", list(donnees.UNITES), index=4)
        intervalle, periodes = donnees.UNITES[unite]
        defaut_p = {"1m": "1d", "5m": "5d", "15m": "5d", "1h": "1mo", "1d": "2y", "1wk": "5y", "1mo": "max"}[intervalle]
        periode = st.selectbox("Historique chargé", periodes, index=periodes.index(defaut_p),
                               format_func=donnees.NOMS_PERIODES.get)
        auto = st.toggle("Actualisation automatique", value=intervalle in ("1m", "5m", "15m"))
        delai = st.select_slider("Toutes les", [15, 30, 60, 120, 300], value=60,
                                 format_func=lambda x: f"{x} s" if x < 60 else f"{x // 60} min",
                                 disabled=not auto)
        if st.button("🔄 Actualiser maintenant"):
            charger_rapide.clear()
            charger.clear()
    elif source == "Fichier CSV":
        f = st.file_uploader("CSV (Date, Open, High, Low, Close, Volume)", type=["csv", "txt"])
        if f:
            try:
                df_brut = donnees.charger_csv(f)
                symbole = f.name.rsplit(".", 1)[0]
            except Exception as e:
                st.error(f"Lecture impossible : {e}")
    else:
        symbole = "DEMO"

    aff_moy, aff_bb, mult_atr = ["sma50", "sma200"], True, 2.0
    if espace.startswith("📈"):
        st.divider()
        st.subheader("Affichage")
        aff_moy = st.multiselect("Moyennes mobiles", ["sma20", "sma50", "sma200"], default=["sma50", "sma200"])
        aff_bb = st.checkbox("Bandes de Bollinger", True)
        mult_atr = st.slider("Stop = cours − N × ATR", 1.0, 4.0, 2.0, 0.5)
    st.caption(AVERTISSEMENT)

# ---------------------------------------------------------------- Espaces sans actif
if espace.startswith("💼"):
    st.title("💼 Mon portefeuille")
    onglet_portefeuille.afficher(source, charger, infos_brutes, rechercher)
    st.stop()
if espace.startswith("🌍"):
    st.title("🌍 Économie")
    onglet_economie.afficher()
    st.stop()

def page():
    brut = df_brut  # données CSV éventuelles (None sinon)
    # ---------------------------------------------------------------- Chargement
    if source == "Fichier CSV" and brut is None:
        st.info("Charge un fichier CSV dans la barre de gauche pour commencer.")
        return

    if brut is None:
        try:
            with st.spinner(f"Téléchargement de {symbole}…"):
                if source.startswith("Démo"):
                    brut = charger("demo", symbole, periode, intervalle)
                elif auto or intervalle in ("1m", "5m", "15m", "1h"):
                    brut = charger_rapide(symbole, periode, intervalle)
                else:
                    brut = charger("yahoo", symbole, periode, intervalle)
        except Exception as e:
            st.error(f"Impossible de récupérer les données : {e}")
            return

    if len(brut) < 30:
        st.warning("Moins de 30 bougies : choisis un historique plus long pour que les indicateurs aient du sens.")

    df = indicateurs.ajouter_indicateurs(brut)
    liste = signaux.analyser(df)
    sc = signaux.score(liste)
    libelle, couleur = signaux.verdict(sc)
    dern = df.iloc[-1]
    var_jour = dern["Close"] / df["Close"].iloc[-2] - 1 if len(df) > 1 else 0

    info = infos(symbole) if source == "Yahoo Finance" else {}
    titre = info.get("Nom", symbole)
    st.title(titre)
    fmt_date = "%d/%m/%Y %H:%M" if intervalle in ("1m", "5m", "15m", "1h") else "%d/%m/%Y"
    direct = prix_direct(symbole) if source == "Yahoo Finance" else {}
    ligne = f"{symbole} · dernière bougie : {df.index[-1]:{fmt_date}}"
    if "Devise" in info:
        ligne += f" · devise : {info['Devise']}"
    if direct:
        var = direct["prix"] / direct["veille"] - 1 if direct.get("veille") else 0
        ligne += (f" · **dernier prix : {direct['prix']:,.2f} ({var * 100:+.2f} % sur la journée)**"
                  f" · mis à jour à {dt.datetime.now():%H:%M:%S}")
    if auto:
        ligne += f" · 🔄 actualisation toutes les {delai} s"
    st.caption(ligne)

    onglet_analyse, onglet_lt, onglet_bt, onglet_liste, onglet_aide = st.tabs(
        ["🔎 Analyse", "🌱 Long terme", "🧪 Backtest", "📋 Liste de suivi", "❓ Comprendre les indicateurs"])

    with onglet_lt:
        onglet_long_terme.afficher(symbole, source, charger, infos_brutes)

    # ---------------------------------------------------------------- Analyse
    with onglet_analyse:
        k = st.columns(5)
        k[0].metric("Dernier cours", f"{dern['Close']:.2f}", pct(var_jour))
        k[1].metric("Score des signaux", f"{sc:+d} / 100")
        k[2].markdown(f"<div style='padding-top:.6rem'>Lecture technique<br>"
                      f"<span style='font-size:1.4rem;font-weight:700;color:{couleur}'>{libelle}</span></div>",
                      unsafe_allow_html=True)
        k[3].metric("RSI (14)", "—" if pd.isna(dern["rsi"]) else f"{dern['rsi']:.0f}")
        niv = signaux.niveaux_risque(df, mult_atr)
        k[4].metric("Volatilité (ATR)", f"{niv['atr_pct']:.1f} %" if niv else "—")

        # Graphique principal
        fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.03,
                            row_heights=[0.55, 0.15, 0.15, 0.15],
                            subplot_titles=("", "Volume", "RSI", "MACD"))
        fig.add_trace(go.Candlestick(x=df.index, open=df["Open"], high=df["High"], low=df["Low"],
                                     close=df["Close"], name="Cours",
                                     increasing_line_color="#26a69a", decreasing_line_color="#ef5350"), 1, 1)
        couleurs_moy = {"sma20": "#f2a900", "sma50": "#2962ff", "sma200": "#9c27b0"}
        for m in aff_moy:
            fig.add_trace(go.Scatter(x=df.index, y=df[m], name=m.upper().replace("SMA", "MM "),
                                     line=dict(width=1.4, color=couleurs_moy[m])), 1, 1)
        if aff_bb:
            fig.add_trace(go.Scatter(x=df.index, y=df["bb_haut"], name="Bollinger haut",
                                     line=dict(width=0.8, color="rgba(120,120,120,.6)")), 1, 1)
            fig.add_trace(go.Scatter(x=df.index, y=df["bb_bas"], name="Bollinger bas", fill="tonexty",
                                     fillcolor="rgba(120,120,120,.08)",
                                     line=dict(width=0.8, color="rgba(120,120,120,.6)")), 1, 1)
        if niv:
            fig.add_hline(y=niv["stop"], line_dash="dot", line_color="#d73027", row=1, col=1,
                          annotation_text="stop indicatif", annotation_position="bottom right")
        coul_vol = ["#26a69a" if c >= o else "#ef5350" for c, o in zip(df["Close"], df["Open"])]
        fig.add_trace(go.Bar(x=df.index, y=df["Volume"], marker_color=coul_vol, name="Volume",
                             showlegend=False), 2, 1)
        fig.add_trace(go.Scatter(x=df.index, y=df["rsi"], name="RSI", line=dict(color="#7e57c2", width=1.2),
                                 showlegend=False), 3, 1)
        for y in (30, 70):
            fig.add_hline(y=y, line_dash="dash", line_color="grey", line_width=0.8, row=3, col=1)
        fig.add_trace(go.Bar(x=df.index, y=df["macd_hist"], name="Histogramme",
                             marker_color=["#26a69a" if v >= 0 else "#ef5350" for v in df["macd_hist"].fillna(0)],
                             showlegend=False), 4, 1)
        fig.add_trace(go.Scatter(x=df.index, y=df["macd"], name="MACD", line=dict(color="#2962ff", width=1.2),
                                 showlegend=False), 4, 1)
        fig.add_trace(go.Scatter(x=df.index, y=df["macd_signal"], name="Signal",
                                 line=dict(color="#ff6d00", width=1.2), showlegend=False), 4, 1)
        fig.update_layout(height=880, margin=dict(l=10, r=10, t=60, b=10), dragmode="pan",
                          legend=dict(orientation="h", y=1.06, x=0.35), hovermode="x unified")
        # Barre de défilement sous le graphique + boutons de zoom rapide
        fig.update_xaxes(rangeslider_visible=False)
        fig.update_xaxes(rangeslider=dict(visible=True, thickness=0.06), row=4, col=1)
        if intervalle in ("1m", "5m", "15m", "1h"):
            boutons = [dict(count=1, label="1 h", step="hour", stepmode="backward"),
                       dict(count=6, label="6 h", step="hour", stepmode="backward"),
                       dict(count=1, label="1 j", step="day", stepmode="backward"),
                       dict(count=5, label="5 j", step="day", stepmode="backward")]
        else:
            boutons = [dict(count=1, label="1 m", step="month", stepmode="backward"),
                       dict(count=3, label="3 m", step="month", stepmode="backward"),
                       dict(count=6, label="6 m", step="month", stepmode="backward"),
                       dict(count=1, label="1 an", step="year", stepmode="backward"),
                       dict(count=5, label="5 ans", step="year", stepmode="backward")]
        fig.update_xaxes(rangeselector=dict(buttons=boutons + [dict(step="all", label="Tout")], x=0, y=1.06),
                         row=1, col=1)
        fig.update_yaxes(fixedrange=False)
        est_24h = symbole.endswith(("-EUR", "-USD")) or symbole.endswith("=X")
        if source == "Yahoo Finance" and not est_24h and intervalle in ("1d", "1m", "5m", "15m", "1h"):
            coupures = [dict(bounds=["sat", "mon"])]
            if intervalle != "1d":
                h = df.index.hour + df.index.minute / 60
                pas = {"1m": 1 / 60, "5m": 5 / 60, "15m": 0.25, "1h": 1}[intervalle]
                if h.max() + pas - h.min() < 23:
                    coupures.append(dict(bounds=[float(h.max() + pas), float(h.min())], pattern="hour"))
            fig.update_xaxes(rangebreaks=coupures)
        st.plotly_chart(fig, width="stretch", config={"scrollZoom": True, "displaylogo": False})
        st.caption("Astuce : fais glisser le graphique pour avancer ou reculer, utilise la molette pour zoomer, "
                   "ou déplace la petite barre en bas. Double-clic pour revenir à la vue complète.")

        gauche, droite = st.columns([3, 2])
        with gauche:
            st.subheader("Pourquoi ce score ?")
            for s in liste:
                icone = {2: "🟢🟢", 1: "🟢", 0: "⚪", -1: "🔴", -2: "🔴🔴"}[s.vote]
                st.markdown(f"{icone} **{s.famille}** — {s.explication}")
            if not liste:
                st.write("Pas assez d'historique pour calculer les signaux.")
        with droite:
            st.subheader("Gestion du risque")
            if niv:
                st.markdown(
                    f"- **Stop indicatif** : {niv['stop']:.2f} ({(niv['stop'] / dern['Close'] - 1) * 100:.1f} %)\n"
                    f"- **Objectif indicatif** (ratio 1:2) : {niv['objectif']:.2f} "
                    f"({(niv['objectif'] / dern['Close'] - 1) * 100:+.1f} %)\n"
                    f"- Calculés à partir de l'ATR ({mult_atr} × {dern['atr']:.2f})."
                )
                with st.expander("Calculer une taille de position"):
                    capital = st.number_input("Capital (€)", 100.0, 1e9, 10_000.0, 500.0)
                    risque = st.slider("Risque maximum par position (% du capital)", 0.25, 5.0, 1.0, 0.25)
                    perte_unit = dern["Close"] - niv["stop"]
                    nb = int(capital * risque / 100 / perte_unit) if perte_unit > 0 else 0
                    nb = min(nb, int(capital / dern["Close"]))
                    st.write(f"➡️ **{nb} titres** (≈ {nb * dern['Close']:,.0f} €). "
                             f"Si le stop est touché, la perte serait d'environ {nb * perte_unit:,.0f} €.")
            st.subheader("Statistiques")
            stats = signaux.statistiques(df)
            st.table(pd.DataFrame({"Valeur": {k_: pct(v) for k_, v in stats.items()}}))
            if info:
                st.subheader("Fondamentaux")
                lignes = {}
                for k_, v in info.items():
                    if k_ == "Nom":
                        continue
                    if k_ == "Capitalisation":
                        v = f"{v / 1e9:,.1f} Md"
                    elif k_ == "Rendement dividende":
                        v = f"{v:.2f} %" if v > 1 else f"{v * 100:.2f} %"
                    elif isinstance(v, float):
                        v = f"{v:,.2f}"
                    lignes[k_] = str(v)
                st.table(pd.DataFrame({"Valeur": lignes}))

    # ---------------------------------------------------------------- Backtest
    with onglet_bt:
        st.write("Teste une règle simple sur l'historique affiché et compare-la à « acheter et garder ». "
                 "Les décisions sont prises à la clôture et exécutées la séance suivante.")
        c1, c2 = st.columns([2, 1])
        nom = c1.selectbox("Stratégie", list(backtest.STRATEGIES))
        frais = c2.number_input("Frais par ordre (%)", 0.0, 2.0, 0.1, 0.05)
        code = backtest.STRATEGIES[nom]
        params = {}
        if code == "croisement":
            a, b = st.columns(2)
            params["rapide"] = a.number_input("Moyenne rapide", 2, 100, 20)
            params["lente"] = b.number_input("Moyenne lente", 5, 300, 50)
        elif code == "rsi":
            a, b = st.columns(2)
            params["bas"] = a.number_input("Acheter si RSI <", 5, 50, 30)
            params["haut"] = b.number_input("Vendre si RSI >", 50, 95, 70)
        elif code == "score":
            params["seuil"] = st.slider("Investi quand le score dépasse", -50, 80, 15, 5)

        res = backtest.lancer(df, code, frais, **params)
        fig_bt = go.Figure()
        for col, c in zip(res["courbe"].columns, ["#2962ff", "#9e9e9e"]):
            fig_bt.add_trace(go.Scatter(x=res["courbe"].index, y=res["courbe"][col] * 100, name=col,
                                        line=dict(color=c, width=2)))
        fig_bt.update_layout(height=420, yaxis_title="Valeur d'un placement de 100",
                             margin=dict(l=10, r=10, t=30, b=10), hovermode="x unified",
                             legend=dict(orientation="h", y=1.05, x=0))
        st.plotly_chart(fig_bt, width="stretch")

        tab = pd.DataFrame(res["stats"])
        fmt = tab.copy().astype(object)
        for idx in tab.index:
            for col in tab.columns:
                v = tab.loc[idx, col]
                if idx == "Ratio de Sharpe":
                    fmt.loc[idx, col] = "—" if pd.isna(v) else f"{v:.2f}"
                elif idx == "Nombre d'ordres":
                    fmt.loc[idx, col] = f"{int(v)}"
                else:
                    fmt.loc[idx, col] = pct(v)
        st.table(fmt)
        st.caption("Un bon résultat passé peut venir du hasard ou d'un réglage trop ajusté à l'historique. "
                   "Teste plusieurs périodes et plusieurs actifs avant d'en tirer une conclusion.")

    # ---------------------------------------------------------------- Liste de suivi
    with onglet_liste:
        if source != "Yahoo Finance":
            st.info("La liste de suivi utilise Yahoo Finance : choisis cette source dans la barre de gauche.")
        else:
            st.write("Compare rapidement plusieurs actifs selon leur score technique.")
            saisie = st.text_area("Symboles (séparés par des virgules)",
                                  "AAPL, MSFT, NVDA, MC.PA, TTE.PA, AI.PA, BTC-EUR, ^FCHI")
            if st.button("Analyser la liste", type="primary"):
                lignes = []
                barre = st.progress(0.0)
                symboles = [x.strip().upper() for x in saisie.split(",") if x.strip()]
                for i, sym in enumerate(symboles):
                    try:
                        d_ = indicateurs.ajouter_indicateurs(charger("yahoo", sym, "2y", "1d"))
                        sg = signaux.analyser(d_)
                        s_ = signaux.score(sg)
                        stt = signaux.statistiques(d_)
                        lignes.append({"Symbole": sym, "Cours": round(d_["Close"].iloc[-1], 2),
                                       "Score": s_, "Lecture": signaux.verdict(s_)[0],
                                       "RSI": round(d_["rsi"].iloc[-1], 0),
                                       "Perf. 1 mois": stt.get("Perf. 1 mois"),
                                       "Perf. 1 an": stt.get("Perf. 1 an"),
                                       "Volatilité": stt.get("Volatilité annualisée")})
                    except Exception as e:
                        lignes.append({"Symbole": sym, "Lecture": f"Erreur : {e}"})
                    barre.progress((i + 1) / len(symboles))
                barre.empty()
                res_l = pd.DataFrame(lignes).sort_values("Score", ascending=False, na_position="last")
                st.dataframe(
                    res_l, hide_index=True, width="stretch",
                    column_config={
                        "Score": st.column_config.ProgressColumn("Score", min_value=-100, max_value=100, format="%d"),
                        "Perf. 1 mois": st.column_config.NumberColumn(format="percent"),
                        "Perf. 1 an": st.column_config.NumberColumn(format="percent"),
                        "Volatilité": st.column_config.NumberColumn(format="percent"),
                    })

    # ---------------------------------------------------------------- Aide
    with onglet_aide:
        st.markdown("""
**Moyennes mobiles (MM 20 / 50 / 200)** — moyenne des cours sur N séances. Un cours au-dessus de sa
MM 200 indique une tendance de fond haussière. Quand la MM 50 passe au-dessus de la MM 200, on parle de
*croisement doré* ; l'inverse est un *croisement de la mort*.

**RSI (Relative Strength Index)** — oscille entre 0 et 100. Sous 30 : l'actif a beaucoup baissé
récemment (survente). Au-dessus de 70 : il a beaucoup monté (surachat). Dans une forte tendance, le RSI
peut rester longtemps en zone extrême.

**MACD** — différence entre deux moyennes exponentielles (12 et 26). Quand il passe au-dessus de sa ligne
de signal, le momentum devient positif.

**Bandes de Bollinger** — enveloppe à ± 2 écarts-types autour de la MM 20. Un cours hors des bandes
signale un mouvement inhabituel ; des bandes qui se resserrent annoncent souvent un mouvement fort.

**ATR (Average True Range)** — amplitude moyenne d'une séance. Sert à placer un stop cohérent avec la
volatilité de l'actif et à dimensionner une position.

**Score des signaux** — chaque règle vote de −2 à +2 ; le total est ramené entre −100 et +100. C'est un
résumé de ce que disent les indicateurs, pas une prévision.

**Bonnes pratiques** : diversifier, ne risquer qu'une petite part du capital par position, définir sa
sortie avant d'entrer, et ne jamais investir de l'argent dont on a besoin à court terme.
    """)
        st.caption(AVERTISSEMENT)



if auto:
    st.fragment(run_every=delai)(page)()
else:
    page()
