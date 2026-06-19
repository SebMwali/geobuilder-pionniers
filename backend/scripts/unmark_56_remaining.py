"""Dé-marque welcome_email_sent (vide la cellule) pour les 56 PIO_IDs bloqués par
le quota Resend du jour. À lancer demain matin avant de relancer mass_mailing_send.py."""
import sys
from dotenv import load_dotenv
load_dotenv('/app/backend/.env')
sys.path.insert(0, '/app/backend')
from services.sheets_service import get_sheets_service

with open('/tmp/pio_to_unmark.txt') as f:
    pio_ids = [l.strip() for l in f if l.strip()]

sh = get_sheets_service()
ok, fail = 0, 0
for pid in pio_ids:
    try:
        idx = sh.find_row_index_by("pionniers", "pio_id", pid)
        if idx:
            sh.update_cell("pionniers", idx, "welcome_email_sent", "")
            ok += 1
            print(f"  ↩️ {pid} (row {idx}) dé-marqué")
        else:
            fail += 1
            print(f"  ❌ {pid} not found")
    except Exception as e:
        fail += 1
        print(f"  ❌ {pid}: {e}")

print(f"\n🏁 Dé-marqués : OK={ok} FAIL={fail} TOTAL={len(pio_ids)}")
