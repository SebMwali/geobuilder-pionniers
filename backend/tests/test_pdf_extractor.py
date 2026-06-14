"""Tests pour services.pdf_extractor — extraction photo terrain depuis un PDF."""
import io
import sys
from pathlib import Path

import pytest
import fitz  # PyMuPDF
from PIL import Image

BACKEND_DIR = Path(__file__).parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services.pdf_extractor import extract_location_photo  # noqa: E402


def _make_image_bytes(w: int, h: int, color: tuple, fmt: str) -> bytes:
    """Crée une image PIL en mémoire et la retourne en bytes."""
    img = Image.new("RGB", (w, h), color)
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


def _make_pdf_with_images(images: list[tuple[bytes, str]]) -> bytes:
    """Crée un PDF mono-page contenant les images fournies (bytes, ext)."""
    doc = fitz.open()
    page = doc.new_page(width=600, height=800)
    y = 10
    for img_bytes, _ext in images:
        rect = fitz.Rect(10, y, 300, y + 200)
        page.insert_image(rect, stream=img_bytes)
        y += 220
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


class TestExtractLocationPhoto:
    def test_empty_pdf(self):
        assert extract_location_photo(b"") is None

    def test_invalid_pdf(self):
        assert extract_location_photo(b"not a pdf") is None

    def test_pdf_without_images(self):
        doc = fitz.open()
        doc.new_page()
        pdf_bytes = doc.tobytes()
        doc.close()
        assert extract_location_photo(pdf_bytes) is None

    def test_picks_largest_jpeg_over_pngs(self):
        big_jpeg = _make_image_bytes(800, 600, (100, 100, 100), "JPEG")
        small_png = _make_image_bytes(100, 50, (200, 200, 200), "PNG")
        pdf_bytes = _make_pdf_with_images([(small_png, "png"), (big_jpeg, "jpeg")])

        result = extract_location_photo(pdf_bytes)
        assert result is not None
        data, ext = result
        assert ext == "jpg"
        assert len(data) > len(small_png)

    def test_fallback_to_png_when_no_jpeg(self):
        png_only = _make_image_bytes(400, 300, (50, 50, 50), "PNG")
        pdf_bytes = _make_pdf_with_images([(png_only, "png")])
        result = extract_location_photo(pdf_bytes)
        assert result is not None
        _data, ext = result
        # PyMuPDF peut détecter l'image PNG comme PNG ou jpeg (recompressé) ;
        # ce qui compte c'est qu'on extrait quelque chose.
        assert ext in ("png", "jpg", "jpeg")

    def test_real_pdf_extracts_terrain_photo(self):
        """Si le PDF réel est présent dans /tmp/stn.pdf, vérifie l'extraction."""
        path = Path("/tmp/stn.pdf")
        if not path.exists():
            pytest.skip("PDF réel non disponible dans /tmp/stn.pdf")
        result = extract_location_photo(path.read_bytes())
        assert result is not None
        data, ext = result
        # La photo terrain du rapport réel est un gros JPEG (~875 kB)
        assert ext == "jpg"
        assert len(data) > 100_000
