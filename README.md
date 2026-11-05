# Bourse — aide à l'analyse des marchés

Application web (Python + Streamlit) qui s'ouvre dans ton navigateur.

## Ce qu'elle fait
- **Analyse** : graphique en chandeliers, moyennes mobiles 20/50/200, bandes de Bollinger, volume, RSI, MACD.
- **Score des signaux** de −100 à +100, avec l'explication de chaque signal en français.
- **Gestion du risque** : stop et objectif indicatifs basés sur la volatilité (ATR), calcul de taille de position.
- **Backtest** : teste 4 stratégies simples sur l'historique et compare-les à « acheter et garder » (frais inclus).
- **Liste de suivi** : classe plusieurs actions/cryptos selon leur score.
- Sources : Yahoo Finance (actions du monde entier, ETF, indices, crypto, or, devises), fichier CSV, ou données de démo.

## Installation (une seule fois)
1. Installe Python 3.10 ou plus récent : https://www.python.org/downloads/ (sous Windows, coche « Add Python to PATH »).
2. Ouvre un terminal dans ce dossier et tape :
   ```
   pip install -r requirements.txt
   ```

## Lancement
- Windows : double-clique sur `lancer.bat`
- Mac / Linux : `./lancer.sh` (ou `streamlit run app.py`)

Le navigateur s'ouvre sur http://localhost:8501.

## Symboles Yahoo Finance
`AAPL` (Apple), `MC.PA` (LVMH, Paris = `.PA`), `^FCHI` (CAC 40), `BTC-EUR` (Bitcoin), `CW8.PA` (ETF World), `GC=F` (or).
Cherche un symbole sur https://finance.yahoo.com.

## Structure
- `app.py` — l'interface
- `analyse/indicateurs.py` — calcul des indicateurs
- `analyse/signaux.py` — règles de signaux, score, risque
- `analyse/backtest.py` — tests de stratégies
- `analyse/donnees.py` — chargement des cours

> ⚠️ Outil d'aide à la réflexion uniquement, ce n'est pas un conseil en investissement.
> Les performances passées ne préjugent pas des performances futures.
