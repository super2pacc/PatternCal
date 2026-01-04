import os.path
import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
import streamlit as st

# Scopes nécessaires (Lecture seule)
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

def get_oauth_flow(redirect_uri):
    """Crée l'objet Flow à partir des secrets (st.secrets ou fichier JSON)."""
    
    # 1. Priorité : Secrets Streamlit Cloud (Production)
    try:
        if "google_oauth" in st.secrets:
            # st.secrets convertit le TOML en dict, on doit adapter pour Flow
            client_config = {"web": st.secrets["google_oauth"]}
            flow = Flow.from_client_config(
                client_config,
                scopes=SCOPES,
                redirect_uri=redirect_uri
            )
            return flow
    except Exception:
        # En local sans secrets.toml, st.secrets peut lever une erreur.
        # On ignore et on passe au fallback.
        pass
        
    # 2. Fallback : Fichier JSON (Local)
    if os.path.exists('client_secret.json'):
        flow = Flow.from_client_secrets_file(
            'client_secret.json',
            scopes=SCOPES,
            redirect_uri=redirect_uri
        )
        return flow
    
    return None

def get_auth_url(redirect_uri):
    """Génère l'URL d'autorisation Google."""
    flow = get_oauth_flow(redirect_uri)
    if not flow:
        return None, "Fichier client_secret.json manquant."
    
    auth_url, _ = flow.authorization_url(prompt='consent')
    return auth_url, None

def get_credentials_from_code(code, redirect_uri):
    """Echange le code d'autorisation contre des credentials."""
    flow = get_oauth_flow(redirect_uri)
    try:
        flow.fetch_token(code=code)
        return flow.credentials
    except Exception as e:
        st.error(f"Erreur échange token: {e}")
        return None

def get_calendar_service(creds):
    """Construit le service API à partir des credentials."""
    if not creds:
        return None
    
    # Refresh si nécessaire
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception:
            return None # Token invalide, il faudra se reconnecter

    # Construction du service
    service = build('calendar', 'v3', credentials=creds)
    return service

def list_calendars(service):
    """Liste les agendas disponibles pour l'utilisateur."""
    # ... (Code existant inchangé)
    page_token = None
    calendars = []
    while True:
        calendar_list = service.calendarList().list(pageToken=page_token).execute()
        for calendar_list_entry in calendar_list['items']:
            calendars.append({
                "id": calendar_list_entry['id'], 
                "summary": calendar_list_entry['summary']
            })
        page_token = calendar_list.get('nextPageToken')
        if not page_token:
            break
    return calendars

def get_events_from_calendar(service, calendar_id, days_back=30):
    """Récupère les événements (Code existant inchangé)"""
    # ...
    # Copie du code précédent pour get_events_from_calendar et _parse_google_date
    # Je dois m'assurer de remettre tout le contenu des fonctions ici.
    
    # Conversion date RFC3339
    now = datetime.datetime.utcnow()
    start_date = (now - datetime.timedelta(days=days_back)).isoformat() + 'Z'
    
    events_result = service.events().list(calendarId=calendar_id, timeMin=start_date,
                                          singleEvents=True,
                                          orderBy='startTime').execute()
    events = events_result.get('items', [])

    normalized_events = []
    if not events:
        return []
        
    for event in events:
        start = event['start'].get('dateTime', event['start'].get('date'))
        end = event['end'].get('dateTime', event['end'].get('date'))
        summary = event.get('summary', 'Sans titre')
        
        dtstart = _parse_google_date(start)
        dtend = _parse_google_date(end)
        
        duration = datetime.timedelta(0)
        if isinstance(dtstart, datetime.datetime) and isinstance(dtend, datetime.datetime):
             if dtstart.tzinfo and not dtend.tzinfo:
                 dtend = dtend.replace(tzinfo=dtstart.tzinfo)
             duration = dtend - dtstart
        elif not isinstance(dtstart, datetime.datetime): 
             duration = dtend - dtstart

        normalized_events.append({
            "summary": summary,
            "dtstart": dtstart,
            "dtend": dtend,
            "duration": duration
        })
        
    return normalized_events

def _parse_google_date(date_str):
    """Transforme une string date Google en objet datetime ou date python."""
    try:
        if 'T' in date_str:
            return datetime.datetime.fromisoformat(date_str)
        else:
            return datetime.date.fromisoformat(date_str)
    except ValueError:
        return date_str

def list_calendars(service):
    """Liste les agendas disponibles pour l'utilisateur."""
    page_token = None
    calendars = []
    while True:
        calendar_list = service.calendarList().list(pageToken=page_token).execute()
        for calendar_list_entry in calendar_list['items']:
            calendars.append({
                "id": calendar_list_entry['id'], 
                "summary": calendar_list_entry['summary']
            })
        page_token = calendar_list.get('nextPageToken')
        if not page_token:
            break
    return calendars

def get_events_from_calendar(service, calendar_id, days_back=30):
    """Récupère les événements et les transforme en format compatible parse_ics (liste de dicts)."""
    
    # Conversion date RFC3339
    now = datetime.datetime.utcnow()
    start_date = (now - datetime.timedelta(days=days_back)).isoformat() + 'Z'  # 'Z' indicates UTC time
    
    events_result = service.events().list(calendarId=calendar_id, timeMin=start_date,
                                          singleEvents=True,
                                          orderBy='startTime').execute()
    events = events_result.get('items', [])

    normalized_events = []
    if not events:
        return []
        
    for event in events:
        start = event['start'].get('dateTime', event['start'].get('date'))
        end = event['end'].get('dateTime', event['end'].get('date'))
        summary = event.get('summary', 'Sans titre')
        
        # Parsing des dates (c'est souvent des str ISO)
        # On utilise une fonction helper pour normaliser
        dtstart = _parse_google_date(start)
        dtend = _parse_google_date(end)
        
        # Calcul durée
        duration = datetime.timedelta(0)
        if isinstance(dtstart, datetime.datetime) and isinstance(dtend, datetime.datetime):
             if dtstart.tzinfo and not dtend.tzinfo:
                 dtend = dtend.replace(tzinfo=dtstart.tzinfo)
             duration = dtend - dtstart
        elif not isinstance(dtstart, datetime.datetime): 
             # Cas Date pure (all day)
             duration = dtend - dtstart

        normalized_events.append({
            "summary": summary,
            "dtstart": dtstart,
            "dtend": dtend,
            "duration": duration
        })
        
    return normalized_events

def _parse_google_date(date_str):
    """Transforme une string date Google en objet datetime ou date python."""
    # Format '2023-11-23T10:00:00+01:00' (dateTime) ou '2023-11-23' (date)
    try:
        if 'T' in date_str:
            return datetime.datetime.fromisoformat(date_str)
        else:
            return datetime.date.fromisoformat(date_str)
    except ValueError:
        return date_str # Fallback
