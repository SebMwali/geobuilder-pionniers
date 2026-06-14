"""
Tests P1 — counter_service.

Périmètre strict :
- aucun appel réseau (gspread mocké)
- aucune modification du code de production
- valide : lecture, incrémentation, format ID, peek, erreur compteur absent,
  thread-safety (race condition concurrente)
"""
import sys
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Permettre l'import de "services" sans installer le package
BACKEND_DIR = Path(__file__).parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services import counter_service  # noqa: E402
from services.counter_service import (  # noqa: E402
    COUNTER_NAMES,
    PREFIXES,
    get_current_counter,
    increment_counter,
    peek_next_id,
)


# ---------------------------------------------------------------------------
# Fixture: faux SheetsService en mémoire — simule 04_Parametres
# ---------------------------------------------------------------------------
class FakeSheetsService:
    """Reproduit l'API utilisée par counter_service sans toucher Google Sheets."""

    def __init__(self, initial: dict):
        # initial : {"Pionnier ID": 1153, "Installation ID": 2156, ...}
        # Ordre des lignes = ordre d'insertion ; les index Sheets commencent à 2 (header=1).
        self._rows = []
        for name, value in initial.items():
            self._rows.append({"Compteurs": name, "Valeur Actuelle": value})
        self.append_row_calls = []
        self.update_cell_calls = []

    # ---- API consommée par counter_service ----
    def find_row_by(self, tab_key, column_name, value):
        assert tab_key == "parametres"
        for r in self._rows:
            if str(r.get(column_name, "")).strip() == str(value).strip():
                return r
        return None

    def find_row_index_by(self, tab_key, column_name, value):
        assert tab_key == "parametres"
        for i, r in enumerate(self._rows, start=2):  # +2 car header=1
            if str(r.get(column_name, "")).strip() == str(value).strip():
                return i
        return None

    def update_cell(self, tab_key, row_idx, column_name, value):
        assert tab_key == "parametres"
        # row_idx en 1-based avec header => index liste = row_idx - 2
        list_idx = row_idx - 2
        if list_idx < 0 or list_idx >= len(self._rows):
            raise IndexError(f"row_idx {row_idx} hors plage")
        self._rows[list_idx][column_name] = value
        self.update_cell_calls.append((row_idx, column_name, value))

    # ---- helpers test ----
    def current(self, counter_name):
        for r in self._rows:
            if r["Compteurs"] == counter_name:
                return r["Valeur Actuelle"]
        return None


@pytest.fixture
def fake_sheets():
    fake = FakeSheetsService({
        "Pionnier ID": 1153,
        "Installation ID": 2156,
        "Maintenance ID": 3123,
        "Document ID": 0,
    })
    with patch.object(counter_service, "get_sheets_service", return_value=fake):
        yield fake


# ---------------------------------------------------------------------------
# Tests — lecture
# ---------------------------------------------------------------------------
class TestRead:
    def test_get_current_counter_pionnier(self, fake_sheets):
        assert get_current_counter("pionnier") == 1153

    def test_get_current_counter_installation(self, fake_sheets):
        assert get_current_counter("installation") == 2156

    def test_get_current_counter_maintenance(self, fake_sheets):
        assert get_current_counter("maintenance") == 3123

    def test_get_current_counter_document(self, fake_sheets):
        assert get_current_counter("document") == 0

    def test_get_current_counter_missing_returns_zero(self, fake_sheets):
        # Compteur absent => 0 (avec warning log côté service)
        assert get_current_counter("inexistant") == 0

    def test_get_current_counter_handles_string_value(self):
        # Le Sheet peut renvoyer une string "1153" — doit être casté
        fake = FakeSheetsService({"Pionnier ID": "1153"})
        with patch.object(counter_service, "get_sheets_service", return_value=fake):
            assert get_current_counter("pionnier") == 1153

    def test_get_current_counter_handles_garbage_value(self):
        fake = FakeSheetsService({"Pionnier ID": "abc"})
        with patch.object(counter_service, "get_sheets_service", return_value=fake):
            # Non castable => 0 (fallback défensif)
            assert get_current_counter("pionnier") == 0


# ---------------------------------------------------------------------------
# Tests — peek (lecture sans incrément)
# ---------------------------------------------------------------------------
class TestPeek:
    def test_peek_format_pionnier(self, fake_sheets):
        assert peek_next_id("pionnier") == "PIO-1154"

    def test_peek_format_installation(self, fake_sheets):
        assert peek_next_id("installation") == "INST-2157"

    def test_peek_format_maintenance(self, fake_sheets):
        assert peek_next_id("maintenance") == "MAINT-3124"

    def test_peek_format_document(self, fake_sheets):
        assert peek_next_id("document") == "DOC-1"

    def test_peek_does_not_mutate(self, fake_sheets):
        before = fake_sheets.current("Pionnier ID")
        peek_next_id("pionnier")
        peek_next_id("pionnier")
        peek_next_id("pionnier")
        assert fake_sheets.current("Pionnier ID") == before
        assert fake_sheets.update_cell_calls == []


# ---------------------------------------------------------------------------
# Tests — incrémentation
# ---------------------------------------------------------------------------
class TestIncrement:
    def test_increment_returns_new_value_and_formatted_id(self, fake_sheets):
        new_val, formatted = increment_counter("pionnier")
        assert new_val == 1154
        assert formatted == "PIO-1154"

    def test_increment_persists_in_sheet(self, fake_sheets):
        increment_counter("pionnier")
        assert fake_sheets.current("Pionnier ID") == 1154

    def test_increment_writes_correct_row_and_column(self, fake_sheets):
        increment_counter("installation")
        # 1 seule update_cell, sur la ligne d'index Sheets attendu, colonne attendue
        assert len(fake_sheets.update_cell_calls) == 1
        row_idx, col, value = fake_sheets.update_cell_calls[0]
        assert col == "Valeur Actuelle"
        assert value == 2157
        # Installation ID est la 2ème ligne (index Sheets = 3)
        assert row_idx == 3

    def test_increment_sequential_no_duplicate(self, fake_sheets):
        ids = [increment_counter("pionnier")[1] for _ in range(5)]
        assert ids == ["PIO-1154", "PIO-1155", "PIO-1156", "PIO-1157", "PIO-1158"]
        assert len(set(ids)) == 5  # tous uniques

    def test_increment_all_counters_independent(self, fake_sheets):
        increment_counter("pionnier")
        increment_counter("pionnier")
        increment_counter("installation")
        increment_counter("maintenance")
        increment_counter("document")
        assert fake_sheets.current("Pionnier ID") == 1155
        assert fake_sheets.current("Installation ID") == 2157
        assert fake_sheets.current("Maintenance ID") == 3124
        assert fake_sheets.current("Document ID") == 1

    def test_increment_raises_when_counter_missing(self):
        fake = FakeSheetsService({"Pionnier ID": 1153})  # pas d'Installation ID
        with patch.object(counter_service, "get_sheets_service", return_value=fake):
            with pytest.raises(RuntimeError, match="not found in 04_Parametres"):
                increment_counter("installation")


# ---------------------------------------------------------------------------
# Tests — race condition (thread-safety du Lock)
# ---------------------------------------------------------------------------
class TestRaceCondition:
    def test_concurrent_increments_no_duplicate(self, fake_sheets):
        """50 threads incrémentent en parallèle — aucun doublon attendu."""
        N = 50
        results = []
        results_lock = threading.Lock()

        def worker():
            _, fid = increment_counter("pionnier")
            with results_lock:
                results.append(fid)

        threads = [threading.Thread(target=worker) for _ in range(N)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == N
        assert len(set(results)) == N, f"Doublons détectés ! {len(set(results))}/{N} uniques"
        # Valeur finale = 1153 + N
        assert fake_sheets.current("Pionnier ID") == 1153 + N
        # IDs attendus = tous ceux de PIO-1154 à PIO-1153+N
        expected = {f"PIO-{1153 + i}" for i in range(1, N + 1)}
        assert set(results) == expected

    def test_concurrent_increments_mixed_counters(self, fake_sheets):
        """Threads concurrents sur 2 compteurs différents — pas d'interférence."""
        N = 20

        def worker_pio():
            increment_counter("pionnier")

        def worker_inst():
            increment_counter("installation")

        threads = []
        for _ in range(N):
            threads.append(threading.Thread(target=worker_pio))
            threads.append(threading.Thread(target=worker_inst))
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert fake_sheets.current("Pionnier ID") == 1153 + N
        assert fake_sheets.current("Installation ID") == 2156 + N


# ---------------------------------------------------------------------------
# Tests — invariants statiques de configuration
# ---------------------------------------------------------------------------
class TestConfig:
    def test_all_counters_have_prefix(self):
        assert set(COUNTER_NAMES.keys()) == set(PREFIXES.keys())

    def test_prefix_values(self):
        assert PREFIXES["pionnier"] == "PIO"
        assert PREFIXES["installation"] == "INST"
        assert PREFIXES["maintenance"] == "MAINT"
        assert PREFIXES["document"] == "DOC"

    def test_counter_names_match_sheet_schema(self):
        # Doit correspondre exactement aux libellés présents en colonne A de 04_Parametres
        assert COUNTER_NAMES["pionnier"] == "Pionnier ID"
        assert COUNTER_NAMES["installation"] == "Installation ID"
        assert COUNTER_NAMES["maintenance"] == "Maintenance ID"
        assert COUNTER_NAMES["document"] == "Document ID"
