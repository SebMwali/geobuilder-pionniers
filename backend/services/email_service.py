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
) -> Dict[str, Any]:
    """Envoi d'email via Resend (réel) avec fallback mock si non configuré ou erreur.

    Le nom de la fonction est conservé (`send_email_mock`) pour compatibilité
    descendante avec le reste du code — son comportement est désormais "real-first,
    mock-fallback".
    """
    record = {
        "to": to,
        "subject": subject,
        "html_body": html_body,
        "metadata": metadata or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    if not _resend_configured():
        record["status"] = "MOCKED"
        record["reason"] = "RESEND_API_KEY or SENDER_EMAIL missing"
        _OUTBOX.appendleft(record)
        logger.info("[MOCK EMAIL — no key] To=%s | Subject=%s", to, subject)
        return {"status": "mocked", "to": to, "subject": subject}

    sender = _get_sender()
    params = {
        "from": sender,
        "to": [to],
        "subject": subject,
        "html": html_body,
    }

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
