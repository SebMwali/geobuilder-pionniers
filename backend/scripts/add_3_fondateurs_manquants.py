"""Création des 3 fondateurs manquants identifiés par Sandrine.

COLLE     - G30 - HR88C24AFR0088 - COMBANI - 14/02/25
BEGUIN    - G30 - HR88C24AFR0734 - 17/02/25
BEN ABDOU Soidri - G10 - ZL9510W23JFR013S - Chembenyoumba - 08/01/25

Méthode : utilise append_in_formatted_zone (règle R1).
"""
from __future__ import annotations
import sys, time
from datetime import datetime, timezone
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT / '.env')

from services.sheets_service import get_sheets_service
from services.counter_service import increment_counter

svc = get_sheets_service()
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")
SOURCE = "import_sandrine_2026-06-16_phase6"

# 3 nouveaux fondateurs
NEW_PIONEERS = [
    {
        'nom': 'COLLE', 'prenom': '', 'produit': 'G30', 'NS': 'HR88C24AFR0088',
        'ville': 'COMBANI', 'tel': "'07 70 21 03 20 / +33788861680",
        'date_install': '14/02/2025', 'commentaire_fondateur': '',
    },
    {
        'nom': 'BEGUIN', 'prenom': '', 'produit': 'G30', 'NS': 'HR88C24AFR0734',
        'ville': '', 'tel': '',
        'date_install': '17/02/2025', 'commentaire_fondateur': '',
    },
    {
        'nom': 'BEN ABDOU', 'prenom': 'Soidri', 'produit': 'G10', 'NS': 'ZL9510W23JFR013S',
        'ville': 'Chembenyoumba', 'tel': "'0639 69 70 37",
        'date_install': '08/01/2025', 'commentaire_fondateur': 'Mahorais - bouche à oreille',
    },
]

# === Construction des lignes 01_Pionniers (23 colonnes) ===
# Pré-incrémenter les compteurs
print("Incrément compteurs...")
pio_rows = []
inst_rows = []
mapping = []  # liste de (pio_id, install_id, info) pour 00_Fondateurs
for p in NEW_PIONEERS:
    _, pio_id = increment_counter("pionnier")
    time.sleep(1.5)
    _, install_id = increment_counter("installation")
    time.sleep(1.5)
    nom_complet = f"{p['prenom']} {p['nom']}".strip()
    # Ligne 01_Pionniers
    pio_rows.append([
        pio_id, p['NS'], p['nom'].upper(), p['prenom'], '', p['tel'],
        'FRANCE', 'MAYOTTE', 'Particulier', TODAY, 'Pionnier',
        'TRUE',  # fondateur=TRUE direct
        'FALSE', '', 'FALSE', 'FALSE', 'FALSE',
        SOURCE, '', 'FALSE', '', '', '',
    ])
    # Ligne 02_Installations
    inst_rows.append([
        install_id, pio_id, p['produit'], p['NS'],
        p['date_install'], '', 'MAYOTTE', '', 'active', 'true',
        nom_complet, '', '', '', p['ville'] or 'MAYOTTE',
        '', '', '', '', 'true', '', '', SOURCE,
    ])
    mapping.append({'pio_id': pio_id, 'install_id': install_id, 'p': p})
    print(f"  Préparé : {pio_id} / {install_id} → {p['nom']}")

# === Insertion en suivant la règle R1 ===
print(f"\nInsertion {len(pio_rows)} pionniers dans 01_Pionniers (à la suite)...")
start_pio = svc.append_in_formatted_zone('pionniers', pio_rows, n_cols=23)
print(f"  ✅ Écrits à partir de L{start_pio}")
time.sleep(3)

print(f"Insertion {len(inst_rows)} installations dans 02_Installations (à la suite)...")
start_inst = svc.append_in_formatted_zone('installations', inst_rows, n_cols=23)
print(f"  ✅ Écrites à partir de L{start_inst}")
time.sleep(3)

# === Ajout dans 00_Fondateurs (à la suite) ===
print("Ajout dans 00_Fondateurs (à la suite des 91 existants)...")
# Récupérer le prochain ordre
ws_f = svc.get_worksheet('00_Fondateurs')
time.sleep(2)
all_vals = ws_f.get_all_values()
last_ordre = 0
for r in all_vals[1:]:
    if r and r[0].strip().isdigit():
        last_ordre = max(last_ordre, int(r[0]))
print(f"  Dernier ordre actuel : {last_ordre}")

fond_rows = []
for i, m in enumerate(mapping, start=1):
    p = m['p']
    fond_rows.append([
        last_ordre + i,
        p['nom'].upper(),
        p['prenom'],
        '',                          # raison_sociale
        p['ville'],
        'MAYOTTE',
        '',                          # email
        p['tel'],
        p['date_install'],
        p['commentaire_fondateur'],
        m['pio_id'],
        'matched',
    ])

start_fond = svc.append_in_formatted_zone('00_Fondateurs', fond_rows, n_cols=12)
print(f"  ✅ Écrits dans 00_Fondateurs à partir de L{start_fond}")

svc.log_event('add_3_fondateurs_missing', result='OK',
              message=f'COLLE/BEGUIN/BEN ABDOU créés ({mapping[0]["pio_id"]}-{mapping[-1]["pio_id"]})')
print(f"\n=== TERMINÉ : 3 fondateurs créés ===")
for m in mapping:
    print(f"  {m['pio_id']} / {m['install_id']} : {m['p']['nom']} {m['p']['prenom']}")
