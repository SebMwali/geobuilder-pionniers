"""purge_pionniers.py — Opération destructive de nettoyage du Sheet
"La Famille des Pionniers".

Plan (validé par utilisateur le 2026-06-17) :

GROUPE A — Mise à jour statut → "Revendu"
  • PIO-1019 (Goachet SABRINA)
  • PIO-1027 (Guerrini Eric)
  • PIO-1053 (Grimault)

LACOMBE (pio_id="xx") → renommé en PIO-1029, statut "Revendu"
  • Propagation dans 02_Installations + 05_Maintenances

GROUPE B — Suppression complète
  • PIO-1012, PIO-1057, PIO-1070, PIO-1076, PIO-1078, PIO-1086
  • Lignes supprimées dans : 01_Pionniers, 02_Installations, 05_Maintenances
  • Fichiers GH Pages supprimés : passeport, certificats, portail, cartes,
    badges (fondateur/ambassadeur/super), pages de signature ambassadeur

15 LIGNES VIDES dans 01_Pionniers → supprimées

Log final dans 08_Automations_Log.

Usage:
    python purge_pionniers.py --dry-run   # simulation
    python purge_pionniers.py --execute   # exécution réelle
"""
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv
load_dotenv()

from services.sheets_service import get_sheets_service  # noqa: E402
from services.github_service import get_github_service  # noqa: E402


# === Configuration ===
GROUP_A_REVENDU = ["PIO-1019", "PIO-1027", "PIO-1053"]
LACOMBE_OLD_ID = "xx"
LACOMBE_NEW_ID = "PIO-1029"
GROUP_B_DELETE = ["PIO-1012", "PIO-1057", "PIO-1070", "PIO-1076", "PIO-1078", "PIO-1086"]

# Chemins GitHub Pages à supprimer par pio_id (et install_id si applicable)
def gh_paths_for(pio_id: str, install_id: str | None) -> list[str]:
    paths = [
        f"docs/pionniers/{pio_id}/index.html",
        f"docs/certificats/pionnier/{pio_id}.html",
        f"docs/cartes/{pio_id}.html",
        f"docs/ambassadeurs/{pio_id}.html",
        f"docs/badges/ambassadeur/{pio_id}.html",
        f"docs/badges/super-ambassadeur/{pio_id}.html",
        f"docs/badges/fondateur/{pio_id}.html",
        f"docs/attestations/ambassadeur/{pio_id}.html",
    ]
    if install_id:
        paths.extend([
            f"docs/passeports/{install_id}/index.html",
            f"docs/certificats/garantie/{install_id}.html",
        ])
    return paths


def main():
    if "--execute" not in sys.argv:
        print("⚠️  Mode dry-run par défaut. Pour exécuter, ajouter --execute.")
        dry_run = True
    else:
        dry_run = False
        print("🔴 MODE EXÉCUTION — opérations destructives en cours.")

    sheets = get_sheets_service()
    gh = get_github_service()

    # --- Phase 0 : Récupération des données ---
    pios = sheets.read_all("pionniers")
    insts = sheets.read_all("installations")

    # Index installations par pio_id pour récupérer install_id
    inst_by_pio = {}
    for r in insts:
        pid = str(r.get("pio_id", "")).strip()
        if pid:
            inst_by_pio.setdefault(pid, []).append(r)

    actions = []
    timestamp = datetime.now(timezone.utc).isoformat()

    # =====================================================
    # PHASE 1 : Groupe A — Update statut → "Revendu"
    # =====================================================
    print("\n[1/5] Groupe A — Mise à jour statut → 'Revendu'")
    for pid in GROUP_A_REVENDU:
        idx = sheets.find_row_index_by("pionniers", "pio_id", pid)
        if not idx:
            print(f"  ⚠️  {pid} non trouvé dans 01_Pionniers")
            continue
        old = next((p for p in pios if str(p.get("pio_id")) == pid), {})
        old_status = old.get("statut", "?")
        print(f"  {pid}: statut '{old_status}' → 'Revendu' (row {idx})")
        if not dry_run:
            sheets.update_cell("pionniers", idx, "statut", "Revendu")
        actions.append(f"A:{pid} statut→Revendu (était '{old_status}')")
        time.sleep(0.3)

    # =====================================================
    # PHASE 2 : Lacombe — renommage pio_id xx → PIO-1029
    # =====================================================
    print(f"\n[2/5] Lacombe — pio_id '{LACOMBE_OLD_ID}' → '{LACOMBE_NEW_ID}'")
    idx_pio = sheets.find_row_index_by("pionniers", "pio_id", LACOMBE_OLD_ID)
    if idx_pio:
        print(f"  01_Pionniers row {idx_pio}: pio_id → {LACOMBE_NEW_ID}, statut → 'Revendu'")
        if not dry_run:
            sheets.update_cell("pionniers", idx_pio, "pio_id", LACOMBE_NEW_ID)
            time.sleep(0.3)
            sheets.update_cell("pionniers", idx_pio, "statut", "Revendu")
            time.sleep(0.3)
        actions.append(f"LACOMBE pio_id xx→{LACOMBE_NEW_ID}, statut→Revendu")
    else:
        print("  ⚠️  Lacombe non trouvé dans 01_Pionniers")

    # Propager dans 02_Installations
    while True:
        idx_inst = sheets.find_row_index_by("installations", "pio_id", LACOMBE_OLD_ID)
        if not idx_inst:
            break
        print(f"  02_Installations row {idx_inst}: pio_id → {LACOMBE_NEW_ID}")
        if not dry_run:
            sheets.update_cell("installations", idx_inst, "pio_id", LACOMBE_NEW_ID)
            time.sleep(0.3)
        else:
            break  # En dry-run on évite la boucle infinie
        actions.append(f"LACOMBE install pio_id xx→{LACOMBE_NEW_ID}")

    # Propager dans 05_Maintenances
    while True:
        idx_m = sheets.find_row_index_by("maintenances", "pio_id", LACOMBE_OLD_ID)
        if not idx_m:
            break
        print(f"  05_Maintenances row {idx_m}: pio_id → {LACOMBE_NEW_ID}")
        if not dry_run:
            sheets.update_cell("maintenances", idx_m, "pio_id", LACOMBE_NEW_ID)
            time.sleep(0.3)
        else:
            break
        actions.append(f"LACOMBE maintenance pio_id xx→{LACOMBE_NEW_ID}")

    # =====================================================
    # PHASE 3 : Groupe B — Suppression complète
    # =====================================================
    print(f"\n[3/5] Groupe B — Suppression complète ({len(GROUP_B_DELETE)} pionniers)")

    # Pour chaque tab, on collecte d'abord TOUS les row indices à supprimer,
    # puis on les trie en descendant et on supprime (préserve les indices).
    for tab_key in ["pionniers", "installations", "maintenances"]:
        ws = sheets.get_worksheet(tab_key)
        rows_to_delete = []
        records = sheets.read_all(tab_key)
        for i, rec in enumerate(records, start=2):  # +2 car header row=1
            pid = str(rec.get("pio_id", "")).strip()
            if pid in GROUP_B_DELETE:
                rows_to_delete.append(i)
        # Sort descending pour préserver les indices
        rows_to_delete.sort(reverse=True)
        print(f"  {tab_key}: {len(rows_to_delete)} ligne(s) à supprimer (rows {rows_to_delete})")
        if not dry_run:
            for ri in rows_to_delete:
                ws.delete_rows(ri)
                actions.append(f"B:{tab_key} delete row {ri}")
                time.sleep(0.5)

    # Suppression GH Pages
    print(f"\n[3.5/5] Suppression fichiers GH Pages")
    for pid in GROUP_B_DELETE:
        install_ids = [str(r.get("install_id", "")).strip()
                       for r in inst_by_pio.get(pid, [])
                       if r.get("install_id")]
        all_inst = install_ids if install_ids else [None]
        for iid in all_inst:
            paths = gh_paths_for(pid, iid)
            for p in paths:
                if dry_run:
                    print(f"  [dry] DELETE {p}")
                else:
                    try:
                        ok = gh.delete_file(p, f"chore: purge {pid} from GH Pages")
                        if ok:
                            print(f"  ✅ DELETE {p}")
                            actions.append(f"B:gh delete {p}")
                        time.sleep(0.4)
                    except Exception as e:
                        print(f"  ⚠️  Erreur DELETE {p}: {e}")

    # =====================================================
    # PHASE 4 : Nettoyage des 15 lignes vides dans 01_Pionniers
    # =====================================================
    print(f"\n[4/5] Nettoyage des lignes vides dans 01_Pionniers")
    ws_p = sheets.get_worksheet("pionniers")
    empty_rows = []
    pios_fresh = sheets.read_all("pionniers")
    for i, rec in enumerate(pios_fresh, start=2):
        pid = str(rec.get("pio_id", "")).strip()
        nom = str(rec.get("nom", "")).strip()
        prenom = str(rec.get("prenom", "")).strip()
        email = str(rec.get("email", "")).strip()
        # Considérée vide si pio_id ET nom ET prenom ET email tous vides
        if not pid and not nom and not prenom and not email:
            empty_rows.append(i)
    empty_rows.sort(reverse=True)
    print(f"  {len(empty_rows)} ligne(s) vide(s) (rows {empty_rows})")
    if not dry_run:
        for ri in empty_rows:
            ws_p.delete_rows(ri)
            actions.append(f"CLEAN: delete empty row {ri} in pionniers")
            time.sleep(0.5)

    # =====================================================
    # PHASE 5 : Log dans 08_Automations_Log
    # =====================================================
    print(f"\n[5/5] Log de l'opération dans 08_Automations_Log")
    log_row = [
        timestamp,
        "purge_pionniers",
        f"GroupA={len(GROUP_A_REVENDU)}, Lacombe→{LACOMBE_NEW_ID}, "
        f"GroupB={len(GROUP_B_DELETE)} deleted, EmptyRows={len(empty_rows)} cleaned",
        "OK" if not dry_run else "DRY-RUN",
        "; ".join(actions[:50]),
    ]
    if not dry_run:
        try:
            sheets.append_row("logs", log_row)
            print(f"  ✅ Log ajouté")
        except Exception as e:
            print(f"  ⚠️  Log échoué: {e}")
    else:
        print(f"  [dry] LOG: {log_row}")

    print(f"\n=== Résumé ===")
    print(f"Actions: {len(actions)}")
    print(f"Mode: {'DRY-RUN' if dry_run else 'EXÉCUTION'}")


if __name__ == "__main__":
    main()
