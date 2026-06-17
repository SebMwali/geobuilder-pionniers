"""fix_fondateurs_docs.py — Régénère les documents (portail + badge fondateur
+ passeport) de tous les pionniers `fondateur=true` pour appliquer :
  - le fix de cadrage du badge Fondateur (CSS @media)
  - le fix de cohérence portail/passeport (statut Ambassadeur "À signer" au lieu
    du faux "Acquis")

Usage:
    python fix_fondateurs_docs.py            # tous les fondateurs
    python fix_fondateurs_docs.py PIO-2025-005  # un seul (test)
"""
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv
load_dotenv()

from services.sheets_service import get_sheets_service  # noqa: E402
from services.github_service import get_github_service  # noqa: E402
from server import _regenerate_all_docs_for_pioneer  # noqa: E402


def main():
    target_pio = sys.argv[1] if len(sys.argv) > 1 else None
    sheets = get_sheets_service()
    gh = get_github_service()

    # Cache des reads pour économiser le quota Sheets
    _cache = {}
    orig = sheets.read_all
    def cached(t):
        if t not in _cache:
            _cache[t] = orig(t)
        return _cache[t]
    sheets.read_all = cached

    pios = sheets.read_all("pionniers")
    insts = sheets.read_all("installations")

    inst_by_pio = {}
    for r in insts:
        pid = str(r.get("pio_id", "")).strip()
        if not pid:
            continue
        if pid not in inst_by_pio:
            inst_by_pio[pid] = r
        else:
            d_e = str(inst_by_pio[pid].get("date_installation", "") or "zzz")
            d_n = str(r.get("date_installation", "") or "zzz")
            if d_n < d_e:
                inst_by_pio[pid] = r

    if target_pio:
        targets = [p for p in pios if str(p.get("pio_id", "")).strip() == target_pio]
        if not targets:
            print(f"❌ PIO {target_pio} introuvable")
            return
    else:
        targets = [p for p in pios
                   if str(p.get("fondateur", "")).strip().upper() in ("TRUE", "OUI", "VRAI", "1")
                   and str(p.get("pio_id", "")).strip() in inst_by_pio]

    print(f"→ {len(targets)} pionnier(s) à régénérer")

    ok = ko = 0
    for i, p in enumerate(targets, 1):
        pid = str(p.get("pio_id", "")).strip()
        if pid not in inst_by_pio:
            print(f"  [{i}/{len(targets)}] {pid} → KO : pas d'installation")
            ko += 1
            continue
        inst = inst_by_pio[pid]
        try:
            pushed = _regenerate_all_docs_for_pioneer(p, inst, sheets, gh)
            print(f"  [{i}/{len(targets)}] {pid} → {len(pushed)} docs OK")
            ok += 1
        except Exception as e:
            print(f"  [{i}/{len(targets)}] {pid} → KO : {e}")
            ko += 1
        time.sleep(0.4)

    print(f"\n✅ OK={ok} KO={ko}")


if __name__ == "__main__":
    main()
