"""
Email service - MOCKED.
Aucune dépendance externe (pas de DB, pas de Mongo, pas de Sheets).
Stocke en mémoire (process) + log console.

Évolution future : brancher SendGrid/Resend OU écrire dans un onglet
Google Sheets dédié (décision en P4).
"""
import logging
from collections import deque
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# Stockage en mémoire (bornée pour éviter fuite mémoire)
_OUTBOX: "deque[Dict[str, Any]]" = deque(maxlen=500)


async def send_email_mock(
    to: str,
    subject: str,
    html_body: str,
    metadata: Optional[dict] = None,
) -> Dict[str, Any]:
    """MOCKED email send - log console + stockage en mémoire (volatile).

    NOTE: la signature ne reçoit plus de DB. Toute modification du sink
    final sera décidée en P4 (logs vs onglet Sheets).
    """
    doc = {
        "to": to,
        "subject": subject,
        "html_body": html_body,
        "metadata": metadata or {},
        "status": "MOCKED",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _OUTBOX.appendleft(doc)
    logger.info("[MOCK EMAIL] To=%s | Subject=%s", to, subject)
    return {"status": "mocked", "to": to, "subject": subject}


def get_outbox_snapshot(limit: int = 200) -> List[Dict[str, Any]]:
    """Lecture courte de la boîte d'envoi mockée (utilisé par /api/health uniquement en P0)."""
    return list(_OUTBOX)[:limit]
