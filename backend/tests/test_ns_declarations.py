"""Tests unitaires LOT 2 — Collecte des NS (V1).

Tests rapides sur les helpers purs (pas d'accès Sheets).
"""
import pytest
from services.ns_declarations import (
    normalize_ns,
    validate_ns_format,
    STATUT_PENDING,
    STATUT_VALIDATED,
    STATUT_REJECTED,
)


class TestNormalizeNs:
    def test_uppercase(self):
        assert normalize_ns("hr88c23efr0080") == "HR88C23EFR0080"

    def test_strip_spaces(self):
        assert normalize_ns("  HR88 C23 EFR0080  ") == "HR88C23EFR0080"

    def test_keep_dash(self):
        assert normalize_ns("hr88-c23-efr0080") == "HR88-C23-EFR0080"

    def test_empty(self):
        assert normalize_ns("") == ""
        assert normalize_ns(None) == ""


class TestValidateNsFormat:
    def test_valid(self):
        assert validate_ns_format("HR88C23EFR0080") is None
        assert validate_ns_format("EA60L23ABC0080") is None
        assert validate_ns_format("AB12-CD34") is None

    def test_empty(self):
        assert "obligatoire" in validate_ns_format("").lower()
        assert "obligatoire" in validate_ns_format(None).lower()

    def test_too_short(self):
        assert "court" in validate_ns_format("AB1").lower()

    def test_invalid_chars(self):
        # Espaces et caractères spéciaux rejetés (après normalisation côté appelant)
        assert validate_ns_format("HR88!C23") is not None
        assert validate_ns_format("HR88@C23") is not None


class TestStatuts:
    def test_three_statuts(self):
        # V1 stricte : seulement 3 statuts
        assert STATUT_PENDING == "EN_ATTENTE"
        assert STATUT_VALIDATED == "VALIDEE"
        assert STATUT_REJECTED == "REFUSEE"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
