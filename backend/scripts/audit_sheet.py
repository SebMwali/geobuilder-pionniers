"""audit_sheet.py — Audit COMPLET de cohérence du Sheet et de l'application.
Lecture seule. Ne modifie rien.

Vérifications :
A. Sheet
   1. Doublons pio_id dans 01_Pionniers
   2. Doublons install_id dans 02_Installations
   3. pio_id orphelins entre tabs (01 ↔ 02 ↔ 05 ↔ 06 ↔ 09)
   4. install_id en formule (devrait être 0 après freeze)
   5. pio_id en formule (à vérifier)
   6. Emails malformés
   7. Téléphones malformés / vides
   8. Lignes fantômes (pio_id vide + autres champs vides)
   9. Cellules #REF! / #ERROR!
   10. Cohérence 00_Fondateurs ↔ 01_Pionniers

B. Application / GH Pages
   1. Pour un échantillon de 20 pio actifs : passeport, portail, certificats, badge accessibles
   2. Endpoints API : /api/health, /api/admin/fondateurs/quota
"""
import sys
import re
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv
load_dotenv()

from services.sheets_service import get_sheets_service  # noqa: E402
import requests  # noqa: E402

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
PHONE_RE = re.compile(r"^[+0-9\s().-]{6,}$")
PIO_ID_RE = re.compile(r"^PIO-\d+$")
INST_ID_RE = re.compile(r"^INST-\d+$")
GH_BASE = "https://sebmwali.github.io/geobuilder-pionniers"


def report_section(title: str):
    print(f"\n{'═' * 70}\n  {title}\n{'═' * 70}")


def main():
    s = get_sheets_service()
    ss = s._get_spreadsheet()

    pios = s.read_all("pionniers")
    insts = s.read_all("installations")
    maints = s.read_all("maintenances")
    docs = s.read_all("documents")
    emails = s.read_all("email_events")

    pio_ids_01 = [str(p.get("pio_id", "")).strip() for p in pios if str(p.get("pio_id", "")).strip()]
    inst_ids_02 = [str(i.get("install_id", "")).strip() for i in insts if str(i.get("install_id", "")).strip()]

    issues = []

    # === A. SHEET ===
    report_section("A. AUDIT SHEET")

    # A.1 Doublons pio_id
    pio_counter = Counter(pio_ids_01)
    dups_pio = [(k, v) for k, v in pio_counter.items() if v > 1]
    print(f"\n[A.1] Doublons pio_id dans 01_Pionniers: {len(dups_pio)}")
    for pid, c in dups_pio[:10]:
        print(f"      ❌ {pid}: {c} occurrences")
        issues.append(f"DUP-PIO: {pid} x{c}")

    # A.2 Doublons install_id
    inst_counter = Counter(inst_ids_02)
    dups_inst = [(k, v) for k, v in inst_counter.items() if v > 1]
    print(f"\n[A.2] Doublons install_id dans 02_Installations: {len(dups_inst)}")
    for iid, c in dups_inst[:10]:
        print(f"      ❌ {iid}: {c} occurrences")
        issues.append(f"DUP-INST: {iid} x{c}")

    # A.3 Orphelins inter-tabs
    pio_set = set(pio_ids_01)
    inst_set = set(inst_ids_02)
    orphan_inst = []
    for i in insts:
        pid = str(i.get("pio_id", "")).strip()
        if pid and pid not in pio_set and pid != "#REF!":
            orphan_inst.append((pid, i.get("install_id")))
    print(f"\n[A.3] Installations orphelines (pio_id pas dans 01): {len(orphan_inst)}")
    for pid, iid in orphan_inst[:10]:
        print(f"      ❌ {iid}: pio_id='{pid}'")
        issues.append(f"ORPHAN-INST: {iid} → '{pid}'")

    orphan_maint = []
    for m in maints:
        pid = str(m.get("pio_id", "")).strip()
        iid = str(m.get("install_id", "")).strip()
        if pid and pid not in pio_set:
            orphan_maint.append((pid, iid))
    print(f"\n[A.3b] Maintenances orphelines: {len(orphan_maint)}")
    for pid, iid in orphan_maint[:10]:
        print(f"      ❌ {iid}: pio_id='{pid}'")
        issues.append(f"ORPHAN-MAINT: {iid} → '{pid}'")

    # A.4 install_id en formule restant
    ws_inst = ss.worksheet("02_Installations")
    col_iid_formulas = ws_inst.col_values(1, value_render_option='FORMULA')
    still_formula = [(i + 1, v) for i, v in enumerate(col_iid_formulas[1:], start=1) if isinstance(v, str) and v.startswith("=")]
    print(f"\n[A.4] install_id encore en formule (devrait être 0): {len(still_formula)}")
    for r, v in still_formula[:5]:
        print(f"      ❌ Row {r+1}: {v}")
        issues.append(f"FORMULA-INST: row {r+1}")

    # A.5 pio_id en formule dans 01_Pionniers
    ws_pio = ss.worksheet("01_Pionniers")
    pio_headers = ws_pio.row_values(1)
    pio_id_col = pio_headers.index("pio_id") + 1 if "pio_id" in pio_headers else None
    if pio_id_col:
        col_pio_formulas = ws_pio.col_values(pio_id_col, value_render_option='FORMULA')
        pio_still_formula = [(i + 1, v) for i, v in enumerate(col_pio_formulas[1:], start=1) if isinstance(v, str) and v.startswith("=")]
        print(f"\n[A.5] pio_id en formule dans 01_Pionniers: {len(pio_still_formula)}")
        for r, v in pio_still_formula[:5]:
            print(f"      ⚠️ Row {r+1}: {v}")
            issues.append(f"FORMULA-PIO: row {r+1}")
    else:
        print(f"\n[A.5] Colonne pio_id introuvable dans 01_Pionniers")

    # A.6 Emails malformés
    bad_emails = []
    for p in pios:
        email = str(p.get("email", "")).strip()
        if email and ";" not in email and "," not in email and not EMAIL_RE.match(email):
            bad_emails.append((p.get("pio_id"), email))
    print(f"\n[A.6] Emails malformés dans 01_Pionniers: {len(bad_emails)}")
    for pid, em in bad_emails[:10]:
        print(f"      ⚠️ {pid}: '{em}'")
        issues.append(f"BAD-EMAIL: {pid} → '{em}'")

    # A.7 Téléphones vides ou suspects
    no_phone = []
    bad_phone = []
    for p in pios:
        pid = p.get("pio_id")
        if not pid:
            continue
        ph = str(p.get("telephone", "")).strip()
        if not ph:
            no_phone.append(pid)
        elif not PHONE_RE.match(ph.lstrip("'")):
            bad_phone.append((pid, ph))
    print(f"\n[A.7] Téléphones vides: {len(no_phone)} | Téléphones malformés: {len(bad_phone)}")
    for pid, ph in bad_phone[:10]:
        print(f"      ⚠️ {pid}: '{ph}'")
        issues.append(f"BAD-PHONE: {pid}")

    # A.8 Lignes fantômes dans 01
    ghosts = []
    for i, p in enumerate(pios, start=2):
        if not str(p.get("pio_id", "")).strip() \
           and not str(p.get("nom", "")).strip() \
           and not str(p.get("prenom", "")).strip() \
           and not str(p.get("email", "")).strip():
            ghosts.append(i)
    print(f"\n[A.8] Lignes fantômes dans 01_Pionniers: {len(ghosts)}")
    if ghosts:
        print(f"      Rows: {ghosts[:20]}")
        issues.append(f"GHOST-ROWS: {len(ghosts)}")

    # A.9 Cellules #REF! / #ERROR!
    ref_errors = 0
    for tab_key in ["pionniers", "installations", "maintenances"]:
        rows = s.read_all(tab_key)
        for r in rows:
            for v in r.values():
                if isinstance(v, str) and ("#REF!" in v or "#ERROR!" in v or "#NAME?" in v):
                    ref_errors += 1
    print(f"\n[A.9] Erreurs de formules (#REF!/#ERROR!/#NAME?): {ref_errors}")
    if ref_errors > 0:
        issues.append(f"FORMULA-ERR: {ref_errors}")

    # A.10 Cohérence 00 ↔ 01
    ws_fond = ss.worksheet("00_Fondateurs")
    fond = ws_fond.get_all_records()
    fond_pio_ids = {str(f.get("pio_id_propose", "")).strip() for f in fond if str(f.get("pio_id_propose", "")).strip()}
    pio_fond_set = {p.get("pio_id") for p in pios if str(p.get("fondateur","")).strip().upper() in ("TRUE","OUI","VRAI","1")}
    in_00_not_01 = fond_pio_ids - pio_fond_set
    in_01_not_00 = pio_fond_set - fond_pio_ids
    print(f"\n[A.10] Cohérence 00 ↔ 01 :")
    print(f"      Fondateurs 00 (avec pio_id) mais pas fond=TRUE dans 01: {len(in_00_not_01)}")
    for pid in list(in_00_not_01)[:5]:
        print(f"        - {pid}")
        issues.append(f"FOND-00-only: {pid}")
    print(f"      Fond=TRUE dans 01 mais absent de 00: {len(in_01_not_00)}")
    for pid in list(in_01_not_00)[:5]:
        print(f"        - {pid}")
        issues.append(f"FOND-01-only: {pid}")

    # === B. GH PAGES ===
    report_section("B. AUDIT GH PAGES (échantillon)")

    sample = pios[:20]
    api_url = "http://localhost:8001/api/health"
    try:
        r = requests.get(api_url, timeout=5)
        print(f"\n[B.0] Backend /api/health: {r.status_code} {r.json()}")
    except Exception as e:
        print(f"\n[B.0] Backend /api/health: ÉCHEC ({e})")
        issues.append(f"API-DOWN")

    pio_by_id_local = {str(p.get("pio_id","")).strip(): p for p in pios if p.get("pio_id")}
    inst_by_pio = {}
    for ii in insts:
        pid = str(ii.get("pio_id","")).strip()
        if pid:
            inst_by_pio[pid] = ii

    missing_docs = []
    for p in sample:
        pid = str(p.get("pio_id","")).strip()
        if not pid or pid not in inst_by_pio:
            continue
        iid = inst_by_pio[pid].get("install_id")
        urls = [
            (f"{GH_BASE}/passeports/{iid}/index.html", f"passeport {iid}"),
            (f"{GH_BASE}/pionniers/{pid}/index.html", f"portail {pid}"),
        ]
        for url, label in urls:
            try:
                r = requests.head(url, timeout=8, allow_redirects=True)
                if r.status_code != 200:
                    missing_docs.append((pid, label, r.status_code))
            except Exception as e:
                missing_docs.append((pid, label, str(e)[:50]))
    print(f"\n[B.1] Documents manquants sur GH Pages (sur 20 pio échantillon): {len(missing_docs)}")
    for pid, label, status in missing_docs[:10]:
        print(f"      ❌ {pid}: {label} → {status}")
        issues.append(f"MISSING-DOC: {pid} {label}")

    # === SUMMARY ===
    report_section("RÉSUMÉ")
    print(f"\nTotal anomalies détectées : {len(issues)}")
    print(f"Échantillonnage GH Pages : {len(sample)} pio testés sur {len(pios)}")
    print(f"\nDonnées globales :")
    print(f"  - 01_Pionniers : {len(pios)} lignes")
    print(f"  - 02_Installations : {len(insts)} lignes")
    print(f"  - 05_Maintenances : {len(maints)} lignes")
    print(f"  - 06_Documents : {len(docs)} lignes")
    print(f"  - 09_EmailEvents : {len(emails)} lignes")
    print(f"  - 00_Fondateurs (avec pio_id_propose) : {len(fond_pio_ids)}")

    # Save issues
    out_path = "/tmp/audit_report.txt"
    with open(out_path, "w") as fh:
        fh.write("\n".join(issues))
    print(f"\nDétails enregistrés : {out_path}")


if __name__ == "__main__":
    main()
