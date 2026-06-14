"""
P3.5 bis — Lecture seule des structures Google Sheets.

GARANTIES TECHNIQUES :
- Aucun append_row()
- Aucun update_cell()
- Aucun push GitHub
- Aucun email
- Uniquement : worksheet.row_values(1) + ws.get_all_values() (lecture)

Pré-requis : GOOGLE_SERVICE_ACCOUNT_JSON doit être posé dans backend/.env
            avec un Service Account ayant accès en lecture au Sheet.
"""
import os
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
    "parametres": [
        "Compteurs", "Valeur Actuelle",
    ],
    "maintenances": [
        # NB: pas écrit par LIVRAISON, mais on vérifie quand même
        "maint_id", "install_id", "pio_id", "type", "date",
        "technicien", "rapport", "pdf",
    ],
    "logs": [
        "timestamp", "level", "source", "message", "payload",
    ],
}

# Compteurs requis dans 04_Parametres (colonne "Compteurs")
REQUIRED_COUNTERS = ["Pionnier ID", "Installation ID", "Maintenance ID", "Document ID"]


def _normalize(s: str) -> str:
    """Pour comparer des entêtes : minuscule + suppression accents + espaces ⇒ underscore."""
    import unicodedata
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    return s.strip().lower().replace(" ", "_").replace("-", "_")


def main() -> int:
    if not os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip():
        print("❌ GOOGLE_SERVICE_ACCOUNT_JSON est VIDE dans backend/.env")
        print("   Posez le JSON Service Account et relancez.")
        return 2

    sheets = get_sheets_service()
    try:
        ss = sheets._get_spreadsheet()
    except Exception as e:
        print(f"❌ Impossible d'ouvrir le Sheet : {e}")
        return 3

    print("=" * 78)
    print(f"P3.5 bis — Lecture des entêtes — Sheet : {ss.title!r}")
    print("=" * 78)

    global_status = "OK"
    rapports = []

    # 1. Entêtes des 6 onglets
    for tab_key in ["pionniers", "installations", "documents", "parametres", "maintenances", "logs"]:
        tab_name = TABS[tab_key]
        try:
            ws = ss.worksheet(tab_name)
            real_headers = ws.row_values(1)
        except Exception as e:
            rapports.append((tab_name, "ERROR", f"impossible de lire : {e}"))
            global_status = "NOK"
            continue

        expected = EXPECTED[tab_key]
        # Comparaison fine
        n = max(len(expected), len(real_headers))
        rows = []
        all_ok = True
        for i in range(n):
            exp = expected[i] if i < len(expected) else "—"
            real = real_headers[i] if i < len(real_headers) else "—"
            if exp == "—" or real == "—":
                status = "❌"
                all_ok = False
            else:
                # Comparaison souple : normalisation
                status = "✅" if _normalize(exp) == _normalize(real) else "⚠️"
                if status == "⚠️":
                    all_ok = False
            rows.append((i + 1, exp, real, status))

        rapports.append((tab_name, "OK" if all_ok else "NOK", rows))
        if not all_ok:
            global_status = "NOK"

    # 2. Affichage
    for tab_name, status, rows in rapports:
        print()
        print(f"━━━ {tab_name} ━━━  [{status}]")
        if status == "ERROR":
            print(f"  {rows}")
            continue
        print(f"  {'Col':>3}  {'Attendu (backend)':32}  {'Réel (Sheet)':32}  Statut")
        print(f"  {'─' * 3}  {'─' * 32}  {'─' * 32}  ──────")
        for idx, exp, real, st in rows:
            print(f"  {idx:>3}  {exp:32.32}  {real:32.32}  {st}")

    # 3. Vérification spécifique 04_Parametres : présence des 4 compteurs
    print()
    print("━━━ 04_Parametres — vérification des compteurs ━━━")
    try:
        ws = ss.worksheet(TABS["parametres"])
        rows = ws.get_all_values()
        headers = rows[0] if rows else []
        col_compteurs = None
        col_valeur = None
        for i, h in enumerate(headers):
            n = _normalize(h)
            if n == "compteurs":
                col_compteurs = i
            if n in ("valeur_actuelle", "valeur"):
                col_valeur = i
        if col_compteurs is None or col_valeur is None:
            print(f"  ❌ Colonnes 'Compteurs' et/ou 'Valeur Actuelle' introuvables (entêtes={headers})")
            global_status = "NOK"
        else:
            present = {}
            for r in rows[1:]:
                if col_compteurs < len(r):
                    name = r[col_compteurs].strip()
                    val = r[col_valeur] if col_valeur < len(r) else ""
                    if name in REQUIRED_COUNTERS:
                        present[name] = val
            for c in REQUIRED_COUNTERS:
                if c in present:
                    print(f"  ✅ {c:20} = {present[c]!r}")
                else:
                    print(f"  ❌ {c:20} MANQUANT")
                    global_status = "NOK"
    except Exception as e:
        print(f"  ❌ Erreur lecture 04_Parametres : {e}")
        global_status = "NOK"

    # 4. Conclusion
    print()
    print("=" * 78)
    print(f"STATUT GLOBAL : {global_status}")
    print("=" * 78)
    if global_status == "NOK":
        print("Divergence détectée → STOP avant P3.6 (votre consigne).")
        return 1
    print("Toutes les structures sont alignées. P3.6 peut être engagé après votre validation.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
