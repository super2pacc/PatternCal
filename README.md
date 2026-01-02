# PatternCal - SaaS Agenda Parser

Application web permettant de convertir des exports d'agenda (`.ics`) ou de se connecter directement à un Google Agenda vira URL privée pour générer des rapports de facturation (CSV/Excel).

## Fonctionnalités
- **Import Flexible** : Upload de fichier `.ics` ou lien iCal privé.
- **Filtrage** : Sélection de la période d'analyse.
- **Extraction Intelligente** : Configuration de règles Regex pour extraire Client, Montant, Projet, etc.
- **Rapports** : 
    - Vue détaillée ligne par ligne.
    - Vue synthétique groupée par Client.
- **Exports** : Téléchargement en CSV ou Excel.

## Installation

```bash
python -m venv .venv
source .venv/Scripts/activate  # Sur Windows
pip install -r requirements.txt
```

## Lancement

```bash
streamlit run app.py
```
