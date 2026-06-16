"""
LOT 2 — Collecte des Numéros de Série (V1 ultra-simple).

Onglet `10_NS_Declarations` :
    demande_id | pio_id | numero_serie | date_demande | statut | commentaire

Statuts : EN_ATTENTE / VALIDEE / REFUSEE
Compteur dans 04_Parametres : "Demande NS ID"
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Dict, List, Optional

from .sheets_service import get_sheets_service

logger = logging.getLogger(__name__)

TAB_KEY = "ns_declarations"
TAB_NAME = "10_NS_Declarations"
HEADERS = ["demande_id", "pio_id", "numero_serie", "date_demande", "statut", "commentaire"]

COUNTER_NAME = "Demande NS ID"
COUNTER_PREFIX = "NSD"

STATUT_PENDING = "EN_ATTENTE"
STATUT_VALIDATED = "VALIDEE"
STATUT_REJECTED = "REFUSEE"

# Regex large : on accepte tout NS commençant par lettres/chiffres (4+ caractères).
# Validation stricte = humaine (Sandrine valide visuellement).
NS_REGEX = re.compile(r"^[A-Z0-9][A-Z0-9\-]{3,}$")

_setup_lock = Lock()
_setup_done = False
_create_lock = Lock()


def ensure_setup() -> None:
    """Crée l'onglet `10_NS_Declarations` et le compteur `Demande NS ID` s'ils manquent.

    Idempotent. Appelé au premier accès via les endpoints (lazy).
    """
    global _setup_done
    if _setup_done:
        return
    with _setup_lock:
        if _setup_done:
            return
        svc = get_sheets_service()
        ss = svc._get_spreadsheet()

        # 1. Onglet
        try:
            ws = ss.worksheet(TAB_NAME)
            # Vérifier headers
            existing = ws.row_values(1)
            if existing != HEADERS:
                if not existing:
                    ws.update("A1:F1", [HEADERS])
                    logger.info(f"[ns_declarations] Headers injectés dans {TAB_NAME}")
                else:
                    logger.warning(
                        f"[ns_declarations] Headers existants {existing} != attendus {HEADERS}. "
                        f"Onglet conservé tel quel (intervention manuelle requise si schéma divergent)."
                    )
        except Exception:
            ws = ss.add_worksheet(title=TAB_NAME, rows=1000, cols=6)
            ws.update("A1:F1", [HEADERS])
            logger.info(f"[ns_declarations] Onglet {TAB_NAME} créé avec headers")

        # 2. Compteur (colonnes F=Compteurs / G=Valeur Actuelle)
        param_row = svc.find_row_by("parametres", "Compteurs", COUNTER_NAME)
        if not param_row:
            ws_param = svc.get_worksheet("parametres")
            all_values = ws_param.get_all_values()
            # Trouver la première ligne dont colonne F est vide
            target_row = None
            for idx, row in enumerate(all_values[1:], start=2):
                col_f = row[5] if len(row) > 5 else ""
                if not col_f.strip():
                    target_row = idx
                    break
            if target_row is None:
                target_row = len(all_values) + 1
            ws_param.update(f"F{target_row}:G{target_row}", [[COUNTER_NAME, 0]])
            logger.info(f"[ns_declarations] Compteur '{COUNTER_NAME}' ajouté en F{target_row}:G{target_row}")

        _setup_done = True


def _next_demande_id() -> str:
    """Incrémente le compteur Demande NS ID et retourne `NSD-XXX`."""
    svc = get_sheets_service()
    row_idx = svc.find_row_index_by("parametres", "Compteurs", COUNTER_NAME)
    if not row_idx:
        raise RuntimeError(f"Compteur '{COUNTER_NAME}' introuvable dans 04_Parametres")
    row = svc.find_row_by("parametres", "Compteurs", COUNTER_NAME) or {}
    try:
        current = int(str(row.get("Valeur Actuelle", 0)).strip() or 0)
    except ValueError:
        current = 0
    new_val = current + 1
    svc.update_cell("parametres", row_idx, "Valeur Actuelle", new_val)
    return f"{COUNTER_PREFIX}-{new_val:03d}"


def normalize_ns(value: str) -> str:
    """Met le NS en majuscules, retire espaces. Conserve tirets."""
    return re.sub(r"\s+", "", (value or "").upper())


def validate_ns_format(ns: str) -> Optional[str]:
    """Retourne un message d'erreur si invalide, None si OK."""
    if not ns:
        return "Le numéro de série est obligatoire."
    if len(ns) < 4:
        return "Le numéro de série semble trop court."
    if not NS_REGEX.match(ns):
        return "Format invalide. Utilisez uniquement lettres, chiffres et tirets (ex: HR88C23EFR0080)."
    return None


def create_declaration(pio_id: str, numero_serie: str, commentaire: str = "") -> Dict[str, Any]:
    """Crée une déclaration NS en statut EN_ATTENTE.

    Vérifie aussi qu'il n'y a pas déjà une demande EN_ATTENTE pour ce pio_id + NS.
    """
    ensure_setup()
    svc = get_sheets_service()
    ns_norm = normalize_ns(numero_serie)

    with _create_lock:
        # Anti-doublon simple : même pio_id + même NS en attente
        for rec in svc.read_all(TAB_KEY):
            if (str(rec.get("pio_id", "")).strip() == pio_id
                    and normalize_ns(str(rec.get("numero_serie", ""))) == ns_norm
                    and str(rec.get("statut", "")).strip() == STATUT_PENDING):
                return {
                    "demande_id": rec.get("demande_id"),
                    "statut": STATUT_PENDING,
                    "duplicate": True,
                }

        demande_id = _next_demande_id()
        date_demande = datetime.now(timezone.utc).isoformat()
        svc.append_row(TAB_KEY, [
            demande_id, pio_id, ns_norm, date_demande, STATUT_PENDING, commentaire,
        ])
        svc.log_event(
            "ns_declaration_submitted",
            install_id="", pio_id=pio_id,
            result="OK",
            message=f"demande_id={demande_id} ns={ns_norm}",
        )
        return {"demande_id": demande_id, "statut": STATUT_PENDING, "duplicate": False}


def list_declarations(statut: Optional[str] = None) -> List[Dict[str, Any]]:
    ensure_setup()
    svc = get_sheets_service()
    rows = svc.read_all(TAB_KEY)
    if statut:
        rows = [r for r in rows if str(r.get("statut", "")).strip() == statut]
    # Tri par date_demande desc
    rows.sort(key=lambda r: str(r.get("date_demande", "")), reverse=True)
    return rows


def get_declaration(demande_id: str) -> Optional[Dict[str, Any]]:
    ensure_setup()
    svc = get_sheets_service()
    return svc.find_row_by(TAB_KEY, "demande_id", demande_id)


def _update_declaration_status(demande_id: str, statut: str, commentaire: str = "") -> Dict[str, Any]:
    svc = get_sheets_service()
    row_idx = svc.find_row_index_by(TAB_KEY, "demande_id", demande_id)
    if not row_idx:
        raise ValueError(f"Demande {demande_id} introuvable")
    svc.update_cell(TAB_KEY, row_idx, "statut", statut)
    if commentaire:
        svc.update_cell(TAB_KEY, row_idx, "commentaire", commentaire)
    return svc.find_row_by(TAB_KEY, "demande_id", demande_id) or {}


def reject_declaration(demande_id: str, motif: str = "") -> Dict[str, Any]:
    ensure_setup()
    row = get_declaration(demande_id)
    if not row:
        raise ValueError(f"Demande {demande_id} introuvable")
    if str(row.get("statut", "")).strip() != STATUT_PENDING:
        raise ValueError(f"Demande {demande_id} n'est pas en attente (statut={row.get('statut')})")
    updated = _update_declaration_status(demande_id, STATUT_REJECTED, motif or "Refusée par admin")
    get_sheets_service().log_event(
        "ns_declaration_rejected",
        pio_id=row.get("pio_id", ""),
        result="OK",
        message=f"demande_id={demande_id} motif={motif}",
    )
    return updated


def find_target_installation(pio_id: str) -> Optional[Dict[str, Any]]:
    """Trouve l'installation cible pour rattacher le NS.

    Règle V1 simple :
    - On cherche dans `02_Installations` les lignes du pionnier
    - On prend la première dont `numero_serie` est vide
    - Sinon, on prend la première installation tout court (admin pourra ajuster)
    """
    svc = get_sheets_service()
    rows = svc.read_all("installations")
    candidates = [r for r in rows if str(r.get("pio_id", "")).strip() == pio_id]
    if not candidates:
        return None
    for r in candidates:
        if not str(r.get("numero_serie", "")).strip():
            return r
    return candidates[0]


def attach_ns_to_installation(pio_id: str, numero_serie: str) -> Optional[Dict[str, Any]]:
    """Met à jour `02_Installations.numero_serie` pour le pionnier.

    Retourne la ligne installation mise à jour (ou None si pas d'installation trouvée).
    """
    svc = get_sheets_service()
    install = find_target_installation(pio_id)
    if not install:
        return None
    install_id = install.get("install_id")
    row_idx = svc.find_row_index_by("installations", "install_id", install_id)
    if not row_idx:
        return None
    svc.update_cell("installations", row_idx, "numero_serie", numero_serie)
    # Relecture
    return svc.find_row_by("installations", "install_id", install_id)


def validate_declaration(demande_id: str, regenerate_passeport_fn=None) -> Dict[str, Any]:
    """Valide une demande : rattache le NS à l'installation + régénère le passeport.

    `regenerate_passeport_fn(install_row)` est injecté par server.py pour éviter
    les imports circulaires.
    """
    ensure_setup()
    row = get_declaration(demande_id)
    if not row:
        raise ValueError(f"Demande {demande_id} introuvable")
    if str(row.get("statut", "")).strip() != STATUT_PENDING:
        raise ValueError(f"Demande {demande_id} n'est pas en attente (statut={row.get('statut')})")

    pio_id = str(row.get("pio_id", "")).strip()
    numero_serie = normalize_ns(str(row.get("numero_serie", "")))

    install_updated = attach_ns_to_installation(pio_id, numero_serie)
    install_id = (install_updated or {}).get("install_id", "")

    # Régénération passeport (best-effort, on n'échoue pas la validation si ça plante)
    passeport_url = ""
    if install_updated and regenerate_passeport_fn:
        try:
            passeport_url = regenerate_passeport_fn(install_updated)
        except Exception as e:
            logger.warning(f"[ns_declarations] Régénération passeport échouée : {e}")

    updated = _update_declaration_status(demande_id, STATUT_VALIDATED, "Validée par admin")
    get_sheets_service().log_event(
        "ns_declaration_validated",
        install_id=install_id,
        pio_id=pio_id,
        result="OK",
        message=f"demande_id={demande_id} ns={numero_serie} install_id={install_id}",
    )
    return {
        **updated,
        "install_id": install_id,
        "passeport_url": passeport_url,
    }
