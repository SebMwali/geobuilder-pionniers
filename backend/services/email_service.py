"""
Email service — envoi RÉEL via Resend.

L'envoi se fait via le SDK officiel `resend` (synchrone), encapsulé dans
`asyncio.to_thread` pour ne pas bloquer la boucle FastAPI.

Si `RESEND_API_KEY` n'est pas configurée OU si l'envoi échoue, on bascule
sur le mode "mock" (log + stockage mémoire) pour ne JAMAIS bloquer le
pipeline LIVRAISON. Le client peut toujours accéder à son passeport via
les URLs retournées dans la réponse webhook, même si l'email échoue.

Stockage mémoire : conserve les 500 derniers envois (réels OU mockés)
pour debug via /api/admin/emails-outbox.
"""
import asyncio
import logging
import os
from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import resend

logger = logging.getLogger(__name__)

# Stockage en mémoire (bornée — debug uniquement, pas de persistance)
_OUTBOX: "deque[Dict[str, Any]]" = deque(maxlen=500)


def _get_sender() -> str:
    """Formatage "Nom <email>" si SENDER_NAME est défini, sinon juste l'email."""
    email = os.environ.get("SENDER_EMAIL", "")
    name = os.environ.get("SENDER_NAME", "").strip()
    if not email:
        return ""
    return f"{name} <{email}>" if name else email


def _resend_configured() -> bool:
    return bool(os.environ.get("RESEND_API_KEY")) and bool(os.environ.get("SENDER_EMAIL"))


async def send_email_mock(
    to: str,
    subject: str,
    html_body: str,
    metadata: Optional[dict] = None,
    tags: Optional[Dict[str, str]] = None,
    cc: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Envoi d'email via Resend (réel) avec fallback mock si non configuré ou erreur.

    Le nom de la fonction est conservé (`send_email_mock`) pour compatibilité
    descendante avec le reste du code — son comportement est désormais "real-first,
    mock-fallback".

    `tags` : dict {key: value} attaché à l'envoi Resend pour permettre le tracking
    via webhook (`pio_id`, `install_id`, `template`...). Les valeurs Resend doivent
    être [a-zA-Z0-9_-] uniquement.

    `cc` : liste d'adresses en copie (utilisé pour les pionniers multi-contacts comme
    les associations / entreprises).
    """
    record = {
        "to": to,
        "cc": cc or [],
        "subject": subject,
        "html_body": html_body,
        "metadata": metadata or {},
        "tags": tags or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    if not _resend_configured():
        record["status"] = "MOCKED"
        record["reason"] = "RESEND_API_KEY or SENDER_EMAIL missing"
        _OUTBOX.appendleft(record)
        logger.info("[MOCK EMAIL — no key] To=%s | Subject=%s", to, subject)
        return {"status": "mocked", "to": to, "subject": subject}

    sender = _get_sender()
    # Fallback text (plain text) — force Resend à envoyer en multipart/alternative.
    # Sans `text`, certains clients mail (Gmail mobile notamment) peuvent afficher
    # le HTML brut. On dérive un texte minimal lisible depuis le HTML.
    import re as _re
    plain_text = _re.sub(r"<[^>]+>", " ", html_body)
    plain_text = _re.sub(r"\s+", " ", plain_text).strip()
    if len(plain_text) > 2000:
        plain_text = plain_text[:2000] + "..."
    if not plain_text:
        plain_text = subject

    # Headers anti-spam (List-Unsubscribe — exigence Gmail/Yahoo 2024 RFC 8058)
    unsub_base = os.environ.get("UNSUBSCRIBE_BASE_URL", "").rstrip("/")
    headers: Dict[str, str] = {}
    if unsub_base:
        unsub_url = f"{unsub_base}/api/unsubscribe?email={to}"
        headers["List-Unsubscribe"] = f"<{unsub_url}>"
        headers["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"

    # Tags Resend (utilisés par webhook pour identifier le pionnier)
    # Format Resend : list[{name, value}] ; [a-zA-Z0-9_-] uniquement
    resend_tags: List[Dict[str, str]] = []
    if tags:
        for k, v in tags.items():
            if v is None:
                continue
            safe_name = _re.sub(r"[^a-zA-Z0-9_-]", "_", str(k))[:256]
            safe_value = _re.sub(r"[^a-zA-Z0-9_-]", "_", str(v))[:256]
            if safe_value:
                resend_tags.append({"name": safe_name, "value": safe_value})

    params: Dict[str, Any] = {
        "from": sender,
        "to": [to],
        "subject": subject,
        "html": html_body,
        "text": plain_text,
    }
    if cc:
        params["cc"] = cc
    if headers:
        params["headers"] = headers
    if resend_tags:
        params["tags"] = resend_tags

    try:
        # Resend SDK est synchrone — on le passe en thread pour ne pas bloquer asyncio
        resend.api_key = os.environ["RESEND_API_KEY"]
        response = await asyncio.to_thread(resend.Emails.send, params)
        email_id = response.get("id") if isinstance(response, dict) else None
        record["status"] = "SENT"
        record["resend_id"] = email_id
        _OUTBOX.appendleft(record)
        logger.info("[REAL EMAIL via Resend] To=%s | Subject=%s | ID=%s", to, subject, email_id)
        return {"status": "sent", "to": to, "subject": subject, "resend_id": email_id}

    except Exception as e:
        # Fallback : ne JAMAIS bloquer le pipeline si Resend tombe
        record["status"] = "ERROR_FALLBACK_MOCK"
        record["error"] = str(e)
        _OUTBOX.appendleft(record)
        logger.error("[EMAIL FAILED — fallback mock] To=%s | Subject=%s | Error=%s",
                     to, subject, e)
        return {"status": "error_mocked", "to": to, "subject": subject, "error": str(e)}


def get_outbox_snapshot(limit: int = 200) -> List[Dict[str, Any]]:
    """Liste des derniers envois (réels + mockés + erreurs) pour debug."""
    return list(_OUTBOX)[:limit]


def parse_email_field(raw: str) -> tuple[str, List[str]]:
    """Sépare un champ email brut en (TO principal, [CC...]).

    Gère les multi-adresses séparées par ';' ou ','. La 1re adresse valide
    devient le destinataire principal, les suivantes vont en CC.
    Retourne ("", []) si aucune adresse valide.

    Exemples :
      'a@x.fr; b@x.fr'        → ('a@x.fr', ['b@x.fr'])
      'a@x.fr; b@x.fr, c@x.fr'→ ('a@x.fr', ['b@x.fr', 'c@x.fr'])
      'a@x.fr'                → ('a@x.fr', [])
      ''                      → ('', [])
    """
    import re as _re
    EMAIL_RX = _re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
    if not raw:
        return ("", [])
    parts = [p.strip() for p in _re.split(r"[;,]\s*", str(raw).strip()) if p.strip()]
    valides = [p for p in parts if EMAIL_RX.match(p)]
    if not valides:
        return ("", [])
    return (valides[0], valides[1:])
