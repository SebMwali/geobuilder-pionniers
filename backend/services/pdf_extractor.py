"""
PDF Extractor - extrait la photo d'emplacement depuis un rapport d'installation PDF.

Heuristique validée sur le rapport réel "STN - LIVRAISON.pdf" :
- Le rapport contient typiquement 1 grande photo JPEG (terrain) + 2-3 PNG (logos Geobuilder)
- La photo terrain est TOUJOURS la plus grande image JPEG du PDF
- Les logos sont en PNG (transparence) et de petite taille

Stratégie :
1. Parcourir toutes les images de toutes les pages
2. Préférer le plus gros JPEG (photo appareil/smartphone)
3. Fallback : la plus grande image par taille en octets

Retourne (bytes, ext) ou None si aucune image exploitable.
"""
from __future__ import annotations

import logging
from typing import Optional, Tuple

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


def extract_location_photo(pdf_bytes: bytes) -> Optional[Tuple[bytes, str]]:
    """
    Extrait la photo d'emplacement depuis un PDF de rapport d'installation.

    Args:
        pdf_bytes: contenu binaire du PDF

    Returns:
        Tuple (image_bytes, extension) ou None si aucune image trouvée.
        Extension exemple : "jpeg", "png".
    """
    if not pdf_bytes:
        return None

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as e:
        logger.warning(f"PDF open failed: {e}")
        return None

    jpegs: list[tuple[int, bytes, str]] = []  # (size, bytes, ext)
    others: list[tuple[int, bytes, str]] = []

    try:
        for page in doc:
            for img in page.get_images(full=True):
                xref = img[0]
                try:
                    base = doc.extract_image(xref)
                except Exception:
                    continue
                ext = (base.get("ext") or "").lower()
                data = base.get("image") or b""
                if not data:
                    continue
                entry = (len(data), data, ext)
                if ext in ("jpeg", "jpg"):
                    jpegs.append(entry)
                else:
                    others.append(entry)
    finally:
        doc.close()

    # Préférer le plus gros JPEG (photo terrain typique)
    if jpegs:
        jpegs.sort(key=lambda x: x[0], reverse=True)
        size, data, ext = jpegs[0]
        logger.info(f"Photo terrain extraite : jpeg {size} bytes")
        return data, "jpg"

    # Fallback : la plus grande image quelle qu'elle soit
    if others:
        others.sort(key=lambda x: x[0], reverse=True)
        size, data, ext = others[0]
        logger.info(f"Photo terrain extraite (fallback) : {ext} {size} bytes")
        return data, ext or "png"

    logger.info("Aucune image exploitable trouvée dans le PDF")
    return None
