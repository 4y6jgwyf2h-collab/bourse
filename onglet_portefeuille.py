"""Onglet « Portefeuille » : construire une répartition adaptée à son profil, puis analyser son portefeuille."""
import json
import os

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from analyse import donnees
from analyse import portefeuille as pf


def _pct(x, d=1, signe=True):
    if x is None or pd.isna(x):
        return "—"
    return f"{x * 100:+.{d}f} %" if signe else f"{x * 100:.{d}f} %"


def _eur(x):
    return f"{x:,.0f} €".replace(",", " ")


def _camembert(labels, valeurs, couleurs=None, titre=""):
    fig = go.Figure(go.Pie(labels=labels, values=valeurs, hole=0.55, sort=False,
                           marker=dict(colors=couleurs), textinfo="percent", textposition="inside"))
    fig.update_layout(height=320, margin=dict(l=10, r=10, t=30, b=10), title=titre,
                      legend=dict(orientation="v", x=1, y=0.5))
    return fig


def _prix(source, charger, symbole, i=0):
    if source.startswith("Démo"):
        return donnees.donnees_demo(jours=1300, graine=100 + i, vol=0.008 + 0.004 * (i % 4),
                                    derive_moy=0.0002 + 0.0001 * (i % 3))["Close"]
    return charger("yahoo", symbole, "5y", "1d")["Close"]


def afficher(source: str, charger, infos_brutes, rechercher=None):
    st.write("Un bon portefeuille, ce n'est pas trouver « la » bonne action : c'est une répartition adaptée à "
             "ton horizon et à ta capacité à supporter les baisses, que tu peux tenir pendant des années.")
    construire, analyser = st.tabs(["🧭 Construire mon portefeuille", "🔍 Analyser mon portefeuille"])

    # ================================================= Construire
    with construire:
        st.subheader("1. Ton profil d'investisseur")
        precaution = st.radio("As-tu déjà une épargne de précaution (3 à 6 mois de dépenses sur un livret) ?",
                              ["Oui", "Non"], horizontal=True, key="pf_prec")
        if precaution == "Non":
            st.warning("Commence par là : mets de côté 3 à 6 mois de dépenses sur un livret disponible à tout moment. "
                       "Sinon, une dépense imprévue pourrait t'obliger à vendre tes placements au pire moment.")
        reponses = {}
        cols = st.columns(2)
        for i, (cle, (question, choix)) in enumerate(pf.QUESTIONS.items()):
            rep = cols[i % 2].radio(question, choix, index=min(2, len(choix) - 1), key=f"pf_q_{cle}")
            reponses[cle] = choix.index(rep)
        nom_profil = pf.profil(reponses)
        st.success(f"**Profil {nom_profil}** : {pf.PROFILS[nom_profil]}")
        autre = st.selectbox("Tu peux aussi choisir un autre profil pour comparer", list(pf.PROFILS),
                             index=list(pf.PROFILS).index(nom_profil), key="pf_profil")

        st.subheader("2. La répartition suggérée")
        montant = st.number_input("Montant à investir (€)", 100, 10_000_000, 10_000, 500, key="pf_montant")
        rep = pf.repartition(autre, montant)
        g, d = st.columns([2, 3])
        g.plotly_chart(_camembert(rep["Classe d'actifs"], rep["Part (%)"],
                                  [pf.COULEURS[c] for c in rep["Classe d'actifs"]]), width="stretch")
        aff = rep.copy()
        aff["Montant (€)"] = aff["Montant (€)"].map(_eur)
        aff["Part (%)"] = aff["Part (%)"].map(lambda x: f"{x} %")
        d.dataframe(aff, hide_index=True, width="stretch")
        d.caption("Les supports cités sont des exemples courants, pas des recommandations. Compare les frais "
                  "et vérifie leur éligibilité à ton enveloppe (PEA, assurance-vie, compte-titres).")

        st.subheader("3. Ce que cette répartition aurait donné")
        alloc = pf.ALLOCATIONS[autre]
        poids = {k: v / 100 for k, v in alloc.items() if v > 0}
        prix, manquants = {}, []
        with st.spinner("Simulation sur les 5 dernières années…"):
            for i, k in enumerate(poids):
                sym = pf.SUPPORTS[k][1]
                if sym is None:
                    continue
                try:
                    prix[k] = _prix(source, charger, sym, i)
                except Exception:
                    manquants.append(k)
        if prix:
            ref = next(iter(prix.values()))
            if "Épargne sécurisée" in poids:
                prix["Épargne sécurisée"] = pd.Series(1.0, index=ref.index)
            for k in manquants:
                poids.pop(k, None)
            try:
                courbe = pf.simuler(prix, poids, {"Épargne sécurisée": pf.TAUX_SECURISE})
                st_ = pf.stats_courbe(courbe)
                k = st.columns(4)
                k[0].metric("Performance annualisée", _pct(st_["Performance annualisée"]))
                k[1].metric("Performance totale", _pct(st_["Performance totale"]))
                k[2].metric("Pire baisse en cours de route", _pct(st_["Pire baisse"], 0))
                k[3].metric("Volatilité", _pct(st_["Volatilité"], 0, signe=False))
                fig = go.Figure(go.Scatter(x=courbe.index, y=courbe / 100 * montant, line=dict(color="#2962ff", width=2),
                                           name=f"Profil {autre}"))
                fig.add_hline(y=montant, line_dash="dash", line_color="grey")
                fig.update_layout(height=320, yaxis_title="€", margin=dict(l=10, r=10, t=10, b=10))
                st.plotly_chart(fig, width="stretch")
                st.caption(f"Simulation sur {st_['Années simulées']:.1f} ans, rééquilibrée chaque mois, avec "
                           f"{pf.TAUX_SECURISE * 100:.0f} %/an pour l'épargne sécurisée"
                           + (f". Données indisponibles pour : {', '.join(manquants)}." if manquants else ".")
                           + (" Mode démo : cours fictifs." if source.startswith("Démo") else ""))
            except Exception as e:
                st.warning(f"Simulation impossible : {e}")
        else:
            st.info("Simulation indisponible : les cours des ETF n'ont pas pu être chargés.")

        with st.expander("Les règles d'or pour tenir ton portefeuille dans le temps"):
            st.markdown("""
- **Investis régulièrement** (chaque mois) plutôt que d'attendre le « bon moment ».
- **Rééquilibre une fois par an** : si les actions ont beaucoup monté et dépassent leur part cible, vends-en un peu pour revenir à ta répartition. C'est une façon automatique de vendre cher et d'acheter bon marché.
- **Ne change pas de profil après une baisse** : c'est exactement le moment où il ne faut pas vendre.
- **Choisis la bonne enveloppe** : PEA (actions européennes et ETF éligibles, avantage fiscal après 5 ans), assurance-vie (fonds euros + ETF, avantage après 8 ans), compte-titres (tout, mais plus imposé).
- **Fais attention aux frais** : un ETF coûte 0,1 à 0,4 % par an, beaucoup de fonds classiques 1,5 à 2 %.
""")

    # ================================================= Analyser
    with analyser:
        st.write("Ajoute tes placements actuels avec le sélecteur ci-dessous, puis ajuste les montants directement "
                 "dans le tableau si besoin.")
        local = os.environ.get("BOURSE_LOCAL") == "1"  # appli lancée sur l'ordinateur (pas le site web)
        if "pf_lignes" not in st.session_state:
            st.session_state.pf_lignes = pf.charger_portefeuille() if local else list(pf.EXEMPLE)
            st.session_state.pf_noms = {l_["Symbole"]: l_["Nom"] for l_ in st.session_state.pf_lignes if l_.get("Nom")}
        if not local:
            fichier = st.file_uploader("Reprendre un portefeuille enregistré (fichier .json)", type=["json"],
                                       key="pf_import")
            if fichier is not None and st.session_state.get("pf_import_nom") != fichier.name + str(fichier.size):
                try:
                    data = json.loads(fichier.getvalue().decode("utf-8"))
                    st.session_state.pf_lignes = [{"Symbole": d["Symbole"], "Montant": float(d["Montant"])}
                                                  for d in data if d.get("Symbole")]
                    st.session_state.pf_import_nom = fichier.name + str(fichier.size)
                    st.session_state.pop("pf_editeur", None)
                    st.session_state.pop("pf_resultat", None)
                    st.rerun()
                except Exception as e:
                    st.error(f"Fichier illisible : {e}")
        noms = {sym: nom for nom, sym in donnees.EXEMPLES.items()}
        noms.update(st.session_state.get("pf_noms", {}))
        depart = pd.DataFrame(st.session_state.pf_lignes, columns=["Symbole", "Montant"])
        depart.insert(0, "Nom", depart["Symbole"].map(lambda x: noms.get(str(x).upper(), "")))
        table = st.data_editor(
            depart, num_rows="dynamic", width="stretch", key="pf_editeur", hide_index=True,
            column_config={"Nom": st.column_config.TextColumn("Placement", disabled=True),
                           "Symbole": st.column_config.TextColumn("Symbole", required=True),
                           "Montant": st.column_config.NumberColumn("Montant actuel (€)", min_value=0.0,
                                                                    step=100.0, format="%.0f €")})
        table = table[["Symbole", "Montant"]].dropna(subset=["Symbole"])
        table["Symbole"] = table["Symbole"].astype(str).str.strip().str.upper()
        table = table[(table["Symbole"] != "") & (table["Montant"].fillna(0) > 0)]
        st.caption("Pour supprimer une ligne : coche-la à gauche puis appuie sur Suppr, ou mets son montant à 0.")

        with st.container(border=True):
            st.markdown("**➕ Ajouter un placement**")
            mode = st.radio("Comment le trouver", ["Dans la liste", "Recherche par nom"], horizontal=True,
                            key="pf_add_mode", label_visibility="collapsed")
            a, b, c, d = st.columns([2, 3, 1.5, 1], vertical_alignment="bottom")
            choix_sym, choix_nom = None, None
            if mode == "Dans la liste":
                cat = a.selectbox("Catégorie", list(donnees.CATALOGUE), index=list(donnees.CATALOGUE).index("ETF"),
                                  key="pf_add_cat")
                nom = b.selectbox("Placement", list(donnees.CATALOGUE[cat]), key="pf_add_nom")
                choix_sym, choix_nom = donnees.CATALOGUE[cat][nom], nom
            else:
                texte = a.text_input("Nom", placeholder="ex. Michelin, Amundi…", key="pf_add_txt")
                res = rechercher(texte) if (rechercher and len(texte.strip()) >= 2) else []
                if res:
                    r = b.selectbox("Résultats", res, key="pf_add_res",
                                    format_func=lambda q: f"{q['nom']} · {q['symbole']} · {q['place']}")
                    choix_sym, choix_nom = r["symbole"], r["nom"]
                else:
                    b.selectbox("Résultats", ["Tape au moins 2 lettres" if len(texte.strip()) < 2 else "Aucun résultat"],
                                disabled=True, key="pf_add_vide")
            montant_aj = c.number_input("Montant (€)", 0.0, 1e9, 1000.0, 100.0, key="pf_add_mt")
            if d.button("Ajouter", key="pf_add_btn", disabled=choix_sym is None, width="stretch"):
                lignes_act = table.to_dict("records")
                for l_ in lignes_act:
                    if l_["Symbole"] == choix_sym:
                        l_["Montant"] = float(l_["Montant"]) + montant_aj
                        break
                else:
                    lignes_act.append({"Symbole": choix_sym, "Montant": montant_aj})
                st.session_state.pf_lignes = lignes_act
                st.session_state.setdefault("pf_noms", {})[choix_sym] = choix_nom
                st.session_state.pop("pf_editeur", None)
                st.toast(f"{choix_nom} ajouté")
                st.rerun()

        b1, b2, _ = st.columns([1, 1, 3])
        if local:
            if b1.button("💾 Enregistrer", key="pf_save"):
                st.session_state.pf_lignes = table.to_dict("records")
                try:
                    pf.enregistrer_portefeuille([{**l_, "Nom": noms.get(l_["Symbole"], "")}
                                                 for l_ in st.session_state.pf_lignes])
                    st.toast("Portefeuille enregistré")
                except Exception as e:
                    st.error(f"Enregistrement impossible : {e}")
        else:
            b1.download_button("💾 Télécharger", json.dumps(table.to_dict("records"), ensure_ascii=False, indent=2),
                               file_name="mon_portefeuille.json", mime="application/json", key="pf_dl",
                               help="Ton portefeuille reste privé : il n'est pas stocké sur le site. "
                                    "Garde ce fichier et recharge-le la prochaine fois.")
        lancer = b2.button("Analyser", type="primary", key="pf_go")
        if not lancer and "pf_resultat" not in st.session_state:
            st.caption("Clique sur « Analyser » pour lancer le diagnostic.")
            return
        if table.empty:
            st.warning("Ajoute au moins une ligne avec un symbole et un montant.")
            return
        if lancer:
            lignes, prix = [], {}
            barre = st.progress(0.0, "Chargement des données…")
            for i, (sym, mt) in enumerate(zip(table["Symbole"], table["Montant"])):
                info = {} if source.startswith("Démo") else (infos_brutes(sym) or {})
                if source.startswith("Démo"):
                    info = {"quoteType": "CRYPTOCURRENCY" if sym.endswith("-EUR") else
                            "ETF" if sym in ("CW8.PA", "EWLD.PA", "IWDA.AS") else "EQUITY",
                            "sector": ["Consumer Cyclical", "Basic Materials", "Energy", "Technology"][i % 4]}
                lignes.append({"Symbole": sym, "Nom": info.get("longName") or info.get("shortName") or sym,
                               "Montant": float(mt), "Classe": pf.classer(info, sym),
                               "Secteur": info.get("sector") or ""})
                try:
                    prix[sym] = _prix(source, charger, sym, i)
                except Exception:
                    pass
                barre.progress((i + 1) / len(table), "Chargement des données…")
            barre.empty()
            st.session_state.pf_resultat = (pd.DataFrame(lignes), prix)
        lignes, prix = st.session_state.pf_resultat

        total = lignes["Montant"].sum()
        rendements = None
        if len(prix) >= 2:
            dfp = pd.DataFrame({k: v for k, v in prix.items()})
            dfp.index = pd.to_datetime(dfp.index).normalize()
            dfp = dfp[~dfp.index.duplicated()].ffill()
            rendements = dfp.resample("W").last().pct_change().dropna(how="all")
        note, remarques = pf.diagnostic(lignes, rendements)

        k = st.columns(4)
        coul = "#1a9850" if note >= 7 else "#f2a900" if note >= 4.5 else "#d73027"
        k[0].markdown(f"<div style='font-size:.85rem;opacity:.7'>Diversification</div>"
                      f"<div style='font-size:2rem;font-weight:700;color:{coul}'>{note:.1f}"
                      f"<span style='font-size:1rem'> / 10</span></div>", unsafe_allow_html=True)
        k[1].metric("Valeur totale", _eur(total))
        k[2].metric("Nombre de lignes", len(lignes))
        poids = dict(zip(lignes["Symbole"], lignes["Montant"] / total))
        courbe = None
        try:
            courbe = pf.simuler(prix, {s: w for s, w in poids.items() if s in prix})
            k[3].metric("Performance annualisée (sur la période)", _pct(pf.stats_courbe(courbe)["Performance annualisée"]))
        except Exception:
            k[3].metric("Performance annualisée", "—")

        g, d = st.columns(2)
        g.plotly_chart(_camembert(lignes["Symbole"], lignes["Montant"], titre="Par ligne"), width="stretch")
        cl = lignes.groupby("Classe")["Montant"].sum()
        d.plotly_chart(_camembert(cl.index, cl.values, [pf.COULEURS.get(c, "#bab0ac") for c in cl.index],
                                  titre="Par type d'actif"), width="stretch")

        st.subheader("Diagnostic")
        for grav, texte in sorted(remarques, key=lambda x: x[0]):
            st.markdown(f"{ {-1: '🔴', 0: '🟠', 1: '🟢'}[grav] } {texte}")
        if not remarques:
            st.write("Rien de particulier à signaler.")

        if courbe is not None:
            st_ = pf.stats_courbe(courbe)
            st.subheader("Si tu avais eu ce portefeuille ces dernières années")
            fig = go.Figure(go.Scatter(x=courbe.index, y=courbe / 100 * total, line=dict(color="#2962ff", width=2)))
            fig.update_layout(height=300, yaxis_title="€", margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig, width="stretch")
            st.caption(f"Avec la répartition actuelle, rééquilibrée chaque mois, sur {st_['Années simulées']:.1f} ans : "
                       f"pire baisse {_pct(st_['Pire baisse'], 0)}, volatilité {_pct(st_['Volatilité'], 0, False)} par an. "
                       "Les cours sont dans la devise de chaque actif (pas de conversion en euros).")

        if rendements is not None:
            with st.expander("Corrélations entre tes lignes"):
                c = rendements.corr()
                fig = go.Figure(go.Heatmap(z=c.values, x=c.columns, y=c.index, zmin=-1, zmax=1,
                                           colorscale="RdBu_r", text=np.round(c.values, 2), texttemplate="%{text}"))
                fig.update_layout(height=380, margin=dict(l=10, r=10, t=10, b=10))
                st.plotly_chart(fig, width="stretch")
                st.caption("1 = évoluent exactement ensemble, 0 = aucun lien, −1 = en sens opposé. "
                           "Des lignes peu corrélées se compensent quand l'une baisse.")

        with st.expander("Comparer à la répartition de mon profil"):
            cible = st.selectbox("Profil", list(pf.PROFILS), index=1, key="pf_cmp")
            alloc = pf.ALLOCATIONS[cible]
            correspondance = {"Actions": "Actions monde", "ETF actions": "Actions monde", "Obligations": "Obligations",
                              "Or": "Or", "Crypto": "Crypto"}
            actuel = {}
            for c_, v in cl.items():
                cle = correspondance.get(c_, "Autre")
                actuel[cle] = actuel.get(cle, 0) + v / total * 100
            actuel_cmp = {k: actuel.get(k, 0) for k in ["Actions monde", "Obligations", "Or", "Crypto"]}
            cible_cmp = {"Actions monde": alloc["Actions monde"] + alloc["Actions émergentes"],
                         "Obligations": alloc["Obligations"], "Or": alloc["Or"], "Crypto": alloc["Crypto"]}
            comp = pd.DataFrame({"Actuel (%)": actuel_cmp, "Cible (%)": cible_cmp}).round(0)
            comp["Écart"] = comp["Actuel (%)"] - comp["Cible (%)"]
            st.dataframe(comp, width="stretch")
            st.caption(f"La cible du profil {cible} prévoit aussi {alloc['Épargne sécurisée']} % d'épargne sécurisée "
                       "(livrets, fonds euros), que tu détiens peut-être en dehors de ce portefeuille.")
