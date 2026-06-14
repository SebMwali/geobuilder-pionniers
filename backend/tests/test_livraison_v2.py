"""Tests P-LIVRAISON-V2 — schéma PIONNIERS-DATA + idempotence + fondateur."""
import sys
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

BACKEND_DIR = Path(__file__).parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import os
os.environ.setdefault("GITHUB_PAGES_URL", "https://sebmwali.github.io/geobuilder-pionniers")
os.environ.setdefault("ADMIN_PASSWORD", "test")
os.environ.setdefault("JWT_SECRET", "test")

import server  # noqa: E402
from server import _process_livraison, LivraisonInput  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def fake_sheets():
    mock = MagicMock()
    mock.append_row = MagicMock()
    mock.log_event = MagicMock()
    mock.find_row_by = MagicMock(return_value=None)  # default: no existing
    return mock


@pytest.fixture
def fake_github():
    mock = MagicMock()
    mock.push_file = MagicMock(side_effect=lambda path, content, msg:
                               f"https://sebmwali.github.io/geobuilder-pionniers/{path.removeprefix('docs/')}")
    mock.push_binary_file = MagicMock(side_effect=lambda path, content, msg:
                                      f"https://sebmwali.github.io/geobuilder-pionniers/{path.removeprefix('docs/')}")
    return mock


@pytest.fixture
def counter_seq():
    state = {"pionnier": 1153, "installation": 2156, "document": 0, "maintenance": 3123}
    prefixes = {"pionnier": "PIO", "installation": "INST", "document": "DOC", "maintenance": "MAINT"}

    def _inc(key):
        state[key] += 1
        return state[key], f"{prefixes[key]}-{state[key]}"

    return _inc


@pytest.fixture
def email_mock():
    return AsyncMock()


@pytest.fixture
def run_pipeline(fake_sheets, fake_github, counter_seq, email_mock):
    def _run(payload, pdf_bytes=None):
        with patch("server.get_sheets_service", return_value=fake_sheets), \
             patch("server.get_github_service", return_value=fake_github), \
             patch("server.increment_counter", side_effect=counter_seq), \
             patch("server.send_email_mock", email_mock):
            return asyncio.run(_process_livraison(payload, pdf_bytes=pdf_bytes))
    return _run


def _base_payload(**overrides):
    base = dict(
        type="LIVRAISON",
        nom="FUMAZ", prenom="Sebastien", email="sebastien.fumaz@geobuilder.fr",
        numero_serie="HR88C25DAZ0100", produit="G30", territoire="MAYOTTE",
        pays="FRANCE", localisation="Rue de la Paix, Mamoudzou",
        date_installation="2026-06-14", technicien="Bacar",
        fondateur=False, photo_generateur_url="", photo_emplacement_url="",
    )
    base.update(overrides)
    return LivraisonInput(**base)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestPionniersDataSchema:
    def test_payload_pionniers_data_accepted(self, run_pipeline):
        result = run_pipeline(_base_payload())
        assert result["pio_id"] == "PIO-1154"
        assert result["install_id"] == "INST-2157"

    def test_response_includes_photo_urls(self, run_pipeline):
        result = run_pipeline(_base_payload())
        assert "photo_generateur_url" in result
        assert "photo_emplacement_url" in result
        # G30 → Cloudinary statique
        assert "cloudinary" in result["photo_generateur_url"]

    def test_response_includes_report_id(self, run_pipeline):
        result = run_pipeline(_base_payload(report_id="abc-123"))
        assert result["report_id"] == "abc-123"


class TestIdempotence:
    def test_replay_returns_existing_ids_without_processing(self, fake_sheets, fake_github, counter_seq, email_mock):
        # Simule une installation déjà existante avec ce report_id
        fake_sheets.find_row_by = MagicMock(return_value={
            "install_id": "INST-9999",
            "pio_id": "PIO-9999",
            "report_id": "REPLAY-001",
        })
        with patch("server.get_sheets_service", return_value=fake_sheets), \
             patch("server.get_github_service", return_value=fake_github), \
             patch("server.increment_counter", side_effect=counter_seq), \
             patch("server.send_email_mock", email_mock):
            result = asyncio.run(_process_livraison(_base_payload(report_id="REPLAY-001")))
        # Doit retourner les IDs existants
        assert result["pio_id"] == "PIO-9999"
        assert result["install_id"] == "INST-9999"
        assert result["idempotent_replay"] is True
        # Aucun append, aucun push, aucun email
        assert fake_sheets.append_row.call_count == 0
        assert fake_github.push_file.call_count == 0
        assert email_mock.call_count == 0

    def test_no_replay_when_report_id_absent(self, run_pipeline, fake_sheets):
        run_pipeline(_base_payload(report_id=None))
        # Pas de check find_row_by("installations", "report_id", ...)
        calls = [c for c in fake_sheets.find_row_by.call_args_list
                 if c.args[1] == "report_id"]
        assert calls == []


class TestFondateur:
    def test_fondateur_true_generates_ambassadeur(self, run_pipeline, fake_github):
        result = run_pipeline(_base_payload(fondateur=True))
        # Push ambassadeur attendu
        paths = [c.args[0] for c in fake_github.push_file.call_args_list]
        assert any("docs/ambassadeurs/" in p for p in paths)
        assert "url_ambassadeur" in result

    def test_fondateur_false_does_not_generate_ambassadeur(self, run_pipeline, fake_github):
        result = run_pipeline(_base_payload(fondateur=False))
        paths = [c.args[0] for c in fake_github.push_file.call_args_list]
        assert not any("docs/ambassadeurs/" in p for p in paths)
        assert "url_ambassadeur" not in result

    def test_fondateur_marks_pionnier_row(self, run_pipeline, fake_sheets):
        run_pipeline(_base_payload(fondateur=True))
        pio_call = fake_sheets.append_row.call_args_list[0]
        assert pio_call.args[0] == "pionniers"
        row = pio_call.args[1]
        assert row[10] == "true"  # K = fondateur
        assert row[11] == "true"  # L = ambassadeur


class TestReportIdStoredInSheets:
    def test_report_id_in_installations_col_w(self, run_pipeline, fake_sheets):
        run_pipeline(_base_payload(report_id="f2d742da-aef0-4e14-886c-7a5c08fd439d"))
        inst_call = fake_sheets.append_row.call_args_list[1]
        assert inst_call.args[0] == "installations"
        row = inst_call.args[1]
        assert len(row) == 23
        assert row[22] == "f2d742da-aef0-4e14-886c-7a5c08fd439d"  # W = report_id


class TestTechnicienStoredAsInstallateur:
    def test_technicien_goes_to_installations_col_h(self, run_pipeline, fake_sheets):
        run_pipeline(_base_payload(technicien="Bacar"))
        inst_call = fake_sheets.append_row.call_args_list[1]
        row = inst_call.args[1]
        assert row[7] == "Bacar"  # H = installateur
