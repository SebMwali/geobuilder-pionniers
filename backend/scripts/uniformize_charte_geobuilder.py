"""Uniformisation graphique des onglets selon la charte Geobuilder V1.

Couleurs :
- Noir principal : #0D0D0D (dominante)
- Bleu électrique : #3A8FE8 (accent, max 20%)
- Blanc : #FFFFFF
- Gris bordures : #E5E5E5

Typo : Montserrat (SemiBold pour titres, Regular pour corps)

Application :
- Header (L1) : fond noir, texte blanc gras, Montserrat 11pt, frozen, hauteur 32px
- Corps : fond blanc, texte noir, Montserrat 10pt
- Bordures grises légères
- Préserve : dropdowns, data validations, formatage conditionnel, formules

Onglets traités : tous sauf 'Import' (feuille de travail)
"""
from __future__ import annotations
import os, sys, json
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

# Couleurs charte
def rgb(hex_str):
    h = hex_str.lstrip('#')
    return {'red': int(h[0:2],16)/255, 'green': int(h[2:4],16)/255, 'blue': int(h[4:6],16)/255}

NOIR = rgb('#0D0D0D')
BLEU = rgb('#3A8FE8')
BLANC = rgb('#FFFFFF')
GRIS_BORDURE = rgb('#E5E5E5')

FONT = "Montserrat"

# Onglets à traiter (exclure Import)
EXCLUDE = {'Import'}

meta = service.spreadsheets().get(spreadsheetId=sheet_id, fields='sheets.properties').execute()
sheets_info = [(s['properties']['title'], s['properties']['sheetId'], s['properties'].get('gridProperties', {}))
               for s in meta['sheets']]

print(f"Onglets disponibles : {[s[0] for s in sheets_info]}")
target_sheets = [(name, sid, gp) for name, sid, gp in sheets_info if name not in EXCLUDE]
print(f"\nÀ uniformiser ({len(target_sheets)}) : {[s[0] for s in target_sheets]}\n")

requests = []
for name, sid, gp in target_sheets:
    row_count = gp.get('rowCount', 1000)
    col_count = gp.get('columnCount', 26)

    # 1. CORPS — Montserrat 10pt, fond blanc, texte noir sur TOUT l'onglet
    requests.append({
        "repeatCell": {
            "range": {"sheetId": sid},
            "cell": {
                "userEnteredFormat": {
                    "textFormat": {
                        "fontFamily": FONT,
                        "fontSize": 10,
                        "foregroundColor": NOIR,
                        "bold": False,
                    },
                    "backgroundColor": BLANC,
                }
            },
            "fields": "userEnteredFormat.textFormat.fontFamily,userEnteredFormat.textFormat.fontSize,userEnteredFormat.textFormat.foregroundColor,userEnteredFormat.textFormat.bold,userEnteredFormat.backgroundColor"
        }
    })

    # 2. HEADER L1 — fond noir, texte blanc gras, Montserrat 11pt, alignement centré vertical
    requests.append({
        "repeatCell": {
            "range": {
                "sheetId": sid,
                "startRowIndex": 0, "endRowIndex": 1,
                "startColumnIndex": 0, "endColumnIndex": col_count,
            },
            "cell": {
                "userEnteredFormat": {
                    "textFormat": {
                        "fontFamily": FONT,
                        "fontSize": 11,
                        "foregroundColor": BLANC,
                        "bold": True,
                    },
                    "backgroundColor": NOIR,
                    "horizontalAlignment": "CENTER",
                    "verticalAlignment": "MIDDLE",
                    "padding": {"top": 6, "bottom": 6, "left": 8, "right": 8},
                }
            },
            "fields": "userEnteredFormat.textFormat,userEnteredFormat.backgroundColor,userEnteredFormat.horizontalAlignment,userEnteredFormat.verticalAlignment,userEnteredFormat.padding"
        }
    })

    # 3. Bordures grises fines sur toute la plage utilisée (header + corps jusqu'à la fin)
    requests.append({
        "updateBorders": {
            "range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": row_count,
                      "startColumnIndex": 0, "endColumnIndex": col_count},
            "innerHorizontal": {"style": "SOLID", "width": 1, "color": GRIS_BORDURE},
            "innerVertical":   {"style": "SOLID", "width": 1, "color": GRIS_BORDURE},
        }
    })

    # 4. Gel de la ligne 1
    requests.append({
        "updateSheetProperties": {
            "properties": {"sheetId": sid, "gridProperties": {"frozenRowCount": 1}},
            "fields": "gridProperties.frozenRowCount"
        }
    })

    # 5. Hauteur de la ligne 1 (32px)
    requests.append({
        "updateDimensionProperties": {
            "range": {"sheetId": sid, "dimension": "ROWS", "startIndex": 0, "endIndex": 1},
            "properties": {"pixelSize": 32},
            "fields": "pixelSize"
        }
    })

    # 6. ACCENT BLEU sur colonne A (IDs) — texte bleu, gras léger pour identifier rapidement
    # max 20% du visuel : c'est 1 colonne sur N → respecte la règle
    requests.append({
        "repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": 1, "endRowIndex": row_count,
                      "startColumnIndex": 0, "endColumnIndex": 1},
            "cell": {
                "userEnteredFormat": {
                    "textFormat": {
                        "foregroundColor": BLEU,
                        "bold": True,
                    }
                }
            },
            "fields": "userEnteredFormat.textFormat.foregroundColor,userEnteredFormat.textFormat.bold"
        }
    })

print(f"Préparation : {len(requests)} requêtes batchUpdate ({len(requests) // len(target_sheets)} par onglet)")
print("Exécution...")
res = service.spreadsheets().batchUpdate(spreadsheetId=sheet_id, body={"requests": requests}).execute()
print(f"✅ Done. Replies : {len(res.get('replies', []))}")
