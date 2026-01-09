import re
import pandas as pd
from googleapiclient.discovery import build

def get_sheets_service(creds):
    """Retourne le service Sheets."""
    service = build('sheets', 'v4', credentials=creds)
    return service

def extract_spreadsheet_id(url):
    """Extrait l'ID d'une Spreadsheet Google depuis son URL."""
    # Pattern: /spreadsheets/d/([a-zA-Z0-9-_]+)
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", url)
    if match:
        return match.group(1)
    return url # Retourne l'URL tel quel si pas de match (peut-être déjà un ID)

def get_sheet_data(service, spreadsheet_id, range_name="A:Z"):
    """
    Lit les données d'une Google Sheet et retourne un DataFrame pandas.
    Suppose que la première ligne contient les headers.
    """
    sheet = service.spreadsheets()
    result = sheet.values().get(spreadsheetId=spreadsheet_id, range=range_name).execute()
    values = result.get('values', [])

    if not values:
        return pd.DataFrame()

    # Création du DataFrame
    # On suppose que la première ligne est le header
    header = values[0]
    data = values[1:]
    
    # On s'assure que toutes les lignes ont la même longueur que le header
    # Sinon pandas risque de se plaindre ou de décaler
    max_len = len(header)
    final_data = []
    for row in data:
        # Si la ligne est plus courte, on complète avec des None (ou empty strings)
        if len(row) < max_len:
            row += [''] * (max_len - len(row))
        # Si plus longue, on tronque (rare mais possible)
        elif len(row) > max_len:
             row = row[:max_len]
        final_data.append(row)

    df = pd.DataFrame(final_data, columns=header)
    return df
