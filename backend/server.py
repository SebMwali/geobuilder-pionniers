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
from fastapi.responses import HTMLResponse, JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, List
import os
import logging
import uuid
import jwt as pyjwt
import secrets

from services.sheets_service import get_sheets_service
from services.counter_service import increment_counter, peek_next_id, get_current_counter
from services.github_service import get_github_service
from services.template_service import render_template
from services.email_service import send_email_mock
from services.catalog import get_product

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

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
    """Vérifie l'état des intégrations critiques."""
    status = {"backend": "ok", "sheets": "unknown", "github": "unknown"}
    try:
        get_sheets_service()._get_spreadsheet()
        status["sheets"] = "ok"
    except Exception as e:
        status["sheets"] = f"error: {e}"
    try:
        get_github_service()._get_repo()
        status["github"] = "ok"
    except Exception as e:
        status["github"] = f"error: {e}"
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
    Pipeline principal :
    1. Allocate PIO-XXXX, INST-XXXX (counter_service, remplace Module 11)
    2. Allocate doc IDs pour passeport/certificat/garantie
    3. Generate HTML (template_service)
    4. Push GitHub Pages (github_service, remplace Module 16)
    5. Append rows in 01_Pionniers + 02_Installations (Sheets)
    6. Append rows in 03_Documents
    7. Mock email
    """
    sheets = get_sheets_service()
    gh = get_github_service()

    # 1. IDs
    _, pio_id = increment_counter("pionnier")
    _, install_id = increment_counter("installation")

    # Doc IDs
    _, doc_passeport = increment_counter("document")
    _, doc_certificat = increment_counter("document")
    _, doc_garantie = increment_counter("document")
    _, doc_portail = increment_counter("document")

    date_inst = payload.date_installation or _today_iso()
    produit_info = get_product(payload.produit)
    date_garantie_fin = _compute_garantie_fin(date_inst, produit_info["garantie_mois"])
    now_iso = datetime.now(timezone.utc).isoformat()
    annee = datetime.now(timezone.utc).year
    nom_complet = f"{payload.prenom} {payload.nom}".strip()

    # 2. URLs GitHub Pages (avant push)
    pages_base = _github_pages_base()
    url_passeport = f"{pages_base}/passeports/{install_id}/index.html"
    url_portail = f"{pages_base}/portail/{pio_id}/index.html"
    url_certificat = f"{pages_base}/certificats/{pio_id}/index.html"
    url_garantie = f"{pages_base}/garanties/{install_id}/index.html"

    # 3. Render templates
    ctx_passeport = {
        "install_id": install_id, "pio_id": pio_id, "nom_complet": nom_complet,
        "statut_label": "Garantie active", "statut_class": "active",
        "produit": produit_info["label"], "numero_serie": payload.numero_serie,
        "date_installation": date_inst, "territoire_installation": payload.territoire,
        "pays_affiche": payload.pays or payload.territoire,
        "localisation_precise": payload.localisation or payload.territoire,
        "garantie_label": "Active", "garantie_class": "active",
        "date_garantie_fin": date_garantie_fin,
        "historique_html": '<table class="histo"><tr><th>Date</th><th>Type</th><th>Technicien</th></tr>'
                           f'<tr><td>{date_inst}</td><td>Installation initiale</td><td>—</td></tr></table>',
        "passeport_url": url_passeport,
        "date_generation": _today_iso(),
        "doc_id": doc_passeport,
    }
    html_passeport = render_template("passeport.html", ctx_passeport)

    ctx_cert = {
        "pio_id": pio_id, "nom_complet": nom_complet, "territoire": payload.territoire,
        "annee": str(annee), "date_creation": _today_iso(),
    }
    html_certificat = render_template("certificat.html", ctx_cert)

    ctx_gar = {
        "pio_id": pio_id, "install_id": install_id, "nom_complet": nom_complet,
        "produit": produit_info["label"], "pays": payload.pays or payload.territoire,
        "numero_serie": payload.numero_serie, "date_installation": date_inst,
        "date_garantie_fin": date_garantie_fin, "doc_id": doc_garantie,
    }
    html_garantie = render_template("garantie.html", ctx_gar)

    ctx_portail = {
        "pio_id": pio_id, "prenom": payload.prenom,
        "url_carte": f"{pages_base}/cartes/{pio_id}/carte.png",
        "url_certificat": url_certificat,
        "url_garantie": url_garantie,
        "url_passeport": url_passeport,
    }
    html_portail = render_template("portail.html", ctx_portail)

    # 4. Push GitHub Pages
    pushed = {}
    try:
        pushed["passeport"] = gh.push_file(f"docs/passeports/{install_id}/index.html", html_passeport,
                                            f"Add passeport {install_id} ({pio_id})")
        pushed["certificat"] = gh.push_file(f"docs/certificats/{pio_id}/index.html", html_certificat,
                                              f"Add certificat {pio_id}")
        pushed["garantie"] = gh.push_file(f"docs/garanties/{install_id}/index.html", html_garantie,
                                            f"Add garantie {install_id}")
        pushed["portail"] = gh.push_file(f"docs/portail/{pio_id}/index.html", html_portail,
                                           f"Add portail {pio_id}")
    except Exception as e:
        logger.error(f"GitHub push failed: {e}")
        sheets.log_event("ERROR", "github_push", str(e), f"pio={pio_id} inst={install_id}")
        raise HTTPException(502, f"GitHub push failed: {e}")

    # 5. Append in 01_Pionniers (column order = header order in the sheet)
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
            (doc_certificat, "CERTIFICAT", url_certificat),
            (doc_garantie, "GARANTIE", url_garantie),
            (doc_portail, "PORTAIL", url_portail),
        ]:
            sheets.append_row("documents", [doc_id, pio_id, dtype, url, now_iso])
    except Exception as e:
        logger.error(f"Sheet append documents failed: {e}")

    # 8. Mock email
    email_html = render_template("email_bienvenue.html", {
        "prenom": payload.prenom, "pio_id": pio_id, "url_portail": url_portail,
    })
    await send_email_mock(db, payload.email, "Bienvenue dans la Famille des Pionniers Geobuilder",
                          email_html, metadata={"pio_id": pio_id, "install_id": install_id})

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
    now_iso = datetime.now(timezone.utc).isoformat()

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


@api_router.get("/admin/emails-outbox")
async def list_outbox(_: dict = Depends(require_admin)):
    """Boîte d'envoi (MOCKED) — les emails qui auraient dû partir."""
    items = await db.emails_outbox.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return items


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
    await send_email_mock(db, email, "Votre lien d'accès — Portail Pionnier", email_html,
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


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
