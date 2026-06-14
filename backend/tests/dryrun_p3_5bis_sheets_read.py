"""
P3.5 bis — Lecture seule des structures Google Sheets (version enrichie).

GARANTIES TECHNIQUES :
- Aucun append_row()
- Aucun update_cell()
- Aucun push GitHub
- Aucun email
- Uniquement : ws.row_values, ws.get_all_values, ss.worksheets, ws.cell  (lecture)

COMPLÉMENTS demandés :
  (1) Liste exhaustive des onglets réels du classeur
  (2) Position exacte (A1) des 4 compteurs dans 04_Parametres
  (3) Détection des colonnes URL existantes + échantillon de valeurs pour
      vérifier la convention de chemin GitHub Pages historiquement utilisée
"""
import os
import re
import sys
from pathlib import Path
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / ".env")

from services.sheets_service import get_sheets_service, TABS  # noqa: E402


# ---------------------------------------------------------------------------
# Spec : ce que le backend va ÉCRIRE (ordre exact des valeurs dans append_row)
# Source : /app/backend/server.py (_process_livraison) au commit P3.2.
# ---------------------------------------------------------------------------
EXPECTED = {
    "pionniers": [
        "pio_id", "nom", "prenom", "email", "telephone",
        "territoire", "pays", "date_creation", "statut", "badge", "url_portail",
    ],
    "installations": [
        "install_id", "pio_id", "numero_serie", "produit",
        "date_installation", "localisation", "garantie_fin", "url_passeport",
    ],
    "documents": [
        "doc_id", "pio_id", "type", "url", "date_creation",
    ],
    "parametres": ["Compteurs", "Valeur Actuelle"],
    "maintenances": [
        "maint_id", "install_id", "pio_id", "type", "date",
        "technicien", "rapport", "pdf",
    ],
    "logs": ["timestamp", "level", "source", "message", "payload"],
}

REQUIRED_COUNTERS = ["Pionnier ID", "Installation ID", "Maintenance ID", "Document ID"]
URL_KEYWORDS = ("url", "lien", "link")


def _normalize(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    return s.strip().lower().replace(" ", "_").replace("-", "_")


def _col_letter(idx_0based: int) -> str:
    """Convertit 0,1,2,... en A,B,C,...,Z,AA,..."""
    result = ""
    n = idx_0based
    while True:
        result = chr(ord("A") + n % 26) + result
        n = n // 26 - 1
        if n < 0:
            return result


# ===========================================================================
# MAIN
# ===========================================================================
def main() -> int:
    if not os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip():
        print("❌ GOOGLE_SERVICE_ACCOUNT_JSON est VIDE dans backend/.env")
        return 2

    sheets = get_sheets_service()
    try:
        ss = sheets._get_spreadsheet()
    except Exception as e:
        print(f"❌ Impossible d'ouvrir le Sheet : {e}")
        return 3

    print("=" * 78)
    print("P3.5 bis — Audit lecture seule")
    print(f"Sheet     : {ss.title!r}")
    print(f"Sheet ID  : {ss.id}")
    print("=" * 78)

    global_status = "OK"

    # ======================================================================
    # (1) LISTE COMPLÈTE DES ONGLETS DU CLASSEUR
    # ======================================================================
    print()
    print("━" * 78)
    print("1) ONGLETS RÉELLEMENT PRÉSENTS DANS LE CLASSEUR")
    print("━" * 78)
    try:
        all_ws = ss.worksheets()
    except Exception as e:
        print(f"  ❌ Impossible de lister les onglets : {e}")
        return 4

    print(f"  {'#':>2}  {'Titre onglet':40}  {'gid':>10}  {'rows':>5}  {'cols':>4}")
    print(f"  {'─' * 2}  {'─' * 40}  {'─' * 10}  {'─' * 5}  {'─' * 4}")
    real_tab_names = []
    for i, ws in enumerate(all_ws, 1):
        title = ws.title
        real_tab_names.append(title)
        print(f"  {i:>2}  {title:40}  {ws.id:>10}  {ws.row_count:>5}  {ws.col_count:>4}")

    print()
    print("  Correspondance avec ce que le backend attend (TABS) :")
    for key, name in TABS.items():
        if name in real_tab_names:
            print(f"    ✅ {key:15} → {name!r} présent")
        else:
            print(f"    ⚠️  {key:15} → {name!r} ABSENT du classeur")
            global_status = "NOK"

    # Onglets en plus côté Sheet ?
    extras = [t for t in real_tab_names if t not in TABS.values()]
    if extras:
        print()
        print("  ⚠️  Onglets présents dans le Sheet mais inconnus du backend :")
        for t in extras:
            print(f"     • {t}")

    # ======================================================================
    # (2) ENTÊTES DES 6 ONGLETS BACKEND
    # ======================================================================
    print()
    print("━" * 78)
    print("2) ENTÊTES — comparaison Attendu (backend) vs Réel (Sheet)")
    print("━" * 78)

    headers_by_tab = {}  # pour réutilisation au point (3)

    for tab_key in ["pionniers", "installations", "documents", "parametres", "maintenances", "logs"]:
        tab_name = TABS[tab_key]
        if tab_name not in real_tab_names:
            print(f"\n  ⏭  {tab_name} — onglet absent, skip")
            continue
        ws = ss.worksheet(tab_name)
        try:
            real_headers = ws.row_values(1)
        except Exception as e:
            print(f"\n  ❌ {tab_name} — erreur lecture row_values(1) : {e}")
            global_status = "NOK"
            continue
        headers_by_tab[tab_key] = real_headers

        expected = EXPECTED[tab_key]
        n = max(len(expected), len(real_headers))
        all_ok = True
        print(f"\n  ━━━ {tab_name} ━━━")
        print(f"    {'Col':>3}  {'Attendu (backend)':32}  {'Réel (Sheet)':32}  Statut")
        print(f"    {'─' * 3}  {'─' * 32}  {'─' * 32}  ──────")
        for i in range(n):
            exp = expected[i] if i < len(expected) else "—"
            real = real_headers[i] if i < len(real_headers) else "—"
            if exp == "—" or real == "—":
                st = "❌"
                all_ok = False
            else:
                st = "✅" if _normalize(exp) == _normalize(real) else "⚠️"
                if st == "⚠️":
                    all_ok = False
            col_letter = _col_letter(i)
            print(f"    {col_letter:>3}  {exp:32.32}  {real:32.32}  {st}")
        if not all_ok:
            global_status = "NOK"

    # ======================================================================
    # (3) POSITION EXACTE DES 4 COMPTEURS dans 04_Parametres
    # ======================================================================
    print()
    print("━" * 78)
    print("3) 04_Parametres — POSITION EXACTE DES 4 COMPTEURS")
    print("━" * 78)
    try:
        ws = ss.worksheet(TABS["parametres"])
        all_rows = ws.get_all_values()
        if not all_rows:
            print("  ❌ Onglet vide")
            global_status = "NOK"
        else:
            headers = all_rows[0]
            # Localiser colonnes "Compteurs" et "Valeur Actuelle"
            col_libelle_idx = None
            col_valeur_idx = None
            for i, h in enumerate(headers):
                n = _normalize(h)
                if n == "compteurs":
                    col_libelle_idx = i
                if n in ("valeur_actuelle", "valeur"):
                    col_valeur_idx = i
            print(f"  Colonne 'Compteurs'       : {_col_letter(col_libelle_idx) if col_libelle_idx is not None else 'INTROUVABLE'}")
            print(f"  Colonne 'Valeur Actuelle' : {_col_letter(col_valeur_idx) if col_valeur_idx is not None else 'INTROUVABLE'}")
            if col_libelle_idx is None or col_valeur_idx is None:
                global_status = "NOK"
            else:
                # Format VERTICAL explicite (un bloc par compteur)
                for c in REQUIRED_COUNTERS:
                    found_row = None
                    for r_idx, row in enumerate(all_rows[1:], start=2):
                        if col_libelle_idx < len(row) and row[col_libelle_idx].strip() == c:
                            found_row = r_idx
                            break
                    print()
                    if found_row is None:
                        print(f"  {c}")
                        print("    Cellule libellé : —")
                        print("    Cellule valeur  : —")
                        print("    Valeur actuelle : ❌ MANQUANT")
                        global_status = "NOK"
                    else:
                        val = all_rows[found_row - 1][col_valeur_idx] if col_valeur_idx < len(all_rows[found_row - 1]) else ""
                        lib_cell = f"{_col_letter(col_libelle_idx)}{found_row}"
                        val_cell = f"{_col_letter(col_valeur_idx)}{found_row}"
                        print(f"  {c}")
                        print(f"    Cellule libellé : {lib_cell}")
                        print(f"    Cellule valeur  : {val_cell}")
                        print(f"    Valeur actuelle : {val!r}")
    except Exception as e:
        print(f"  ❌ Erreur : {e}")
        global_status = "NOK"

    # ======================================================================
    # (4) COLONNES URL réellement utilisées dans 01/02/03
    #     → DERNIÈRE LIGNE NON VIDE (convention historique la plus récente)
    # ======================================================================
    print()
    print("━" * 78)
    print("4) COLONNES URL — convention historique la plus récente")
    print("   (01_Pionniers / 02_Installations / 03_Documents)")
    print("━" * 78)
    for tab_key in ["pionniers", "installations", "documents"]:
        tab_name = TABS[tab_key]
        if tab_key not in headers_by_tab:
            print(f"\n  ⏭  {tab_name} — pas d'entêtes lus, skip")
            continue
        headers = headers_by_tab[tab_key]
        url_cols = []
        for i, h in enumerate(headers):
            n = _normalize(h)
            if any(k in n for k in URL_KEYWORDS):
                url_cols.append((i, h))

        print(f"\n  ━━━ {tab_name} ━━━")
        if not url_cols:
            print("    (aucune colonne contenant url/lien/link dans l'entête)")
            continue
        ws = ss.worksheet(tab_name)
        try:
            data = ws.get_all_values()
        except Exception as e:
            print(f"    ❌ erreur lecture : {e}")
            continue
        rows = data[1:]  # skip header

        for idx, hname in url_cols:
            col_letter = _col_letter(idx)
            # Dernière ligne où la cellule de cette colonne est non vide
            last_row_num = None
            last_value = None
            for offset in range(len(rows) - 1, -1, -1):
                row = rows[offset]
                if idx < len(row):
                    v = row[idx].strip()
                    if v:
                        last_row_num = offset + 2  # +2 car header=1 et offset 0-based
                        last_value = v
                        break
            print(f"    Colonne {col_letter} ({hname!r}) :")
            if last_row_num is None:
                print("      (colonne vide)")
            else:
                print(f"      Dernière ligne non vide : {col_letter}{last_row_num}")
                print(f"      Valeur                  : {last_value}")

    # ======================================================================
    # CONCLUSION
    # ======================================================================
    print()
    print("=" * 78)
    print(f"STATUT GLOBAL : {global_status}")
    print("=" * 78)
    if global_status == "NOK":
        print("⚠️  Divergences détectées → STOP avant P3.6.")
        return 1
    print("✅ Structures alignées. P3.6 envisageable après votre validation.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
