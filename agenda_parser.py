import streamlit as st
import pandas as pd
import re
import numpy as np

# --- Configuration de la page Streamlit ---
st.set_page_config(page_title="Parseur d'Agenda", layout="wide")

def extraire_informations_agenda(
    titres: list[str], 
    regex_client_str: str, 
    regex_montant_str: str, 
    regex_duree_str: str
) -> pd.DataFrame:
    """
    Analyse les titres d'événements avec les Regex fournies par l'utilisateur
    et retourne un DataFrame.
    """
    
    # Valider et compiler les Regex en direct, avec gestion d'erreurs
    try:
        regex_client = re.compile(regex_client_str)
    except re.error as e:
        st.error(f"Erreur dans la Regex 'client': {e}")
        return pd.DataFrame() # Retourne un DF vide en cas d'erreur

    try:
        regex_montant = re.compile(regex_montant_str, re.IGNORECASE)
    except re.error as e:
        st.error(f"Erreur dans la Regex 'montant': {e}")
        return pd.DataFrame()

    try:
        regex_duree = re.compile(regex_duree_str, re.IGNORECASE)
    except re.error as e:
        st.error(f"Erreur dans la Regex 'durée': {e}")
        return pd.DataFrame()

    donnees_extraites = []

    for titre in titres:
        match_client = regex_client.search(titre)
        match_montant = regex_montant.search(titre)
        match_duree = regex_duree.search(titre)

        client = match_client.group(1).strip() if match_client else None
        
        if match_montant:
            # Assurer que le groupe de capture existe avant de l'utiliser
            montant_str = match_montant.group(1).replace(',', '.') if match_montant.groups() else ""
            montant = float(montant_str) if montant_str else np.nan
        else:
            montant = np.nan

        duree = match_duree.group(1) if match_duree and match_duree.groups() else None

        donnees_extraites.append({
            "titre_original": titre,
            "client": client,
            "montant_eur": montant,
            "duree": duree
        })

    df = pd.DataFrame(donnees_extraites)
    return df[["titre_original", "client", "montant_eur", "duree"]]

# --- Interface Utilisateur Streamlit ---

st.title("📄 Parseur d'Événements d'Agenda")
st.write("Collez vos titres d'événements, ajustez les expressions régulières (Regex) et visualisez les résultats en temps réel.")

# --- Données par défaut ---
donnees_agenda_defaut = (
    "Coaching PNL avec Jean Dupont pour 150€ (1h30)\n"
    "Session de design (2h) - Marie Curie - 250 EUR\n"
    "Consultation 90min avec Martin Durand pour 120,50€\n"
    "Réunion interne de projet (pas de client)\n"
    "Facturation Luc Martin pour 80€\n"
    "Appel de suivi (30min) avec Sophie Leroy\n"
    "Atelier Créativité - 450€ - 4h - Collectif Artistes"
)

# Regex par défaut
regex_client_defaut = r"([A-ZÀ-ÿ][a-zà-ÿ]+(?:[\s-][A-ZÀ-ÿ][a-zà-ÿ]+)+)"
regex_montant_defaut = r"(\d+([.,]\d{1,2})?)\s?(?:€|EUR)"
regex_duree_defaut = r"(\d{1,2}h\d{0,2}|\d+min)"


# --- Zones de saisie ---

col1, col2 = st.columns(2)

with col1:
    st.subheader("1. Vos événements")
    titres_input = st.text_area(
        "Un événement par ligne", 
        donnees_agenda_defaut, 
        height=250,
        help="Collez ici la liste des titres de vos événements, avec un événement par ligne."
    )

with col2:
    st.subheader("2. Vos Expressions Régulières")
    regex_client_input = st.text_input("Regex pour 'Client'", regex_client_defaut, help="Capture le nom du client. Le groupe de capture 1 doit être le nom.")
    regex_montant_input = st.text_input("Regex pour 'Montant'", regex_montant_defaut, help="Capture la valeur numérique du montant. Le groupe de capture 1 doit être le nombre.")
    regex_duree_input = st.text_input("Regex pour 'Durée'", regex_duree_defaut, help="Capture la durée. Ex: '1h30', '90min'. Le groupe de capture 1 doit être la durée.")


# --- Logique et Affichage des résultats ---

st.divider()
st.subheader("3. Tableau des résultats")

if titres_input:
    # Convertit le bloc de texte en une liste de chaînes non vides
    liste_titres = [ligne for ligne in titres_input.strip().split('\n') if ligne]
    
    if liste_titres:
        df_resultats = extraire_informations_agenda(
            liste_titres, 
            regex_client_input, 
            regex_montant_input, 
            regex_duree_input
        )
        
        st.dataframe(df_resultats, use_container_width=True)
    else:
        st.warning("La zone de texte des événements est vide.")
else:
    st.info("Veuillez saisir des événements dans la zone de texte ci-dessus pour voir les résultats.")