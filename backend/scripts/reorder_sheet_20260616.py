"""Réordonnancement : déplace les lignes appendées vers la zone formatée du sheet.

01_Pionniers : L198-L211 → L151-L164 (puis vide L198-L211)
02_Installations : L263-L277 → L158-L172 (puis vide L263-L277)

Méthode : `ws.update(range, values)` met à jour valeurs SANS toucher au formatage
des cellules destination (qui ont déjà les dropdowns/couleurs configurés par Sandrine).
Puis `batch_clear` efface seulement les valeurs des lignes source.
"""
from __future__ import annotations
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / '.env')

from services.sheets_service import get_sheets_service

svc = get_sheets_service()

def move_block(tab_key: str, source_start: int, source_end: int, dest_start: int, n_cols: int):
    """Déplace n_rows × n_cols depuis source_start vers dest_start, préserve le format."""
    ws = svc.get_worksheet(tab_key)
    time.sleep(2)
    print(f"\n[{tab_key}] Read {source_start}-{source_end} ({source_end - source_start + 1} rows × {n_cols} cols)")

    from gspread.utils import rowcol_to_a1
    src_range = f"A{source_start}:{rowcol_to_a1(source_end, n_cols).rstrip('0123456789')}{source_end}"
    src_range = f"A{source_start}:{chr(ord('A') + n_cols - 1)}{source_end}"  # ex: A198:W211
    data = ws.get(src_range)
    print(f"   ↳ Read {len(data)} rows")
    time.sleep(2)

    # Padding : chaque ligne doit faire exactement n_cols colonnes
    padded = [(row + [""] * n_cols)[:n_cols] for row in data]

    n_rows = source_end - source_start + 1
    dest_end = dest_start + n_rows - 1
    dest_range = f"A{dest_start}:{chr(ord('A') + n_cols - 1)}{dest_end}"

    print(f"[{tab_key}] Write to {dest_range} (préserve format destination)")
    ws.update(dest_range, padded, value_input_option="USER_ENTERED")
    time.sleep(3)

    print(f"[{tab_key}] Clear source {src_range}")
    ws.batch_clear([src_range])
    time.sleep(2)
    print(f"[{tab_key}] ✅ done")


print("=== Réordonnancement 01_Pionniers ===")
# Header L1, existants L2-L150, zone vide L151-L197, appendés L198-L211 (14 lignes)
# 23 colonnes (A-W)
move_block("pionniers", source_start=198, source_end=211, dest_start=151, n_cols=23)

print("\n=== Réordonnancement 02_Installations ===")
# Header L1, existants L2-L157, zone vide L158-L262, appendés L263-L277 (15 lignes)
# 23 colonnes (A-W)
move_block("installations", source_start=263, source_end=277, dest_start=158, n_cols=23)

print("\n=== TERMINÉ ===")
svc.log_event("reordering_sheet_2026-06-16", result="OK",
              message="Lignes appendées remontées dans la zone formatée (01_Pionniers L151-L164, 02_Installations L158-L172)")
