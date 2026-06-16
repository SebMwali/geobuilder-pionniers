"""fix_telephones_only.py — Réparation #ERROR! téléphones (suite, batch).

Reprend les téléphones encore en #ERROR! dans 00_Fondateurs après la 1re tentative
(qui a hit le quota). Utilise batch_update pour minimiser les appels.
"""
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv
load_dotenv()

from services.sheets_service import get_sheets_service  # noqa: E402


def main():
    s = get_sheets_service()
    ws = s.get_worksheet("00_Fondateurs")
    headers = ws.row_values(1)
    col_tel_idx = headers.index("telephone") + 1
    col_letter = chr(64 + col_tel_idx)

    # 1 seul appel batch : récupère toutes les formules de la colonne H
    print(f"Lecture batch colonne {col_letter}…")
    rng = f"{col_letter}2:{col_letter}101"
    formula_resp = ws.batch_get([rng], value_render_option="FORMULA")
    formulas = formula_resp[0] if formula_resp else []

    # Identifier ce qui commence par + (= source du parse error)
    to_fix = []
    for i, row in enumerate(formulas, start=2):
        val = row[0] if row else ""
        if isinstance(val, str) and val.startswith("+") and len(val) > 1:
            to_fix.append((f"{col_letter}{i}", val))

    print(f"Téléphones à corriger : {len(to_fix)}")
    if not to_fix:
        print("✓ Rien à faire — tout est OK.")
        return

    # Update 1 par 1 avec sleep 1.2s pour rester sous 60 writes/min
    print("Mise à jour avec valeur RAW (force texte)…")
    fixed = 0
    for cell_a1, val in to_fix:
        try:
            # value_input_option=RAW interdit l'interprétation comme formule
            ws.update(values=[[val]], range_name=cell_a1, value_input_option="RAW")
            fixed += 1
            print(f"  ✓ {cell_a1} : {val}")
            time.sleep(1.2)
        except Exception as e:
            print(f"  ✗ {cell_a1} : {e}")
            time.sleep(5)
    print(f"\n✅ {fixed}/{len(to_fix)} téléphones réparés")


if __name__ == "__main__":
    main()
