"""
PDF service - convertit HTML en PDF via WeasyPrint.
"""
import logging
from weasyprint import HTML

logger = logging.getLogger(__name__)


def html_to_pdf_bytes(html_string: str, base_url: str = None) -> bytes:
    """Convertit un HTML string en bytes PDF."""
    try:
        return HTML(string=html_string, base_url=base_url).write_pdf()
    except Exception as e:
        logger.error(f"WeasyPrint failed: {e}")
        raise
