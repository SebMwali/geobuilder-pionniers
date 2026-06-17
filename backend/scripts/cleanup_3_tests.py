"""cleanup_3_tests.py — Suppression des 3 pionniers/installations/maintenances de test."""
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv
load_dotenv()

from services.sheets_service import get_sheets_service  # noqa: E402

PIO_IDS = ["PIO-1215", "PIO-1216", "PIO-1217", "PIO-1218"]
INSTALL_IDS = ["INST-2219", "INST-2220", "INST-2221", "INST-2222"]


def main():
    s = get_sheets_service()

    # 1. Pionniers (par ordre décroissant pour ne pas décaler)
    print("→ Suppression pionniers…")
    ws_pio = s.get_worksheet("pionniers")
    indices = []
    for pid in PIO_IDS:
        idx = s.find_row_index_by("pionniers", "pio_id", pid)
        if idx:
            indices.append((idx, pid))
    for idx, pid in sorted(indices, key=lambda x: -x[0]):
        ws_pio.delete_rows(idx)
        print(f"  ✓ {pid} (ligne {idx}) supprimé")
        time.sleep(1.5)

    # 2. Installations
    print("\n→ Suppression installations…")
    ws_inst = s.get_worksheet("installations")
    indices = []
    for iid in INSTALL_IDS:
        idx = s.find_row_index_by("installations", "install_id", iid)
        if idx:
            indices.append((idx, iid))
    for idx, iid in sorted(indices, key=lambda x: -x[0]):
        ws_inst.delete_rows(idx)
        print(f"  ✓ {iid} (ligne {idx}) supprimée")
        time.sleep(1.5)

    # 3. Maintenances (cherche par pio_id de test)
    print("\n→ Suppression maintenances…")
    ws_maint = s.get_worksheet("maintenances")
    all_rows = ws_maint.get_all_values()
    headers = all_rows[0]
    pio_col_idx = headers.index("pio_id")
    to_delete = []
    for i, row in enumerate(all_rows[1:], start=2):
        if pio_col_idx < len(row) and row[pio_col_idx] in PIO_IDS:
            to_delete.append((i, row[pio_col_idx], row[headers.index("maintenance_id")] if "maintenance_id" in headers else ""))
    for idx, pid, mid in sorted(to_delete, key=lambda x: -x[0]):
        ws_maint.delete_rows(idx)
        print(f"  ✓ maintenance {mid} (ligne {idx}, {pid}) supprimée")
        time.sleep(1.5)

    print("\n✅ Cleanup terminé.")


if __name__ == "__main__":
    main()
