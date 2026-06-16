"""Uniformisation des polices sur 01_Pionniers et 02_Installations.

Police cible : Arial 10pt
Préserve : couleurs, bordures, dropdowns (data validation), gel des lignes, etc.
Seul `textFormat.fontFamily` et `textFormat.fontSize` sont modifiés via fields mask.
"""
from __future__ import annotations
import os, sys, json, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / '.env')

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

creds = Credentials.from_service_account_info(
    json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]),
    scopes=["https://www.googleapis.com/auth/spreadsheets"],
)
service = build('sheets', 'v4', credentials=creds, cache_discovery=False)
sheet_id = os.environ["SHEET_ID"]

# Récupérer les sheetId numériques des onglets
meta = service.spreadsheets().get(spreadsheetId=sheet_id, fields='sheets.properties').execute()
sheets_by_name = {s['properties']['title']: s['properties']['sheetId'] for s in meta['sheets']}
print("Onglets disponibles :")
for n, sid in sheets_by_name.items():
    print(f"  {n} → sheetId={sid}")

TARGETS = ['01_Pionniers', '02_Installations']
FONT_FAMILY = "Arial"
FONT_SIZE = 10

requests = []
for name in TARGETS:
    if name not in sheets_by_name:
        print(f"⚠️ {name} introuvable, skip")
        continue
    sid = sheets_by_name[name]
    requests.append({
        "repeatCell": {
            "range": {"sheetId": sid},  # Toutes les cellules de l'onglet
            "cell": {
                "userEnteredFormat": {
                    "textFormat": {
                        "fontFamily": FONT_FAMILY,
                        "fontSize": FONT_SIZE,
                    }
                }
            },
            "fields": "userEnteredFormat.textFormat.fontFamily,userEnteredFormat.textFormat.fontSize",
        }
    })

if not requests:
    print("Aucune requête à exécuter")
    sys.exit(1)

print(f"\nApplication de Arial {FONT_SIZE}pt sur {len(requests)} onglet(s)...")
res = service.spreadsheets().batchUpdate(
    spreadsheetId=sheet_id, body={"requests": requests}
).execute()
print(f"✅ Done. Replies count: {len(res.get('replies', []))}")
