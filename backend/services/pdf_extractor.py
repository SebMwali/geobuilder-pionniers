"""
PDF Extractor - extrait la photo d'emplacement ET les champs labellisés
depuis un rapport d'installation PDF.

Heuristique validée sur les rapports réels SAV-Innov'eau :
- 1 grande photo JPEG (terrain) + 2-3 PNG (logos Geobuilder)
- Champs labellisés en français : "Modèle:", "N° Série:", "Adresse:", "Date:", "Client:", "Technicien(s):", "Type:"
"""
from __future__ import annotations

import logging
import re
from typing import Optional, Tuple

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


# Labels reconnus dans les rapports SAV-Innov'eau
_LABELS = {
    "produit":         re.compile(r"Mod[èe]le\s*:\s*(.+)", re.IGNORECASE),
    "numero_serie":    re.compile(r"N[°º]\s*S[ée]rie\s*:\s*(.+)", re.IGNORECASE),
    "adresse":         re.compile(r"Adresse\s*:\s*(.+)", re.IGNORECASE),
    "date":            re.compile(r"^\s*Date\s*:\s*(\d{2}/\d{2}/\d{4})", re.IGNORECASE | re.MULTILINE),
    "client":          re.compile(r"^\s*Client\s*:\s*(.+)", re.IGNORECASE | re.MULTILINE),
    "technicien":      re.compile(r"Technicien\(s\)\s*:\s*(.+)", re.IGNORECASE),
    "type":            re.compile(r"^\s*Type\s*:\s*(LIVRAISON|MAINTENANCE|SAV|INSTALLATION)", re.IGNORECASE | re.MULTILINE),
}


def extract_location_photo(pdf_bytes: bytes) -> Optional[Tuple[bytes, str]]:
    """
    Extrait la photo d'emplacement depuis un PDF de rapport d'installation.
    Stratégie : plus gros JPEG, fallback sur la plus grande image.
    """
    if not pdf_bytes:
        return None

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as e:
        logger.warning(f"PDF open failed: {e}")
        return None

    jpegs: list[tuple[int, bytes, str]] = []
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

    if jpegs:
        jpegs.sort(key=lambda x: x[0], reverse=True)
        return jpegs[0][1], "jpg"
    if others:
        others.sort(key=lambda x: x[0], reverse=True)
        size, data, ext = others[0]
        return data, ext or "png"
    return None


def extract_text(pdf_bytes: bytes) -> str:
    """Concatène le texte de toutes les pages du PDF."""
    if not pdf_bytes:
        return ""
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as e:
        logger.warning(f"PDF open failed: {e}")
        return ""
    try:
        return "\n".join(page.get_text() for page in doc)
    finally:
        doc.close()


def extract_fields(pdf_bytes: bytes) -> dict:
    """
    Extrait les champs labellisés d'un rapport SAV.
    Retourne un dict avec : produit, numero_serie, adresse, date (DD/MM/YYYY),
    client (nom complet), technicien, type. Clés absentes = champ non trouvé.
    """
    text = extract_text(pdf_bytes)
    if not text:
        return {}
    result = {}
    for key, pattern in _LABELS.items():
        m = pattern.search(text)
        if m:
            value = m.group(1).strip()
            # Nettoyage : on s'arrête à la première ligne (les labels suivants sont sur les lignes d'après)
            value = value.split("\n")[0].strip()
            if value:
                result[key] = value
    return result


def split_client_name(client_fullname: str) -> tuple[str, str]:
    """
    "Sébastien FUMAZ" → (prenom="Sébastien", nom="FUMAZ").
    Heuristique : le DERNIER mot est le nom de famille (convention SAV-Innov'eau).
    Si un seul mot, on le met dans les deux.
    """
    if not client_fullname:
        return "", ""
    parts = client_fullname.strip().split()
    if len(parts) == 1:
        return parts[0], parts[0]
    return " ".join(parts[:-1]), parts[-1]


def parse_date_fr(date_str: str) -> str:
    """DD/MM/YYYY → YYYY-MM-DD. Retourne '' si format invalide."""
    if not date_str:
        return ""
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})", date_str.strip())
    if not m:
        return ""
    d, mo, y = m.groups()
    return f"{y}-{mo}-{d}"

