"""Rattrapage : marque welcome_email_sent=true pour les 156 PIO_IDs envoyés."""
import sys
from dotenv import load_dotenv
load_dotenv('/app/backend/.env')
sys.path.insert(0, '/app/backend')
from services.sheets_service import get_sheets_service

with open('/tmp/sent_pio_ids.txt') as f:
    pio_ids = [l.strip() for l in f if l.strip()]

sh = get_sheets_service()
ok, fail = 0, 0
for pid in pio_ids:
    try:
        idx = sh.find_row_index_by("pionniers", "pio_id", pid)
        if idx:
            sh.update_cell("pionniers", idx, "welcome_email_sent", "true")
            ok += 1
            print(f"  ✅ {pid} (row {idx})")
        else:
            fail += 1
            print(f"  ❌ {pid} not found")
    except Exception as e:
        fail += 1
        print(f"  ❌ {pid}: {e}")

print(f"\n🏁 OK={ok} FAIL={fail} TOTAL={len(pio_ids)}")
