"""Tests P-LIVRAISON-SAV-NATIF — normalisation + parsing PDF + defaults Mayotte."""
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

from server import _process_livraison, _normalize_livraison_payload, LivraisonInput  # noqa: E402
from fastapi import HTTPException  # noqa: E402


@pytest.fixture
def real_pdf_bytes():
    """Charge le vrai PDF SAV pour les tests d'intégration parser."""
    path = Path("/tmp/livraison_v2.pdf")
    if not path.exists():
        pytest.skip("Real PDF not available")
    return path.read_bytes()


class TestSavNativeAliasing:
    def test_ns_becomes_numero_serie(self):
        p = LivraisonInput(
            ns="G30-MYT-TEST-001",
            client="Sébastien FUMAZ",
            email_client="sebastien.fumaz@geobuilder.fr",
            produit="G30",  # bypass PDF parsing
        )
        result = asyncio.run(_normalize_livraison_payload(p))
        assert result.numero_serie == "G30-MYT-TEST-001"

    def test_client_split_into_nom_prenom(self):
        p = LivraisonInput(
            ns="X",
            client="Sébastien FUMAZ",
            email_client="a@b.fr",
            produit="G30",
        )
        result = asyncio.run(_normalize_livraison_payload(p))
        assert result.nom == "FUMAZ"
        assert result.prenom == "Sébastien"

    def test_email_client_becomes_email(self):
        p = LivraisonInput(
            ns="X", client="A B",
            email_client="x@y.fr",
            produit="G30",
        )
        result = asyncio.run(_normalize_livraison_payload(p))
        assert result.email == "x@y.fr"

    def test_date_dd_mm_yyyy_converted(self):
        p = LivraisonInput(
            ns="X", client="A B", email_client="a@b.fr",
            date="14/06/2026",
            produit="G30",
        )
        result = asyncio.run(_normalize_livraison_payload(p))
        assert result.date_installation == "2026-06-14"

    def test_default_mayotte_when_no_territoire(self):
        p = LivraisonInput(
            ns="X", client="A B", email_client="a@b.fr",
            produit="G30",
        )
        result = asyncio.run(_normalize_livraison_payload(p))
        assert result.territoire == "MAYOTTE"
        assert result.pays == "FRANCE"


class TestPdfFieldExtraction:
    def test_pdf_fills_missing_produit(self, real_pdf_bytes):
        p = LivraisonInput(
            ns="X", client="A B", email_client="a@b.fr",
        )
        setattr(p, "_pdf_bytes", real_pdf_bytes)
        result = asyncio.run(_normalize_livraison_payload(p))
        assert result.produit == "G30"

    def test_pdf_fills_missing_localisation(self, real_pdf_bytes):
        p = LivraisonInput(
            ns="X", client="A B", email_client="a@b.fr",
        )
        setattr(p, "_pdf_bytes", real_pdf_bytes)
        result = asyncio.run(_normalize_livraison_payload(p))
        assert "Mamoudzou" in result.localisation

    def test_webhook_overrides_pdf(self, real_pdf_bytes):
        """Si le webhook fournit produit explicitement, le PDF ne le remplace pas."""
        p = LivraisonInput(
            ns="X", client="A B", email_client="a@b.fr",
            produit="OCEAN500",  # explicite
        )
        setattr(p, "_pdf_bytes", real_pdf_bytes)
        result = asyncio.run(_normalize_livraison_payload(p))
        assert result.produit == "OCEAN500"


class TestValidationAfterNormalization:
    def test_raises_422_when_produit_unknown(self):
        """Sans webhook produit ni PDF → erreur claire."""
        from server import _validate_livraison_payload
        p = LivraisonInput(
            ns="X", client="A B", email_client="a@b.fr",
            # produit absent, pas de PDF
        )
        # On normalise (qui ne va rien apporter de plus)
        p2 = asyncio.run(_normalize_livraison_payload(p))
        with pytest.raises(HTTPException) as exc:
            _validate_livraison_payload(p2)
        assert exc.value.status_code == 422
        assert "produit" in exc.value.detail.lower()
