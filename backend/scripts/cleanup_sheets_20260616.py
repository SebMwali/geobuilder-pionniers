"""cleanup_sheets_20260616.py — Nettoyage Sheet selon décisions utilisateur 16/06/2026.

Actions exécutées (dans cet ordre) :
  1. Supprimer les 4 installations corrompues #REF! (INST-2108, 2119, 2147, 2148)
  2. Harmoniser 'MAYOTTE' → 'Mayotte' dans 00_Fondateurs.territoire
  3. Décocher fondateur=true pour 5 pionniers (PIO-1063, 1064, 1069, 1101, 1104)
     + nettoyer communaute_statut si "Fondateur"
  4. Réparer les 21 #ERROR! téléphone dans 00_Fondateurs (préfixe ' devant +)

IDEMPOTENT : peut être rejoué sans dommage (les actions sont des update_cell sur
clés stables, pas des append).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv
load_dotenv()

from services.sheets_service import get_sheets_service  # noqa: E402


def main():
    s = get_sheets_service()
    print("=" * 70)
    print("CLEANUP SHEETS — décisions utilisateur 16/06/2026")
    print("=" * 70)

    # ──────────────────────────────────────────────────────────────────────
    # ACTION 1. Supprimer les 4 installations #REF!
    # ──────────────────────────────────────────────────────────────────────
    print("\n1️⃣  Suppression des 4 installations #REF! dans 02_Installations")
    ws_inst = s.get_worksheet("installations")
    bad_iids = ["INST-2108", "INST-2119", "INST-2147", "INST-2148"]
    # On collecte les indices à supprimer (en partant du bas pour ne pas décaler)
    indices_to_delete = []
    for iid in bad_iids:
        idx = s.find_row_index_by("installations", "install_id", iid)
        if idx:
            indices_to_delete.append((idx, iid))
        else:
            print(f"   ⚠️  {iid} introuvable (déjà supprimé ?)")
    for idx, iid in sorted(indices_to_delete, key=lambda x: -x[0]):
        ws_inst.delete_rows(idx)
        print(f"   ✓ Ligne {idx} supprimée ({iid})")

    # ──────────────────────────────────────────────────────────────────────
    # ACTION 2. Harmoniser MAYOTTE → Mayotte
    # ──────────────────────────────────────────────────────────────────────
    print("\n2️⃣  Harmonisation territoire MAYOTTE → Mayotte dans 00_Fondateurs")
    ws_fond = s.get_worksheet("00_Fondateurs")
    headers_fond = ws_fond.row_values(1)
    col_terr_idx = headers_fond.index("territoire") + 1
    rows_fond = ws_fond.get_all_values()
    fixed = 0
    for row_num, row in enumerate(rows_fond[1:], start=2):
        if col_terr_idx - 1 < len(row):
            v = row[col_terr_idx - 1].strip()
            if v == "MAYOTTE":
                ws_fond.update_cell(row_num, col_terr_idx, "Mayotte")
                fixed += 1
    print(f"   ✓ {fixed} cellules normalisées")

    # ──────────────────────────────────────────────────────────────────────
    # ACTION 3. Décocher fondateur=true pour 5 pionniers
    # ──────────────────────────────────────────────────────────────────────
    print("\n3️⃣  Décocher fondateur=true pour 5 pionniers extra dans 01_Pionniers")
    pio_to_uncheck = ["PIO-1063", "PIO-1064", "PIO-1069", "PIO-1101", "PIO-1104"]
    ws_pio = s.get_worksheet("pionniers")
    headers_pio = ws_pio.row_values(1)
    print(f"   (colonnes : {headers_pio[:15]})")
    for pid in pio_to_uncheck:
        idx = s.find_row_index_by("pionniers", "pio_id", pid)
        if not idx:
            print(f"   ⚠️  {pid} introuvable")
            continue
        # Décocher fondateur (col K = "fondateur")
        if "fondateur" in headers_pio:
            s.update_cell("pionniers", idx, "fondateur", "false")
        # Nettoyer communaute_statut si == "Fondateur"
        if "communaute_statut" in headers_pio:
            current = ws_pio.cell(idx, headers_pio.index("communaute_statut") + 1).value or ""
            if "Fondateur" in current:
                # On vide seulement si c'était purement "Fondateur" (sans autre rôle)
                new_val = current.replace("Fondateur · ", "").replace(" · Fondateur", "").replace("Fondateur", "").strip(" ·")
                s.update_cell("pionniers", idx, "communaute_statut", new_val)
        print(f"   ✓ {pid} (ligne {idx}) : fondateur=false")

    # ──────────────────────────────────────────────────────────────────────
    # ACTION 4. Réparer les #ERROR! téléphone dans 00_Fondateurs
    # ──────────────────────────────────────────────────────────────────────
    print("\n4️⃣  Réparation des #ERROR! téléphone dans 00_Fondateurs (préfixe ')")
    col_tel_idx = headers_fond.index("telephone") + 1
    fixed_tel = 0
    # Recharge le sheet (à cause des modifs précédentes)
    rows_fond2 = ws_fond.get_all_values()
    for row_num, row in enumerate(rows_fond2[1:], start=2):
        if col_tel_idx - 1 >= len(row):
            continue
        # On récupère la formule brute via UNFORMATTED_VALUE
        cell_a1 = f"{chr(64 + col_tel_idx)}{row_num}"
        try:
            # Lecture FORMULA = renvoie la valeur saisie (avec +262... brut)
            raw = ws_fond.acell(cell_a1, value_render_option="FORMULA").value or ""
        except Exception:
            raw = ""
        if isinstance(raw, str) and raw.startswith("+") and len(raw) > 1:
            # Force texte avec apostrophe (gspread interprète le ' devant)
            new_val = raw  # texte tel-quel, on passe value_input_option=RAW
            ws_fond.update(cell_a1, [[new_val]], value_input_option="RAW")
            fixed_tel += 1
            if fixed_tel <= 5 or fixed_tel % 5 == 0:
                print(f"   ✓ {cell_a1} fixé : {raw}")
    print(f"   ✓ Total téléphones réparés : {fixed_tel}")

    print("\n" + "=" * 70)
    print("✅ CLEANUP TERMINÉ")
    print("=" * 70)


if __name__ == "__main__":
    main()
