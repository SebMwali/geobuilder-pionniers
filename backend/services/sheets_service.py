"""
Google Sheets Service - utilise un Service Account pour lire/écrire dans le Sheet.
Remplace les modules Make défaillants (lecture compteurs + écriture lignes).
"""
import os
import json
import time
import random
import logging
import functools
from typing import List, Dict, Any, Optional
import gspread
from gspread.exceptions import APIError
from google.oauth2.service_account import Credentials

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def _retry_on_quota(max_attempts: int = 5, base_delay: float = 1.5):
    """Décorateur : retry exponentiel sur 429 (quota Google Sheets API).
    
    Indispensable pour les webhooks arrivés en parallèle qui saturent
    la limite 60 reads/min/user de l'API Sheets v4.
    """
    def deco(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except APIError as e:
                    code = getattr(e, "code", None) or str(e)
                    msg = str(e)
                    is_quota = "429" in msg or "Quota exceeded" in msg or code == 429
                    if not is_quota or attempt == max_attempts:
                        raise
                    last_exc = e
                    # Backoff exponentiel + jitter
                    delay = base_delay * (2 ** (attempt - 1)) + random.uniform(0, 0.8)
                    logger.warning(
                        f"[sheets_retry] Quota 429 sur {func.__name__} (try {attempt}/{max_attempts}) "
                        f"-> sleep {delay:.1f}s"
                    )
                    time.sleep(delay)
            raise last_exc  # type: ignore
        return wrapper
    return deco


# Mapping nom d'onglet -> nom dans le Sheet (aligné sur le Sheet réel "La Famille des Pionniers")
TABS = {
    "pionniers": "01_Pionniers",
    "installations": "02_Installations",
    "medias": "03_Medias",
    "parametres": "04_Parametres",
    "maintenances": "05_Maintenances",
    "documents": "06_Documents",
    "ressources": "07_Produits",
    "catalog": "07_Catalog",
    "logs": "08_Automations_Log",
    "ns_declarations": "10_NS_Declarations",
}


class SheetsService:
    _instance = None
    _client = None
    _spreadsheet = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _get_client(self):
        if self._client is not None:
            return self._client
        raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
        if not raw:
            raise RuntimeError(
                "GOOGLE_SERVICE_ACCOUNT_JSON is empty. "
                "Add the service account JSON content in backend/.env"
            )
        try:
            info = json.loads(raw)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"GOOGLE_SERVICE_ACCOUNT_JSON is not valid JSON: {e}")
        creds = Credentials.from_service_account_info(info, scopes=SCOPES)
        self._client = gspread.authorize(creds)
        return self._client

    def _get_spreadsheet(self):
        if self._spreadsheet is None:
            sheet_id = os.environ["SHEET_ID"]
            self._spreadsheet = self._get_client().open_by_key(sheet_id)
        return self._spreadsheet

    def get_worksheet(self, tab_key: str):
        """Retourne l'objet worksheet pour la clé donnée (ex: 'pionniers')."""
        tab_name = TABS.get(tab_key, tab_key)
        return self._get_spreadsheet().worksheet(tab_name)

    def read_all(self, tab_key: str) -> List[Dict[str, Any]]:
        """Lit toutes les lignes d'un onglet sous forme de liste de dicts."""
        ws = self.get_worksheet(tab_key)
        return _retry_on_quota()(ws.get_all_records)()

    @_retry_on_quota()
    def append_row(self, tab_key: str, row: List[Any]):
        """Ajoute une ligne à la fin d'un onglet (USER_ENTERED pour interpréter formules/dates)."""
        ws = self.get_worksheet(tab_key)
        ws.append_row(row, value_input_option="USER_ENTERED")
        logger.info(f"Appended row to {tab_key}: {row}")

    def find_row_by(self, tab_key: str, column_name: str, value: str) -> Optional[Dict[str, Any]]:
        """Trouve la première ligne où column_name == value. Renvoie dict ou None."""
        records = self.read_all(tab_key)
        for rec in records:
            if str(rec.get(column_name, "")).strip() == str(value).strip():
                return rec
        return None

    @_retry_on_quota()
    def find_row_index_by(self, tab_key: str, column_name: str, value: str) -> Optional[int]:
        """Retourne l'index 1-based de la ligne dans la feuille (header = 1)."""
        ws = self.get_worksheet(tab_key)
        all_values = ws.get_all_values()
        if not all_values:
            return None
        headers = all_values[0]
        try:
            col_idx = headers.index(column_name)
        except ValueError:
            return None
        for i, row in enumerate(all_values[1:], start=2):
            if col_idx < len(row) and row[col_idx].strip() == str(value).strip():
                return i
        return None

    @_retry_on_quota()
    def update_cell(self, tab_key: str, row_idx: int, column_name: str, value: Any):
        ws = self.get_worksheet(tab_key)
        headers = ws.row_values(1)
        if column_name not in headers:
            raise ValueError(f"Column {column_name} not in {tab_key}")
        col_idx = headers.index(column_name) + 1
        ws.update_cell(row_idx, col_idx, value)

    def log_event(self, action: str, install_id: str = "", pio_id: str = "",
                  result: str = "OK", message: str = "", erreur_detail: str = ""):
        """Écrit un événement dans 08_Automations_Log.

        Colonnes Sheet réelles : timestamp, action, install_id, pio_id, result, message, erreur_detail
        """
        from datetime import datetime, timezone
        try:
            ts = datetime.now(timezone.utc).isoformat()
            self.append_row("logs", [ts, action, install_id, pio_id, result, message, erreur_detail])
        except Exception as e:
            logger.warning(f"Could not log to sheet: {e}")


_service: Optional[SheetsService] = None


def get_sheets_service() -> SheetsService:
    global _service
    if _service is None:
        _service = SheetsService()
    return _service
