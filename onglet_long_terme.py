"""Onglet « Long terme » de l'appli Bourse."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from analyse import inflation as inf
from analyse import long_terme as lt

VERT, ROUGE, GRIS, BLEU = "#1a9850", "#d73027", "#9e9e9e", "#2962ff"


def _pct(x, d=1, signe=True):
    if x is None or pd.isna(x):
        return "—"
    return f"{x * 100:+.{d}f} %" if signe else f"{x * 100:.{d}f} %"


def _eur(x):
    return f"{x:,.0f} €".replace(",", " ")


def _couleur_note(n):
    return GRIS if n is None else VERT if n >= 6.5 else "#66bd63" if n >= 5.5 else "#888888" if n >= 4.5 else ROUGE


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def inflation_cache():
    try:
        return inf.charger_inflation()
    except Exception:
        return None


def afficher(symbole: str, source: str, charger, infos_brutes):
    st.write("Pour investir sur plusieurs années, la question n'est pas « est-ce que ça monte demain » mais "
             "« est-ce une bonne entreprise, à un prix raisonnable, et est-ce que je peux supporter les baisses ». "
             "Cet onglet t'aide à y réfléchir.")

    # ------------------------------------------------ Données longues
    try:
        with st.spinner("Chargement de l'historique long…"):
            if source == "Yahoo Finance":
                hist = charger("yahoo", symbole, "max", "1d")
                info = infos_brutes(symbole)
            elif source.startswith("Démo"):
                hist = charger("demo_long", symbole, "max", "1d")
                info = lt.infos_demo()
            else:
                hist, info = None, {}
    except Exception as e:
        st.error(f"Impossible de charger l'historique long : {e}")
        return
    if hist is None:
        st.info("L'onglet long terme a besoin de Yahoo Finance (ou du mode démo) pour récupérer plusieurs années "
                "d'historique et les chiffres de l'entreprise.")
        return
    close = hist["Close"]

    sec1, sec2, sec3, sec4 = st.tabs(["🏢 Santé de l'entreprise", "📜 Historique long",
                                      "📅 Investir chaque mois", "🎯 Projeter mon épargne"])
    infl_df = inflation_cache()

    # ------------------------------------------------ 1. Fondamentaux
    with sec1:
        if source.startswith("Démo"):
            st.caption("Mode démo : chiffres d'une entreprise fictive, pour montrer le fonctionnement.")
        if not info:
            st.warning("Yahoo Finance n'a renvoyé aucune information sur cet actif.")
        elif not lt.est_entreprise(info):
            type_ = (info.get("quoteType") or "").upper()
            noms = {"ETF": "un ETF (fonds indiciel)", "INDEX": "un indice", "CRYPTOCURRENCY": "une cryptomonnaie",
                    "MUTUALFUND": "un fonds", "FUTURE": "une matière première", "CURRENCY": "une devise"}
            st.info(f"Cet actif est {noms.get(type_, 'autre chose qu’une action')} : il n'y a pas de bénéfices "
                    "ou de dette à analyser comme pour une entreprise.")
            if type_ in ("ETF", "MUTUALFUND"):
                frais = lt._f(info, "netExpenseRatio", "annualReportExpenseRatio")
                if frais is not None:
                    frais = frais / 100 if frais > 0.05 else frais
                    st.metric("Frais annuels du fonds", _pct(frais, 2, signe=False))
                    st.write("Des frais faibles (sous 0,3 %) comptent énormément sur 20 ans : 1 % de frais en trop "
                             "peut coûter près de 20 % du capital final.")
                if info.get("category"):
                    st.write(f"Catégorie : **{info['category']}**")
                st.write("Un ETF large (monde, S&P 500, Europe) est souvent la base d'un portefeuille long terme : "
                         "diversifié d'un coup, frais bas, pas besoin de choisir les entreprises.")
            elif type_ == "CRYPTOCURRENCY":
                st.write("Les cryptomonnaies ne produisent ni bénéfices ni dividendes : leur prix dépend uniquement de "
                         "l'offre et de la demande. Leur volatilité est très forte (baisses de 70 à 80 % déjà vues "
                         "plusieurs fois). Si tu en détiens, garde-les à une petite part de ton patrimoine.")
        else:
            crit = lt.note_fondamentale(info)
            notes = lt.notes_par_pilier(crit)
            if not crit:
                st.warning("Pas assez de chiffres disponibles pour noter cette entreprise.")
            else:
                cols = st.columns(len(lt.PILIERS) + 1)
                g = notes["Globale"]
                cols[0].markdown(
                    f"<div style='font-size:.85rem;opacity:.7'>Note globale</div>"
                    f"<div style='font-size:2rem;font-weight:700;color:{_couleur_note(g)}'>"
                    f"{'—' if g is None else f'{g:.1f}'}<span style='font-size:1rem'> / 10</span></div>",
                    unsafe_allow_html=True)
                for col, p in zip(cols[1:], lt.PILIERS):
                    n = notes[p]
                    col.markdown(
                        f"<div style='font-size:.85rem;opacity:.7'>{p}</div>"
                        f"<div style='font-size:1.4rem;font-weight:600;color:{_couleur_note(n)}'>"
                        f"{'—' if n is None else f'{n:.1f}'}</div>", unsafe_allow_html=True)
                st.caption("Note sur 10 par thème, 5 = dans la moyenne. Le dividende n'entre pas dans la note "
                           "globale : une entreprise peut être excellente sans en verser.")

                forts = [c for c in crit if c.vote > 0]
                faibles = [c for c in crit if c.vote < 0]
                a, b = st.columns(2)
                with a:
                    st.subheader("Points forts")
                    for c in forts:
                        st.markdown(f"🟢 **{c.nom}** ({c.valeur}) : {c.explication}")
                    if not forts:
                        st.write("Aucun point fort net d'après ces chiffres.")
                with b:
                    st.subheader("Points de vigilance")
                    for c in faibles:
                        st.markdown(f"🔴 **{c.nom}** ({c.valeur}) : {c.explication}")
                    if not faibles:
                        st.write("Aucun point faible net d'après ces chiffres.")
                neutres = [c for c in crit if c.vote == 0]
                if neutres:
                    with st.expander("Critères dans la moyenne"):
                        for c in neutres:
                            st.markdown(f"⚪ **{c.nom}** ({c.valeur}) : {c.explication}")
                st.caption("Ces chiffres viennent de Yahoo Finance et portent sur les 12 derniers mois. Ils ne disent "
                           "rien de l'avenir du secteur, de la concurrence ou de la qualité des dirigeants : "
                           "lis aussi le rapport annuel de l'entreprise avant de décider.")

    # ------------------------------------------------ 2. Historique long
    with sec2:
        if len(close) < 250:
            st.warning("Moins d'un an d'historique : pas assez pour juger sur le long terme.")
        else:
            h = lt.historique_long(close)
            st.caption(f"Historique du {close.index[0]:%d/%m/%Y} au {close.index[-1]:%d/%m/%Y}"
                       + (" · cours ajustés des dividendes réinvestis" if source == "Yahoo Finance" else ""))
            cols = st.columns(len(h["cagr"]))
            for col, (k, v) in zip(cols, h["cagr"].items()):
                col.metric(f"Par an, {k.lower()}", _pct(v))
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Pire baisse", _pct(h["drawdown"], 0))
            c2.metric("Temps pour s'en remettre",
                      "pas encore remonté" if h["recuperation_ans"] is None else f"{h['recuperation_ans']:.1f} ans")
            c3.metric("Périodes de 5 ans gagnantes",
                      "—" if h["pct_5ans_gagnants"] is None else f"{h['pct_5ans_gagnants'] * 100:.0f} %")
            c4.metric("Pire période de 5 ans", _pct(h["pire_5ans"], 0))
            st.write(f"La pire baisse a eu lieu entre le {h['date_pic']:%d/%m/%Y} et le {h['date_creux']:%d/%m/%Y}. "
                     f"Demande-toi honnêtement : si ton placement perdait {abs(h['drawdown']) * 100:.0f} %, "
                     "est-ce que tu tiendrais sans vendre ?")

            fig = go.Figure(go.Scatter(x=close.index, y=close, line=dict(color=BLEU, width=1.4), name="Cours"))
            fig.update_layout(height=320, yaxis_type="log", yaxis_title="Cours (échelle logarithmique)",
                              margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig, width="stretch")

            an = h["annees"]
            fig2 = go.Figure(go.Bar(x=an.index.astype(str), y=an * 100,
                                    marker_color=[VERT if v >= 0 else ROUGE for v in an],
                                    text=[f"{v * 100:+.0f}%" for v in an], textposition="outside"))
            fig2.update_layout(height=300, yaxis_title="Performance de l'année (%)", margin=dict(l=10, r=10, t=10, b=10))
            st.subheader("Année par année")
            st.plotly_chart(fig2, width="stretch")
            n_neg = int((an < 0).sum())
            st.write(f"{n_neg} année(s) négative(s) sur {len(an)}. Les mauvaises années font partie du parcours : "
                     "sur le long terme, c'est la durée de détention qui réduit le risque de perdre de l'argent.")

    # ------------------------------------------------ 3. DCA
    with sec3:
        st.write("Investir la même somme chaque mois, quel que soit le cours, évite d'avoir à choisir le « bon moment » "
                 "et lisse le prix d'achat. Voici ce que ça aurait donné sur cet actif, avec les vrais cours passés.")
        ans_dispo = max(1, int((close.index[-1] - close.index[0]).days / 365.25))
        a, b, c = st.columns(3)
        mens = a.number_input("Somme investie chaque mois (€)", 10, 100_000, 200, 10, key="dca_m")
        duree = b.slider("Depuis combien d'années", 1, min(ans_dispo, 30), min(10, ans_dispo), key="dca_d")
        frais = c.number_input("Frais par achat (%)", 0.0, 5.0, 0.5, 0.1, key="dca_f")
        debut = close.index[-1] - pd.DateOffset(years=duree)
        try:
            r = lt.simuler_dca(close, mens, debut, frais)
        except ValueError as e:
            st.warning(str(e))
        else:
            k = st.columns(4)
            k[0].metric("Total versé", _eur(r["verse"]), f"{r['nb_mois']} mois")
            k[1].metric("Valeur aujourd'hui", _eur(r["valeur"]), _pct(r["valeur"] / r["verse"] - 1))
            k[2].metric("Rendement annuel équivalent", _pct(r["taux_annuel"]))
            k[3].metric("Pire moment (en cours de route)", _pct(r["pire_moment"], 0))
            courbe = r["courbe"]
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=courbe.index, y=courbe["Valeur du portefeuille"], name="Valeur du portefeuille",
                                     line=dict(color=BLEU, width=2)))
            fig.add_trace(go.Scatter(x=courbe.index, y=courbe["Total versé"], name="Total versé",
                                     line=dict(color=GRIS, width=1.5, dash="dash")))
            fig.update_layout(height=360, yaxis_title="€", hovermode="x unified",
                              margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h", y=1.08))
            st.plotly_chart(fig, width="stretch")
            diff = r["valeur_unique"] - r["valeur"]
            st.write(f"À titre de comparaison, investir les {_eur(r['verse'])} d'un coup au départ aurait donné "
                     f"**{_eur(r['valeur_unique'])}** ({'plus' if diff > 0 else 'moins'} que l'investissement mensuel). "
                     "Quand le marché monte, tout investir tôt gagne souvent ; l'investissement mensuel, lui, "
                     "réduit le risque d'avoir tout acheté juste avant une chute, et reste plus facile à tenir.")

    # ------------------------------------------------ 4. Projection
    with sec4:
        st.write("Combien pourrait valoir ton épargne dans X années ? Personne ne connaît le rendement futur, "
                 "donc on regarde trois scénarios.")
        auto_t = lt.taux_depuis_historique(close)
        a, b, c = st.columns(3)
        cap = a.number_input("Capital de départ (€)", 0, 10_000_000, 1_000, 500, key="pj_c")
        mens = b.number_input("Versement mensuel (€)", 0, 100_000, 200, 10, key="pj_m")
        annees = c.slider("Durée (années)", 1, 40, 20, key="pj_a")
        a, b = st.columns(2)
        options = (["Rendement passé de cet actif"] if auto_t else []) + ["Je choisis mon taux"]
        mode_t = a.radio("Taux de rendement utilisé", options, key="pj_mode", horizontal=True)
        infl = b.slider("Inflation annuelle moyenne (%)", 0.0, 6.0, 2.0, 0.5, key="pj_i",
                        help="Sur 20 ans, l'inflation moyenne en zone euro tourne autour de 2 %, "
                             "même si elle peut être bien plus haute certaines années.") / 100
        if infl_df is not None and "France" in infl_df:
            fr = infl_df["France"].dropna()
            b.caption(f"Inflation actuelle en France : {fr.iloc[-1]:.1f} % ({fr.index[-1]:%m/%Y}), "
                      "détails dans l'espace 🌍 Économie.")
        if mode_t == "Je choisis mon taux":
            central = st.slider("Rendement annuel central (%)", 0.0, 12.0, 6.0, 0.5, key="pj_t",
                                help="Ordre de grandeur historique d'un ETF actions monde : 6 à 8 % par an avant "
                                     "inflation. Un livret rapporte 2 à 3 %.") / 100
            scen = {"Pessimiste": max(central - 0.03, 0.0), "Central": central, "Optimiste": central + 0.03}
        else:
            central = auto_t["central"]
            scen = {"Pessimiste": auto_t["pessimiste"], "Central": central, "Optimiste": auto_t["optimiste"]}
            msg = f"Taux central : {_pct(auto_t['brut'])} par an, le rendement moyen de cet actif sur les {auto_t['libelle']}."
            if auto_t["plafonne"]:
                msg += (f" C'est exceptionnel, et un tel rythme dure rarement : la projection le plafonne à "
                        f"{central * 100:.0f} % par an pour rester réaliste.")
            st.info(msg + " " + auto_t["methode"])
        projs = {k: lt.projeter(cap, mens, annees, t, infl) for k, t in scen.items()}
        k = st.columns(4)
        verse = projs["Central"]["Versé"].iloc[-1]
        k[0].metric("Total versé", _eur(verse))
        for col, (nom, t) in zip(k[1:], scen.items()):
            fin = projs[nom].iloc[-1]
            reel = _eur(fin["Valeur en euros d'aujourd'hui"])
            col.metric(f"{nom} ({t * 100:.1f} %/an)", _eur(fin["Valeur"]),
                       f"soit {reel} d'aujourd'hui", delta_color="off")
        fig = go.Figure()
        for nom, col_ in zip(scen, [ROUGE, BLEU, VERT]):
            fig.add_trace(go.Scatter(x=projs[nom].index, y=projs[nom]["Valeur"], name=nom, line=dict(color=col_, width=2)))
        fig.add_trace(go.Scatter(x=projs["Central"].index, y=projs["Central"]["Versé"], name="Versé",
                                 line=dict(color=GRIS, dash="dash")))
        fig.update_layout(height=360, xaxis_title="Années", yaxis_title="€", hovermode="x unified",
                          margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h", y=1.08))
        st.plotly_chart(fig, width="stretch")
        interets = projs["Central"]["Valeur"].iloc[-1] - verse
        st.write(f"Dans le scénario central, les intérêts composés rapportent **{_eur(interets)}** de plus que "
                 "ce que tu as versé. Plus tu commences tôt, plus cet effet est fort.")

    with st.expander("✅ Les bases de l'investissement long terme"):
        st.markdown("""
- **Épargne de précaution d'abord** : garde 3 à 6 mois de dépenses sur un livret avant d'investir en bourse.
- **Horizon** : n'investis en actions que l'argent dont tu n'auras pas besoin avant 5 à 8 ans minimum.
- **Diversifie** : un ETF monde contient des milliers d'entreprises. Une seule action peut perdre 90 %.
- **Surveille les frais** : sur 20 ans, 1 % de frais annuels en plus peut coûter environ 20 % du capital final.
- **Enveloppe fiscale** : en France, le PEA et l'assurance-vie réduisent les impôts sur les gains après quelques années.
- **Investis régulièrement** et ne vends pas en panique pendant les baisses : c'est souvent là que se perdent les gains.
- **Ne mets pas tous tes œufs dans la crypto ou une seule action**, même si elles ont beaucoup monté.
""")
    st.caption("Aide à la réflexion uniquement, pas un conseil en investissement. Les performances passées ne "
               "préjugent pas des performances futures.")
