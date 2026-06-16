"""Étape A — Normalisation territoire = MAYOTTE pour les 177 lignes vides
Étape B — Ajout colonne 'produits' dans 01_Pionniers (agrégation depuis 02_Installations)
"""
from __future__ import annotations
import sys, time, os, json
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT / '.env')
from services.sheets_service import get_sheets_service
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

svc = get_sheets_service()
creds = Credentials.from_service_account_info(
    json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]),
    scopes=["https://www.googleapis.com/auth/spreadsheets"])
api = build('sheets', 'v4', credentials=creds, cache_discovery=False)
sheet_id = os.environ["SHEET_ID"]

# === Étape A : Normalisation territoire ===
print("=== A. Normalisation territoire → MAYOTTE ===")
ws = svc.get_worksheet('pionniers')
time.sleep(2)
all_vals = ws.get_all_values()
header = all_vals[0]
col_pio = header.index('pio_id')
col_terr = header.index('territoire')
col_letter_terr = chr(ord('A') + col_terr)

batch = []
for i, row in enumerate(all_vals[1:], start=2):
    if not row or not row[col_pio].strip():
        continue
    cur = row[col_terr].strip() if len(row) > col_terr else ''
    if not cur:
        batch.append({'range': f'{col_letter_terr}{i}', 'values': [['MAYOTTE']]})

print(f"  {len(batch)} cellules à mettre à jour")
if batch:
    ws.batch_update(batch, value_input_option='USER_ENTERED')
    print(f"  ✅ territoire normalisé = MAYOTTE")
time.sleep(3)

# === Étape B : Colonne 'produits' dans 01_Pionniers ===
print("\n=== B. Ajout colonne 'produits' dans 01_Pionniers ===")

# Récupérer sheetId numérique
meta = api.spreadsheets().get(spreadsheetId=sheet_id, fields='sheets.properties').execute()
sid_pio = next(s['properties']['sheetId'] for s in meta['sheets'] if s['properties']['title']=='01_Pionniers')
n_cols_pio = next(s['properties']['gridProperties']['columnCount'] for s in meta['sheets'] if s['properties']['title']=='01_Pionniers')
print(f"  sheetId={sid_pio}, n_cols actuelles={n_cols_pio}")

# 1. Vérifier si la colonne 'produits' existe déjà
if 'produits' in header:
    col_produits_idx = header.index('produits')
    print(f"  Colonne 'produits' existe déjà à l'index {col_produits_idx}")
    NEW_COL = False
else:
    # 2. Insérer une nouvelle colonne juste après 'NS' (col B → nouvelle col C)
    col_ns_idx = header.index('NS')
    insert_at = col_ns_idx + 1
    print(f"  Insertion d'une nouvelle colonne à l'index {insert_at} (après 'NS')")
    api.spreadsheets().batchUpdate(
        spreadsheetId=sheet_id,
        body={"requests": [{
            "insertDimension": {
                "range": {"sheetId": sid_pio, "dimension": "COLUMNS",
                          "startIndex": insert_at, "endIndex": insert_at + 1},
                "inheritFromBefore": True
            }
        }]}
    ).execute()
    time.sleep(3)
    # Écrire le header
    col_letter_new = chr(ord('A') + insert_at)
    ws.update(f'{col_letter_new}1', [['produits']], value_input_option='USER_ENTERED')
    time.sleep(2)
    col_produits_idx = insert_at
    NEW_COL = True
    print(f"  ✅ Colonne 'produits' insérée à la lettre {col_letter_new}")

# 3. Calculer les produits par pio_id
inst = svc.read_all('installations')
prod_by_pio = {}
for r in inst:
    pid = str(r.get('pio_id','')).strip()
    prod = str(r.get('produit','')).strip()
    if not pid or pid == '#REF!' or not prod:
        continue
    prod_by_pio.setdefault(pid, []).append(prod)

# Format : "G30" ou "G30 (x2)" si multi-installations même produit
def fmt_produits(prods):
    from collections import Counter
    c = Counter(prods)
    parts = []
    for p, n in c.most_common():
        parts.append(f"{p} (x{n})" if n > 1 else p)
    return ' + '.join(parts)

# 4. Reread sheet pour avoir le nouvel index
time.sleep(2)
all_vals = ws.get_all_values()
header = all_vals[0]
col_produits = header.index('produits')
col_letter_prod = chr(ord('A') + col_produits)
col_pio = header.index('pio_id')

batch = []
for i, row in enumerate(all_vals[1:], start=2):
    if not row or not row[col_pio].strip():
        continue
    pid = row[col_pio].strip()
    prods = prod_by_pio.get(pid, [])
    if not prods:
        continue
    val = fmt_produits(prods)
    cur = row[col_produits].strip() if len(row) > col_produits else ''
    if cur == val:
        continue
    batch.append({'range': f'{col_letter_prod}{i}', 'values': [[val]]})

print(f"  {len(batch)} cellules produits à remplir")
if batch:
    ws.batch_update(batch, value_input_option='USER_ENTERED')
    print(f"  ✅ Colonne 'produits' remplie")

svc.log_event('normalize_territoire_add_produits', result='OK',
              message=f'territoire vide → MAYOTTE x{177}; colonne produits ajoutée dans 01_Pionniers')

print("\n=== TERMINÉ ===")
PYEOF
