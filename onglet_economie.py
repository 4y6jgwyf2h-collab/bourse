"""Espace « Économie » : indicateurs qui ne dépendent pas d'un actif (inflation…)."""
import plotly.graph_objects as go
import streamlit as st

from onglet_long_terme import BLEU, GRIS, ROUGE, VERT, _eur, inflation_cache
from analyse import inflation as inf


def afficher():
    infl_df = inflation_cache()
    st.subheader("🏷️ Inflation")
    if infl_df is None or infl_df.empty:
        st.warning("Impossible de joindre Eurostat pour récupérer l'inflation. Vérifie ta connexion internet.")
    else:
        st.write("L'inflation, c'est la hausse moyenne des prix sur un an. Un placement ne t'enrichit vraiment "
                 "que s'il rapporte plus que l'inflation.")
        derniers = {z: infl_df[z].dropna() for z in infl_df.columns if infl_df[z].notna().any()}
        cols = st.columns(len(derniers))
        for col, (z, serie) in zip(cols, derniers.items()):
            avant = serie.iloc[-2] if len(serie) > 1 else None
            col.metric(f"{z} ({serie.index[-1]:%m/%Y})", f"{serie.iloc[-1]:.1f} %",
                       None if avant is None else f"{serie.iloc[-1] - avant:+.1f} pt sur un mois",
                       delta_color="inverse")
        if "France" in derniers:
            fr = derniers["France"]
            st.info(inf.commentaire(fr.iloc[-1]))
            livret = 1.7
            reel = livret - fr.iloc[-1]
            st.write(f"Exemple : avec un livret à {livret:.1f} % et une inflation de {fr.iloc[-1]:.1f} %, "
                     f"ton pouvoir d'achat {'baisse' if reel < 0 else 'augmente'} d'environ {abs(reel):.1f} % par an. "
                     f"Sur 10 ans, à ce rythme, 10 000 € placés auraient le pouvoir d'achat de "
                     f"{_eur(10000 * (1 + reel / 100) ** 10)} d'aujourd'hui.")
        fig = go.Figure()
        couleurs = [BLEU, "#ff6d00", GRIS, "#7e57c2", VERT]
        for (z, serie), c in zip(derniers.items(), couleurs):
            fig.add_trace(go.Scatter(x=serie.index, y=serie, name=z,
                                     line=dict(color=c, width=2.4 if z == "France" else 1.2)))
        fig.add_hline(y=2, line_dash="dash", line_color=ROUGE, annotation_text="objectif BCE 2 %",
                      annotation_position="top left")
        fig.update_layout(height=380, yaxis_title="Inflation sur un an (%)", hovermode="x unified",
                          margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h", y=1.08))
        st.plotly_chart(fig, width="stretch")
        st.caption("Source : Eurostat, indice des prix à la consommation harmonisé (IPCH), taux annuel. "
                   "Publié chaque mois, avec environ 2 à 4 semaines de décalage.")

