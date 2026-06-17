"""fix_ambassadeurs_badges.py — Pour chaque pionnier ambassadeur=true,
pousse le badge Ambassadeur (s'il manque sur GH Pages) et régénère son passeport
pour que le slot Ambassadeur apparaisse en "Acquis" (déverrouillé).
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
    sheets = get_sheets_service()
    gh = get_github_service()

    # Cache read_all pour quota Sheets
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

    amb_pios = [p for p in pios
                if str(p.get("ambassadeur", "")).strip().upper() in ("TRUE", "OUI", "VRAI", "1")
                and str(p.get("pio_id", "")).strip() in inst_by_pio]

    print(f"→ {len(amb_pios)} pionniers Ambassadeurs à corriger")

    ok = ko = 0
    for i, p in enumerate(amb_pios, 1):
        pid = str(p.get("pio_id", "")).strip()
        inst = inst_by_pio[pid]
        try:
            pushed = _regenerate_all_docs_for_pioneer(p, inst, sheets, gh)
            print(f"  [{i}/{len(amb_pios)}] {pid} → {len(pushed)} docs")
            ok += 1
        except Exception as e:
            print(f"  [{i}/{len(amb_pios)}] {pid} → KO : {e}")
            ko += 1
        time.sleep(0.4)

    print(f"\n✅ OK={ok} KO={ko}")


if __name__ == "__main__":
    main()
