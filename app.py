import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import io
import requests

# Imports des modules locaux
from translations import TRANSLATIONS
from utils import parse_ics, extraire_informations_agenda
from oauth import get_calendar_service, list_calendars, get_events_from_calendar, get_auth_url, get_credentials_from_code
from oauth import get_calendar_service, list_calendars, get_events_from_calendar
from invoice import get_services, extract_id_from_url, generate_invoice

# --- Configuration de la page Streamlit ---
st.set_page_config(page_title="PatternCal", layout="wide", page_icon="📅")

# --- Initialisation Session State (Langue) ---
if 'lang' not in st.session_state:
    st.session_state.lang = 'fr'

# --- Sélecteur de Langue (Sidebar) ---
with st.sidebar:
    st.header("Language 🌍")
    lang_options = {"fr": "Français 🇫🇷", "en": "English 🇬🇧", "es": "Español 🇪🇸"}
    selected_lang = st.selectbox(
        "Choisir / Choose / Elegir", 
        options=list(lang_options.keys()), 
        format_func=lambda x: lang_options[x],
        index=0
    )
    if selected_lang != st.session_state.lang:
        st.session_state.lang = selected_lang
        st.rerun()

t = TRANSLATIONS[st.session_state.lang]

# --- Initialisation Session State (Données) ---
if 'regex_config' not in st.session_state:
    st.session_state.regex_config = [
        {"name": "Client", "pattern": r"([A-ZÀ-ÿ][a-zà-ÿ]+(?:[\s-][A-ZÀ-ÿ][a-zà-ÿ]+)+)", "type": "text"},
        {"name": "Montant", "pattern": r"(\d+([.,]\d{1,2})?)\s?(?:€|EUR)", "type": "number"},
    ]

if 'raw_events' not in st.session_state:
    st.session_state.raw_events = None

# --- Zone Principale : Layout ---

st.title(t["main_title"])
st.markdown(t["description"])

# Ligne 1 : Import (Gauche) et Dates (Droite)
col_top_left, col_top_right = st.columns([1, 1], gap="large")

with col_top_left:
    st.subheader(t["source"])
    tab_file, tab_link, tab_oauth = st.tabs([t["tab_file"], t["tab_link"], t["tab_oauth"]])
    
    with tab_file:
        uploaded_file = st.file_uploader(t["upload_label"], type="ics", label_visibility="collapsed", help=t["upload_help"])
        if uploaded_file is not None:
             # Parsing immédiat
             try:
                events = parse_ics(uploaded_file.getvalue(), translations=t)
                st.session_state.raw_events = events
             except Exception as e:
                st.error(str(e))
            
    with tab_link:
        ics_url = st.text_input(t["url_label"], 
                                placeholder=t["url_placeholder"],
                                help=t["url_help"])
        if ics_url:
            if st.button(t["load_btn"]):
                try:
                    resp = requests.get(ics_url)
                    resp.raise_for_status()
                    events = parse_ics(resp.content, translations=t)
                    st.session_state.raw_events = events
                    st.success(t["success_load"])
                except Exception as e:
                    st.error(t["error_load"].format(e))

    with tab_oauth:
        # Détermination de l'URL de redirection
        # En prod (Streamlit Cloud), il faut définir "redirect_url" dans les secrets
        # En local, on fallback sur localhost
        redirect_uri = "http://localhost:8501"
        try:
            if "google_oauth" in st.secrets and "redirect_url" in st.secrets["google_oauth"]:
                redirect_uri = st.secrets["google_oauth"]["redirect_url"]
        except Exception:
            # En local sans secrets.toml, st.secrets lève StreamlitSecretNotFoundError
            pass

        # Gestion du Retour OAuth (Callback)
        if "code" in st.query_params:
            code = st.query_params["code"]
            
            creds = get_credentials_from_code(code, redirect_uri)
            if creds:
                st.session_state.google_creds = creds
                # Nettoyage de l'URL
                st.query_params.clear()
                st.rerun()
            else:
                st.error("Erreur lors de l'authentification.")

        # Vérification si connecté (via session_state ou token valide)
        service = None
        if 'google_creds' in st.session_state:
             service = get_calendar_service(st.session_state.google_creds)
        
        if service:
            st.success("✅ Connecté à Google Calendar")
            if st.button("Se déconnecter"):
                del st.session_state.google_creds
                st.rerun()
            
            # Listing Agendas
            try:
                cals = list_calendars(service)
                cal_options = {c['summary']: c['id'] for c in cals}
                selected_cal_name = st.selectbox(t["select_cal"], list(cal_options.keys()))
                
                if st.button(t["load_cal_btn"]):
                    cal_id = cal_options[selected_cal_name]
                    events = get_events_from_calendar(service, cal_id, days_back=90)
                    st.session_state.raw_events = events
                    st.success(t["success_load"])
            except Exception as e:
                st.error(f"Erreur API: {e}")

        else:
            # Bouton de connexion qui redirige
            auth_url, err = get_auth_url(redirect_uri)
            if auth_url:
                # st.link_button ouvre souvent un nouvel onglet. On force le même onglet avec du HTML.
                st.markdown(f'<a href="{auth_url}" target="_self" style="background-color: #f0f2f6; color: #31333F; padding: 0.5rem; text-decoration: none; border: 1px solid #d6d6d8; border-radius: 0.25rem; display: inline-block;">{t["connect_google"]}</a>', unsafe_allow_html=True)
            elif err:
                st.error(err)
            else:
                st.error("Erreur inconnue lors de la génération du lien.")

with col_top_right:
    st.subheader(t["period"])
    c_d1, c_d2 = st.columns(2)
    today = datetime.now().date()
    m_1 = today - timedelta(days=30)
    
    with c_d1:
        date_debut = st.date_input(t["date_start"], value=m_1)
    with c_d2:
        date_fin = st.date_input(t["date_end"], value=today)

st.divider()

# Ligne 2 : Règles d'extraction
st.subheader(t["rules"])
st.info(t["rules_info"])

# Affichage et édition des règles
to_remove = []
h1, h2, h3, h4 = st.columns([2, 3, 1.5, 0.5])
h1.caption(t["header_name"])
h2.caption(t["header_regex"])
h3.caption(t["header_type"])

for i, config in enumerate(st.session_state.regex_config):
    c1, c2, c3, c4 = st.columns([2, 3, 1.5, 0.5])
    with c1:
        new_name = st.text_input(f"Nom chp {i}", value=config["name"], label_visibility="collapsed", key=f"name_{i}", placeholder=t["placeholder_name"])
        st.session_state.regex_config[i]["name"] = new_name
    with c2:
        new_pattern = st.text_input(f"Regex chp {i}", value=config["pattern"], label_visibility="collapsed", key=f"pattern_{i}", placeholder=t["placeholder_regex"])
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
    if st.button(t["add_rule"], use_container_width=True):
        st.session_state.regex_config.append({"name": t["new_field"], "pattern": "", "type": "text"})
        st.rerun()
with b_col2:
    if st.button(t["reset_rules"], use_container_width=True):
         st.session_state.regex_config = [
            {"name": "Client", "pattern": r"([A-ZÀ-ÿ][a-zà-ÿ]+(?:[\s-][A-ZÀ-ÿ][a-zà-ÿ]+)+)", "type": "text"},
            {"name": "Montant", "pattern": r"(\d+([.,]\d{1,2})?)\s?(?:€|EUR)", "type": "number"},
            {"name": "Projet", "pattern": r"Projet\s*:\s*(\w+)", "type": "text"},
        ]
         st.rerun()

st.divider()

if st.session_state.raw_events is not None:
    # Les événements sont déjà parsés et stockés dans raw_events
    raw_events = st.session_state.raw_events
        
    # Filtrage par date
    events_filtrés = []
    for evt in raw_events:
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

    st.success(t["found_events"].format(len(events_filtrés), len(raw_events)))
    
    # Extraction intelligente (utils)
    df_final = extraire_informations_agenda(
        events_filtrés, 
        st.session_state.regex_config
    )
    
    if not df_final.empty:
        st.subheader(t["results"])
        
        # Identification de la colonne de regroupement (Client) - AVANT les tabs
        col_client = None
        candidates = [c for c in df_final.columns if "client" in c.lower()]
        if candidates:
            col_client = candidates[0]
        elif "Client" in [c["name"] for c in st.session_state.regex_config]:
                col_client = "Client"

        tab_detail, tab_synthese = st.tabs([t["tab_detail"], t["tab_synthesis"]])
        
        with tab_detail:
            st.dataframe(df_final, use_container_width=True)
            # Export Buttons removed as requested

        with tab_synthese:
            if col_client and col_client in df_final.columns:
                # Agrégation
                numeric_cols = df_final.select_dtypes(include=[np.number]).columns.tolist()
                df_grouped = df_final.groupby(col_client)[numeric_cols].sum().reset_index()
                
                if "Durée (h)" in df_grouped.columns:
                    df_grouped = df_grouped.sort_values("Durée (h)", ascending=False)
                    
                st.dataframe(df_grouped, use_container_width=True)
                # Export Buttons removed as requested
            else:
                st.info("Aucune colonne 'Client' détectée pour le regroupement. Vérifiez vos règles d'extraction.")

        st.divider()
        
        # --- Etape 5 : Génération de Factures ---
        st.header("5. Génération de Factures (Google Docs)")
        
        if col_client and col_client in df_final.columns:
            c_inv1, c_inv2 = st.columns(2)
            with c_inv1:
                template_url = st.text_input("URL du Template Google Doc", placeholder="https://docs.google.com/document/d/...")
            with c_inv2:
                folder_url = st.text_input("URL du Dossier de Destination", placeholder="https://drive.google.com/drive/folders/...")
            
            if st.button("Générer les factures 🧾"):
                if not template_url or not folder_url:
                    st.warning("Veuillez fournir les deux URLs.")
                elif 'google_creds' not in st.session_state:
                        st.error("Vous devez être connecté à Google pour générer des factures.")
                else:
                    template_id = extract_id_from_url(template_url)
                    folder_id = extract_id_from_url(folder_url)
                    
                    try:
                        # Construction des services
                        drive_service, docs_service = get_services(st.session_state.google_creds)
                        
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        groups = df_final.groupby(col_client)
                        total_groups = len(groups)
                        
                        results_links = []
                        
                        for idx, (client_name, group) in enumerate(groups):
                            status_text.text(f"Génération pour {client_name}...")
                            
                            # Préparation des données
                            nb_presta = len(group)
                            cout_total = 0
                            # Recherche d'une colonne de montant
                            for col in group.columns:
                                if "montant" in col.lower() or "price" in col.lower() or "eur" in col.lower():
                                        try:
                                            cout_total = group[col].sum()
                                        except:
                                            pass
                                        break
                            
                            # Liste des dates
                            dates = []
                            for _, row in group.iterrows():
                                start = row.get("Date")
                                if start:
                                        if isinstance(start, (datetime, pd.Timestamp)):
                                            dates.append(start.strftime("%d/%m/%Y"))
                                        else:
                                            dates.append(str(start))
                            liste_dates = ", ".join(dates)
                            
                            invoice_data = {
                                "CLIENT_NOM": client_name,
                                "NOMBRE_PRESTATION": nb_presta,
                                "COUT_TOTAL": f"{cout_total:.2f} €",
                                "LISTE_DATE_PRESTATION": liste_dates
                            }
                            
                            try:
                                res = generate_invoice(drive_service, docs_service, template_id, folder_id, invoice_data)
                                results_links.append(f"- {client_name}: [PDF]({res['pdf_link']})")
                            except Exception as e:
                                st.error(f"Erreur pour {client_name}: {e}")
                            
                            progress_bar.progress((idx + 1) / total_groups)
                            
                        status_text.text("Terminé !")
                        st.success("Toutes les factures ont été générées.")
                        if results_links:
                            st.markdown("\n".join(results_links))
                            
                    except Exception as e:
                        st.error(f"Erreur globale : {e}")
        else:
            st.warning("Impossible de générer des factures sans colonne 'Client'.")

        st.divider()
        
        # --- KPI Globaux ---
        cols = st.columns(len(st.session_state.regex_config) + 1)
        
        total_heures = df_final["Durée (h)"].sum()
        cols[0].metric(label=t["total_hours"], value=f"{total_heures:.2f} h")
        
        idx = 1
        for config in st.session_state.regex_config:
            if config["type"] == "number" and config["name"] in df_final.columns:
                total = df_final[config["name"]].sum()
                if idx < len(cols):
                    cols[idx].metric(label=t["total_prefix"].format(config['name']), value=f"{total:.2f}")
                idx += 1
              
    else:
        st.warning(t["no_data"])
        
else:
    st.info(t["waiting"])