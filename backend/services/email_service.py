"""
Email service - MOCKED for first version.
Stocke les emails générés dans MongoDB + console log.
À remplacer par SendGrid/Resend/SMTP plus tard.
"""
import logging
from datetime import datetime, timezone
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


async def send_email_mock(
    db: AsyncIOMotorDatabase,
    to: str,
    subject: str,
    html_body: str,
    metadata: Optional[dict] = None,
):
    """MOCKED email send - stocke en DB + log."""
    doc = {
        "to": to,
        "subject": subject,
        "html_body": html_body,
        "metadata": metadata or {},
        "status": "MOCKED",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.emails_outbox.insert_one(doc)
    logger.info(f"[MOCK EMAIL] To: {to} | Subject: {subject}")
    return {"status": "mocked", "to": to, "subject": subject}
