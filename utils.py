import icalendar
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import re
import streamlit as st # Pour st.error si besoin, ou on lève une exception

def parse_ics(file_content: bytes, translations: dict = None) -> list[dict]:
    """
    Parse le contenu d'un fichier ICS et retourne une liste de dictionnaires
    contenant les informations brutes des événements.
    """
    try:
        cal = icalendar.Calendar.from_ical(file_content)
    except Exception as e:
        msg = f"Erreur de lecture du fichier ICS: {e}"
        if translations and "error_load" in translations:
             msg = translations["error_load"].format(e)
        # On peut choisir de print l'erreur ici ou de la laisser remonter
        # Pour rester iso avec le code d'avant qui faisait st.error :
        # L'appelant gérera l'affichage ou on le fait ici si on a acces a st
        # Mais pour un utils pur, mieux vaut ne pas dépendre de st.
        # Cependant, le code d'avant faisait st.error puis return []
        # On va raise une exception ou return [] et laisser l'appelant gérer l'UI
        raise ValueError(msg)

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
            duration = timedelta(0)
            
            # Cas 1: deux datetimes
            if isinstance(dtstart, datetime) and isinstance(dtend, datetime):
                 try:
                     duration = dtend - dtstart
                 except TypeError:
                     # un des deux est naive, l'autre aware -> on rend tout naive
                     duration = dtend.replace(tzinfo=None) - dtstart.replace(tzinfo=None)

            # Cas 2: deux dates (all day event)
            elif hasattr(dtstart, 'date') and hasattr(dtend, 'date'):
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
