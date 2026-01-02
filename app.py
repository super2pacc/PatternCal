import streamlit as st
import pandas as pd
import re
import numpy as np
import icalendar
from datetime import datetime, timedelta
import io

import requests

# --- Configuration de la page Streamlit ---
st.set_page_config(page_title="Parseur d'Agenda ical", layout="wide", page_icon="📅")

# --- Initialisation Session State ---
if 'regex_config' not in st.session_state:
    st.session_state.regex_config = [
        {"name": "Client", "pattern": r"([A-ZÀ-ÿ][a-zà-ÿ]+(?:[\s-][A-ZÀ-ÿ][a-zà-ÿ]+)+)", "type": "text"},
        {"name": "Montant", "pattern": r"(\d+([.,]\d{1,2})?)\s?(?:€|EUR)", "type": "number"},
    ]

# --- Fonctions ---
def parse_ics(file_content: bytes) -> list[dict]:
    """
    Parse le contenu d'un fichier ICS et retourne une liste de dictionnaires
    contenant les informations brutes des événements.
    """
    try:
        cal = icalendar.Calendar.from_ical(file_content)
    except Exception as e:
        st.error(f"Erreur de lecture du fichier ICS: {e}")
        return []

    events = []

    for component in cal.walk():
        if component.name == "VEVENT":
            summary = str(component.get('summary'))
            dtstart_prop = component.get('dtstart')
            dtend_prop = component.get('dtend')
            
            if not dtstart_prop:
                continue
                
            dtstart = dtstart_prop.dt
            # Certains événements n'ont pas de dtend, on prend dtstart ou on ignore
            if dtend_prop:
                dtend = dtend_prop.dt
            else:
                dtend = dtstart

            # Calcul durée (gestion simplifiée des types dates/datetime)
            # On convertit tout vers datetime si nécessaire pour soustraction, 
            # mais ici on garde simple en checkant les types
            duration = timedelta(0)
            
            # Cas 1: deux datetimes
            if isinstance(dtstart, datetime) and isinstance(dtend, datetime):
                 # Si offset-naive vs offset-aware, on ne peut pas soustraire direct en python pur sans unifier
                 # icalendar parse souvent avec tz info.
                 # On tente la soustraction, si erreur on retire tz
                 try:
                     duration = dtend - dtstart
                 except TypeError:
                     # un des deux est naive, l'autre aware -> on rend tout naive
                     duration = dtend.replace(tzinfo=None) - dtstart.replace(tzinfo=None)

            # Cas 2: deux dates (all day event)
            elif hasattr(dtstart, 'date') and hasattr(dtend, 'date'):
                 # dtend est exclusif, donc diff en jours correcte
                 # mais dtstart/dtend sont des objets 'date' python
                 delta = dtend - dtstart # donne timedelta
                 duration = delta

            events.append({
                "summary": summary,
                "dtstart": dtstart,
                "dtend": dtend,
                "duration": duration
            })
    return events


def extraire_informations_agenda(
    events: list[dict], 
    regex_configs: list[dict]
) -> pd.DataFrame:
    """
    Analyse les 'summary' des événements ICS avec les Regex dynamiques et enrichit les données.
    """
    
    # Compilation des regex
    compiled_regexes = {}
    for config in regex_configs:
        try:
            flag = re.IGNORECASE if config["type"] == "number" else 0 
            compiled_regexes[config["name"]] = {
                "regex": re.compile(config["pattern"], flag),
                "type": config["type"]
            }
        except re.error:
            continue

    donnees_traitees = []

    for event in events:
        titre = event["summary"]
        
        # Base de l'entrée
        entry = {
            "Date": event["dtstart"],
            "Titre": titre,
        }
        
        # Extraction dynamique
        for name, processor in compiled_regexes.items():
            match = processor["regex"].search(titre)
            valeur = None
            
            if match:
                val_str = match.group(1) if match.groups() else match.group(0)
                if processor["type"] == "number":
                    val_str = val_str.replace(',', '.')
                    try:
                        valeur = float(val_str)
                    except ValueError:
                        valeur = np.nan
                else:
                    valeur = val_str.strip()
            
            if processor["type"] == "number" and valeur is None:
                valeur = np.nan
                
            entry[name] = valeur

        # Formatage durée
        duree_td = event["duration"]
        duree_heures = duree_td.total_seconds() / 3600 if isinstance(duree_td, timedelta) else 0.0
        
        # Nettoyage date pour Excel
        dt_start = event["dtstart"]
        if isinstance(dt_start, datetime) and dt_start.tzinfo:
             dt_start = dt_start.replace(tzinfo=None)
        
        entry["Date"] = dt_start
        entry["Durée (h)"] = round(duree_heures, 2)
        
        donnees_traitees.append(entry)

    df = pd.DataFrame(donnees_traitees)
    
    if not df.empty:
        dynamic_cols = [c["name"] for c in regex_configs]
        cols_order = ["Date", "Titre"] + dynamic_cols + ["Durée (h)"]
        final_cols = [c for c in cols_order if c in df.columns]
        return df[final_cols]
        
    return df

# --- Interface Utilisateur Streamlit ---

st.title("📅 Convertisseur Agenda (.ics) vers CSV")
st.markdown("""
Transformez vos exports d'agenda en rapports facturables.
""")

# --- Initialisation Session State ---
if 'regex_config' not in st.session_state:
    st.session_state.regex_config = [
        {"name": "Client", "pattern": r"([A-ZÀ-ÿ][a-zà-ÿ]+(?:[\s-][A-ZÀ-ÿ][a-zà-ÿ]+)+)", "type": "text"},
        {"name": "Montant", "pattern": r"(\d+([.,]\d{1,2})?)\s?(?:€|EUR)", "type": "number"},
    ]

if 'ics_content' not in st.session_state:
    st.session_state.ics_content = None

# ... (Fonctions parse_ics et extraire_informations_agenda inchangées) ...

# --- Zone Principale : Layout ---

# Ligne 1 : Import (Gauche) et Dates (Droite)
col_top_left, col_top_right = st.columns([1, 1], gap="large")

with col_top_left:
    st.subheader("1. Source")
    tab_file, tab_link = st.tabs(["📁 Fichier ICS", "🔗 Lien Privé"])
    
    with tab_file:
        uploaded_file = st.file_uploader("Upload .ics", type="ics", label_visibility="collapsed")
        if uploaded_file is not None:
            # On met à jour le session state seulement si nouveau fichier
            # Note: uploaded_file.getvalue() est plus sûr pour les re-runs
            st.session_state.ics_content = uploaded_file.getvalue()
            
    with tab_link:
        ics_url = st.text_input("URL secrète de l'agenda (iCal)", 
                                placeholder="https://calendar.google.com/...",
                                help="Trouvez ce lien dans les paramètres de votre agenda Google > Intégrer l'agenda > Adresse secrète au format iCal")
        if ics_url:
            if st.button("Charger l'agenda"):
                try:
                    resp = requests.get(ics_url)
                    resp.raise_for_status()
                    st.session_state.ics_content = resp.content
                    st.success("Agenda récupéré avec succès !")
                except Exception as e:
                    st.error(f"Erreur lors de la récupération : {e}")

with col_top_right:
    st.subheader("2. Période d'analyse")
    c_d1, c_d2 = st.columns(2)
    today = datetime.now().date()
    m_1 = today - timedelta(days=30)
    
    with c_d1:
        date_debut = st.date_input("Date de début", value=m_1)
    with c_d2:
        date_fin = st.date_input("Date de fin", value=today)

st.divider()

# Ligne 2 : Règles d'extraction (Centré ou Pleine largeur)
st.subheader("3. Règles d'extraction")
st.info("Configurez ici les informations à extraire des titres de vos événements.")

# Affichage et édition des règles
to_remove = []
# En-têtes pour plus de clarté
h1, h2, h3, h4 = st.columns([2, 3, 1.5, 0.5])
h1.caption("Nom du champ")
h2.caption("Expression Régulière (Regex)")
h3.caption("Type")

for i, config in enumerate(st.session_state.regex_config):
    c1, c2, c3, c4 = st.columns([2, 3, 1.5, 0.5])
    with c1:
        new_name = st.text_input(f"Nom chp {i}", value=config["name"], label_visibility="collapsed", key=f"name_{i}", placeholder="Nom")
        st.session_state.regex_config[i]["name"] = new_name
    with c2:
        new_pattern = st.text_input(f"Regex chp {i}", value=config["pattern"], label_visibility="collapsed", key=f"pattern_{i}", placeholder="Regex pattern")
        st.session_state.regex_config[i]["pattern"] = new_pattern
    with c3:
        new_type = st.selectbox(f"Type chp {i}", options=["text", "number"], index=0 if config["type"]=="text" else 1, label_visibility="collapsed", key=f"type_{i}")
        st.session_state.regex_config[i]["type"] = new_type
    with c4:
        if st.button("🗑️", key=f"del_{i}"):
            to_remove.append(i)

# Suppression des éléments marqués
if to_remove:
    for index in sorted(to_remove, reverse=True):
        del st.session_state.regex_config[index]
    st.rerun()

# Boutons d'action pour regex
b_col1, b_col2 = st.columns([1, 1])
with b_col1:
    if st.button("➕ Ajouter une règle", use_container_width=True):
        st.session_state.regex_config.append({"name": "Nouveau champ", "pattern": "", "type": "text"})
        st.rerun()
with b_col2:
    if st.button("Réinitialiser par défaut", use_container_width=True):
         st.session_state.regex_config = [
            {"name": "Client", "pattern": r"([A-ZÀ-ÿ][a-zà-ÿ]+(?:[\s-][A-ZÀ-ÿ][a-zà-ÿ]+)+)", "type": "text"},
            {"name": "Montant", "pattern": r"(\d+([.,]\d{1,2})?)\s?(?:€|EUR)", "type": "number"},
            {"name": "Projet", "pattern": r"Projet\s*:\s*(\w+)", "type": "text"},
        ]
         st.rerun()

st.divider()

if st.session_state.ics_content is not None:
    # Lecture et parsing
    try:
        raw_events = parse_ics(st.session_state.ics_content)
        
        # Filtrage par date si sélectionné
        events_filtrés = []
        for evt in raw_events:
            # Conversion en date naive pour comparaison (on ignore l'heure et la TZ)
            dt_evt = evt["dtstart"]
            if isinstance(dt_evt, datetime):
                date_evt = dt_evt.date()
            else:
                date_evt = dt_evt
            
            in_range = True
            if date_debut and date_evt < date_debut:
                in_range = False
            if date_fin and date_evt > date_fin:
                in_range = False
            
            if in_range:
                events_filtrés.append(evt)

        st.success(f"{len(events_filtrés)} événements trouvés dans la période (sur {len(raw_events)} total).")
        
        # Extraction intelligente sur les événements filtrés
        df_final = extraire_informations_agenda(
            events_filtrés, 
            st.session_state.regex_config
        )
        
        if not df_final.empty:
            st.subheader("4. Résultats")
            
            tab_detail, tab_synthese = st.tabs(["📄 Détail complet", "📊 Synthèse par Client"])
            
            with tab_detail:
                st.dataframe(df_final, use_container_width=True)
                
                # Zone d'export Détail
                st.write("---")
                col_exp_opt, col_exp_btn = st.columns([1, 2])
                with col_exp_opt:
                    format_export = st.selectbox(
                        "Format d'export", 
                        ["CSV", "Excel (.xlsx)", "Google Sheets (Bientôt)"],
                        label_visibility="collapsed",
                        key="fmt_det"
                    )
                
                with col_exp_btn:
                    if format_export == "CSV":
                        csv = df_final.to_csv(index=False).encode('utf-8')
                        st.download_button(label="📥 Télécharger CSV", data=csv, file_name='events_detail.csv', mime='text/csv')
                    elif format_export == "Excel (.xlsx)":
                        buffer = io.BytesIO()
                        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                            df_final.to_excel(writer, index=False, sheet_name='Détail')
                        st.download_button(label="📥 Télécharger Excel", data=buffer.getvalue(), file_name='events_detail.xlsx', mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                    else:
                        st.button("🚀 Envoyer vers Google Sheets", disabled=True)

            with tab_synthese:
                # Identification de la colonne de regroupement (Client)
                col_client = None
                # On cherche une colonne qui s'appelle Client (ou contient Client)
                candidates = [c for c in df_final.columns if "client" in c.lower()]
                if candidates:
                    col_client = candidates[0]
                elif "Client" in [c["name"] for c in st.session_state.regex_config]:
                     # Si configuré mais pas trouvé
                     col_client = "Client"
                
                if col_client and col_client in df_final.columns:
                    # Agrégation
                    numeric_cols = df_final.select_dtypes(include=[np.number]).columns.tolist()
                    df_grouped = df_final.groupby(col_client)[numeric_cols].sum().reset_index()
                    
                    if "Durée (h)" in df_grouped.columns:
                        df_grouped = df_grouped.sort_values("Durée (h)", ascending=False)
                        
                    st.dataframe(df_grouped, use_container_width=True)
                    
                    # Export Synthèse
                    st.write("---")
                    col_exp_opt_g, col_exp_btn_g = st.columns([1, 2])
                    with col_exp_opt_g:
                         format_export_g = st.selectbox(
                            "Format d'export", 
                            ["CSV", "Excel (.xlsx)", "Google Sheets (Bientôt)"],
                            label_visibility="collapsed",
                            key="fmt_syn"
                        )
                    
                    with col_exp_btn_g:
                        if format_export_g == "CSV":
                            csv_g = df_grouped.to_csv(index=False).encode('utf-8')
                            st.download_button(label="📥 Télécharger CSV", data=csv_g, file_name='synthese_client.csv', mime='text/csv')
                        elif format_export_g == "Excel (.xlsx)":
                            buffer_g = io.BytesIO()
                            with pd.ExcelWriter(buffer_g, engine='openpyxl') as writer:
                                df_grouped.to_excel(writer, index=False, sheet_name='Synthèse')
                            st.download_button(label="📥 Télécharger Excel", data=buffer_g.getvalue(), file_name='synthese_client.xlsx', mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                        else:
                            st.button("🚀 Envoyer vers Google Sheets", disabled=True, key="btn_gs_syn")
                        
                else:
                    st.info("Aucune colonne 'Client' détectée pour le regroupement. Vérifiez vos règles d'extraction.")

            st.divider()
            
            # --- KPI Globaux (restent visibles en bas) ---
            # Calcul dynamique des totaux
            cols = st.columns(len(st.session_state.regex_config) + 1)
            
            total_heures = df_final["Durée (h)"].sum()
            cols[0].metric(label="Total Heures", value=f"{total_heures:.2f} h")
            
            idx = 1
            for config in st.session_state.regex_config:
                if config["type"] == "number" and config["name"] in df_final.columns:
                    total = df_final[config["name"]].sum()
                    if idx < len(cols):
                        cols[idx].metric(label=f"Total {config['name']}", value=f"{total:.2f}")
                    idx += 1
                  
        else:
            st.warning("Aucune donnée n'a pu être extraite dans cette période avec les règles actuelles.")
            
    except Exception as e:
        st.error(f"Une erreur est survenue lors de la lecture du fichier : {e}")
        
else:
    st.info("👋 En attente d'un morceau d'agenda (Fichier ou Lien) pour commencer.")