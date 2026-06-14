"""
Geobuilder Pionniers — Backend FastAPI
Remplace les modules Make défaillants (11 + 16) et orchestre :
- Création Pionnier (PIO-XXXX)
- Création Installation (INST-XXXX)
- Création Maintenance (MAINT-XXXX)
- Génération documents (passeport, certificat, garantie, portail)
- Push GitHub Pages
- Email de bienvenue (mock)
- Portail Pionnier (lien magique)
"""
from fastapi import FastAPI, APIRouter, HTTPException, Header, Depends
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional
import os
import logging
import jwt as pyjwt

from services.sheets_service import get_sheets_service
from services.counter_service import increment_counter, peek_next_id, get_current_counter
from services.github_service import get_github_service
from services.template_service import render_template, TEMPLATE_DIR
from services.email_service import send_email_mock, get_outbox_snapshot
from services.catalog import get_product

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# NOTE P0: MongoDB retiré. Google Sheets est la seule source de vérité.
# Les emails mockés sont stockés en mémoire dans services/email_service.py.

app = FastAPI(title="Geobuilder Pionniers API")
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# =========================================================================
# MODELS
# =========================================================================
class LivraisonInput(BaseModel):
    """Payload reçu depuis le webhook LIVRAISON ou créé manuellement par l'admin."""
    nom: str
    prenom: str
    email: EmailStr
    telephone: Optional[str] = ""
    territoire: str  # ex: MAYOTTE, MOHELI, REUNION
    pays: Optional[str] = ""
    produit: str  # ex: G20 MOJA, OCEAN 500
    numero_serie: str
    date_installation: Optional[str] = None  # YYYY-MM-DD
    localisation: Optional[str] = ""


class MaintenanceInput(BaseModel):
    numero_serie: str  # on cherche l'installation à partir du NS
    type: str  # ex: "Préventive", "Corrective"
    date: Optional[str] = None
    technicien: str
    rapport: str


class AdminLogin(BaseModel):
    password: str


# =========================================================================
# AUTH
# =========================================================================
JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret")
JWT_ALG = "HS256"


def make_jwt(payload: dict, hours: int = 24) -> str:
    payload = {**payload, "exp": datetime.now(timezone.utc) + timedelta(hours=hours)}
    return pyjwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def verify_jwt(token: str) -> dict:
    try:
        return pyjwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except pyjwt.PyJWTError as e:
        raise HTTPException(401, f"Invalid token: {e}")


def require_admin(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing Bearer token")
    payload = verify_jwt(authorization.split(" ", 1)[1])
    if payload.get("role") != "admin":
        raise HTTPException(403, "Not admin")
    return payload


# =========================================================================
# HELPERS
# =========================================================================
def _today_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _public_base_url() -> str:
    """URL publique du backend (utilisée dans les liens magiques)."""
    return os.environ.get("PUBLIC_BACKEND_URL", "").rstrip("/")


def _github_pages_base() -> str:
    return os.environ.get("GITHUB_PAGES_URL", "").rstrip("/")


def _compute_garantie_fin(date_installation: str, mois: int) -> str:
    """Calcule la date de fin de garantie. Format YYYY-MM-DD."""
    try:
        dt = datetime.strptime(date_installation, "%Y-%m-%d")
    except (ValueError, TypeError):
        dt = datetime.now(timezone.utc)
    # Approx: ajoute mois * 30 jours (suffit pour la garantie)
    fin = dt + timedelta(days=mois * 30)
    return fin.strftime("%Y-%m-%d")


# =========================================================================
# ROUTES — HEALTH & ADMIN
# =========================================================================
@api_router.get("/")
async def root():
    return {"service": "Geobuilder Pionniers API", "status": "ok"}


@api_router.get("/health")
async def health():
    """Vérifie l'état des intégrations critiques (P0 — stabilisation technique)."""
    status = {
        "backend": "ok",
        "sheets": "unknown",
        "github": "unknown",
        "templates": "unknown",
        "counters_ready": "unknown",
        "email_outbox_size": len(get_outbox_snapshot()),
    }
    # Sheets
    try:
        get_sheets_service()._get_spreadsheet()
        status["sheets"] = "ok"
    except Exception as e:
        status["sheets"] = f"error: {e}"
    # GitHub
    try:
        get_github_service()._get_repo()
        status["github"] = "ok"
    except Exception as e:
        status["github"] = f"error: {e}"
    # Templates (présence locale)
    expected = [
        "passeport_installation.html",
        "certificat-pionnier.html",
        "certificat-garantie.html",
        "portail_pionnier.html",
        "email-final.html",
    ]
    missing = [f for f in expected if not (TEMPLATE_DIR / f).exists()]
    status["templates"] = "ok" if not missing else f"missing: {missing}"
    # Counters (uniquement si Sheets OK)
    if status["sheets"] == "ok":
        try:
            _ = get_current_counter("pionnier")
            status["counters_ready"] = "ok"
        except Exception as e:
            status["counters_ready"] = f"error: {e}"
    else:
        status["counters_ready"] = "skipped (sheets not ready)"
    return status


@api_router.post("/admin/login")
async def admin_login(payload: AdminLogin):
    admin_pwd = os.environ.get("ADMIN_PASSWORD", "")
    if not admin_pwd or payload.password != admin_pwd:
        raise HTTPException(401, "Invalid password")
    token = make_jwt({"role": "admin", "sub": "admin"}, hours=12)
    return {"token": token, "expires_in": 12 * 3600}


# =========================================================================
# ROUTES — COUNTERS (preview)
# =========================================================================
@api_router.get("/counters")
async def counters(_: dict = Depends(require_admin)):
    """Retourne l'état actuel des compteurs (remplace Module 11 de Make)."""
    try:
        return {
            "pionnier": {"current": get_current_counter("pionnier"), "next": peek_next_id("pionnier")},
            "installation": {"current": get_current_counter("installation"), "next": peek_next_id("installation")},
            "maintenance": {"current": get_current_counter("maintenance"), "next": peek_next_id("maintenance")},
            "document": {"current": get_current_counter("document"), "next": peek_next_id("document")},
        }
    except Exception as e:
        raise HTTPException(500, str(e))


# =========================================================================
# ROUTES — LIVRAISON (Webhook + Admin)
# =========================================================================
async def _process_livraison(payload: LivraisonInput) -> dict:
    """
    Pipeline LIVRAISON (P3 - templates prod alignés).

    1. Allocate PIO-XXXX, INST-XXXX (counter_service)
    2. Allocate doc IDs pour passeport / certificat pionnier / certificat garantie / portail
    3. Render templates PROD (passeport_installation, certificat-pionnier,
       certificat-garantie, email-final, portail_pionnier)
    4. Push GitHub Pages (chemins alignés convention prod)
    5. Append rows in 01_Pionniers + 02_Installations + 03_Documents
       NB: ordre des colonnes Sheets INCHANGÉ vs P0/P1/P2 (validation P3.6)
    6. Mock email
    """
    sheets = get_sheets_service()
    gh = get_github_service()

    # 1. IDs
    _, pio_id = increment_counter("pionnier")
    _, install_id = increment_counter("installation")
    _, doc_passeport = increment_counter("document")
    _, doc_cert_pio = increment_counter("document")
    _, doc_cert_gar = increment_counter("document")
    _, doc_portail = increment_counter("document")

    date_inst = payload.date_installation or _today_iso()
    produit_info = get_product(payload.produit)
    date_garantie_fin = _compute_garantie_fin(date_inst, produit_info["garantie_mois"])
    now_iso = datetime.now(timezone.utc).isoformat()
    annee = str(datetime.now(timezone.utc).year)
    nom_complet = f"{payload.prenom} {payload.nom}".strip()
    pays_affiche = payload.pays or payload.territoire

    # 2. URLs GitHub Pages (alignées convention prod)
    pages_base = _github_pages_base()
    url_passeport = f"{pages_base}/passeports/{install_id}/index.html"
    url_certificat = f"{pages_base}/certificats/pionnier/{pio_id}.html"
    url_garantie = f"{pages_base}/certificats/garantie/{install_id}.html"
    url_portail = f"{pages_base}/pionniers/{pio_id}/index.html"
    url_famille = pages_base + "/"  # Q4 = homepage GitHub Pages

    # 3. Render templates PROD
    # 3a. Passeport (snake_case, 27 variables ; Q2 = display:none pour blocs sans donnée)
    histo_html = (
        '<table class="histo"><tr><th>Date</th><th>Type</th><th>Technicien</th></tr>'
        f'<tr><td>{date_inst}</td><td>Installation initiale</td><td>—</td></tr></table>'
    )
    ctx_passeport = {
        "install_id": install_id,
        "pio_id": pio_id,
        "numero_serie": payload.numero_serie,
        "produit": produit_info["label"],
        "date_installation": date_inst,
        "date_garantie_fin": date_garantie_fin,
        "territoire_installation": payload.territoire,
        "pays_affiche": pays_affiche,
        "localisation_precise": payload.localisation or payload.territoire,
        "statut_label": "Pionnier",
        "statut_class": "active",
        "garantie_label": "Active",
        "garantie_class": "active",
        "historique_html": histo_html,
        "passeport_url": url_passeport,
        "url_fiche_technique": produit_info.get("fiche_technique_url", ""),
        "url_manuel": produit_info.get("manuel_url", ""),
        "url_certificat": url_certificat,
        "url_telecharger_tout": "",
        # Blocs masqués V1 (Q2 = display:none) — Ambassadeur/Fondateur/photos/planning hors périmètre
        "display_pionnier": "block",
        "display_ambassadeur": "none",
        "display_statut_communaute": "block",
        "badge_pionnier_url": "",
        "badge_ambassadeur_url": "",
        "photo_generateur_url": "",
        "photo_emplacement_url": "",
        "prochain_entretien": "",
        "prochain_dans": "",
        "prochain_type": "",
        "prochain_rdv_url": "",
    }
    html_passeport = render_template("passeport_installation.html", ctx_passeport)

    # 3b. Certificat Pionnier (UPPER_SNAKE)
    ctx_cert_pio = {
        "ANNEE": annee,
        "NOM_COMPLET": nom_complet,
        "PAYS": pays_affiche,
        "PIO_ID": pio_id,
    }
    html_cert_pio = render_template("certificat-pionnier.html", ctx_cert_pio)

    # 3c. Certificat Garantie (UPPER_SNAKE)
    ctx_cert_gar = {
        "DATE_INSTALLATION": date_inst,
        "DOC_ID": doc_cert_gar,
        "INSTALL_ID": install_id,
        "NOM_COMPLET": nom_complet,
        "PAYS": pays_affiche,
        "PIO_ID": pio_id,
        "PRODUIT": produit_info["label"],
        "PRODUIT_IMG_ID": produit_info.get("image_cloudinary_id", ""),
        "SERIAL": payload.numero_serie,
    }
    html_cert_gar = render_template("certificat-garantie.html", ctx_cert_gar)

    # 3d. Portail Pionnier (simple, généré dans /docs/pionniers/{PIO}/index.html)
    ctx_portail = {
        "PIO_ID": pio_id,
        "PRENOM": payload.prenom,
        "ANNEE": annee,
        "URL_CERTIFICAT": url_certificat,
        "URL_GARANTIE": url_garantie,
        "URL_PASSEPORT": url_passeport,
        "URL_CARTE": "",
        "URL_FAMILLE": url_famille,
        # Q2 — display:none pour les blocs sans cible utile en V1
        "DISPLAY_CERTIFICAT": "block",
        "DISPLAY_GARANTIE": "block",
        "DISPLAY_PASSEPORT": "block",
        "DISPLAY_CARTE": "none",  # carte non générée en V1
        "DISPLAY_FAMILLE": "block",
    }
    html_portail = render_template("portail_pionnier.html", ctx_portail)

    # 3e. Email final (UPPER_SNAKE)
    ctx_email = {
        "ANNEE": annee,
        "INSTALL_ID": install_id,
        "PAYS": pays_affiche,
        "PIO_ID": pio_id,
        "URL_CARTE": "",
        "URL_CERTIFICAT": url_certificat,
        "URL_ESPACE": url_portail,
        "URL_FAMILLE": url_famille,
        "URL_GARANTIE": url_garantie,
    }
    email_html = render_template("email-final.html", ctx_email)

    # 4. Push GitHub Pages (chemins prod-aligned)
    pushed = {}
    try:
        pushed["passeport"] = gh.push_file(
            f"docs/passeports/{install_id}/index.html", html_passeport,
            f"Add passeport {install_id} ({pio_id})")
        pushed["certificat_pionnier"] = gh.push_file(
            f"docs/certificats/pionnier/{pio_id}.html", html_cert_pio,
            f"Add certificat pionnier {pio_id}")
        pushed["certificat_garantie"] = gh.push_file(
            f"docs/certificats/garantie/{install_id}.html", html_cert_gar,
            f"Add certificat garantie {install_id}")
        pushed["portail"] = gh.push_file(
            f"docs/pionniers/{pio_id}/index.html", html_portail,
            f"Add portail {pio_id}")
    except Exception as e:
        logger.error(f"GitHub push failed: {e}")
        sheets.log_event("ERROR", "github_push", str(e), f"pio={pio_id} inst={install_id}")
        raise HTTPException(502, f"GitHub push failed: {e}")

    # 5. Append in 01_Pionniers (ordre colonnes INCHANGÉ — validation P3.6)
    try:
        sheets.append_row("pionniers", [
            pio_id, payload.nom, payload.prenom, payload.email, payload.telephone,
            payload.territoire, payload.pays, now_iso, "Pionnier", "Pionnier", url_portail,
        ])
    except Exception as e:
        logger.error(f"Sheet append pionniers failed: {e}")
        sheets.log_event("ERROR", "sheet_pionnier", str(e), f"pio={pio_id}")

    # 6. Append in 02_Installations
    try:
        sheets.append_row("installations", [
            install_id, pio_id, payload.numero_serie, produit_info["label"],
            date_inst, payload.localisation or payload.territoire,
            date_garantie_fin, url_passeport,
        ])
    except Exception as e:
        logger.error(f"Sheet append installations failed: {e}")
        sheets.log_event("ERROR", "sheet_install", str(e), f"inst={install_id}")

    # 7. Append documents
    try:
        for doc_id, dtype, url in [
            (doc_passeport, "PASSEPORT", url_passeport),
            (doc_cert_pio, "CERTIFICAT_PIONNIER", url_certificat),
            (doc_cert_gar, "CERTIFICAT_GARANTIE", url_garantie),
            (doc_portail, "PORTAIL", url_portail),
        ]:
            sheets.append_row("documents", [doc_id, pio_id, dtype, url, now_iso])
    except Exception as e:
        logger.error(f"Sheet append documents failed: {e}")

    # 8. Mock email
    await send_email_mock(
        payload.email,
        "Bienvenue dans la Famille des Pionniers Geobuilder",
        email_html,
        metadata={"pio_id": pio_id, "install_id": install_id},
    )

    sheets.log_event("INFO", "livraison", "Livraison processed",
                     f"pio={pio_id} inst={install_id} ns={payload.numero_serie}")

    return {
        "pio_id": pio_id, "install_id": install_id,
        "url_portail": url_portail, "url_passeport": url_passeport,
        "url_certificat": url_certificat, "url_garantie": url_garantie,
        "github": pushed,
    }


@api_router.post("/webhook/livraison")
async def webhook_livraison(payload: LivraisonInput):
    """Webhook public (à appeler depuis votre formulaire actuel ou Make)."""
    try:
        return await _process_livraison(payload)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Webhook livraison failed")
        raise HTTPException(500, str(e))


@api_router.post("/admin/livraison")
async def admin_create_livraison(payload: LivraisonInput, _: dict = Depends(require_admin)):
    """Création manuelle d'une livraison depuis l'interface admin."""
    return await _process_livraison(payload)


# =========================================================================
# ROUTES — MAINTENANCE (Webhook + Admin)
# =========================================================================
async def _process_maintenance(payload: MaintenanceInput) -> dict:
    sheets = get_sheets_service()
    gh = get_github_service()

    # 1. Find installation by NS
    install = sheets.find_row_by("installations", "numéro série", payload.numero_serie)
    if not install:
        # Try alternative column name
        install = sheets.find_row_by("installations", "Numéro série", payload.numero_serie)
    if not install:
        raise HTTPException(404, f"No installation found for NS={payload.numero_serie}")

    install_id = install.get("install_id") or install.get("Install ID") or ""
    pio_id = install.get("pio_id") or install.get("Pio ID") or ""

    # 2. Allocate MAINT ID
    _, maint_id = increment_counter("maintenance")
    date_m = payload.date or _today_iso()
    now_iso = datetime.now(timezone.utc).isoformat()  # noqa: F841 — variable préservée, sera utilisée en P3 (MAINTENANCE)

    # 3. Append row in 05_Maintenances
    try:
        sheets.append_row("maintenances", [
            maint_id, install_id, pio_id, payload.type, date_m,
            payload.technicien, payload.rapport, "",  # pdf url filled later
        ])
    except Exception as e:
        logger.error(f"Sheet append maintenances failed: {e}")
        raise HTTPException(500, f"Sheet write failed: {e}")

    # 4. Regenerate passeport with updated history
    maint_rows = [r for r in sheets.read_all("maintenances") if str(r.get("install_id", "")) == install_id]
    histo = '<table class="histo"><tr><th>Date</th><th>Type</th><th>Technicien</th><th>Rapport</th></tr>'
    histo += f'<tr><td>{install.get("date installation", "")}</td><td>Installation</td><td>—</td><td>—</td></tr>'
    for m in maint_rows:
        histo += (f'<tr><td>{m.get("date","")}</td><td>{m.get("type","")}</td>'
                  f'<td>{m.get("technicien","")}</td><td>{m.get("rapport","")[:80]}</td></tr>')
    histo += "</table>"

    pages_base = _github_pages_base()
    url_passeport = f"{pages_base}/passeports/{install_id}/index.html"
    ctx = {
        "install_id": install_id, "pio_id": pio_id,
        "nom_complet": "", "statut_label": "Garantie active", "statut_class": "active",
        "produit": install.get("produit", ""), "numero_serie": payload.numero_serie,
        "date_installation": install.get("date installation", ""),
        "territoire_installation": "", "pays_affiche": "",
        "localisation_precise": install.get("localisation", ""),
        "garantie_label": "Active", "garantie_class": "active",
        "date_garantie_fin": install.get("garantie fin", ""),
        "historique_html": histo, "passeport_url": url_passeport,
        "date_generation": _today_iso(), "doc_id": "",
    }
    html_passeport = render_template("passeport.html", ctx)

    try:
        gh.push_file(f"docs/passeports/{install_id}/index.html", html_passeport,
                     f"Update passeport {install_id} after maintenance {maint_id}")
    except Exception as e:
        logger.error(f"GitHub push (maintenance) failed: {e}")

    sheets.log_event("INFO", "maintenance", "Maintenance added",
                     f"maint={maint_id} inst={install_id} ns={payload.numero_serie}")

    return {
        "maint_id": maint_id, "install_id": install_id, "pio_id": pio_id,
        "url_passeport": url_passeport,
    }


@api_router.post("/webhook/maintenance")
async def webhook_maintenance(payload: MaintenanceInput):
    return await _process_maintenance(payload)


@api_router.post("/admin/maintenance")
async def admin_create_maintenance(payload: MaintenanceInput, _: dict = Depends(require_admin)):
    return await _process_maintenance(payload)


# =========================================================================
# ROUTES — ADMIN VIEWS (lecture Sheet)
# =========================================================================
@api_router.get("/admin/pionniers")
async def list_pionniers(_: dict = Depends(require_admin)):
    try:
        return get_sheets_service().read_all("pionniers")
    except Exception as e:
        raise HTTPException(500, str(e))


@api_router.get("/admin/installations")
async def list_installations(_: dict = Depends(require_admin)):
    try:
        return get_sheets_service().read_all("installations")
    except Exception as e:
        raise HTTPException(500, str(e))


@api_router.get("/admin/maintenances")
async def list_maintenances(_: dict = Depends(require_admin)):
    try:
        return get_sheets_service().read_all("maintenances")
    except Exception as e:
        raise HTTPException(500, str(e))


# NOTE P0: /api/admin/emails-outbox retiré (dépendait de MongoDB).
# Sera réintroduit en P4 (logs ou onglet Sheets, décision à venir).


# =========================================================================
# ROUTES — MAGIC LINK PORTAL
# =========================================================================
@api_router.post("/portal/magic-link")
async def magic_link(email: EmailStr):
    """Génère un lien magique pour le pionnier qui a cet email."""
    sheets = get_sheets_service()
    row = sheets.find_row_by("pionniers", "email", email)
    if not row:
        raise HTTPException(404, "Email not found in 01_Pionniers")
    pio_id = row.get("pio_id") or row.get("Pio ID")
    token = make_jwt({"role": "pionnier", "pio_id": pio_id, "email": email}, hours=24 * 30)
    base = _public_base_url() or ""
    link = f"{base}/api/portal/access?token={token}"
    email_html = (f"<p>Bonjour {row.get('prénom', '')},</p>"
                  f"<p>Voici votre lien d'accès au portail Pionnier :</p>"
                  f'<p><a href="{link}">{link}</a></p>'
                  "<p>Ce lien est valable 30 jours.</p>")
    await send_email_mock(email, "Votre lien d'accès — Portail Pionnier", email_html,
                          metadata={"pio_id": pio_id, "type": "magic_link"})
    return {"status": "ok", "message": "Magic link mocked (check /api/admin/emails-outbox)"}


@api_router.get("/portal/access", response_class=HTMLResponse)
async def portal_access(token: str):
    """Accès au portail via lien magique."""
    payload = verify_jwt(token)
    if payload.get("role") != "pionnier":
        raise HTTPException(403, "Invalid token")
    pio_id = payload["pio_id"]
    pages_base = _github_pages_base()
    # Redirige vers la page GitHub Pages du portail
    return HTMLResponse(
        f'<meta http-equiv="refresh" content="0; url={pages_base}/portail/{pio_id}/index.html">'
        f'<p>Redirection vers votre portail... <a href="{pages_base}/portail/{pio_id}/index.html">Cliquez ici si rien ne se passe</a></p>'
    )


# =========================================================================
# APP SETUP
# =========================================================================
app.include_router(api_router)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)
