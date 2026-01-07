import re
import io
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

def get_services(creds):
    """Retourne les services Drive et Docs."""
    drive_service = build('drive', 'v3', credentials=creds)
    docs_service = build('docs', 'v1', credentials=creds)
    return drive_service, docs_service

def extract_id_from_url(url):
    """Extrait l'ID d'un fichier ou dossier Google depuis son URL."""
    # Pattern pour Docs: /document/d/([a-zA-Z0-9-_]+)
    # Pattern pour Drive Folder: /folders/([a-zA-Z0-9-_]+)
    
    match = re.search(r"/d/([a-zA-Z0-9-_]+)", url)
    if match:
        return match.group(1)
    
    match = re.search(r"/folders/([a-zA-Z0-9-_]+)", url)
    if match:
        return match.group(1)
        
    return url # Retourne l'URL tel quel si pas de match (peut-être déjà un ID)

def generate_invoice(drive_service, docs_service, template_id, folder_id, data):
    """
    Génère une facture à partir d'un template Google Doc.
    
    Args:
        data (dict): Dictionnaire contenant:
                     - CLIENT_NOM
                     - NOMBRE_PRESTATION
                     - COUT_TOTAL
                     - LISTE_DATE_PRESTATION
    """
    
    # 1. Copie du Template
    client_name = data.get("CLIENT_NOM", "Client")
    file_metadata = {
        'name': f'Facture - {client_name}',
        'parents': [folder_id]
    }
    
    copy_response = drive_service.files().copy(
        fileId=template_id,
        body=file_metadata
    ).execute()
    new_doc_id = copy_response.get('id')
    
    if not new_doc_id:
        raise Exception("Échec de la copie du template.")
        
    # 2. Remplacement des Balises
    requests = []
    
    # Mapping des clés vers les balises
    replacements = {
        "{{CLIENT_NOM}}": str(data.get("CLIENT_NOM", "")),
        "{{NOMBRE_PRESTATION}}": str(data.get("NOMBRE_PRESTATION", "")),
        "{{COUT_TOTAL}}": str(data.get("COUT_TOTAL", "")),
        "{{LISTE_DATE_PRESTATION}}": str(data.get("LISTE_DATE_PRESTATION", ""))
    }
    
    for placeholder, value in replacements.items():
        requests.append({
            'replaceAllText': {
                'containsText': {
                    'text': placeholder,
                    'matchCase': True
                },
                'replaceText': value
            }
        })
        
    docs_service.documents().batchUpdate(
        documentId=new_doc_id,
        body={'requests': requests}
    ).execute()
    
    # 3. Export en PDF
    pdf_content = drive_service.files().export(
        fileId=new_doc_id,
        mimeType='application/pdf'
    ).execute()
    
    # 4. Upload du PDF dans le même dossier
    file_metadata_pdf = {
        'name': f'Facture - {client_name}.pdf',
        'parents': [folder_id]
    }
    
    media = MediaIoBaseUpload(io.BytesIO(pdf_content), mimetype='application/pdf', resumable=True)
    
    pdf_file = drive_service.files().create(
        body=file_metadata_pdf,
        media_body=media,
        fields='id, webViewLink'
    ).execute()
    
    return {
        "doc_id": new_doc_id,
        "pdf_id": pdf_file.get('id'),
        "pdf_link": pdf_file.get('webViewLink')
    }
