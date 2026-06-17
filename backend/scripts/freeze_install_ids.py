"""freeze_install_ids.py — Option D : restaure les install_id ORIGINAUX
(d'avant la suppression du Groupe B) et les gèle en valeurs statiques.

Suppressions effectuées le 2026-06-17 (rows originales du Sheet) :
  [14, 58, 70, 76, 78, 86]

Pour chaque row actuelle R, l'install_id ORIGINAL est calculé en trouvant
la row O telle que O - nb_suppressions_avant(O) == R.

Idempotent : si une cellule contient déjà une valeur statique (pas de formule),
elle est laissée telle quelle.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv
load_dotenv()

from services.sheets_service import get_sheets_service  # noqa: E402


# Rows originales (avant suppression) des 6 pio_id du Groupe B
DELETED_ORIGINAL_ROWS = [14, 58, 70, 76, 78, 86]


def original_row(current_row: int, deletions=DELETED_ORIGINAL_ROWS) -> int:
    """Calcule la row d'origine (avant les suppressions) à partir de la row actuelle."""
    o = current_row
    while True:
        offset = sum(1 for d in deletions if d <= o)
        if o - offset == current_row:
            return o
        o += 1


def main():
    dry = "--execute" not in sys.argv
    print(f"Mode: {'DRY-RUN' if dry else 'EXECUTE'}")

    sheets = get_sheets_service()
    ws = sheets.get_worksheet("installations")

    # Récupère toutes les valeurs (formules + valeurs)
    headers = ws.row_values(1)
    iid_col = headers.index("install_id") + 1  # 1-based
    if iid_col != 1:
        print(f"⚠️ Attention: install_id n'est pas en colonne A (col={iid_col})")

    all_values = ws.get_all_values()
    total_rows = len(all_values)
    print(f"Total rows (header inclus): {total_rows}")

    # Récupère aussi les formules pour identifier celles déjà figées
    formula_col = ws.col_values(iid_col, value_render_option='FORMULA')

    updates = []
    skipped = 0
    for current_row in range(2, total_rows + 1):
        cell_val = formula_col[current_row - 1] if current_row - 1 < len(formula_col) else ""
        # Si déjà figée (pas de formule), on skip
        if not str(cell_val).startswith("="):
            skipped += 1
            continue
        orig_row = original_row(current_row)
        orig_iid = f"INST-{orig_row + 1998}"
        # Range A{current_row} (colonne install_id)
        range_a1 = f"A{current_row}"  # iid_col=1 = colonne A
        updates.append({"range": range_a1, "values": [[orig_iid]]})

    print(f"Cellules à figer : {len(updates)}")
    print(f"Cellules déjà figées (skipped) : {skipped}")
    print(f"\nÉchantillon des 10 premiers changements :")
    for u in updates[:10]:
        print(f"  {u['range']} → {u['values'][0][0]}")
    print(f"...")
    print(f"Échantillon des 5 derniers :")
    for u in updates[-5:]:
        print(f"  {u['range']} → {u['values'][0][0]}")

    if dry:
        print("\n[DRY-RUN] Aucune modification. Relancer avec --execute pour appliquer.")
        return

    # Batch update via gspread
    print(f"\n→ Application du batch_update ({len(updates)} cellules)...")
    ws.batch_update(updates, value_input_option="USER_ENTERED")
    print(f"✅ {len(updates)} install_id figés à leur valeur ORIGINALE.")


if __name__ == "__main__":
    main()
