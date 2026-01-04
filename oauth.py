import os.path
import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import streamlit as st

# Scopes nécessaires (Lecture seule)
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

def get_calendar_service():
    """Authentifie l'utilisateur via OAuth et retourne le service Calendar API."""
    creds = None
    # Token stocké pour ne pas se reconnecter à chaque fois (dans un vrai cas SaaS, gérer par user_id)
    # Ici, c'est du local/MVP, on stocke en fichier token.json
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    # Si pas de creds valides, on lance le flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # On cherche le fichier client_secrets.json (téléchargé depuis GCP)
            if not os.path.exists('client_secret.json'):
                st.error("Fichier 'client_secret.json' manquant. Téléchargez-le depuis la console Google Cloud.")
                return None
                
            flow = InstalledAppFlow.from_client_secrets_file(
                'client_secret.json', SCOPES)
            
            # En local, ça ouvre un port local. Sur serveur, il faudrait un Redirect URI.
            creds = flow.run_local_server(port=0)
            
        # Sauvegarde du token pour la prochaine fois
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    service = build('calendar', 'v3', credentials=creds)
    return service

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
