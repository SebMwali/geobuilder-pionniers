"""Synchronisation des fondateurs avec la liste cible Sandrine (16/06/2026).

Étape 1 — Décocher fondateur=TRUE pour 62 pionniers hors liste
Étape 2 — Cocher fondateur=TRUE pour 23 pionniers de la liste cible
Étape 3 — Vider l'onglet 00_Fondateurs (lignes 2-72) en préservant le formatage
Étape 4 — Repopulater 00_Fondateurs avec les 29 fondateurs (+ colonne commentaire métier)
Étape 5 — Tagger PIO-1151 Tetrama : client_type=Structure
"""
from __future__ import annotations
import os, sys, json, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / '.env')

from services.sheets_service import get_sheets_service

svc = get_sheets_service()

# Liste cible Sandrine (29 fondateurs trouvés)
TARGET = {
    'PIO-1058': ('BOURCIER',   'Valérie',     'Travaille au collège de Chiconi - fait formations dans tous les collèges'),
    'PIO-1022': ('LARREGAIN',  '',            ''),
    'PIO-1016': ('REBOURS',    'Gaëtan',      'Chef chez TOTAL'),
    'PIO-1054': ('JAVAUDIN',   '',            'Médecine du travail'),
    'PIO-1207': ('LERICHE',    'Stéphane',    ''),
    'PIO-1202': ('KEISLER',    'Fernand',     "Pilote d'avion"),
    'PIO-1096': ('LEMARCHAND', '',            ''),
    'PIO-1077': ('CLEMENT',    'Olivier',     "Chef tribunal administratif - conjointe THORAL (cheffe conseil d'État)"),
    'PIO-1122': ('BERTHET',    'Tony',        ''),
    'PIO-1208': ('RASTAMI',    'Cedryann',    ''),
    'PIO-1130': ('LE DU',      'Sylvain',     'Médecin'),
    'PIO-1090': ('GUIBBERT',   'William',     ''),
    'PIO-1119': ('ANDAZA',     '',            "Chef d'un collège"),
    'PIO-1126': ('DUPRE',      'Guillaume',   "Chef établissement scolaire (DUPRE WESEKA Guillaume) - actif dans plusieurs assoc"),
    'PIO-1115': ('JARY',       'Fatoumina',   'FRANCE TRAVAIL'),
    'PIO-1094': ('JOSEPH',     '',            'FRANCE TRAVAIL'),
    'PIO-1051': ('STAHL',      'Anthony',     'Travaille chez Mayotte Incendie (équipé)'),
    'PIO-1120': ('BATARD',     'Nicolas',     'Très sympa'),
    'PIO-1065': ('ALI HAMISSI','Anassati',    'Mahorais - bouche à oreille'),
    'PIO-1129': ('HADRAMI',    'Nassaire',    'Mahorais - bouche à oreille'),
    'PIO-1066': ('ALI MARI',   'Sandati',     'Mahorais - bouche à oreille'),
    'PIO-1049': ('ALI HAMIDI', 'Sedji (Ali)', 'Mahorais - bouche à oreille'),
    'PIO-1052': ('SAINDOU',    'Fayadhui',    "Mahorais - bouche à oreille (SAINDOU M'SOILI)"),
    'PIO-1204': ('MADI',       'Idriss',      'Mahorais - bouche à oreille'),
    'PIO-1105': ('MROIVILI',   'Echati',      'Mahorais - bouche à oreille (MROIVILI Echati Moussa)'),
    'PIO-1111': ('BRAHIME',    'Rahamatou',   'Mahorais - bouche à oreille'),
    'PIO-1099': ('MARI',       'Soihibou',    'Mahorais - bouche à oreille'),
    'PIO-1098': ('MARI',       'Mambadi',     'Mahorais - bouche à oreille'),
    'PIO-1100': ('MARI',       'Toulaybi',    'Mahorais - bouche à oreille'),
}

# === LECTURE DE L'ÉTAT ACTUEL ===
print("Loading data...")
ws_pio = svc.get_worksheet('pionniers')
time.sleep(2)
all_vals = ws_pio.get_all_values()
header = all_vals[0]
col_pio = header.index('pio_id')      # 0
col_fond = header.index('fondateur')  # 11 (col L)
# Construire index pio_id → row_number
pio_to_row = {}
for i, row in enumerate(all_vals[1:], start=2):
    if row and row[col_pio].strip():
        pio_to_row[row[col_pio].strip()] = (i, row)

print(f"   {len(pio_to_row)} pionniers chargés, col fondateur = {col_fond} (lettre L)")

# Calculer les modifs
modifs = []  # liste de (row_number, value_str, label)

# Pionniers cibles → fondateur=TRUE
for pid in TARGET:
    if pid not in pio_to_row:
        print(f"   ⚠️ {pid} introuvable dans 01_Pionniers")
        continue
    row_num, row = pio_to_row[pid]
    cur = row[col_fond].strip().upper() if len(row) > col_fond else ''
    if cur in ('TRUE', 'OUI', '1', 'VRAI', 'YES'):
        continue  # déjà OK
    modifs.append((row_num, 'TRUE', f"{pid} ← TRUE"))

# Tous les autres fondateurs=TRUE actuels → fondateur=FALSE
for pid, (row_num, row) in pio_to_row.items():
    if pid in TARGET:
        continue
    cur = row[col_fond].strip().upper() if len(row) > col_fond else ''
    if cur in ('TRUE', 'OUI', '1', 'VRAI', 'YES'):
        modifs.append((row_num, 'FALSE', f"{pid} ← FALSE"))

print(f"\n=== Étape 1+2 — {len(modifs)} modifs fondateur ===")
# Batch update via batch_update
col_letter = chr(ord('A') + col_fond)
batch_data = [{'range': f'{col_letter}{rn}', 'values': [[v]]} for rn, v, _ in modifs]
if batch_data:
    ws_pio.batch_update(batch_data, value_input_option='USER_ENTERED')
    print(f"   ✅ {len(batch_data)} cellules fondateur mises à jour en 1 appel batch")
time.sleep(3)

# === Étape 3 — Vider 00_Fondateurs (lignes 2-72) ===
print("\n=== Étape 3 — Vider 00_Fondateurs ===")
ws_fond = svc.get_worksheet('00_Fondateurs')
time.sleep(2)
ws_fond.batch_clear(['A2:L72'])
time.sleep(2)
print("   ✅ lignes 2-72 vidées (formatage conservé)")

# === Étape 4 — Repopulater avec les 29 fondateurs cible ===
print("\n=== Étape 4 — Repopulater 00_Fondateurs ===")
# Lire installations pour récupérer date_installation et ville
inst = svc.read_all('installations')
inst_by_pio = {}
for r in inst:
    pid = str(r.get('pio_id','')).strip()
    if not pid or pid == '#REF!':
        continue
    inst_by_pio.setdefault(pid, []).append(r)

# Reread pio_cache au cas où
time.sleep(2)
pio_cache = svc.read_all('pionniers')
pio_by_id = {str(r.get('pio_id','')).strip(): r for r in pio_cache}

# Construire les lignes
rows = []
for ordre, (pid, (nom_target, prenom_target, commentaire)) in enumerate(TARGET.items(), start=1):
    p = pio_by_id.get(pid, {})
    insts = inst_by_pio.get(pid, [])
    date_inst = ''
    ville = ''
    if insts:
        sorted_i = sorted(insts, key=lambda x: str(x.get('date_installation','') or 'zzz'))
        date_inst = str(sorted_i[0].get('date_installation','')).strip()
        ville = str(sorted_i[0].get('localisation_precise','')).strip()
    nom = str(p.get('nom','')).strip() or nom_target
    prenom = str(p.get('prenom','')).strip() or prenom_target
    raison_sociale = nom if str(p.get('client_type','')).strip().lower() == 'structure' else ''
    territoire = str(p.get('territoire','')).strip() or str(p.get('pays','')).strip() or 'MAYOTTE'
    rows.append([
        ordre, nom, prenom, raison_sociale, ville, territoire,
        str(p.get('email','')).strip(), str(p.get('telephone','')).strip(),
        date_inst, commentaire, pid, 'matched',
    ])

start_line = svc.append_in_formatted_zone('00_Fondateurs', rows, n_cols=12)
print(f"   ✅ {len(rows)} lignes écrites à partir de L{start_line}")
time.sleep(3)

# === Étape 5 — Tetrama → client_type=Structure ===
print("\n=== Étape 5 — Tetrama PIO-1151 → client_type=Structure ===")
row_idx = svc.find_row_index_by('pionniers', 'pio_id', 'PIO-1151')
if row_idx:
    time.sleep(1.5)
    svc.update_cell('pionniers', row_idx, 'client_type', 'Structure')
    print(f"   ✅ PIO-1151 client_type=Structure")
else:
    print("   ⚠️ PIO-1151 introuvable")

# Log final
svc.log_event('sync_fondateurs_sandrine_2026-06-16',
              result='OK',
              message=f'62 décochés + 23 cochés + 29 lignes 00_Fondateurs + Tetrama=Structure')
print("\n=== TERMINÉ ===")
