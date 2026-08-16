"""Client SMTP pour l'envoi du rapport par email.

Aucune action technique n'est effectuée : seul un email informatif est envoyé.
Le client supporte l'authentification TLS/STARTTLS (Gmail, Outlook, etc.).
"""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from pathlib import Path
from typing import Any

from config.settings import get_settings

logger = logging.getLogger(__name__)


class EmailClient:
    """Envoi d'email SMTP avec pièce jointe PDF."""

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        from_addr: str | None = None,
    ) -> None:
        settings = get_settings()
        self.host = host or settings.SMTP_HOST
        self.port = port or settings.SMTP_PORT
        self.from_addr = from_addr or settings.SMTP_FROM
        self.user = settings.SMTP_USER or ""
        self.password = settings.SMTP_PASS or ""
        self.use_tls = settings.SMTP_USE_TLS
        self.recipients = settings.REPORT_RECIPIENTS

    def build_subject(self, incident_id: str, confidence_label: str) -> str:
        return f"[CCU] Incident Report {incident_id} - {confidence_label} confidence"

    def build_body(self, incident_id: str, report_path: str) -> str:
        return (
            f"Please find attached the diagnostic report for incident {incident_id}.\n\n"
            f"Report path: {report_path}\n\n"
            "This message was generated automatically by the CCU Diagnostic Agent. "
            "No technical action has been executed on production systems."
        )

    def send_report(
        self,
        incident_id: str,
        confidence_label: str,
        report_path: str,
        recipients: list[str] | None = None,
    ) -> dict[str, Any]:
        """Envoie le rapport par email avec pièce jointe."""
        recipients = recipients or self.recipients
        if not recipients:
            logger.warning("Aucun destinataire configuré pour l'envoi de rapport.")
            return {"sent": False, "reason": "no_recipients", "recipients": []}

        msg = EmailMessage()
        msg["From"] = self.from_addr
        msg["To"] = ", ".join(recipients)
        msg["Subject"] = self.build_subject(incident_id, confidence_label)
        msg.set_content(self.build_body(incident_id, report_path))

        path = Path(report_path)
        if path.exists():
            with open(path, "rb") as f:
                content = f.read()
            msg.add_attachment(
                content,
                maintype="application",
                subtype="pdf",
                filename=path.name,
            )

        try:
            with smtplib.SMTP(self.host, self.port, timeout=20) as server:
                if self.use_tls:
                    server.starttls()
                if self.user and self.password:
                    server.login(self.user, self.password)
                server.send_message(msg)
            logger.info("Email envoyé à %s", recipients)
            return {"sent": True, "recipients": recipients}
        except Exception as exc:
            logger.warning("Échec envoi email : %s", exc)
            return {"sent": False, "reason": str(exc), "recipients": recipients}
