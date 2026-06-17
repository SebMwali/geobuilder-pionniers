"""test_email_nadjmou.py — Test parcours 19 mois (bypass webhook pour quota)."""
import asyncio
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv
load_dotenv()


async def main():
    from services.sheets_service import get_sheets_service
    from services.github_service import get_github_service
    from services.email_service import send_email_mock
    from services.template_service import render_template
    from services.counter_service import increment_counter
    from server import _regenerate_all_docs_for_pioneer

    sheets = get_sheets_service()
    gh = get_github_service()

    # === Étape 1 : Allocation IDs ===
    _, pio_id = increment_counter("pionnier")
    _, install_id = increment_counter("installation")
    print(f"[1/4] Allocations: {pio_id} / {install_id}")

    # === Étape 2 : Insertion 01_Pionniers + 02_Installations (bypass quota) ===
    now_iso = datetime.now(timezone.utc).isoformat()
    sheets.append_row("pionniers", [
        pio_id,                  # A pio_id
        "TEST-NADJMOU-2024",     # B NS
        "G30",                   # C produits
        "BOINA",                 # D nom
        "Nadjmou",               # E prenom
        "boina@kannel.io",       # F email
        "",                      # G telephone
        "France",                # H pays
        "Mayotte",               # I territoire
        "",                      # J client_type
        now_iso,                 # K date_entree
        "Pionnier",              # L statut
        "true",                  # M fondateur
        "false",                 # N ambassadeur
        "Fondateur",             # O communaute_statut
        "", "", "",              # P-R
        "test_email_19mois",     # S source
        "livraison_complete",    # T workflow_status
        "true",                  # U welcome_email_sent (mis à jour après envoi)
        "", "", "",              # V-X
    ])
    time.sleep(1)

    # Récupérer les headers de installations pour insertion correcte
    ws_i = sheets.get_worksheet("installations")
    i_headers = ws_i.row_values(1)
    print(f"  Headers installations: {i_headers[:10]}...")

    inst_row_data = []
    for h in i_headers:
        h_lc = h.lower().strip()
        if h_lc == "install_id":
            inst_row_data.append(install_id)
        elif h_lc == "pio_id":
            inst_row_data.append(pio_id)
        elif h_lc == "numero_serie":
            inst_row_data.append("TEST-NADJMOU-2024")
        elif h_lc == "produit":
            inst_row_data.append("G30")
        elif "date_installation" in h_lc:
            inst_row_data.append("17/11/2024")
        elif h_lc == "territoire":
            inst_row_data.append("Mayotte")
        elif h_lc == "nom_client" or h_lc == "client":
            inst_row_data.append("BOINA Nadjmou")
        elif h_lc == "report_id":
            inst_row_data.append("test-nadjmou-2024-11-17")
        elif "created" in h_lc or h_lc == "date_creation":
            inst_row_data.append(now_iso)
        else:
            inst_row_data.append("")
    sheets.append_row("installations", inst_row_data)
    print(f"  ✅ Insertions 01+02 OK")
    time.sleep(2)

    # === Étape 3 : 3 maintenances ===
    print(f"\n[2/4] Ajout 3 maintenances...")
    ws_m = sheets.get_worksheet("maintenances")
    m_headers = ws_m.row_values(1)
    print(f"  Headers maintenances: {m_headers}")

    maintenances = [
        ("17/05/2025", "Maintenance 6 mois", "6 mois"),
        ("17/11/2025", "Maintenance 12 mois", "12 mois"),
        ("17/05/2026", "Maintenance 18 mois", "18 mois"),
    ]
    for date_str, libelle, periodicite in maintenances:
        row = []
        for h in m_headers:
            h_lc = h.lower().strip()
            if "maintenance_id" in h_lc or h_lc == "id":
                row.append("")
            elif h_lc == "pio_id":
                row.append(pio_id)
            elif h_lc == "install_id":
                row.append(install_id)
            elif "date" in h_lc:
                row.append(date_str)
            elif any(k in h_lc for k in ("libelle", "operation", "intervention", "description", "type")):
                row.append(libelle)
            elif "periodicite" in h_lc or "echeance" in h_lc:
                row.append(periodicite)
            elif "statut" in h_lc:
                row.append("Effectuée")
            elif "technicien" in h_lc:
                row.append("TEST")
            else:
                row.append("")
        sheets.append_row("maintenances", row)
        print(f"  ✅ {date_str} - {libelle}")
        time.sleep(1)

    # === Étape 4 : Régénération docs + envoi mail ===
    print(f"\n[3/4] Régénération des docs (passeport intègre les maintenances)...")
    pio_row = sheets.find_row_by("pionniers", "pio_id", pio_id)
    inst_row = sheets.find_row_by("installations", "pio_id", pio_id)
    pushed = _regenerate_all_docs_for_pioneer(pio_row, inst_row, sheets, gh)
    print(f"  ✅ {len(pushed)} docs régénérés")

    # === Envoi mail ===
    print(f"\n[4/4] Envoi du mail de bienvenue (test)...")
    pages_base = "https://sebmwali.github.io/geobuilder-pionniers"
    # Pour cohérence parfaite avec la prod : on récupère le pio_row à jour
    # et on détermine fondateur (pour switcher URL_CARTE vers badge fondateur).
    pio_row_final = sheets.find_row_by("pionniers", "pio_id", pio_id) or {}
    is_fondateur = str(pio_row_final.get("fondateur", "")).strip().upper() in ("TRUE", "OUI", "1", "YES", "VRAI")
    url_carte = f"{pages_base}/cartes/{pio_id}.html"
    url_badge_fondateur = f"{pages_base}/badges/fondateur/{pio_id}.html"
    ctx_email = {
        "ANNEE": "2026",
        "INSTALL_ID": install_id,
        "PAYS": "Mayotte",
        "PIO_ID": pio_id,
        "URL_CARTE": url_badge_fondateur if is_fondateur else url_carte,
        "URL_CERTIFICAT": f"{pages_base}/certificats/pionnier/{pio_id}.html",
        "URL_ESPACE": f"{pages_base}/pionniers/{pio_id}/index.html",
        "URL_GARANTIE": f"{pages_base}/certificats/garantie/{install_id}.html",
        "URL_PASSEPORT": f"{pages_base}/passeports/{install_id}/index.html",
        "URL_AMBASSADEUR_CTA": f"{pages_base}/ambassadeur.html",
        "CTA_AMBASSADEUR_TITLE": "Devenez Ambassadeur",
        "CTA_AMBASSADEUR_DESC": "Les Pionniers ouvrent la voie.",
    }
    email_html = render_template("email-final.html", ctx_email)

    await send_email_mock(
        "boina@kannel.io",
        "[TEST 19 mois] Bienvenue dans la Famille des Pionniers Geobuilder",
        email_html,
        cc=["sebastien.fumaz@geobuilder.fr"],
        metadata={"pio_id": pio_id, "install_id": install_id, "test": "true"},
        tags={"pio_id": pio_id, "install_id": install_id, "template": "test_19mois"},
    )
    print(f"  ✅ Envoyé à boina@kannel.io + CC sebastien.fumaz@geobuilder.fr")
    print(f"\n=== Récap ===")
    print(f"  pio_id      : {pio_id}")
    print(f"  install_id  : {install_id}")
    print(f"  Passeport   : {pages_base}/passeports/{install_id}/index.html")
    print(f"  Portail     : {pages_base}/pionniers/{pio_id}/index.html")


if __name__ == "__main__":
    asyncio.run(main())
