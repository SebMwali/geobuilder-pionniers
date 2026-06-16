"""regenerate_all_pioneers.py — Régénération de MASSE de tous les documents HTML
des pionniers existants, et push sur GitHub Pages.

⚠️ AUCUN email envoyé.
⚠️ AUCUN write Google Sheets.

Lit 01_Pionniers et 02_Installations, puis pour chaque pio_id ayant au moins
une installation, régénère les 7 documents :
  passeport / certificat_pionnier / certificat_garantie / portail / badge
  + (si fondateur) ambassadeur + badge_fondateur

USAGE :
    cd /app/backend && python -m scripts.regenerate_all_pioneers [--limit N] [--start PIO-XXXX] [--dry-run]

Options :
    --limit N         Ne traite que les N premiers pio_id (utile pour tests).
    --start PIO-XXXX  Reprend depuis ce pio_id (utile en cas d'interruption).
    --dry-run         N'écrit rien sur GitHub, log seulement.
"""
import sys
import time
import argparse
from pathlib import Path

# Permet d'exécuter le script depuis n'importe où
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.sheets_service import get_sheets_service  # noqa: E402
from services.github_service import get_github_service  # noqa: E402
from server import _regenerate_all_docs_for_pioneer  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Régénération de masse pionniers")
    parser.add_argument("--limit", type=int, default=0, help="Limite nb de pio_id traités")
    parser.add_argument("--start", type=str, default="", help="Reprend depuis ce pio_id")
    parser.add_argument("--dry-run", action="store_true", help="Pas de push GitHub")
    parser.add_argument("--sleep", type=float, default=1.0, help="Pause entre pionniers (s)")
    args = parser.parse_args()

    print("=" * 70)
    print("REGENERATION MASSE — PIONNIERS GEOBUILDER")
    print("=" * 70)
    print(f"  limit   = {args.limit or '∞'}")
    print(f"  start   = {args.start or '(début)'}")
    print(f"  dry-run = {args.dry_run}")
    print(f"  sleep   = {args.sleep}s entre pionniers")
    print()

    sheets = get_sheets_service()
    gh = None if args.dry_run else get_github_service()

    # Patch read_all et find_row_by pour cacher les lectures (évite quota Sheets)
    _read_cache: dict = {}
    _orig_read_all = sheets.read_all

    def _cached_read_all(tab_key):
        if tab_key not in _read_cache:
            _read_cache[tab_key] = _orig_read_all(tab_key)
        return _read_cache[tab_key]

    sheets.read_all = _cached_read_all  # type: ignore[method-assign]
    print("→ Cache read_all activé\n")

    print("→ Lecture 01_Pionniers…")
    pio_rows = sheets.read_all("pionniers")
    print(f"  {len(pio_rows)} pionniers")

    print("→ Lecture 02_Installations…")
    inst_rows = sheets.read_all("installations")
    print(f"  {len(inst_rows)} installations")

    # Index installations par pio_id (1ère installation chronologique)
    inst_by_pio: dict[str, dict] = {}
    for r in inst_rows:
        pid = str(r.get("pio_id", "")).strip()
        if not pid:
            continue
        existing = inst_by_pio.get(pid)
        if existing is None:
            inst_by_pio[pid] = r
        else:
            # garde la plus ancienne (1ère installation)
            d_existing = str(existing.get("date_installation", "") or "zzz")
            d_new = str(r.get("date_installation", "") or "zzz")
            if d_new < d_existing:
                inst_by_pio[pid] = r

    # Filtrer pionniers avec install + appliquer start/limit
    todo = []
    started = (args.start == "")
    for p in pio_rows:
        pid = str(p.get("pio_id", "")).strip()
        if not pid:
            continue
        if not started:
            if pid == args.start:
                started = True
            else:
                continue
        if pid not in inst_by_pio:
            continue
        todo.append((p, inst_by_pio[pid]))

    if args.limit:
        todo = todo[: args.limit]

    print(f"→ {len(todo)} pionniers à régénérer\n")

    ok, ko = 0, 0
    errors: list[str] = []
    for i, (pio_row, install_row) in enumerate(todo, start=1):
        pid = str(pio_row.get("pio_id", "")).strip()
        iid = str(install_row.get("install_id", "")).strip()
        is_fond = str(pio_row.get("fondateur", "")).strip().upper() in ("TRUE", "OUI", "1", "VRAI")
        tag = " [FONDATEUR]" if is_fond else ""
        print(f"[{i:>3}/{len(todo)}] {pid} ({iid}){tag} …", end="", flush=True)

        if args.dry_run:
            print(" DRY-RUN ✓")
            ok += 1
            continue

        try:
            pushed = _regenerate_all_docs_for_pioneer(pio_row, install_row, sheets, gh)
            n_docs = len(pushed)
            print(f" OK ({n_docs} docs)")
            ok += 1
        except Exception as e:
            print(f" ❌ {e}")
            errors.append(f"{pid}: {e}")
            ko += 1

        time.sleep(args.sleep)

    print()
    print("=" * 70)
    print(f"TERMINE — OK: {ok} | KO: {ko}")
    print("=" * 70)
    if errors:
        print("\nErreurs :")
        for e in errors:
            print(f"  • {e}")


if __name__ == "__main__":
    main()
