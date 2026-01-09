# Documentation Technique - PatternCal

## 📝 Présentation
**PatternCal** est une application Streamlit conçue pour transformer des données brutes d'agenda (fichiers `.ics` ou Google Calendar) en rapports facturables et en factures PDF. Elle permet l'extraction intelligente d'informations via des expressions régulières (Regex), l'enrichissement de données via Google Sheets, et la génération de documents via Google Docs/Drive.

## 🏗 Architecture Télésurveillée

### 1. Structure du Projet
```text
PatternCal/
├── app.py              # Point d'entrée principal (UI Streamlit & Orchestration)
├── oauth.py            # Gestion de l'authentification Google OAuth
├── utils.py            # Logique métier (Parsing ICS, Regex, Calculs)
├── invoice.py          # Module Facturation (Google Docs & Drive API)
├── sheets.py           # Module Enrichissement (Google Sheets API)
├── translations.py     # Dictionnaire de traduction (FR/EN/ES)
├── requirements.txt    # Dépendances Python
└── .streamlit/
    └── secrets.toml    # Configuration & Secrets (Google OAuth)
```

### 2. Flux de Données
1.  **Entrée** : API Google Calendar (`oauth.py`).
2.  **Traitement** : Extraction des événements (`get_events_from_calendar`).
3.  **Filtrage & Transformation** :
    *   Application des Regex définies par l'utilisateur (`utils.extraire_informations_agenda`).
    *   Calcul des durées et formatage des dates.
4.  **Enrichissement (Optionnel)** :
    *   Lecture d'une Google Sheet (`sheets.py`).
    *   Fusion ("Left Join") avec les données de l'agenda sur une colonne commune.
5.  **Sortie** :
    *   Visualisation Pandas (Streamlit).
    *   Génération de Factures PDF (`invoice.py`).

## 🧩 Modules Détaillés

### `app.py`
Le cœur de l'application. Il gère :
*   L'état de la session (`st.session_state`) : stockage des événements bruts, des configurations Regex, des credentials.
*   L'interface utilisateur (Tabs, Sidebars, Inputs).
*   L'intégration de tous les sous-modules pour former le pipeline complet.

### `oauth.py`
Gère l'authentification OAuth 2.0 avec Google.
*   **Scopes** :
    *   `calendar.readonly` : Lecture des agendas.
    *   `drive` : Création de dossiers et fichiers (PDF).
    *   `documents` : Édition du template de facture.
    *   `spreadsheets.readonly` : Lecture pour enrichissement.
*   **Flow** : Utilise `google_auth_oauthlib`. Gère le cas local (`client_secret.json`) et Cloud (`st.secrets`).

### `utils.py`
Contient la logique pure, sans dépendance directe forte à l'UI.
*   `parse_ics()` : Lit un fichier binaire ICS et renvoie une liste de dicts standardisés.
*   `extraire_informations_agenda()` :
    *   Prend les événements et une config Regex.
    *   Applique les regex sur les titres (`summary`).
    *   Gère les types (Nombre/Texte) et les conversions.
    *   Retourne un `pd.DataFrame`.

### `invoice.py`
Moteur de génération de factures.
*   **Principe** : Copie un template Google Doc, remplace des balises, exporte en PDF.
*   **Tags Dynamiques** :
    *   Accepte un dictionnaire de données arbitraire.
    *   Pour chaque clé `KEY`, cherche et remplace `{{KEY}}` dans le Doc.
    *   Exemple : Colonne "Adresse" -> Tag `{{Adresse}}`.

### `sheets.py`
Interface avec l'API Google Sheets.
*   `get_sheet_data()` : Récupère les données d'une plage (A:Z) et les convertit en DataFrame pandas propre.

## 🔑 Configuration (.streamlit/secrets.toml)
Fichier critique (non versionné) contenant les identifiants OAuth.
```toml
[google_oauth]
client_id = "..."
client_secret = "..."
project_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
redirect_uri = "http://localhost:8501" # ou URL de prod
```

## 🚀 Guide Développeur
*   **Ajout d'une fonctionnalité API** :
    1.  Ajouter le scope dans `oauth.py` (`SCOPES`).
    2.  Demander à l'utilisateur de se reconnecter.
    3.  Créer un module dédié (ex: `gmail.py`) pour la logique.
    4.  Intégrer dans `app.py`.
*   **Modification des Règles Regex** :
    *   Géré dans l'état Streamlit (`st.session_state.regex_config`).
    *   Structure : `[{"name": "Client", "pattern": "...", "type": "text"}, ...]`.
