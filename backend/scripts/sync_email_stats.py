"""
Agrège les events Resend (`09_EmailEvents`) et écrit les stats dans `01_Pionniers`.

Ajoute/met à jour 5 colonnes dans 01_Pionniers :
  Y  email_delivered    (true/false/'')
  Z  email_opens        (entier)
  AA email_clicks       (entier)
  AB email_bounced      (true/false/'')
  AC last_event_at      (ISO UTC du dernier event)

USAGE:
  python3 scripts/sync_email_stats.py            # tous les pio_id présents dans EmailEvents
  python3 scripts/sync_email_stats.py --campaign welcome   # uniquement template bienvenue_livraison
"""
import argparse
import sys
from collections import defaultdict
from datetime import datetime
from dotenv import load_dotenv
load_dotenv('/app/backend/.env')
sys.path.insert(0, '/app/backend')

from services.sheets_service import get_sheets_service

NEW_HEADERS = ["email_delivered", "email_opens", "email_clicks",
               "email_bounced", "last_event_at"]
# Cols Y, Z, AA, AB, AC (indices 0-based : 24, 25, 26, 27, 28)
START_COL_IDX = 24


def ensure_headers(ws):
    """Garantit que les headers Y..AC existent."""
    headers = ws.row_values(1)
    needed = START_COL_IDX + len(NEW_HEADERS)
    if len(headers) < needed:
        headers += [""] * (needed - len(headers))
    changed = False
    for i, h in enumerate(NEW_HEADERS):
        if headers[START_COL_IDX + i] != h:
            headers[START_COL_IDX + i] = h
            changed = True
    if changed:
        ws.update("A1", [headers])
        print(f"  ✅ Headers mis à jour : {NEW_HEADERS}")


def aggregate(events, campaign_filter=None):
    """events → {pio_id: {delivered, opens, clicks, bounced, last_event_at}}"""
    agg = defaultdict(lambda: {"delivered": False, "opens": 0, "clicks": 0,
                               "bounced": False, "last_event_at": ""})
    for e in events:
        pio_id = (e.get("pio_id") or "").strip()
        if not pio_id:
            continue
        if campaign_filter == "welcome":
            tpl = (e.get("template") or "").strip().lower()
            if tpl != "bienvenue_livraison":
                continue
        ev = (e.get("event") or "").strip().lower()
        ts = (e.get("timestamp_utc") or "").strip()
        row = agg[pio_id]
        if ev.endswith("delivered"):
            row["delivered"] = True
        elif ev.endswith("opened"):
            row["opens"] += 1
        elif ev.endswith("clicked"):
            row["clicks"] += 1
        elif ev.endswith("bounced"):
            row["bounced"] = True
        elif ev.endswith("complained"):
            row["bounced"] = True  # plainte = bounce logique
        if ts > row["last_event_at"]:
            row["last_event_at"] = ts
    return agg


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--campaign", choices=["welcome"], default=None,
                   help="Filtre uniquement les events de cette campagne.")
    args = p.parse_args()

    sh = get_sheets_service()
    ws = sh.get_worksheet("pionniers")
    ensure_headers(ws)

    print("📥 Lecture 09_EmailEvents...")
    events = sh.read_all("email_events")
    print(f"   {len(events)} events bruts")

    agg = aggregate(events, args.campaign)
    print(f"📊 {len(agg)} pio_id distincts avec events"
          + (f" (campagne welcome)" if args.campaign else ""))

    # Indexation pio_id → row index
    print("📥 Lecture 01_Pionniers...")
    pionniers = sh.read_all("pionniers")
    pio_to_row = {(r.get("pio_id") or "").strip(): i + 2 for i, r in enumerate(pionniers)}

    # Batch update: une plage Y:AC par pionnier
    updates = []
    matched = 0
    for pio_id, stats in agg.items():
        row = pio_to_row.get(pio_id)
        if not row:
            continue
        matched += 1
        updates.append({
            "range": f"Y{row}:AC{row}",
            "values": [[
                "true" if stats["delivered"] else "",
                str(stats["opens"]) if stats["opens"] else "",
                str(stats["clicks"]) if stats["clicks"] else "",
                "true" if stats["bounced"] else "",
                stats["last_event_at"],
            ]],
        })

    print(f"📝 {matched} lignes à mettre à jour dans 01_Pionniers...")
    if updates:
        ws.batch_update(updates, value_input_option="USER_ENTERED")

    # Stats résumé
    total_delivered = sum(1 for s in agg.values() if s["delivered"])
    total_opened = sum(1 for s in agg.values() if s["opens"] > 0)
    total_clicked = sum(1 for s in agg.values() if s["clicks"] > 0)
    total_bounced = sum(1 for s in agg.values() if s["bounced"])

    print()
    print("=" * 60)
    print("  📊 RÉSUMÉ CAMPAGNE" + (f" — welcome" if args.campaign else ""))
    print("=" * 60)
    print(f"  Destinataires uniques avec ≥1 event : {len(agg)}")
    print(f"  ✅ Délivrés    : {total_delivered}")
    if total_delivered:
        print(f"  👁️ Ouverts     : {total_opened} ({100*total_opened/total_delivered:.1f}%)")
        print(f"  🖱️ Cliqués     : {total_clicked} ({100*total_clicked/total_delivered:.1f}%)")
    print(f"  ⚠️ Bounce/plainte: {total_bounced}")
    print(f"\n  🕒 Synchronisé : {datetime.utcnow().isoformat()}Z")


if __name__ == "__main__":
    main()
