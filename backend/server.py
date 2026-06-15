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
from fastapi import FastAPI, APIRouter, HTTPException, Header, Depends, UploadFile, File, Form, Request
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional
import os
import logging
import httpx
import jwt as pyjwt

from services.sheets_service import get_sheets_service
from services.counter_service import increment_counter, peek_next_id, get_current_counter
from services.github_service import get_github_service
from services.template_service import render_template, TEMPLATE_DIR
from services.email_service import send_email_mock, get_outbox_snapshot
from services.catalog import get_product, HISTORIC_FALLBACK_PHOTO
from services.pdf_extractor import extract_location_photo

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
    """Payload accepté par /api/webhook/livraison.

    Supporte 2 formats :
    - PIONNIERS-DATA canonique (champs en français : nom, prenom, email, …)
    - SAV-natif (champs alias : ns, client, email_client, date, rapport_pdf_url)

    Les champs requis (`produit`, `territoire`, etc.) peuvent être absents du
    webhook : ils seront alors complétés par parsing du PDF (`rapport_pdf_url`)
    et/ou par les defaults Mayotte.
    """
    # === Identifiants & contexte ===
    type: Optional[str] = "LIVRAISON"
    report_id: Optional[str] = None  # idempotence

    # === Client — format canonique ===
    nom: Optional[str] = None
    prenom: Optional[str] = None
    email: Optional[EmailStr] = None
    telephone: Optional[str] = ""

    # === Client — alias SAV-natif ===
    client: Optional[str] = None        # "Sébastien FUMAZ" → split en nom + prenom
    email_client: Optional[EmailStr] = None  # alias de email

    # === Matériel — format canonique ===
    numero_serie: Optional[str] = None
    produit: Optional[str] = None
    territoire: Optional[str] = None
    pays: Optional[str] = ""

    # === Matériel — alias SAV-natif ===
    ns: Optional[str] = None            # alias de numero_serie

    # === Lieu / date — format canonique ===
    localisation: Optional[str] = ""
    date_installation: Optional[str] = None  # YYYY-MM-DD

    # === Lieu / date — alias SAV-natif ===
    date: Optional[str] = None          # DD/MM/YYYY → date_installation
    prochain_entretien: Optional[str] = None  # info SAV, non utilisée V1

    # === Intervention ===
    technicien: Optional[str] = ""
    fondateur: Optional[bool] = False

    # === Photos (override) ===
    photo_generateur_url: Optional[str] = ""
    photo_emplacement_url: Optional[str] = ""

    # === PDF source ===
    rapport_pdf_url: Optional[str] = None
    pdf_url: Optional[str] = None       # alias historique


class SavInput(BaseModel):
    """Payload du webhook SAV (rapport de maintenance).

    Minimaliste : crée une ligne dans 05_Maintenances + régénère le passeport.
    Aucune photo, aucun ticket, aucun ERP.
    """
    install_id: str
    date_intervention: Optional[str] = None  # YYYY-MM-DD, défaut = aujourd'hui
    type_intervention: str
    technicien: Optional[str] = ""
    statut: Optional[str] = "Réalisé"  # Réalisé / Terminé / OK / En cours / etc.
    observations: Optional[str] = ""
    pieces_changees: Optional[str] = ""
    prochain_rdv: Optional[str] = ""
    source: Optional[str] = "backend_sav"
    rapport_url: Optional[str] = ""


class MaintenanceInput(BaseModel):  # noqa: D401 — DEPRECATED, remplacé par SavInput
    """DEPRECATED — conservé pour compat éventuelle. Utiliser SavInput."""
    numero_serie: str
    type: str
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


# Defaults V1 — focus Mayotte uniquement. Quand on s'ouvrira à d'autres
# territoires, on devra soit (a) recevoir le champ via webhook/PIONNIERS-DATA,
# soit (b) détecter via le code postal du PDF.
DEFAULT_TERRITOIRE = "MAYOTTE"
DEFAULT_PAYS = "FRANCE"


async def _normalize_livraison_payload(payload: LivraisonInput) -> LivraisonInput:
    """Fusionne le payload SAV-natif avec les données extraites du PDF.

    Étapes :
    1. Alias SAV → canonique (`ns→numero_serie`, `client→nom+prenom`, `date→date_installation`, etc.)
    2. Téléchargement du PDF si `rapport_pdf_url` fourni
    3. Extraction des champs labellisés du PDF (`Modèle:`, `Adresse:`, etc.) pour combler ce qui manque
    4. Defaults Mayotte/FRANCE si toujours rien

    Le PDF (bytes) est attaché à l'instance via attribut `_pdf_bytes` pour
    éviter un 2e téléchargement plus loin dans le pipeline.
    """
    from services.pdf_extractor import extract_fields, split_client_name, parse_date_fr

    # 1. Aliasing SAV-natif → format canonique
    if payload.ns and not payload.numero_serie:
        payload.numero_serie = payload.ns
    if payload.email_client and not payload.email:
        payload.email = payload.email_client
    if payload.client and not (payload.nom and payload.prenom):
        prenom, nom = split_client_name(payload.client)
        payload.nom = payload.nom or nom
        payload.prenom = payload.prenom or prenom
    if payload.date and not payload.date_installation:
        converted = parse_date_fr(payload.date)
        if converted:
            payload.date_installation = converted
    if payload.rapport_pdf_url and not payload.pdf_url:
        payload.pdf_url = payload.rapport_pdf_url

    # 2. Téléchargement du PDF (une seule fois — réutilisé plus loin dans le pipeline)
    pdf_bytes = getattr(payload, "_pdf_bytes", None)
    pdf_source_url = payload.rapport_pdf_url or payload.pdf_url
    if pdf_bytes is None and pdf_source_url:
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                resp = await client.get(pdf_source_url)
                resp.raise_for_status()
                pdf_bytes = resp.content
        except Exception as e:
            logger.warning(f"PDF download failed ({pdf_source_url}): {e}")
            pdf_bytes = None

    # 3. Parsing du PDF pour les champs manquants
    if pdf_bytes:
        try:
            pdf_fields = extract_fields(pdf_bytes)
        except Exception as e:
            logger.warning(f"PDF field extraction failed: {e}")
            pdf_fields = {}

        if not payload.produit and pdf_fields.get("produit"):
            payload.produit = pdf_fields["produit"]
        if not payload.numero_serie and pdf_fields.get("numero_serie"):
            payload.numero_serie = pdf_fields["numero_serie"]
        if not payload.localisation and pdf_fields.get("adresse"):
            payload.localisation = pdf_fields["adresse"]
        if not payload.date_installation and pdf_fields.get("date"):
            payload.date_installation = parse_date_fr(pdf_fields["date"])
        if not payload.technicien and pdf_fields.get("technicien"):
            payload.technicien = pdf_fields["technicien"]
        if not (payload.nom and payload.prenom) and pdf_fields.get("client"):
            prenom, nom = split_client_name(pdf_fields["client"])
            payload.nom = payload.nom or nom
            payload.prenom = payload.prenom or prenom

    # 4. Defaults Mayotte (V1 — focus Mayotte uniquement)
    if not payload.territoire:
        payload.territoire = DEFAULT_TERRITOIRE
    if not payload.pays:
        payload.pays = DEFAULT_PAYS

    # Stocke le PDF bytes pour réutilisation dans le pipeline (évite 2 download)
    setattr(payload, "_pdf_bytes", pdf_bytes)
    return payload


def _validate_livraison_payload(payload: LivraisonInput) -> None:
    """Vérifie qu'après normalisation, les champs critiques sont présents.
    Lève HTTPException(422) avec un message explicite en cas de manque."""
    missing = []
    if not payload.nom:
        missing.append("nom (ou client)")
    if not payload.prenom:
        missing.append("prenom (ou client)")
    if not payload.email:
        missing.append("email (ou email_client)")
    if not payload.numero_serie:
        missing.append("numero_serie (ou ns, ou PDF avec champ 'N° Série')")
    if not payload.produit:
        missing.append("produit (ou PDF avec champ 'Modèle')")
    if missing:
        raise HTTPException(422, f"Champs manquants après normalisation: {', '.join(missing)}")


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
async def _process_livraison(payload: LivraisonInput, pdf_bytes: Optional[bytes] = None) -> dict:
    """
    Pipeline LIVRAISON.

    0. Normalisation (alias SAV → canonique, parsing PDF, defaults Mayotte)
    1. Idempotence : si report_id déjà présent dans 02_Installations, renvoyer les IDs existants
    2. Allocate PIO-XXXX, INST-XXXX, 4× DOC-XXXX (5× si fondateur)
    3. Extraire la photo d'emplacement depuis le PDF et la pousser sur GitHub
    4. Render templates PROD (passeport, certificats, portail, email, ambassadeur)
    5. Push GitHub Pages
    6. Append rows in 01_Pionniers + 02_Installations + 06_Documents
    7. Mock email
    """
    # 0. Normalisation (mutates payload in place)
    if pdf_bytes is not None:
        setattr(payload, "_pdf_bytes", pdf_bytes)
    payload = await _normalize_livraison_payload(payload)
    _validate_livraison_payload(payload)
    pdf_bytes = getattr(payload, "_pdf_bytes", None)

    sheets = get_sheets_service()
    gh = get_github_service()

    # 0. Idempotence via report_id (col W de 02_Installations)
    if payload.report_id:
        try:
            existing = sheets.find_row_by("installations", "report_id", payload.report_id)
        except Exception as e:
            logger.warning(f"Idempotence check failed (non-bloquant) : {e}")
            existing = None
        if existing:
            pages_base = _github_pages_base()
            inst_id = existing.get("install_id", "")
            pio_id = existing.get("pio_id", "")
            logger.info(f"Idempotent replay détecté pour report_id={payload.report_id} -> {inst_id}/{pio_id}")
            return {
                "pio_id": pio_id,
                "install_id": inst_id,
                "url_portail": f"{pages_base}/pionniers/{pio_id}/index.html",
                "url_passeport": f"{pages_base}/passeports/{inst_id}/index.html",
                "url_certificat": f"{pages_base}/certificats/pionnier/{pio_id}.html",
                "url_garantie": f"{pages_base}/certificats/garantie/{inst_id}.html",
                "idempotent_replay": True,
                "report_id": payload.report_id,
            }

    # 1. IDs
    _, pio_id = increment_counter("pionnier")
    _, install_id = increment_counter("installation")

    # === RÈGLE FONDATEUR : les 100 premiers PIO_ID sont fondateurs automatiquement ===
    # Override possible via env FORCE_FONDATEUR_FOR_TEST=true (test mode)
    try:
        _pio_num = int(pio_id.replace("PIO-", ""))
    except ValueError:
        _pio_num = 99999
    _auto_fondateur = _pio_num <= 100
    _test_force = os.environ.get("FORCE_FONDATEUR_FOR_TEST", "").strip().lower() in ("true", "1", "yes")
    if _auto_fondateur or _test_force:
        payload.fondateur = True
        logger.info(
            f"[FONDATEUR] {pio_id} marqué fondateur=True "
            f"(auto={_auto_fondateur}, force_test={_test_force})"
        )

    _, doc_passeport = increment_counter("document")
    _, doc_cert_pio = increment_counter("document")
    _, doc_cert_gar = increment_counter("document")
    _, doc_portail = increment_counter("document")
    doc_ambassadeur = ""
    if payload.fondateur:
        _, doc_ambassadeur = increment_counter("document")

    date_inst = payload.date_installation or _today_iso()
    produit_info = get_product(payload.produit)
    date_garantie_fin = _compute_garantie_fin(date_inst, produit_info["garantie_mois"])
    now_iso = datetime.now(timezone.utc).isoformat()
    annee = str(datetime.now(timezone.utc).year)
    nom_complet = f"{payload.prenom} {payload.nom}".strip()
    pays_affiche = payload.territoire or payload.pays

    # 2. URLs GitHub Pages (alignées convention prod)
    pages_base = _github_pages_base()
    url_passeport = f"{pages_base}/passeports/{install_id}/index.html"
    url_certificat = f"{pages_base}/certificats/pionnier/{pio_id}.html"
    url_garantie = f"{pages_base}/certificats/garantie/{install_id}.html"
    url_portail = f"{pages_base}/pionniers/{pio_id}/index.html"
    url_carte = f"{pages_base}/cartes/{pio_id}.html"
    url_ambassadeur = f"{pages_base}/ambassadeurs/{pio_id}.html" if payload.fondateur else ""
    # Page d'invitation Ambassadeur universelle (existe à la racine /docs/ambassadeur.html)
    url_ambassadeur_landing = f"{pages_base}/ambassadeur.html"
    url_famille = pages_base + "/"

    # Badges luxe (badge-fondateur.html + badge-ambassadeur.html templates personnalisés)
    url_badge_fondateur = f"{pages_base}/badges/fondateur/{pio_id}.html" if payload.fondateur else ""
    url_badge_ambassadeur = f"{pages_base}/badges/ambassadeur/{pio_id}.html" if payload.fondateur else ""

    # URL historique relative à stocker en Sheet (convention héritée Make)
    passeport_url_sheet = f"/install/{install_id}"

    # 2.bis Extraction de la photo d'emplacement depuis le PDF déjà téléchargé en normalisation
    photo_emplacement_url = payload.photo_emplacement_url or ""
    if not photo_emplacement_url and pdf_bytes:
        extracted = extract_location_photo(pdf_bytes)
        if extracted:
            img_bytes, ext = extracted
            ext = "jpg" if ext.lower() in ("jpeg", "jpg") else ext
            photo_path = f"docs/photos/{install_id}/emplacement.{ext}"
            try:
                photo_emplacement_url = gh.push_binary_file(
                    photo_path, img_bytes,
                    f"Add photo emplacement {install_id}",
                )
            except Exception as e:
                logger.error(f"GitHub push photo failed: {e}")
                sheets.log_event("github_push_photo", install_id, pio_id, "ERROR", str(e), "")

    if not photo_emplacement_url:
        photo_emplacement_url = HISTORIC_FALLBACK_PHOTO

    # Photo générateur : payload > catalog Cloudinary > fallback historique
    photo_generateur_url = (
        payload.photo_generateur_url
        or produit_info.get("photo_generateur_url", "")
        or HISTORIC_FALLBACK_PHOTO
    )

    # 3. Render templates PROD
    # 3a. Passeport (snake_case, 27 variables ; Q2 = display:none pour blocs sans donnée)
    histo_html = (
        '<div class="histo-row">'
        f'<div class="histo-icon"></div>'
        f'<div class="histo-date">{date_inst}</div>'
        '<div class="histo-type">Installation initiale</div>'
        '<div class="histo-tech">—</div>'
        '<div class="histo-pdf"></div>'
        '</div>'
    )
    ctx_passeport = {
        "install_id": install_id,
        "pio_id": pio_id,
        "annee": str(datetime.now(timezone.utc).year),
        "pays": pays_affiche,
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
        "url_garantie": url_garantie,
        "url_fiche_technique": produit_info.get("fiche_technique_url", ""),
        "url_manuel": produit_info.get("manuel_url", ""),
        "url_certificat": url_certificat,
        "url_ambassadeur_cta": url_ambassadeur_landing,
        "url_telecharger_tout": "",
        # Statut communauté — affiche les badges Fondateur + Ambassadeur (iframes)
        "display_pionnier": "block" if payload.fondateur else "none",
        "display_ambassadeur": "block" if payload.fondateur else "none",
        "display_statut_communaute": "block" if payload.fondateur else "none",
        "badge_fondateur_url": url_badge_fondateur,
        "badge_ambassadeur_url": url_badge_ambassadeur,
        "photo_generateur_url": photo_generateur_url,
        "photo_emplacement_url": photo_emplacement_url,
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
        "URL_GARANTIE": url_garantie,  # QR pointe vers cette URL
    }
    html_cert_gar = render_template("certificat-garantie.html", ctx_cert_gar)

    # 3d. Portail Pionnier — refonte design Geobuilder V1 (cyan électrique)
    # Construire mois d'adhésion en français
    _MOIS_FR = ["", "JANVIER", "FÉVRIER", "MARS", "AVRIL", "MAI", "JUIN", "JUILLET", "AOÛT", "SEPTEMBRE", "OCTOBRE", "NOVEMBRE", "DÉCEMBRE"]
    try:
        _d = datetime.fromisoformat(date_inst.replace("Z", "+00:00")) if "T" in date_inst else datetime.strptime(date_inst[:10], "%Y-%m-%d")
        mois_annee_adhesion = f"{_MOIS_FR[_d.month]} {_d.year}"
        date_install_fmt = f"{_d.day} {_MOIS_FR[_d.month].lower()} {_d.year}"
        _dgar = _d.replace(year=_d.year + (produit_info.get("garantie_mois", 24) // 12))
        date_garantie_fin = f"{_dgar.day} {_MOIS_FR[_dgar.month].lower()} {_dgar.year}"
    except Exception:
        mois_annee_adhesion = annee
        date_install_fmt = date_inst[:10]
        date_garantie_fin = ""

    # Distinctions — règles V1
    # Carte Ambassadeur (Acquis si fondateur) : pointe vers badge personnalisé /badges/ambassadeur/{PIO}.html
    # Carte Super Ambassadeur : reste verrouillée (statut + template pas encore implémentés)
    if payload.fondateur:
        amb_class, amb_label = "acquis", "Acquis"
        amb_dot = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>'
        sup_class, sup_label, sup_dot = "non-acquis", "Non acquis", ""
        carte_amb_class, carte_amb_status, url_carte_amb = "acquis", "Acquise", url_badge_ambassadeur
        carte_sup_class, carte_sup_status, url_carte_sup = "locked", "Non acquise", "#"
    else:
        amb_class, amb_label, amb_dot = "encours", "En cours", ""
        sup_class, sup_label, sup_dot = "non-acquis", "Non acquis", ""
        carte_amb_class, carte_amb_status, url_carte_amb = "locked", "Non acquise", "#"
        carte_sup_class, carte_sup_status, url_carte_sup = "locked", "Non acquise", "#"

    territoire_complet = f"{pays_affiche}, {payload.pays}" if payload.pays and payload.pays != pays_affiche else pays_affiche

    ctx_portail = {
        "PIO_ID": pio_id,
        "PRENOM": payload.prenom,
        "NOM_COMPLET": nom_complet,
        "ANNEE": annee,
        "MOIS_ANNEE_ADHESION": mois_annee_adhesion,
        "PRODUIT_LABEL": produit_info['label'],
        "PRODUIT_IMAGE_URL": produit_info.get("photo_generateur_url", ""),
        "NUMERO_SERIE": payload.numero_serie or f"MJ-{annee}-{install_id.replace('INST-','')}",
        "TERRITOIRE_COMPLET": territoire_complet,
        "DATE_INSTALLATION_FORMATEE": date_install_fmt,
        "DATE_GARANTIE_FIN": date_garantie_fin,
        "URL_CERTIFICAT": url_certificat,
        "URL_GARANTIE": url_garantie,
        "URL_PASSEPORT": url_passeport,
        "URL_CARTE": url_carte,
        "URL_WHATSAPP": os.environ.get("URL_WHATSAPP_GROUPE", "#"),
        "URL_FACEBOOK": os.environ.get("URL_FACEBOOK", "#"),
        "URL_INSTAGRAM": os.environ.get("URL_INSTAGRAM", "#"),
        "URL_YOUTUBE": os.environ.get("URL_YOUTUBE", "#"),
        "URL_LINKEDIN": os.environ.get("URL_LINKEDIN", "#"),
        # Statuts dynamiques distinctions
        "STATUS_AMBASSADEUR_CLASS": amb_class,
        "STATUS_AMBASSADEUR_LABEL": amb_label,
        "STATUS_AMBASSADEUR_DOT": amb_dot,
        "STATUS_SUPER_CLASS": sup_class,
        "STATUS_SUPER_LABEL": sup_label,
        "STATUS_SUPER_DOT": sup_dot,
        # Mini-cartes Ambassadeur / Super Ambassadeur (verrouillées si non acquises)
        "CARTE_AMBASSADEUR_CLASS": carte_amb_class,
        "CARTE_AMBASSADEUR_STATUS": carte_amb_status,
        "URL_CARTE_AMBASSADEUR": url_carte_amb,
        "CARTE_SUPER_CLASS": carte_sup_class,
        "CARTE_SUPER_STATUS": carte_sup_status,
        "URL_CARTE_SUPER": url_carte_sup,
    }
    html_portail = render_template("portail_pionnier.html", ctx_portail)

    # 3e. Email final (UPPER_SNAKE)
    # Logique CTA "Devenez Ambassadeur" :
    # - Toujours le même texte "Devenez Ambassadeur" + même phrase de description
    # - Pour fondateurs : pointe vers la page perso /ambassadeurs/{PIO_ID}.html
    # - Pour les autres : pointe vers la landing universelle /ambassadeur.html
    cta_url = url_ambassadeur if payload.fondateur else url_ambassadeur_landing
    cta_title = "Devenez Ambassadeur"
    cta_desc = "Les Pionniers ouvrent la voie."

    ctx_email = {
        "ANNEE": annee,
        "INSTALL_ID": install_id,
        "PAYS": pays_affiche,
        "PIO_ID": pio_id,
        "URL_CARTE": url_carte,
        "URL_CERTIFICAT": url_certificat,
        "URL_ESPACE": url_portail,
        "URL_FAMILLE": url_famille,
        "URL_GARANTIE": url_garantie,
        "URL_PASSEPORT": url_passeport,
        "URL_AMBASSADEUR_CTA": cta_url,
        "CTA_AMBASSADEUR_TITLE": cta_title,
        "CTA_AMBASSADEUR_DESC": cta_desc,
    }
    email_html = render_template("email-final.html", ctx_email)

    # 3e-bis. Badge Pionnier (HTML éditable, QR vers espace pionnier)
    from urllib.parse import quote as _quote
    ctx_badge = {
        "NOM_COMPLET": nom_complet,
        "PIO_ID": pio_id,
        "TERRITOIRE": pays_affiche,
        "ANNEE": annee,
        "URL_ESPACE": url_portail,
        "QR_URL_ENCODED": _quote(url_portail, safe=""),
    }
    html_badge = render_template("badge-pionnier.html", ctx_badge)

    # 3f. Page Ambassadeur (uniquement si fondateur=true)
    html_ambassadeur = ""
    if payload.fondateur:
        ctx_ambassadeur = {
            "annee": annee,
            "nom": payload.nom,
            "prenom": payload.prenom,
            "email": payload.email,
            "pio_id": pio_id,
            "territoire": payload.territoire,
            "redirect_url": url_portail,
            "webhook_ambassadeur_url": os.environ.get("AMBASSADEUR_WEBHOOK_URL", ""),
        }
        html_ambassadeur = render_template("ambassadeur.html", ctx_ambassadeur)

    # 3g. Badges luxe Fondateur + Ambassadeur (templates {{PIO_ID}}/{{ANNEE}}/{{PAYS}})
    html_badge_fondateur = ""
    html_badge_amb_perso = ""
    if payload.fondateur:
        ctx_badge_luxe = {
            "PIO_ID": pio_id,
            "ANNEE": str(datetime.now(timezone.utc).year),
            "PAYS": pays_affiche,
        }
        html_badge_fondateur = render_template("badge-fondateur.html", ctx_badge_luxe)
        html_badge_amb_perso = render_template("badge-ambassadeur.html", ctx_badge_luxe)

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
        pushed["badge"] = gh.push_file(
            f"docs/cartes/{pio_id}.html", html_badge,
            f"Add badge pionnier {pio_id}")
        if payload.fondateur and html_ambassadeur:
            pushed["ambassadeur"] = gh.push_file(
                f"docs/ambassadeurs/{pio_id}.html", html_ambassadeur,
                f"Add ambassadeur {pio_id} (fondateur)")
        if payload.fondateur and html_badge_fondateur:
            pushed["badge_fondateur"] = gh.push_file(
                f"docs/badges/fondateur/{pio_id}.html", html_badge_fondateur,
                f"Add badge fondateur luxe {pio_id}")
        if payload.fondateur and html_badge_amb_perso:
            pushed["badge_ambassadeur"] = gh.push_file(
                f"docs/badges/ambassadeur/{pio_id}.html", html_badge_amb_perso,
                f"Add badge ambassadeur luxe {pio_id}")
    except Exception as e:
        logger.error(f"GitHub push failed: {e}")
        sheets.log_event("github_push", install_id, pio_id, "ERROR", str(e), "")
        raise HTTPException(502, f"GitHub push failed: {e}")

    # 5. Append in 01_Pionniers — 22 colonnes alignées Sheet réel
    try:
        sheets.append_row("pionniers", [
            pio_id,                       # A  pio_id
            payload.nom,                  # B  nom
            payload.prenom,               # C  prenom
            payload.email,                # D  email
            payload.telephone,            # E  telephone
            payload.pays,                 # F  pays
            payload.territoire,           # G  territoire
            "",                           # H  client_type (V1 vide)
            now_iso,                      # I  date_entree
            "Pionnier",                   # J  statut
            "true" if payload.fondateur else "false",  # K  fondateur
            "true" if payload.fondateur else "false",  # L  ambassadeur (immédiat si fondateur)
            "Fondateur · Ambassadeur" if payload.fondateur else "",  # M  communaute_statut
            "",                           # N  droit_image
            "",                           # O  temoignage_autorise
            "",                           # P  visite_possible
            "backend_livraison",          # Q  source_creation
            "livraison_complete",         # R  workflow_status (Q4=b)
            "true",                       # S  welcome_email_sent
            url_certificat,               # T  certificat_url
            url_carte,                    # U  carte_url
            "",                           # V  qr_code_url (V1)
        ])
    except Exception as e:
        logger.error(f"Sheet append pionniers failed: {e}")
        sheets.log_event("sheet_pionnier", install_id, pio_id, "ERROR", str(e), "")

    # 6. Append in 02_Installations — 23 colonnes (W = report_id pour idempotence)
    try:
        sheets.append_row("installations", [
            install_id,                                       # A  install_id
            pio_id,                                           # B  pio_id
            produit_info["label"],                            # C  produit
            payload.numero_serie,                             # D  numero_serie
            date_inst,                                        # E  date_installation
            "",                                               # F  date_sortie
            payload.territoire,                               # G  territoire_installation
            payload.technicien or "",                         # H  installateur
            "active",                                         # I  installation_status (Q3=b)
            "true",                                           # J  pionnier_created (Q3=b)
            nom_complet,                                      # K  nom_client
            "",                                               # L  gamme (V1)
            "",                                               # M  contrat_maintenance_type
            date_garantie_fin,                                # N  date_garantie_fin
            payload.localisation or payload.territoire,       # O  localisation_precise
            "",                                               # P  statut_eau
            "",                                               # Q  derniere_maintenance
            "",                                               # R  prochain_entretien
            passeport_url_sheet,                              # S  passeport_url (Q1=a, URL relative)
            "true",                                           # T  installation_active (Q3=b)
            photo_generateur_url,                             # U  photo_generateur_url
            photo_emplacement_url,                            # V  photo_emplacement_url
            payload.report_id or "",                          # W  report_id (idempotence)
        ])
    except Exception as e:
        logger.error(f"Sheet append installations failed: {e}")
        sheets.log_event("sheet_install", install_id, pio_id, "ERROR", str(e), "")

    # 7. Append in 06_Documents — 10 colonnes
    try:
        docs_to_log = [
            (doc_passeport, install_id, "PASSEPORT", url_passeport),
            (doc_cert_pio, "", "CERTIFICAT_PIONNIER", url_certificat),
            (doc_cert_gar, install_id, "CERTIFICAT_GARANTIE", url_garantie),
            (doc_portail, "", "PORTAIL", url_portail),
        ]
        if payload.fondateur and doc_ambassadeur:
            docs_to_log.append((doc_ambassadeur, "", "AMBASSADEUR", url_ambassadeur))
        for d_id, d_inst, d_type, d_url in docs_to_log:
            sheets.append_row("documents", [
                d_id,         # A  doc_id
                d_inst,       # B  install_id (vide pour cert pionnier et portail)
                pio_id,       # C  pio_id
                d_type,       # D  type_doc
                now_iso,      # E  date_generation
                d_url,        # F  url_doc
                "generated",  # G  statut_envoi
                "",           # H  date_envoi
                "",           # I  canal_envoi
                "",           # J  html_content (vide pour ne pas polluer Sheets)
            ])
    except Exception as e:
        logger.error(f"Sheet append documents failed: {e}")
        sheets.log_event("sheet_documents", install_id, pio_id, "ERROR", str(e), "")

    # 8. Mock email
    await send_email_mock(
        payload.email,
        "Bienvenue dans la Famille des Pionniers Geobuilder",
        email_html,
        metadata={"pio_id": pio_id, "install_id": install_id},
    )

    sheets.log_event("livraison", install_id, pio_id, "OK",
                     f"Livraison processed ns={payload.numero_serie} report_id={payload.report_id or ''}", "")

    response = {
        "pio_id": pio_id, "install_id": install_id,
        "url_portail": url_portail, "url_passeport": url_passeport,
        "url_certificat": url_certificat, "url_garantie": url_garantie,
        "photo_generateur_url": photo_generateur_url,
        "photo_emplacement_url": photo_emplacement_url,
        "github": pushed,
        "report_id": payload.report_id or "",
    }
    if payload.fondateur:
        response["url_ambassadeur"] = url_ambassadeur
    return response


@api_router.post("/webhook/livraison")
async def webhook_livraison(payload: LivraisonInput):
    """Webhook public en JSON (Make/Drive). Si payload.pdf_url est renseigné,
    le PDF est téléchargé puis la photo terrain en est extraite."""
    try:
        return await _process_livraison(payload)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Webhook livraison failed")
        raise HTTPException(500, str(e))


@api_router.post("/webhook/livraison-upload")
async def webhook_livraison_upload(
    nom: str = Form(...),
    prenom: str = Form(...),
    email: EmailStr = Form(...),
    territoire: str = Form(...),
    produit: str = Form(...),
    numero_serie: str = Form(...),
    telephone: str = Form(""),
    pays: str = Form(""),
    date_installation: Optional[str] = Form(None),
    localisation: str = Form(""),
    technicien: str = Form(""),
    fondateur: bool = Form(False),
    report_id: Optional[str] = Form(None),
    type: str = Form("LIVRAISON"),
    pdf: Optional[UploadFile] = File(None),
):
    """Webhook LIVRAISON en multipart/form-data, accepte un PDF directement
    en pièce jointe (technicien / formulaire interne / SAV-Pionniers direct)."""
    pdf_bytes = await pdf.read() if pdf is not None else None
    payload = LivraisonInput(
        type=type, report_id=report_id,
        nom=nom, prenom=prenom, email=email, telephone=telephone,
        territoire=territoire, pays=pays, produit=produit,
        numero_serie=numero_serie, date_installation=date_installation,
        localisation=localisation, technicien=technicien, fondateur=fondateur,
    )
    try:
        return await _process_livraison(payload, pdf_bytes=pdf_bytes)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Webhook livraison-upload failed")
        raise HTTPException(500, str(e))


@api_router.post("/admin/livraison")
async def admin_create_livraison(payload: LivraisonInput, _: dict = Depends(require_admin)):
    """Création manuelle d'une livraison depuis l'interface admin."""
    return await _process_livraison(payload)


# =========================================================================
# ROUTES — AMBASSADEUR (signature électronique de consentement)
# =========================================================================
class AmbassadeurSignature(BaseModel):
    """Payload de signature électronique Ambassadeur.

    Émis depuis la page `/ambassadeurs/{PIO_ID}.html` quand le client coche
    les 3 cases d'autorisation et clique "Je rejoins les Ambassadeurs".

    Vaut signature électronique :
    - droit_image : utilisation photos/vidéos de l'installation
    - temoignage_autorise : publication témoignage
    - publication_autorisee : diffusion supports communication
    """
    pio_id: str
    nom: Optional[str] = ""
    prenom: Optional[str] = ""
    email: Optional[EmailStr] = None
    ambassadeur: Optional[str] = "OUI"
    droit_image: str
    temoignage_autorise: str
    publication_autorisee: str
    date_validation_ambassadeur: Optional[str] = None
    source: Optional[str] = "ambassadeur.html"


@api_router.post("/ambassadeur/signature")
async def ambassadeur_signature(
    payload: AmbassadeurSignature,
    request: Request,
):
    """Enregistre la signature électronique Ambassadeur dans `01_Pionniers`.

    Met à jour les colonnes :
    - L  ambassadeur          = TRUE
    - M  communaute_statut    = "Ambassadeur" (ou conserve "Fondateur · Ambassadeur")
    - N  droit_image          = OUI/NON
    - O  temoignage_autorise  = OUI/NON
    - P  visite_possible      = "" (V1, non utilisé)

    Stocke aussi un log légal complet dans `08_Automations_Log` (timestamp UTC
    + IP source pour preuve de signature).

    Renvoie 200 + JSON pour permettre au formulaire JS de basculer en succès.
    """
    sheets = get_sheets_service()
    ts_utc = payload.date_validation_ambassadeur or datetime.now(timezone.utc).isoformat()
    client_ip = request.client.host if request.client else ""
    user_agent = request.headers.get("user-agent", "")[:300]

    # 1. Trouve la ligne Pionnier
    try:
        idx = sheets.find_row_index_by("pionniers", "pio_id", payload.pio_id)
    except Exception as e:
        logger.error(f"Lookup PIO failed: {e}")
        raise HTTPException(500, "Sheet lookup failed")
    if not idx:
        logger.warning(f"PIO non trouvé pour signature ambassadeur: {payload.pio_id}")
        raise HTTPException(404, f"Pionnier {payload.pio_id} introuvable")

    # 2. Lit l'état existant pour préserver "Fondateur · …"
    rec = sheets.find_row_by("pionniers", "pio_id", payload.pio_id) or {}
    is_fondateur = str(rec.get("fondateur", "")).strip().lower() in ("true", "vrai", "1", "oui")
    new_statut = "Fondateur · Ambassadeur" if is_fondateur else "Ambassadeur"

    # 3. Patche les colonnes
    try:
        sheets.update_cell("pionniers", idx, "ambassadeur", "TRUE")
        sheets.update_cell("pionniers", idx, "communaute_statut", new_statut)
        sheets.update_cell("pionniers", idx, "droit_image", payload.droit_image)
        sheets.update_cell("pionniers", idx, "temoignage_autorise", payload.temoignage_autorise)
    except Exception as e:
        logger.error(f"Update pionnier failed: {e}")
        raise HTTPException(500, "Sheet update failed")

    # 4. Log légal (signature électronique — preuve juridique)
    signature_proof = (
        f"droit_image={payload.droit_image} | "
        f"temoignage={payload.temoignage_autorise} | "
        f"publication={payload.publication_autorisee} | "
        f"ts_utc={ts_utc} | "
        f"ip={client_ip} | "
        f"ua={user_agent}"
    )
    sheets.log_event(
        "ambassadeur_signature", "", payload.pio_id, "OK", signature_proof, ""
    )
    logger.info(
        f"[AMBASSADEUR_SIGNATURE] {payload.pio_id} -> ambassadeur=TRUE, "
        f"droit_image={payload.droit_image}, ip={client_ip}"
    )

    return {
        "status": "ok",
        "pio_id": payload.pio_id,
        "ambassadeur": "TRUE",
        "communaute_statut": new_statut,
        "signature_timestamp_utc": ts_utc,
    }


# =========================================================================
# ROUTES — SAV (Maintenance) — pipeline minimal
# =========================================================================
# Statuts qui rendent une maintenance visible dans le passeport (cf. spec).
_STATUTS_VISIBLES = {"réalisé", "realise", "réalisée", "terminé", "termine", "terminée", "ok"}


def _build_historique_html(install_id: str, install_row: dict, sheets) -> str:
    """Reconstruit le bloc HTML historique du passeport en lisant 05_Maintenances.

    Affiche : Date / Type intervention / Technicien / Observations.
    Filtre sur les statuts visibles (Réalisé / Terminé / OK).
    Inclut systématiquement la ligne "Installation initiale" en tête.
    """
    date_inst = (
        install_row.get("date_installation")
        or install_row.get("date installation")
        or ""
    )

    rows_html = [
        '<div class="histo-row">'
        '<div class="histo-icon"></div>'
        f'<div class="histo-date">{date_inst}</div>'
        '<div class="histo-type">Installation initiale</div>'
        '<div class="histo-tech">—</div>'
        '<div class="histo-pdf"></div>'
        '</div>'
    ]

    try:
        maint_rows = sheets.read_all("maintenances")
    except Exception as e:
        logger.warning(f"read maintenances failed: {e}")
        maint_rows = []

    # Tri par date décroissante (interventions récentes en haut)
    filtered = [
        r for r in maint_rows
        if str(r.get("install_id", "")).strip() == install_id
        and str(r.get("statut", "")).strip().lower() in _STATUTS_VISIBLES
    ]
    filtered.sort(key=lambda r: str(r.get("date_intervention", "")), reverse=True)

    for r in filtered:
        date = str(r.get("date_intervention", "") or "")
        type_inter = str(r.get("type_intervention", "") or "")
        technicien = str(r.get("technicien", "") or "—")
        observations = str(r.get("observations", "") or "")[:120]
        rows_html.append(
            '<div class="histo-row">'
            '<div class="histo-icon"></div>'
            f'<div class="histo-date">{date}</div>'
            f'<div class="histo-type">{type_inter}'
            + (f'<span class="desc">{observations}</span>' if observations else "")
            + '</div>'
            f'<div class="histo-tech">{technicien}</div>'
            '<div class="histo-pdf"></div>'
            '</div>'
        )
    return "".join(rows_html)


def _regenerate_passeport(install_row: dict, sheets, gh) -> str:
    """Régénère le passeport HTML pour une installation et le push sur GitHub Pages.

    Retourne l'URL publique du passeport.
    """
    install_id = (install_row.get("install_id") or "").strip()
    pio_id = (install_row.get("pio_id") or "").strip()
    produit_label = install_row.get("produit") or ""
    produit_info = get_product(produit_label)
    date_inst = install_row.get("date_installation") or install_row.get("date installation") or ""
    date_garantie_fin = (
        install_row.get("date_garantie_fin")
        or install_row.get("date garantie fin")
        or _compute_garantie_fin(date_inst, produit_info["garantie_mois"])
    )
    territoire = install_row.get("territoire_installation") or install_row.get("territoire installation") or ""
    pays_affiche = install_row.get("territoire_installation") or install_row.get("pays") or territoire
    nom_complet = install_row.get("nom_client") or ""
    localisation_precise = install_row.get("localisation_precise") or territoire
    numero_serie = install_row.get("numero_serie") or install_row.get("numéro_serie") or install_row.get("Numéro série") or ""
    photo_gen = install_row.get("photo_generateur_url") or produit_info.get("photo_generateur_url") or HISTORIC_FALLBACK_PHOTO
    photo_emp = install_row.get("photo_emplacement_url") or HISTORIC_FALLBACK_PHOTO

    pages_base = _github_pages_base()
    url_passeport = f"{pages_base}/passeports/{install_id}/index.html"
    url_certificat = f"{pages_base}/certificats/pionnier/{pio_id}.html"

    historique_html = _build_historique_html(install_id, install_row, sheets)

    ctx = {
        "install_id": install_id,
        "pio_id": pio_id,
        "numero_serie": numero_serie,
        "produit": produit_info["label"],
        "date_installation": date_inst,
        "date_garantie_fin": date_garantie_fin,
        "territoire_installation": territoire,
        "pays_affiche": pays_affiche,
        "localisation_precise": localisation_precise,
        "statut_label": "Pionnier",
        "statut_class": "active",
        "garantie_label": "Active",
        "garantie_class": "active",
        "historique_html": historique_html,
        "passeport_url": url_passeport,
        "url_garantie": f"{pages_base}/certificats/garantie/{install_id}.html",
        "url_fiche_technique": produit_info.get("fiche_technique_url", ""),
        "url_manuel": produit_info.get("manuel_url", ""),
        "url_certificat": url_certificat,
        "url_ambassadeur_cta": f"{pages_base}/ambassadeur.html",
        "url_telecharger_tout": "",
        "display_pionnier": "block",
        "display_ambassadeur": "none",
        "display_statut_communaute": "block",
        "badge_pionnier_url": "",
        "badge_ambassadeur_url": "",
        "photo_generateur_url": photo_gen,
        "photo_emplacement_url": photo_emp,
        "prochain_entretien": "",
        "prochain_dans": "",
        "prochain_type": "",
        "prochain_rdv_url": "",
        # Bonus contexte (nom client en cas de placeholder futur)
        "nom_complet": nom_complet,
    }
    html = render_template("passeport_installation.html", ctx)
    gh.push_file(
        f"docs/passeports/{install_id}/index.html", html,
        f"Update passeport {install_id} (SAV)",
    )
    return url_passeport


async def _process_sav(payload: SavInput) -> dict:
    """Pipeline SAV minimal :
    1. Vérifier que l'installation existe (lecture 02_Installations).
    2. Allouer MAINT-XXXX.
    3. Append une ligne dans 05_Maintenances (12 colonnes A-L).
    4. Régénérer le passeport + push GitHub.
    Aucune photo, aucun ticket, aucun ERP.
    """
    sheets = get_sheets_service()
    gh = get_github_service()

    install = sheets.find_row_by("installations", "install_id", payload.install_id)
    if not install:
        raise HTTPException(404, f"No installation found for install_id={payload.install_id}")

    pio_id = (install.get("pio_id") or "").strip()
    _, maint_id = increment_counter("maintenance")
    date_m = payload.date_intervention or _today_iso()

    # 3. Append 05_Maintenances — 12 colonnes A..L (cf. structure réelle Sheet)
    try:
        sheets.append_row("maintenances", [
            maint_id,                      # A  maintenance_id
            payload.install_id,            # B  install_id
            pio_id,                        # C  pio_id
            date_m,                        # D  date_intervention
            payload.type_intervention,     # E  type_intervention
            payload.technicien or "",      # F  technicien
            payload.statut or "Réalisé",   # G  statut
            payload.rapport_url or "",     # H  rapport_url
            payload.observations or "",    # I  observations
            payload.pieces_changees or "", # J  pieces_changees
            payload.prochain_rdv or "",    # K  prochain_rdv
            payload.source or "backend_sav",  # L  source
        ])
    except Exception as e:
        logger.error(f"Sheet append maintenances failed: {e}")
        sheets.log_event("sheet_maintenance", payload.install_id, pio_id, "ERROR", str(e), "")
        raise HTTPException(500, f"Sheet write failed: {e}")

    # 4. Régénération passeport + push GitHub
    try:
        url_passeport = _regenerate_passeport(install, sheets, gh)
    except Exception as e:
        logger.error(f"Passeport regeneration failed: {e}")
        sheets.log_event("regen_passeport", payload.install_id, pio_id, "ERROR", str(e), "")
        raise HTTPException(502, f"Passeport regeneration failed: {e}")

    sheets.log_event("sav", payload.install_id, pio_id, "OK",
                     f"SAV ajouté maint={maint_id} type={payload.type_intervention}", "")

    return {
        "maintenance_id": maint_id,
        "install_id": payload.install_id,
        "pio_id": pio_id,
        "url_passeport": url_passeport,
    }


@api_router.post("/sav/rapport")
async def sav_rapport(payload: SavInput):
    """Webhook public SAV (Make/Odoo). Append + régénération passeport."""
    return await _process_sav(payload)


@api_router.post("/admin/sav")
async def admin_create_sav(payload: SavInput, _: dict = Depends(require_admin)):
    return await _process_sav(payload)


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


@api_router.get("/admin/installation/{install_id}")
async def admin_get_installation(install_id: str, _: dict = Depends(require_admin)):
    """Retourne une installation par son ID + historique des maintenances filtrées."""
    sheets = get_sheets_service()
    install = sheets.find_row_by("installations", "install_id", install_id)
    if not install:
        raise HTTPException(404, f"No installation found for {install_id}")
    maints = [
        r for r in sheets.read_all("maintenances")
        if str(r.get("install_id", "")).strip() == install_id
    ]
    return {"installation": install, "maintenances": maints}


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
