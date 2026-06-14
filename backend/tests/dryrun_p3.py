"""
Dry-run P3.3 - rendu local des 5 templates avec contexte fictif.
Vérifie qu'aucun {{...}} ne subsiste après rendu.
Aucun appel réseau. Aucune écriture GitHub. Aucune écriture Sheets.
"""
import re
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from services.template_service import render_template  # noqa: E402
from services.catalog import get_product  # noqa: E402

OUT_DIR = Path("/tmp/p3_dryrun")
OUT_DIR.mkdir(exist_ok=True)

# Contexte de test (PIO de test fictif)
PIO_ID = "PIO-9999"
INST_ID = "INST-9999"
DOC_PASS = "DOC-90001"
DOC_CERT_PIO = "DOC-90002"
DOC_CERT_GAR = "DOC-90003"
DOC_PORT = "DOC-90004"
ANNEE = "2026"
NOM_COMPLET = "Aïsha Diallo"
PAYS = "Mayotte"
DATE_INST = "2026-02-15"
DATE_GAR_FIN = "2027-12-12"
NS = "P3-TEST-NS-0001"
PROD_INFO = get_product("G20 MOJA")
PAGES = "https://sebmwali.github.io/geobuilder-pionniers"
URL_PASS = f"{PAGES}/passeports/{INST_ID}/index.html"
URL_CERT = f"{PAGES}/certificats/pionnier/{PIO_ID}.html"
URL_GAR = f"{PAGES}/certificats/garantie/{INST_ID}.html"
URL_PORT = f"{PAGES}/pionniers/{PIO_ID}/index.html"
URL_FAM = PAGES + "/"

renders = []

# 1. Passeport
ctx_passeport = {
    "install_id": INST_ID, "pio_id": PIO_ID, "numero_serie": NS,
    "produit": PROD_INFO["label"], "date_installation": DATE_INST,
    "date_garantie_fin": DATE_GAR_FIN, "territoire_installation": "MAYOTTE",
    "pays_affiche": PAYS, "localisation_precise": "Mamoudzou, Mayotte",
    "statut_label": "Pionnier", "statut_class": "active",
    "garantie_label": "Active", "garantie_class": "active",
    "historique_html": "<table class='histo'><tr><th>Date</th><th>Type</th><th>Technicien</th></tr>"
                       f"<tr><td>{DATE_INST}</td><td>Installation initiale</td><td>—</td></tr></table>",
    "passeport_url": URL_PASS,
    "url_fiche_technique": PROD_INFO.get("fiche_technique_url", ""),
    "url_manuel": PROD_INFO.get("manuel_url", ""),
    "url_certificat": URL_CERT,
    "url_telecharger_tout": "",
    "display_pionnier": "block", "display_ambassadeur": "none",
    "display_statut_communaute": "block",
    "badge_pionnier_url": "", "badge_ambassadeur_url": "",
    "photo_generateur_url": "", "photo_emplacement_url": "",
    "prochain_entretien": "", "prochain_dans": "",
    "prochain_type": "", "prochain_rdv_url": "",
}
renders.append(("passeport_installation.html", ctx_passeport))

# 2. Certificat Pionnier
ctx_cert_pio = {
    "ANNEE": ANNEE, "NOM_COMPLET": NOM_COMPLET, "PAYS": PAYS, "PIO_ID": PIO_ID,
}
renders.append(("certificat-pionnier.html", ctx_cert_pio))

# 3. Certificat Garantie
ctx_cert_gar = {
    "DATE_INSTALLATION": DATE_INST, "DOC_ID": DOC_CERT_GAR, "INSTALL_ID": INST_ID,
    "NOM_COMPLET": NOM_COMPLET, "PAYS": PAYS, "PIO_ID": PIO_ID,
    "PRODUIT": PROD_INFO["label"], "PRODUIT_IMG_ID": PROD_INFO.get("image_cloudinary_id", ""),
    "SERIAL": NS,
}
renders.append(("certificat-garantie.html", ctx_cert_gar))

# 4. Email final
ctx_email = {
    "ANNEE": ANNEE, "INSTALL_ID": INST_ID, "PAYS": PAYS, "PIO_ID": PIO_ID,
    "URL_CARTE": "", "URL_CERTIFICAT": URL_CERT, "URL_ESPACE": URL_PORT,
    "URL_FAMILLE": URL_FAM, "URL_GARANTIE": URL_GAR,
}
renders.append(("email-final.html", ctx_email))

# 5. Portail Pionnier (local)
ctx_portail = {
    "PIO_ID": PIO_ID, "PRENOM": "Aïsha", "ANNEE": ANNEE,
    "URL_CERTIFICAT": URL_CERT, "URL_GARANTIE": URL_GAR,
    "URL_PASSEPORT": URL_PASS, "URL_CARTE": "", "URL_FAMILLE": URL_FAM,
    "DISPLAY_CERTIFICAT": "block", "DISPLAY_GARANTIE": "block",
    "DISPLAY_PASSEPORT": "block", "DISPLAY_CARTE": "none",
    "DISPLAY_FAMILLE": "block",
}
renders.append(("portail_pionnier.html", ctx_portail))


# Exécution + vérification
PATTERN_UNRESOLVED = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")

print("=" * 72)
print("DRY-RUN P3.3 — rendu local")
print("=" * 72)
all_ok = True
for tpl_name, ctx in renders:
    try:
        out = render_template(tpl_name, ctx)
    except Exception as e:
        print(f"❌ {tpl_name:35} → ERREUR: {e}")
        all_ok = False
        continue
    out_file = OUT_DIR / tpl_name.replace("/", "_")
    out_file.write_text(out, encoding="utf-8")
    unresolved = PATTERN_UNRESOLVED.findall(out)
    unresolved_unique = sorted(set(unresolved))
    if unresolved_unique:
        all_ok = False
        print(f"⚠️  {tpl_name:35} rendu, {len(out)} octets, "
              f"{len(unresolved_unique)} variable(s) non remplacée(s): {unresolved_unique}")
    else:
        print(f"✅ {tpl_name:35} rendu, {len(out):>8} octets, 0 variable non remplacée")

print()
print(f"Fichiers de sortie: {OUT_DIR}/")
print(f"Statut global: {'OK' if all_ok else 'ÉCHEC — variables non remplacées'}")
sys.exit(0 if all_ok else 1)
