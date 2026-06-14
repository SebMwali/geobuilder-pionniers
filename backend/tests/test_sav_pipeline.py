"""Tests P-SAV — pipeline SAV minimal (_process_sav).

Vérifie :
- Recherche installation par install_id
- Allocation MAINT-XXXX
- Append 12 colonnes dans 05_Maintenances (structure réelle A..L)
- Régénération du passeport (push GitHub)
- Filtrage des statuts dans l'historique (Réalisé/Terminé/OK uniquement)
"""
import sys
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

BACKEND_DIR = Path(__file__).parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import os
os.environ.setdefault("GITHUB_PAGES_URL", "https://sebmwali.github.io/geobuilder-pionniers")
os.environ.setdefault("ADMIN_PASSWORD", "test")
os.environ.setdefault("JWT_SECRET", "test")

import server  # noqa: E402
from server import _process_sav, SavInput  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def install_row():
    return {
        "install_id": "INST-2157",
        "pio_id": "PIO-1154",
        "produit": "G30 Home",
        "numero_serie": "NS-001",
        "date_installation": "2025-01-10",
        "date_garantie_fin": "2027-01-10",
        "territoire_installation": "MAYOTTE",
        "localisation_precise": "Mamoudzou",
        "nom_client": "Aïsha Diallo",
        "photo_generateur_url": "https://res.cloudinary.com/dahmkv4ra/image/upload/v1781308463/G30-_fqyqhz.png",
        "photo_emplacement_url": "https://sebmwali.github.io/geobuilder-pionniers/photos/INST-2157/emplacement.jpg",
    }


@pytest.fixture
def fake_sheets(install_row):
    mock = MagicMock()
    mock.find_row_by = MagicMock(return_value=install_row)
    mock.append_row = MagicMock()
    mock.log_event = MagicMock()
    # Historique : 3 maintenances (2 visibles, 1 non visible)
    mock.read_all = MagicMock(return_value=[
        {"install_id": "INST-2157", "date_intervention": "2025-06-10",
         "type_intervention": "Préventive", "technicien": "Karim", "statut": "Réalisé",
         "observations": "RAS"},
        {"install_id": "INST-2157", "date_intervention": "2025-09-15",
         "type_intervention": "Corrective", "technicien": "Sophie", "statut": "En cours",
         "observations": "à reprogrammer"},
        {"install_id": "INST-2999", "date_intervention": "2025-05-01",
         "type_intervention": "Préventive", "technicien": "Autre", "statut": "Réalisé"},
    ])
    return mock


@pytest.fixture
def fake_github():
    mock = MagicMock()
    mock.push_file = MagicMock(side_effect=lambda path, content, msg:
                               f"https://sebmwali.github.io/geobuilder-pionniers/{path.removeprefix('docs/')}")
    return mock


@pytest.fixture
def counter_seq():
    state = {"maintenance": 3123}

    def _inc(key):
        state[key] = state[key] + 1
        return state[key], f"MAINT-{state[key]}"

    return _inc


@pytest.fixture
def run_sav(fake_sheets, fake_github, counter_seq):
    def _run(payload: SavInput):
        with patch("server.get_sheets_service", return_value=fake_sheets), \
             patch("server.get_github_service", return_value=fake_github), \
             patch("server.increment_counter", side_effect=counter_seq):
            return asyncio.run(_process_sav(payload))
    return _run


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestProcessSav:
    def test_returns_maint_id_and_passeport_url(self, run_sav):
        payload = SavInput(
            install_id="INST-2157",
            date_intervention="2026-02-10",
            type_intervention="Préventive 6 mois",
            technicien="Jean",
            statut="Réalisé",
            observations="Filtre changé",
        )
        result = run_sav(payload)
        assert result["maintenance_id"] == "MAINT-3124"
        assert result["install_id"] == "INST-2157"
        assert result["pio_id"] == "PIO-1154"
        assert result["url_passeport"].endswith("/passeports/INST-2157/index.html")

    def test_maintenance_row_has_12_columns(self, run_sav, fake_sheets):
        payload = SavInput(
            install_id="INST-2157",
            date_intervention="2026-02-10",
            type_intervention="Préventive 6 mois",
            technicien="Jean",
            statut="Réalisé",
            observations="Filtre changé",
            pieces_changees="Filtre charbon",
            prochain_rdv="2026-08-10",
            source="Make",
            rapport_url="https://drive.google.com/abc",
        )
        run_sav(payload)
        # Premier append = "maintenances"
        first_call = fake_sheets.append_row.call_args_list[0]
        assert first_call.args[0] == "maintenances"
        row = first_call.args[1]
        assert len(row) == 12
        assert row[0] == "MAINT-3124"      # A maintenance_id
        assert row[1] == "INST-2157"       # B install_id
        assert row[2] == "PIO-1154"        # C pio_id
        assert row[3] == "2026-02-10"      # D date_intervention
        assert row[4] == "Préventive 6 mois"  # E type_intervention
        assert row[5] == "Jean"            # F technicien
        assert row[6] == "Réalisé"         # G statut
        assert row[7] == "https://drive.google.com/abc"  # H rapport_url
        assert row[8] == "Filtre changé"   # I observations
        assert row[9] == "Filtre charbon"  # J pieces_changees
        assert row[10] == "2026-08-10"     # K prochain_rdv
        assert row[11] == "Make"           # L source

    def test_passeport_pushed_to_github(self, run_sav, fake_github):
        payload = SavInput(
            install_id="INST-2157",
            type_intervention="Corrective",
            statut="Réalisé",
        )
        run_sav(payload)
        # Au moins 1 push : passeport (path docs/passeports/INST-2157/index.html)
        paths = [c.args[0] for c in fake_github.push_file.call_args_list]
        assert "docs/passeports/INST-2157/index.html" in paths

    def test_passeport_contains_visible_interventions_only(self, run_sav, fake_github):
        payload = SavInput(
            install_id="INST-2157",
            type_intervention="Préventive",
            statut="Terminé",
        )
        run_sav(payload)
        passeport_call = next(
            c for c in fake_github.push_file.call_args_list
            if c.args[0] == "docs/passeports/INST-2157/index.html"
        )
        html = passeport_call.args[1]
        # La maintenance "Réalisé" doit être présente
        assert "Karim" in html
        # La maintenance "En cours" doit être FILTRÉE
        assert "Sophie" not in html
        # Aucun placeholder non rempli
        assert "{{" not in html

    def test_404_when_installation_not_found(self, fake_sheets, fake_github, counter_seq):
        from fastapi import HTTPException
        fake_sheets.find_row_by = MagicMock(return_value=None)
        payload = SavInput(install_id="INST-9999", type_intervention="x")
        with patch("server.get_sheets_service", return_value=fake_sheets), \
             patch("server.get_github_service", return_value=fake_github), \
             patch("server.increment_counter", side_effect=counter_seq):
            with pytest.raises(HTTPException) as exc:
                asyncio.run(_process_sav(payload))
            assert exc.value.status_code == 404
