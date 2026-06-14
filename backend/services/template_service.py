"""
Template service - remplace les placeholders {{...}} dans les templates HTML.
"""
import os
import re
from pathlib import Path
from typing import Dict

TEMPLATE_DIR = Path(__file__).parent.parent / "templates"


def render_template(template_name: str, context: Dict[str, str]) -> str:
    """
    Charge un template HTML et remplace les placeholders {{KEY}} par context[KEY].
    Les clés manquantes sont remplacées par une chaîne vide (avec un warning loggé).
    """
    path = TEMPLATE_DIR / template_name
    if not path.exists():
        raise FileNotFoundError(f"Template not found: {path}")
    html = path.read_text(encoding="utf-8")

    def replace(match):
        key = match.group(1).strip()
        return str(context.get(key, ""))

    rendered = re.sub(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}", replace, html)
    return rendered
