"""
Catalogue produits Geobuilder (lecture dynamique depuis Sheet `07_Catalog`).

- Cache mémoire 5 minutes (évite saturation quota Sheets API 60 reads/min)
- Fallback hardcodé si Sheet inaccessible (résilience)
- Si une ligne mal saisie : log warning, garde l'ancienne valeur
- API publique inchangée : `get_product(label_or_key)`, `normalize_product_key(...)`
- Force reload : `reload_catalog()` (appelé par /api/admin/reload-catalog)
"""
import logging
import time
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Photo statique générique utilisée pour les clients historiques (pas de PDF d'installation)
HISTORIC_FALLBACK_PHOTO = "https://res.cloudinary.com/dahmkv4ra/image/upload/v1781392846/G-30_myykrz.png"

# Fallback en dur — utilisé si Sheet inaccessible au démarrage
_FALLBACK_CATALOG: Dict[str, Dict[str, Any]] = {
    "G30": {
        "label": "G30",
        "garantie_mois": 24,
        "fiche_technique_url": "https://sebmwali.github.io/geobuilder-pionniers/Geobuilder_Fiche_G30.pdf",
        "manuel_url": "https://sebmwali.github.io/geobuilder-pionniers/G30%20USER%20MANUAL-1.pdf",
        "image_cloudinary_id": "g30",
        "photo_generateur_url": "https://res.cloudinary.com/dahmkv4ra/image/upload/v1781308463/G30-_fqyqhz.png",
    },
}

# Cache en mémoire
_cache: Dict[str, Dict[str, Any]] = {}
_cache_ts: float = 0.0
_TTL_SECONDS = 300  # 5 minutes


def _safe_int(v, default: int = 24) -> int:
    """Convertit en entier en gérant les saisies utilisateur (str, espaces, virgule)."""
    if isinstance(v, int):
        return v
    if v is None or v == "":
        return default
    s = str(v).strip().replace(",", ".").replace(" ", "")
    try:
        return int(float(s))
    except (ValueError, TypeError):
        logger.warning(f"[catalog] garantie_mois invalide '{v}', utilise défaut {default}")
        return default


def _load_from_sheet() -> Dict[str, Dict[str, Any]]:
    """Lit l'onglet 07_Catalog et retourne un dict produit_id -> infos."""
    from services.sheets_service import get_sheets_service
    sheets = get_sheets_service()
    rows = sheets.read_all("catalog")
    catalog: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        produit_id = str(row.get("produit_id") or "").strip().upper()
        if not produit_id:
            continue
        actif = str(row.get("actif", "OUI")).strip().upper() in ("OUI", "TRUE", "1", "YES")
        if not actif:
            continue
        catalog[produit_id] = {
            "label": str(row.get("label") or produit_id).strip(),
            "garantie_mois": _safe_int(row.get("garantie_mois"), 24),
            "fiche_technique_url": str(row.get("fiche_technique_url") or "").strip(),
            "manuel_url": str(row.get("manuel_url") or "").strip(),
            "image_cloudinary_id": str(row.get("image_cloudinary_id") or "").strip(),
            "photo_generateur_url": str(row.get("photo_generateur_url") or "").strip(),
        }
    return catalog


def _get_catalog() -> Dict[str, Dict[str, Any]]:
    """Retourne le catalogue (cache 5 min)."""
    global _cache, _cache_ts
    now = time.time()
    if _cache and (now - _cache_ts) < _TTL_SECONDS:
        return _cache
    try:
        fresh = _load_from_sheet()
        if fresh:
            _cache = fresh
            _cache_ts = now
            logger.info(f"[catalog] Chargé {len(fresh)} produits depuis Sheet")
        else:
            logger.warning("[catalog] Sheet vide, fallback hardcoded")
            _cache = _FALLBACK_CATALOG
            _cache_ts = now
    except Exception as e:
        # Erreur quota ou réseau : garder le cache existant si dispo, sinon fallback
        logger.error(f"[catalog] Lecture Sheet échouée: {e}")
        if not _cache:
            _cache = _FALLBACK_CATALOG
            _cache_ts = now  # avoid hammering
    return _cache


def reload_catalog() -> Dict[str, Any]:
    """Force le rechargement du catalogue depuis la Sheet (admin endpoint)."""
    global _cache, _cache_ts
    _cache = {}
    _cache_ts = 0.0
    cat = _get_catalog()
    return {"reloaded": True, "produits": list(cat.keys()), "count": len(cat)}


def normalize_product_key(label_or_key: str) -> str:
    """Normalise une chaîne produit en clé catalogue.

    Accepte : "G30", "g30", "Source XL", "SOURCE_XL"...
    Retourne la clé canonique (ex: "G30", "SOURCE_XL").
    """
    if not label_or_key:
        return ""
    catalog = _get_catalog()
    k = str(label_or_key).upper().strip().replace(" ", "_").replace("-", "_")
    # 1. Recherche exacte par produit_id
    if k in catalog:
        return k
    # 2. Recherche par label (case-insensitive)
    label_lower = str(label_or_key).lower().strip()
    for key, info in catalog.items():
        if info.get("label", "").lower().strip() == label_lower:
            return key
    # 3. Recherche partielle (G20 -> G20_MOJA, etc.)
    for key in catalog:
        if k in key or key.startswith(k):
            return key
    return k


def get_product(label_or_key: str) -> dict:
    """Retourne les infos produit, ou un fallback générique si non trouvé."""
    catalog = _get_catalog()
    k = normalize_product_key(label_or_key)
    if k in catalog:
        return catalog[k]
    # Fallback pour produit inconnu
    return {
        "label": label_or_key or "Produit Geobuilder",
        "garantie_mois": 24,
        "fiche_technique_url": "",
        "manuel_url": "",
        "image_cloudinary_id": "",
        "photo_generateur_url": "",
    }


# ===== Compat shim — accès direct au dict (lecture seule, lazy) =====
class _LazyCatalogDict:
    def __getitem__(self, k):
        return _get_catalog()[k]
    def __contains__(self, k):
        return k in _get_catalog()
    def get(self, k, default=None):
        return _get_catalog().get(k, default)
    def keys(self):
        return _get_catalog().keys()
    def values(self):
        return _get_catalog().values()
    def items(self):
        return _get_catalog().items()
    def __iter__(self):
        return iter(_get_catalog())
    def __len__(self):
        return len(_get_catalog())


CATALOG = _LazyCatalogDict()
