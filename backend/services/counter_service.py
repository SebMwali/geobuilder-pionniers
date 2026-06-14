"""
Counter service - remplace le Module 11 (Array Aggregator) de Make.

Lit / incrémente les compteurs depuis 04_Parametres.
Structure attendue dans la feuille :
   | Compteurs        | Valeur Actuelle |
   | Pionnier ID      | 1153            |
   | Installation ID  | 2156            |
   | Maintenance ID   | 3123            |
   | Document ID      | 0               |
"""
import logging
from typing import Tuple
from threading import Lock
from .sheets_service import get_sheets_service

logger = logging.getLogger(__name__)

# Mapping clé interne -> ligne dans 04_Parametres (nom du compteur)
COUNTER_NAMES = {
    "pionnier": "Pionnier ID",
    "installation": "Installation ID",
    "maintenance": "Maintenance ID",
    "document": "Document ID",
}

# Préfixes des IDs
PREFIXES = {
    "pionnier": "PIO",
    "installation": "INST",
    "maintenance": "MAINT",
    "document": "DOC",
}

# Lock pour éviter les race conditions (un webhook concurrent ne doit pas allouer le même ID)
_lock = Lock()


def get_current_counter(counter_key: str) -> int:
    """Lit la valeur actuelle d'un compteur. Renvoie 0 si non trouvé."""
    svc = get_sheets_service()
    counter_name = COUNTER_NAMES.get(counter_key, counter_key)
    row = svc.find_row_by("parametres", "Compteurs", counter_name)
    if not row:
        logger.warning(f"Counter {counter_name} not found in 04_Parametres")
        return 0
    val = row.get("Valeur Actuelle", 0)
    try:
        return int(val)
    except (ValueError, TypeError):
        return 0


def increment_counter(counter_key: str) -> Tuple[int, str]:
    """
    Incrémente le compteur dans Google Sheets et retourne (nouveau_numero, id_formate).
    Thread-safe.

    Ex: increment_counter("pionnier") -> (1154, "PIO-1154")
    """
    with _lock:
        svc = get_sheets_service()
        counter_name = COUNTER_NAMES.get(counter_key, counter_key)
        row_idx = svc.find_row_index_by("parametres", "Compteurs", counter_name)
        if not row_idx:
            raise RuntimeError(f"Counter '{counter_name}' not found in 04_Parametres. "
                               f"Add a row with that exact name in column 'Compteurs'.")
        current = get_current_counter(counter_key)
        new_val = current + 1
        svc.update_cell("parametres", row_idx, "Valeur Actuelle", new_val)
        formatted = f"{PREFIXES[counter_key]}-{new_val}"
        logger.info(f"Counter {counter_key} incremented: {current} -> {new_val} ({formatted})")
        return new_val, formatted


def peek_next_id(counter_key: str) -> str:
    """Renvoie ce que serait le PROCHAIN ID sans incrémenter (utile pour preview)."""
    current = get_current_counter(counter_key)
    return f"{PREFIXES[counter_key]}-{current + 1}"
