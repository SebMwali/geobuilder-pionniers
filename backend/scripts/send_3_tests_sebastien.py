"""send_3_tests_sebastien.py — Envoi de 3 emails de test à Sébastien Fumaz.

3 scénarios :
  A) G10 — Pionnier "simple" (ni fondateur, ni ambassadeur)
  B) G30 — Fondateur + Ambassadeur, avec 3 maintenances historiques
  C) G60 — Ambassadeur + Super Ambassadeur

Pour chaque test :
  - Crée pionnier dans 01_Pionniers + installation dans 02_Installations
  - Régénère tous les docs HTML sur GitHub Pages
  - Envoie un email réel via Resend à sebastien.fumaz@gmail.com avec le bon contexte

A la fin → garde la liste des pio_id / install_id à nettoyer (cleanup séparé).
"""
import asyncio
import os
import sys
import time
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv
load_dotenv()

from services.sheets_service import get_sheets_service  # noqa: E402
from services.github_service import get_github_service  # noqa: E402
from services.template_service import render_template  # noqa: E402
from services.email_service import send_email_mock  # noqa: E402
from services.catalog import get_product  # noqa: E402
from server import _regenerate_all_docs_for_pioneer, _github_pages_base  # noqa: E402

DEST_EMAIL = "sebastien.fumaz@gmail.com"
PAGES_BASE = _github_pages_base()


def _next_id(sheets, tab_key: str, col: str, prefix: str) -> str:
    rows = sheets.read_all(tab_key)
    max_n = 0
    for r in rows:
        v = str(r.get(col) or "").strip()
        if v.startswith(prefix):
            try:
                n = int(v.replace(prefix, ""))
                max_n = max(max_n, n)
            except Exception:
                pass
    return f"{prefix}{max_n + 1}"


def _build_row_for_tab(sheets, tab_key: str, values: dict) -> list:
    """Aligne un dict {colonne: valeur} sur l'ordre exact des colonnes de l'onglet."""
    ws = sheets.get_worksheet(tab_key)
    headers = ws.row_values(1)
    return [values.get(h, "") for h in headers]


def _append_pioneer(sheets, pid, nom, prenom, email, telephone, fondateur, ambassadeur, communaute):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    values = {
        "pio_id": pid, "nom": nom, "prenom": prenom, "email": email,
        "telephone": telephone, "pays": "France", "territoire": "Mayotte",
        "client_type": "particulier", "date_entree": today, "statut": "actif",
        "fondateur": "true" if fondateur else "false",
        "ambassadeur": "true" if ambassadeur else "false",
        "communaute_statut": communaute,
        "source_creation": "test_email_20260616",
        "welcome_email_sent": "false",
    }
    row = _build_row_for_tab(sheets, "pionniers", values)
    sheets.append_in_formatted_zone("pionniers", [row], n_cols=len(row))
    print(f"  ✓ Pionnier {pid} créé")


def _append_install(sheets, iid, pid, produit, ns, date_inst, nom_client):
    info = get_product(produit)
    values = {
        "install_id": iid, "pio_id": pid, "produit": produit,
        "numero_serie": ns, "date_installation": date_inst,
        "territoire_installation": "Mayotte",
        "installateur": "Geobuilder Tech (TEST)",
        "installation_status": "actif",
        "pionnier_created": "true",
        "nom_client": nom_client,
        "gamme": info.get("label", produit),
        "contrat_maintenance_type": "standard",
        "installation_active": "true",
        "photo_generateur_url": info.get("photo_generateur_url", ""),
        "photo_emplacement_url": info.get("photo_generateur_url", ""),
        "report_id": f"TEST-{int(time.time())}-{iid}",
    }
    row = _build_row_for_tab(sheets, "installations", values)
    sheets.append_in_formatted_zone("installations", [row], n_cols=len(row))
    print(f"  ✓ Installation {iid} ({produit}) créée")


def _append_maintenances(sheets, pid, iid, dates):
    rows = []
    for i, dt in enumerate(dates, 1):
        values = {
            "maintenance_id": f"MAINT-TEST-{pid.replace('PIO-','')}-{i}",
            "install_id": iid, "pio_id": pid,
            "date_intervention": dt, "type_intervention": "preventive",
            "technicien": "Geobuilder Tech", "statut": "effectuee",
            "observations": f"Maintenance préventive #{i} — TEST",
            "source": "test_email_20260616",
        }
        rows.append(_build_row_for_tab(sheets, "maintenances", values))
    sheets.append_in_formatted_zone("maintenances", rows, n_cols=len(rows[0]))
    print(f"  ✓ {len(rows)} maintenances ajoutées")


def _build_email_ctx(pio_id, install_id, produit_label, territoire="Mayotte"):
    annee = str(datetime.now(timezone.utc).year)
    return {
        "ANNEE": annee, "INSTALL_ID": install_id, "PAYS": territoire, "PIO_ID": pio_id,
        "URL_CARTE": f"{PAGES_BASE}/cartes/{pio_id}.html",
        "URL_CERTIFICAT": f"{PAGES_BASE}/certificats/pionnier/{pio_id}.html",
        "URL_ESPACE": f"{PAGES_BASE}/pionniers/{pio_id}/index.html",
        "URL_FAMILLE": f"{PAGES_BASE}/index.html",
        "URL_GARANTIE": f"{PAGES_BASE}/certificats/garantie/{install_id}.html",
        "URL_PASSEPORT": f"{PAGES_BASE}/passeports/{install_id}/index.html",
        "URL_AMBASSADEUR_CTA": f"{PAGES_BASE}/ambassadeur.html",
        "CTA_AMBASSADEUR_TITLE": "Devenez Ambassadeur",
        "CTA_AMBASSADEUR_DESC": "Les Pionniers ouvrent la voie.",
    }


async def main():
    print(f"\n{'=' * 70}\n  ENVOI 3 TESTS → {DEST_EMAIL}\n{'=' * 70}\n")
    sheets = get_sheets_service()
    gh = get_github_service()

    # Préparer 3 pio_id / install_id uniques
    pid_base = _next_id(sheets, "pionniers", "pio_id", "PIO-")
    iid_base = _next_id(sheets, "installations", "install_id", "INST-")
    pid_n = int(pid_base.replace("PIO-", ""))
    iid_n = int(iid_base.replace("INST-", ""))
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # ─── TEST A : G10 simple ───────────────────────────────────────────────
    test_a = {
        "pio_id": f"PIO-{pid_n}", "install_id": f"INST-{iid_n}",
        "nom": "TestSimple", "prenom": "Pionnier A",
        "produit": "G10", "ns": "TEST-G10-A001",
        "fondateur": False, "ambassadeur": False, "super": False,
        "subject": "[TEST A — G10 simple] Bienvenue dans la Famille des Pionniers",
    }
    # ─── TEST B : G30 fondateur + ambassadeur + maintenances ──────────────
    test_b = {
        "pio_id": f"PIO-{pid_n + 1}", "install_id": f"INST-{iid_n + 1}",
        "nom": "TestFondateur", "prenom": "Pionnier B",
        "produit": "G30", "ns": "TEST-G30-B001",
        "fondateur": True, "ambassadeur": True, "super": False,
        "subject": "[TEST B — G30 Fondateur+Ambassadeur] Bienvenue Pionnier",
        "maintenances_dates": ["2024-01-15", "2024-07-20", "2025-01-10"],
    }
    # ─── TEST C : G60 ambassadeur + super ─────────────────────────────────
    test_c = {
        "pio_id": f"PIO-{pid_n + 2}", "install_id": f"INST-{iid_n + 2}",
        "nom": "TestSuper", "prenom": "Pionnier C",
        "produit": "G60", "ns": "TEST-G60-C001",
        "fondateur": False, "ambassadeur": True, "super": True,
        "subject": "[TEST C — G60 Ambassadeur+Super] Bienvenue Pionnier",
    }

    cleanup_pio = []
    cleanup_inst = []
    cleanup_maint = []

    for t in (test_a, test_b, test_c):
        print(f"\n→ Préparation {t['pio_id']} ({t['produit']}) ...")
        communaute = ""
        roles = []
        if t["fondateur"]: roles.append("Fondateur")
        if t["ambassadeur"]: roles.append("Ambassadeur")
        if t["super"]: roles.append("Super Ambassadeur")
        communaute = " · ".join(roles)

        _append_pioneer(
            sheets, t["pio_id"], t["nom"], t["prenom"],
            DEST_EMAIL, "+33000000000",
            t["fondateur"], t["ambassadeur"], communaute,
        )
        cleanup_pio.append(t["pio_id"])
        time.sleep(2)  # quota Sheets

        _append_install(
            sheets, t["install_id"], t["pio_id"],
            t["produit"], t["ns"], today,
            nom_client=f"{t['prenom']} {t['nom']}",
        )
        cleanup_inst.append(t["install_id"])
        time.sleep(2)

        if t.get("maintenances_dates"):
            _append_maintenances(sheets, t["pio_id"], t["install_id"], t["maintenances_dates"])
            cleanup_maint.append(t["pio_id"])
            time.sleep(2)

    # Petit délai pour que les ajouts soient bien visibles côté Sheets
    time.sleep(3)

    # ─── RÉGÉNÉRATION DES DOCS POUR LES 3 TESTS ───────────────────────────
    for t in (test_a, test_b, test_c):
        print(f"\n→ Régénération docs pour {t['pio_id']}…")
        pio_row = sheets.find_row_by("pionniers", "pio_id", t["pio_id"])
        inst_row = sheets.find_row_by("installations", "install_id", t["install_id"])
        if not pio_row or not inst_row:
            print(f"  ❌ Manquant pio_row={bool(pio_row)} inst_row={bool(inst_row)}")
            continue
        try:
            pushed = _regenerate_all_docs_for_pioneer(pio_row, inst_row, sheets, gh)
            print(f"  ✓ {len(pushed)} docs poussés sur GH Pages")
        except Exception as e:
            print(f"  ❌ Erreur regen : {e}")
        time.sleep(3)

    # Attendre 30s pour que GH Pages rebuild les URLs
    print("\n→ Attente 60s pour propagation GH Pages…")
    time.sleep(60)

    # ─── ENVOI DES 3 EMAILS ───────────────────────────────────────────────
    print("\n→ Envoi des 3 emails à", DEST_EMAIL)
    for t in (test_a, test_b, test_c):
        ctx = _build_email_ctx(t["pio_id"], t["install_id"], t["produit"])
        html = render_template("email-final.html", ctx)
        tags = {
            "pio_id": t["pio_id"], "install_id": t["install_id"],
            "template": "test_run_20260616", "scenario": t["pio_id"][-1:],
        }
        res = await send_email_mock(
            to=DEST_EMAIL,
            subject=t["subject"],
            html_body=html,
            metadata={"test": True, "scenario": t["pio_id"]},
            tags=tags,
        )
        print(f"  ✓ {t['pio_id']} → status={res['status']} id={res.get('resend_id','')}")
        await asyncio.sleep(2)

    print("\n" + "=" * 70)
    print("✅ 3 emails envoyés. Liste à nettoyer :")
    print(f"   pio_id   : {cleanup_pio}")
    print(f"   install_id : {cleanup_inst}")
    print(f"   maintenances pio_id : {cleanup_maint}")
    print("=" * 70)
    # Sauvegarde pour cleanup
    with open("/tmp/test_cleanup_list.txt", "w") as f:
        f.write(f"PIONNIERS_TO_DELETE={','.join(cleanup_pio)}\n")
        f.write(f"INSTALLS_TO_DELETE={','.join(cleanup_inst)}\n")
        f.write(f"MAINT_PIOS_TO_DELETE={','.join(cleanup_maint)}\n")
    print("\nListe sauvegardée dans /tmp/test_cleanup_list.txt")


if __name__ == "__main__":
    asyncio.run(main())
