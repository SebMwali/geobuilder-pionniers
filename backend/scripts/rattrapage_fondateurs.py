"""rattrapage_fondateurs.py — Création de 4 nouveaux Pionniers Fondateurs + correction CLEMENT.

Mode RATTRAPAGE : aucun envoi d'email (toutes les comm sont mockées en no-op).
Tous les autres effets (sheets + GH Pages docs) sont exécutés normalement.

Actions :
  1. PIO-XXX BERTRAND Stéphane   (NS HR88C23LFR1135, 15/02/2025)
  2. PIO-XXX APAYA Teddy         (NS HR88C22KFR0401, 01/08/2023)  — update 00 row 84
  3. PIO-XXX Michon Adrien       (NS EA60L23JFR0060S, 27/03/2024) — update 00 row 19
  4. PIO-XXX Mohamed Khaled      (NS HR88C23LFR1040, 01/09/2023)  — add slot #99
  5. PIO-XXX THORAL Agnès        (reassign INST-2200, NS HR88C23LFR1043, 05/05/2025) — slot #98
  6. Correction date CLEMENT PIO-1077 INST-2075 : 11/03/2026 → 07/08/2024
"""
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv
load_dotenv()


async def _noop(*args, **kwargs):
    return None


def disable_emails():
    """Patch en mémoire la fonction d'envoi pour ne rien envoyer pendant le rattrapage."""
    import services.email_service as es
    es.send_email_mock = _noop
    import server
    server.send_email_mock = _noop


async def create_pionnier(payload_dict: dict) -> dict:
    from server import LivraisonInput, _process_livraison
    payload = LivraisonInput(**payload_dict)
    return await _process_livraison(payload)


async def reassign_install_to_thoral(sheets, gh, new_pio_id: str):
    """Étape spéciale pour THORAL : INST-2200 (actuellement attribué à PIO-1077
    CLEMENT) est réassigné à THORAL avec sa propre date."""
    from server import _regenerate_all_docs_for_pioneer

    inst_idx = sheets.find_row_index_by("installations", "install_id", "INST-2200")
    if not inst_idx:
        raise RuntimeError("INST-2200 introuvable")

    # Update install row
    sheets.update_cell("installations", inst_idx, "pio_id", new_pio_id)
    time.sleep(0.5)
    sheets.update_cell("installations", inst_idx, "date_installation", "05/05/2025")
    time.sleep(0.5)
    sheets.update_cell("installations", inst_idx, "localisation_precise",
                       "312 rue Combo Mtsachiwa, Mtsangamouji")
    time.sleep(0.5)
    sheets.update_cell("installations", inst_idx, "nom_client", "THORAL Agnès")
    time.sleep(0.5)

    # Régénère tous les docs pour THORAL
    pio_row = sheets.find_row_by("pionniers", "pio_id", new_pio_id)
    inst_row = sheets.find_row_by("installations", "install_id", "INST-2200")
    pushed = _regenerate_all_docs_for_pioneer(pio_row, inst_row, sheets, gh)
    return list(pushed.keys())


async def correct_clement_date(sheets):
    """Met à jour la date d'installation de CLEMENT PIO-1077 INST-2075."""
    inst_idx = sheets.find_row_index_by("installations", "install_id", "INST-2075")
    if not inst_idx:
        return False
    sheets.update_cell("installations", inst_idx, "date_installation", "07/08/2024")
    return True


async def add_to_00_fondateurs(ws_fond, slot_ordre: int, nom: str, prenom: str, email: str,
                                telephone: str, date_install: str, new_pio_id: str,
                                comm: str = ""):
    """Ajoute / met à jour une ligne dans 00_Fondateurs."""
    rows = ws_fond.get_all_values()
    headers = rows[0]
    # Map header → col index (1-based)
    COL = {h: i + 1 for i, h in enumerate(headers)}

    # Trouver la row du slot ordre
    target_row = None
    for i, r in enumerate(rows[1:], start=2):
        if str(r[COL["ordre"] - 1]).strip() == str(slot_ordre):
            target_row = i
            break

    if target_row is None:
        # Ajouter une nouvelle ligne en bas
        ws_fond.append_row([
            slot_ordre, nom, prenom, "", "Mayotte", "Mayotte",
            email, telephone, date_install, comm, new_pio_id, "matched"
        ], value_input_option="USER_ENTERED")
        return f"appended ordre={slot_ordre}"

    # Sinon update les cellules
    updates = [
        (target_row, COL["Nom"], nom),
        (target_row, COL["Prénom"], prenom),
        (target_row, COL["territoire"], "MAYOTTE"),
        (target_row, COL["ville"], "Mayotte"),
        (target_row, COL["email"], email),
        (target_row, COL["telephone"], telephone),
        (target_row, COL["date_installation_estimee"], date_install),
        (target_row, COL["commentaire"], comm),
        (target_row, COL["pio_id_propose"], new_pio_id),
        (target_row, COL["match_status"], "matched"),
    ]
    import gspread
    batch = [{"range": gspread.utils.rowcol_to_a1(r, c), "values": [[v]]} for r, c, v in updates]
    ws_fond.batch_update(batch, value_input_option="USER_ENTERED")
    return f"updated row {target_row}"


async def update_00_pio_propose(ws_fond, ordre: int, new_pio_id: str):
    """Met à jour seulement le pio_id_propose d'une ligne existante."""
    rows = ws_fond.get_all_values()
    headers = rows[0]
    COL = {h: i + 1 for i, h in enumerate(headers)}
    for i, r in enumerate(rows[1:], start=2):
        if str(r[COL["ordre"] - 1]).strip() == str(ordre):
            ws_fond.update_cell(i, COL["pio_id_propose"], new_pio_id)
            return i
    return None


async def main():
    disable_emails()

    from services.sheets_service import get_sheets_service
    from services.github_service import get_github_service
    sheets = get_sheets_service()
    gh = get_github_service()
    ss = sheets._get_spreadsheet()
    ws_fond = ss.worksheet("00_Fondateurs")

    new_pio_ids = {}

    # =====================================================
    # 1. BERTRAND Stéphane
    # =====================================================
    print("\n[1/6] BERTRAND Stéphane...")
    try:
        r = await create_pionnier({
            "nom": "BERTRAND", "prenom": "Stéphane",
            "email": "stephane.bertrand@mayotte.gouv.fr",
            "telephone": "",
            "territoire": "Mayotte", "pays": "France",
            "produit": "G30", "numero_serie": "HR88C23LFR1135",
            "date_installation": "15/02/2025",
            "fondateur": True,
            "report_id": "rattrapage-bertrand-2025-02",
        })
        new_pio_ids["BERTRAND"] = r["pio_id"]
        print(f"  ✅ {r['pio_id']} / {r['install_id']}")
        time.sleep(2)
    except Exception as e:
        print(f"  ❌ BERTRAND: {e}")

    # =====================================================
    # 2. APAYA Teddy
    # =====================================================
    print("\n[2/6] APAYA Teddy...")
    try:
        r = await create_pionnier({
            "nom": "APAYA", "prenom": "Teddy",
            "email": "teddy.apaya@sogea-mayotte.com",
            "telephone": "",
            "territoire": "Mayotte", "pays": "France",
            "produit": "G30", "numero_serie": "HR88C22KFR0401",
            "date_installation": "01/08/2023",
            "fondateur": True,
            "report_id": "rattrapage-apaya-2023-08",
        })
        new_pio_ids["APAYA"] = r["pio_id"]
        print(f"  ✅ {r['pio_id']} / {r['install_id']}")
        time.sleep(2)
    except Exception as e:
        print(f"  ❌ APAYA: {e}")

    # =====================================================
    # 3. Michon Adrien
    # =====================================================
    print("\n[3/6] Michon Adrien...")
    try:
        r = await create_pionnier({
            "nom": "Michon", "prenom": "Adrien",
            "email": "adrien@cc-petiteterre.fr",
            "telephone": "",
            "territoire": "Mayotte", "pays": "France",
            "produit": "G60", "numero_serie": "EA60L23JFR0060S",
            "date_installation": "27/03/2024",
            "fondateur": True,
            "report_id": "rattrapage-michon-2024-03",
        })
        new_pio_ids["MICHON"] = r["pio_id"]
        print(f"  ✅ {r['pio_id']} / {r['install_id']}")
        time.sleep(2)
    except Exception as e:
        print(f"  ❌ Michon: {e}")

    # =====================================================
    # 4. Mohamed Khaled
    # =====================================================
    print("\n[4/6] Mohamed Khaled...")
    try:
        r = await create_pionnier({
            "nom": "Mohamed", "prenom": "Khaled",
            "email": "contact.stn976@gmail.com",
            "telephone": "",
            "territoire": "Mayotte", "pays": "France",
            "produit": "G30", "numero_serie": "HR88C23LFR1040",
            "date_installation": "01/09/2023",
            "fondateur": True,
            "report_id": "rattrapage-mohamed-2023-09",
        })
        new_pio_ids["MOHAMED"] = r["pio_id"]
        print(f"  ✅ {r['pio_id']} / {r['install_id']}")
        time.sleep(2)
    except Exception as e:
        print(f"  ❌ Mohamed: {e}")

    # =====================================================
    # 5. THORAL Agnès — création + réassignation INST-2200
    # =====================================================
    print("\n[5/6] THORAL Agnès (création + réassignation INST-2200)...")
    try:
        # 5a. Créer la fiche pionnier seule (sans nouvelle install)
        from services.counter_service import increment_counter
        _, thoral_pio = increment_counter("pionnier")
        new_pio_ids["THORAL"] = thoral_pio
        from datetime import datetime, timezone
        now_iso = datetime.now(timezone.utc).isoformat()
        sheets.append_row("pionniers", [
            thoral_pio, "THORAL", "Agnès", "agnes.thoral@juradm.fr",
            "06 37 81 02 90", "France", "Mayotte", "", now_iso,
            "Pionnier", "true", "false", "Fondateur", "", "", "",
            "rattrapage", "livraison_complete", "false",  # welcome_email_sent=false (rattrapage)
            "", "", "",
        ])
        time.sleep(2)
        # 5b. Réassignation INST-2200
        pushed = await reassign_install_to_thoral(sheets, gh, thoral_pio)
        print(f"  ✅ {thoral_pio} / INST-2200 réassignée | docs régénérés: {len(pushed)}")
        time.sleep(2)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"  ❌ THORAL: {e}")

    # =====================================================
    # 6. Correction date CLEMENT
    # =====================================================
    print("\n[6/6] Correction date CLEMENT PIO-1077 INST-2075...")
    try:
        ok = await correct_clement_date(sheets)
        print(f"  ✅ Date corrigée à 07/08/2024" if ok else "  ⚠️ INST-2075 introuvable")
    except Exception as e:
        print(f"  ❌ CLEMENT: {e}")

    # =====================================================
    # 7. Mise à jour 00_Fondateurs
    # =====================================================
    print("\n[7/7] Mise à jour 00_Fondateurs...")

    # Update existing rows
    if "APAYA" in new_pio_ids:
        r = await update_00_pio_propose(ws_fond, 84, new_pio_ids["APAYA"])
        print(f"  ✅ Row 84 (APAYA) pio_id_propose → {new_pio_ids['APAYA']} (row {r})")
        time.sleep(1)
    if "MICHON" in new_pio_ids:
        r = await update_00_pio_propose(ws_fond, 19, new_pio_ids["MICHON"])
        print(f"  ✅ Row 19 (Michon) pio_id_propose → {new_pio_ids['MICHON']} (row {r})")
        time.sleep(1)

    # Add to empty slots 97, 98, 99
    if "BERTRAND" in new_pio_ids:
        r = await add_to_00_fondateurs(ws_fond, 97, "BERTRAND", "Stéphane",
                                        "stephane.bertrand@mayotte.gouv.fr", "",
                                        "15/02/2025", new_pio_ids["BERTRAND"],
                                        "Rattrapage 17/06/2026")
        print(f"  ✅ Slot 97 BERTRAND ({r})")
        time.sleep(1)
    if "THORAL" in new_pio_ids:
        r = await add_to_00_fondateurs(ws_fond, 98, "THORAL", "Agnès",
                                        "agnes.thoral@juradm.fr", "06 37 81 02 90",
                                        "05/05/2025", new_pio_ids["THORAL"],
                                        "Conjoint CLEMENT, GEA séparé, Rattrapage 17/06/2026")
        print(f"  ✅ Slot 98 THORAL ({r})")
        time.sleep(1)
    if "MOHAMED" in new_pio_ids:
        r = await add_to_00_fondateurs(ws_fond, 99, "Mohamed", "Khaled",
                                        "contact.stn976@gmail.com", "",
                                        "01/09/2023", new_pio_ids["MOHAMED"],
                                        "Rattrapage 17/06/2026")
        print(f"  ✅ Slot 99 Mohamed Khaled ({r})")
        time.sleep(1)

    # Log final
    from datetime import datetime, timezone
    sheets.append_row("logs", [
        datetime.now(timezone.utc).isoformat(),
        "rattrapage_4_fondateurs",
        f"BERTRAND={new_pio_ids.get('BERTRAND','?')}, APAYA={new_pio_ids.get('APAYA','?')}, "
        f"MICHON={new_pio_ids.get('MICHON','?')}, MOHAMED={new_pio_ids.get('MOHAMED','?')}, "
        f"THORAL={new_pio_ids.get('THORAL','?')}, CLEMENT date corrected",
        "OK",
        "Mode rattrapage (emails désactivés)",
    ])
    print("\n✅ Rattrapage terminé.")
    print(f"Récap: {new_pio_ids}")


if __name__ == "__main__":
    asyncio.run(main())
