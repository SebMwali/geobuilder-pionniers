"""
Tests P3.4 — pipeline LIVRAISON (_process_livraison) avec mocks.

Périmètre strict :
- Aucun appel réseau (Sheets + GitHub mockés)
- Aucune modification du code de production
- Valide :
  * allocation correcte des 6 IDs (1 PIO + 1 INST + 4 DOC)
  * appel des 5 templates PROD (passeport_installation, certificat-pionnier,
    certificat-garantie, portail_pionnier, email-final)
  * 4 chemins GitHub conformes à la convention prod
  * 6 lignes Sheets append (1 PIO + 1 INST + 4 DOC) + 1 log
  * 1 email mock dans l'outbox
  * réponse HTTP avec les 4 URLs publiques attendues
"""
import sys
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

BACKEND_DIR = Path(__file__).parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Variables d'env requises avant l'import de server.py
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
    return mock


@pytest.fixture
def fake_github():
    mock = MagicMock()
    mock.push_file = MagicMock(side_effect=lambda path, content, msg:
                                f"https://sebmwali.github.io/geobuilder-pionniers/{path.removeprefix('docs/')}")
    return mock


@pytest.fixture
def counters_sequence():
    """Simule l'allocation séquentielle des IDs."""
    state = {"pionnier": 1153, "installation": 2156, "document": 0, "maintenance": 3123}
    prefixes = {"pionnier": "PIO", "installation": "INST", "document": "DOC", "maintenance": "MAINT"}

    def fake_increment(key):
        state[key] += 1
        return state[key], f"{prefixes[key]}-{state[key]}"

    return fake_increment


@pytest.fixture
def sample_payload():
    return LivraisonInput(
        nom="Diallo",
        prenom="Aïsha",
        email="aisha.diallo@example.com",
        telephone="+262 692 00 00 00",
        territoire="MAYOTTE",
        pays="Mayotte",
        produit="G20 MOJA",
        numero_serie="P3-TEST-NS-0001",
        date_installation="2026-02-15",
        localisation="Mamoudzou, Mayotte",
    )


@pytest.fixture
def run_pipeline(fake_sheets, fake_github, counters_sequence, sample_payload):
    """Helper qui exécute le pipeline avec tous les mocks en place."""
    def _run():
        with patch.object(server, "get_sheets_service", return_value=fake_sheets), \
             patch.object(server, "get_github_service", return_value=fake_github), \
             patch.object(server, "increment_counter", side_effect=counters_sequence), \
             patch.object(server, "send_email_mock", new=AsyncMock(return_value={"status": "mocked"})) as email_mock:
            result = asyncio.run(_process_livraison(sample_payload))
            return result, email_mock
    return _run


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestPipelineLivraison:

    def test_returns_expected_ids(self, run_pipeline):
        result, _ = run_pipeline()
        assert result["pio_id"] == "PIO-1154"
        assert result["install_id"] == "INST-2157"

    def test_returns_4_public_urls_correctly_formatted(self, run_pipeline):
        result, _ = run_pipeline()
        base = "https://sebmwali.github.io/geobuilder-pionniers"
        assert result["url_passeport"] == f"{base}/passeports/INST-2157/index.html"
        assert result["url_certificat"] == f"{base}/certificats/pionnier/PIO-1154.html"
        assert result["url_garantie"] == f"{base}/certificats/garantie/INST-2157.html"
        assert result["url_portail"] == f"{base}/pionniers/PIO-1154/index.html"

    def test_pushes_4_files_to_github_with_correct_paths(self, run_pipeline, fake_github):
        run_pipeline()
        assert fake_github.push_file.call_count == 4
        paths = [c.args[0] for c in fake_github.push_file.call_args_list]
        assert paths == [
            "docs/passeports/INST-2157/index.html",
            "docs/certificats/pionnier/PIO-1154.html",
            "docs/certificats/garantie/INST-2157.html",
            "docs/pionniers/PIO-1154/index.html",
        ]

    def test_pushed_html_contains_expected_markers(self, run_pipeline, fake_github):
        """Vérifie que chaque HTML poussé contient les variables clés résolues (pas de {{...}})."""
        run_pipeline()
        contents = {c.args[0]: c.args[1] for c in fake_github.push_file.call_args_list}

        # Passeport
        pass_html = contents["docs/passeports/INST-2157/index.html"]
        assert "INST-2157" in pass_html
        assert "PIO-1154" in pass_html
        assert "P3-TEST-NS-0001" in pass_html
        assert "G20 Moja" in pass_html
        assert "{{" not in pass_html, "Variables non remplacées dans passeport"

        # Certificat Pionnier
        cp_html = contents["docs/certificats/pionnier/PIO-1154.html"]
        assert "PIO-1154" in cp_html
        assert "Aïsha Diallo" in cp_html
        assert "Mayotte" in cp_html
        assert "{{" not in cp_html

        # Certificat Garantie
        cg_html = contents["docs/certificats/garantie/INST-2157.html"]
        assert "INST-2157" in cg_html
        assert "PIO-1154" in cg_html
        assert "P3-TEST-NS-0001" in cg_html
        assert "Aïsha Diallo" in cg_html
        assert "G20 Moja" in cg_html
        assert "g20_moja" in cg_html  # PRODUIT_IMG_ID
        assert "{{" not in cg_html

        # Portail
        portail_html = contents["docs/pionniers/PIO-1154/index.html"]
        assert "PIO-1154" in portail_html
        assert "Aïsha" in portail_html
        assert "{{" not in portail_html
        # La carte est masquée (V1)
        assert 'style="display:none"' in portail_html

    def test_appends_6_rows_to_sheets(self, run_pipeline, fake_sheets):
        """1 PIO + 1 INST + 4 DOC = 6 lignes append."""
        run_pipeline()
        append_calls = [c for c in fake_sheets.append_row.call_args_list]
        assert len(append_calls) == 6
        tabs = [c.args[0] for c in append_calls]
        assert tabs == ["pionniers", "installations", "documents", "documents", "documents", "documents"]

    def test_pionniers_row_content(self, run_pipeline, fake_sheets):
        run_pipeline()
        pio_call = fake_sheets.append_row.call_args_list[0]
        assert pio_call.args[0] == "pionniers"
        row = pio_call.args[1]
        assert len(row) == 22  # 22 colonnes du Sheet réel
        assert row[0] == "PIO-1154"
        assert row[1] == "Diallo"
        assert row[2] == "Aïsha"
        assert row[3] == "aisha.diallo@example.com"
        assert row[5] == "Mayotte"      # F = pays
        assert row[6] == "MAYOTTE"      # G = territoire
        assert row[9] == "Pionnier"     # J = statut
        assert row[16] == "backend_livraison"   # Q = source_creation
        assert row[17] == "livraison_complete"  # R = workflow_status
        assert row[18] == "true"        # S = welcome_email_sent
        assert row[19].startswith("https://sebmwali.github.io")  # T = certificat_url

    def test_installations_row_content(self, run_pipeline, fake_sheets):
        run_pipeline()
        inst_call = fake_sheets.append_row.call_args_list[1]
        assert inst_call.args[0] == "installations"
        row = inst_call.args[1]
        assert len(row) == 22  # 22 colonnes (U et V = photos)
        assert row[0] == "INST-2157"
        assert row[1] == "PIO-1154"
        assert row[2] == "G20 Moja"          # C = produit
        assert row[3] == "P3-TEST-NS-0001"   # D = numero_serie
        assert row[4] == "2026-02-15"        # E = date_installation
        assert row[8] == "active"            # I = installation_status
        assert row[9] == "true"              # J = pionnier_created
        assert row[18] == "/install/INST-2157"  # S = passeport_url (relative)
        assert row[19] == "true"             # T = installation_active
        # U = photo_generateur_url (peut être vide pour G20 ou cloudinary)
        assert isinstance(row[20], str)
        # V = photo_emplacement_url (fallback historique si pas de PDF)
        assert row[21].startswith("https://")

    def test_documents_4_rows_with_correct_types(self, run_pipeline, fake_sheets):
        run_pipeline()
        doc_calls = fake_sheets.append_row.call_args_list[2:6]
        # 10 colonnes par doc
        for c in doc_calls:
            assert len(c.args[1]) == 10
        types = [c.args[1][3] for c in doc_calls]  # D = type_doc
        assert types == ["PASSEPORT", "CERTIFICAT_PIONNIER", "CERTIFICAT_GARANTIE", "PORTAIL"]
        doc_ids = [c.args[1][0] for c in doc_calls]
        assert doc_ids == ["DOC-1", "DOC-2", "DOC-3", "DOC-4"]
        # install_id présent pour PASSEPORT et GARANTIE, vide pour CERT_PIO et PORTAIL
        inst_ids = [c.args[1][1] for c in doc_calls]
        assert inst_ids == ["INST-2157", "", "INST-2157", ""]
        # statut_envoi = "generated"
        statuts = [c.args[1][6] for c in doc_calls]
        assert statuts == ["generated"] * 4

    def test_logs_info_event(self, run_pipeline, fake_sheets):
        run_pipeline()
        assert fake_sheets.log_event.call_count >= 1
        last_call = fake_sheets.log_event.call_args_list[-1]
        # Nouvelle signature : (action, install_id, pio_id, result, message, erreur_detail)
        assert last_call.args[0] == "livraison"
        assert last_call.args[1] == "INST-2157"
        assert last_call.args[2] == "PIO-1154"
        assert last_call.args[3] == "OK"

    def test_sends_one_email_mock(self, run_pipeline):
        _, email_mock = run_pipeline()
        assert email_mock.call_count == 1
        call = email_mock.call_args
        assert call.args[0] == "aisha.diallo@example.com"
        assert "Bienvenue" in call.args[1]
        # Le HTML contient l'install_id et le PIO_ID
        html = call.args[2]
        assert "INST-2157" in html
        assert "PIO-1154" in html
        assert "{{" not in html

    def test_email_metadata(self, run_pipeline):
        _, email_mock = run_pipeline()
        meta = email_mock.call_args.kwargs["metadata"]
        assert meta == {"pio_id": "PIO-1154", "install_id": "INST-2157"}

    def test_no_sheets_column_order_change(self, run_pipeline, fake_sheets):
        """Largeurs colonnes alignées sur le Sheet réel (P3.5 bis)."""
        run_pipeline()
        pio_row = fake_sheets.append_row.call_args_list[0].args[1]
        assert len(pio_row) == 22
        inst_row = fake_sheets.append_row.call_args_list[1].args[1]
        assert len(inst_row) == 22
        doc_row = fake_sheets.append_row.call_args_list[2].args[1]
        assert len(doc_row) == 10
