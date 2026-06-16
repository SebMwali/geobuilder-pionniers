"""Rectification : restauration de tous les fondateurs originaux + conservation des 23 ajouts.

Erreur précédente : j'ai décoché 62 fondateurs alors que Sandrine voulait juste AJOUTER ses 23.
Correction : recocher les 62 + garder les 23 + repopulater 00_Fondateurs avec la liste complète.
"""
from __future__ import annotations
import os, sys, time, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / '.env')

from services.sheets_service import get_sheets_service

svc = get_sheets_service()

# Les 62 pio_ids que j'avais décochés à tort (à re-cocher TRUE)
TO_RECHECK = [
    'PIO-1000','PIO-1001','PIO-1002','PIO-1003','PIO-1004','PIO-1005','PIO-1006','PIO-1007',
    'PIO-1008','PIO-1009','PIO-1010','PIO-1011','PIO-1012','PIO-1013','PIO-1014','PIO-1015',
    'PIO-1017','PIO-1018','PIO-1019','PIO-1020','PIO-1021','PIO-1023','PIO-1024','PIO-1025',
    'PIO-1026','PIO-1027','PIO-1028','PIO-1029','PIO-1030','PIO-1031','PIO-1032','PIO-1033',
    'PIO-1034','PIO-1035','PIO-1036','PIO-1037','PIO-1038','PIO-1039','PIO-1040','PIO-1041',
    'PIO-1042','PIO-1043','PIO-1044','PIO-1045','PIO-1046','PIO-1047','PIO-1048','PIO-1050',
    'PIO-1053','PIO-1055','PIO-1056','PIO-1060','PIO-1061','PIO-1062','PIO-1073','PIO-1081',
    'PIO-1082','PIO-1083','PIO-1106','PIO-1148','PIO-1151','PIO-1152',
]
# Note: PIO-1151 Tetrama et PIO-1152 RAFFARD sont dans la liste mais l'utilisateur n'a pas
# dit de les exclure - on les remet TRUE comme demandé.

# Liste cible Sandrine — commentaires métier à utiliser dans 00_Fondateurs (info contextuelle)
SANDRINE_RECO_COMMENT = {
    'PIO-1058': "Travaille au collège de Chiconi - formations dans tous les collèges",
    'PIO-1022': "",
    'PIO-1016': "Chef chez TOTAL",
    'PIO-1054': "Médecine du travail",
    'PIO-1207': "",
    'PIO-1202': "Pilote d'avion",
    'PIO-1096': "",
    'PIO-1077': "Chef tribunal administratif - conjointe THORAL (cheffe conseil d'État)",
    'PIO-1122': "",
    'PIO-1208': "",
    'PIO-1130': "Médecin",
    'PIO-1090': "",
    'PIO-1119': "Chef d'un collège",
    'PIO-1126': "Chef établissement scolaire (DUPRE WESEKA) - actif dans plusieurs assoc",
    'PIO-1115': "FRANCE TRAVAIL",
    'PIO-1094': "FRANCE TRAVAIL",
    'PIO-1051': "Travaille chez Mayotte Incendie (équipé)",
    'PIO-1120': "Très sympa",
    'PIO-1065': "Mahorais - bouche à oreille",
    'PIO-1129': "Mahorais - bouche à oreille",
    'PIO-1066': "Mahorais - bouche à oreille",
    'PIO-1049': "Mahorais - bouche à oreille",
    'PIO-1052': "Mahorais - bouche à oreille (SAINDOU M'SOILI)",
    'PIO-1204': "Mahorais - bouche à oreille",
    'PIO-1105': "Mahorais - bouche à oreille (MROIVILI Echati Moussa)",
    'PIO-1111': "Mahorais - bouche à oreille",
    'PIO-1099': "Mahorais - bouche à oreille",
    'PIO-1098': "Mahorais - bouche à oreille",
    'PIO-1100': "Mahorais - bouche à oreille",
}

# === ÉTAPE 1 — Re-cocher les 62 décochés à tort ===
print("Loading 01_Pionniers...")
ws_pio = svc.get_worksheet('pionniers')
time.sleep(2)
all_vals = ws_pio.get_all_values()
header = all_vals[0]
col_pio = header.index('pio_id')
col_fond = header.index('fondateur')
col_letter_fond = chr(ord('A') + col_fond)

pio_to_row = {}
for i, row in enumerate(all_vals[1:], start=2):
    if row and row[col_pio].strip():
        pio_to_row[row[col_pio].strip()] = (i, row)

print(f"  {len(pio_to_row)} pionniers indexés. col fondateur={col_letter_fond}")

batch = []
for pid in TO_RECHECK:
    if pid not in pio_to_row:
        print(f"  ⚠️ {pid} introuvable")
        continue
    row_num = pio_to_row[pid][0]
    batch.append({'range': f'{col_letter_fond}{row_num}', 'values': [['TRUE']]})

print(f"\n=== Étape 1 — Re-cocher {len(batch)} fondateurs ===")
if batch:
    ws_pio.batch_update(batch, value_input_option='USER_ENTERED')
    print(f"  ✅ {len(batch)} fondateurs ré-activés en 1 batch")
time.sleep(3)

# === ÉTAPE 2 — Recharger et vérifier ===
print("\n=== Étape 2 — Reload + vérification ===")
ws_pio = svc.get_worksheet('pionniers')
time.sleep(2)
pio = svc.read_all('pionniers')
fondateurs = [r for r in pio if str(r.get('fondateur','')).strip().upper() in ('TRUE','OUI','1','VRAI','YES')]
print(f"  Fondateurs TRUE : {len(fondateurs)}")

# === ÉTAPE 3 — Vider 00_Fondateurs et repopulater complet ===
print("\n=== Étape 3 — Vider 00_Fondateurs ===")
ws_fond = svc.get_worksheet('00_Fondateurs')
time.sleep(2)
ws_fond.batch_clear(['A2:L150'])  # large range pour effacer tout
time.sleep(2)

# === ÉTAPE 4 — Repopulater avec tous les fondateurs (tri pio_id) ===
print("\n=== Étape 4 — Repopulater 00_Fondateurs ===")
inst = svc.read_all('installations')
inst_by_pio = {}
for r in inst:
    pid = str(r.get('pio_id','')).strip()
    if not pid or pid == '#REF!':
        continue
    inst_by_pio.setdefault(pid, []).append(r)

import re
def _pid_num(p):
    m = re.search(r'(\d+)', str(p.get('pio_id','')))
    return int(m.group(1)) if m else 9999

fondateurs.sort(key=_pid_num)
rows = []
for ordre, p in enumerate(fondateurs, start=1):
    pid = str(p.get('pio_id','')).strip()
    insts = inst_by_pio.get(pid, [])
    date_inst, ville = '', ''
    if insts:
        sorted_i = sorted(insts, key=lambda x: str(x.get('date_installation','') or 'zzz'))
        date_inst = str(sorted_i[0].get('date_installation','')).strip()
        ville = str(sorted_i[0].get('localisation_precise','')).strip()
    raison_sociale = str(p.get('nom','')).strip() if str(p.get('client_type','')).strip().lower() == 'structure' else ''
    territoire = str(p.get('territoire','')).strip() or str(p.get('pays','')).strip()
    comment = SANDRINE_RECO_COMMENT.get(pid, '')
    rows.append([
        ordre,
        str(p.get('nom','')).strip(),
        str(p.get('prenom','')).strip(),
        raison_sociale,
        ville,
        territoire,
        str(p.get('email','')).strip(),
        str(p.get('telephone','')).strip(),
        date_inst,
        comment,
        pid,
        'matched',
    ])

start_line = svc.append_in_formatted_zone('00_Fondateurs', rows, n_cols=12)
print(f"  ✅ {len(rows)} fondateurs écrits à partir de L{start_line}")

svc.log_event('rectif_fondateurs_2026-06-16', result='OK',
              message=f'Restauration: {len(fondateurs)} fondateurs (anciens + recos Sandrine)')
print("\n=== TERMINÉ ===")
