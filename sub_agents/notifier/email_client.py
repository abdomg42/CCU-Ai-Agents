"""Client SMTP pour l'envoi du rapport par email.

Aucune action technique n'est effectuée : seul un email informatif est envoyé.
Le client supporte l'authentification TLS/STARTTLS (Gmail, Outlook, etc.).
"""
from __future__ import annotations

import logging
import smtplib
from email.headerregistry import Address
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

    def build_subject(self, context: dict[str, Any]) -> str:
        incident_id_f = context.get("incident_id", "N/A")
        incident_id = incident_id_f.split('/')[-1]
        incident_type = context.get("incident_type", "")
        priority = context.get("priority", "")
        parts = ["[CCU] Incident détecté"]
        if incident_type:
            parts.append(incident_type)
        if priority:
            parts.append(f"priorité {priority}")
        parts.append(f"{incident_id}")
        return " - ".join(parts)

    def build_body(self, context: dict[str, Any]) -> str:
        incident_id = context.get("incident_id", "N/A")
        report_path = context.get("report_path", "")
        report_name = Path(report_path).name if report_path else ""

        lines = [
            "Bonjour,",
            "",
            f"Un incident a été détecté pour le client {context.get('customer_id', 'N/A')}.",
            "",
            "Détails de l'incident :",
            f"  - ID incident     : {incident_id}",
            f"  - Service         : {context.get('service_id', 'N/A')}",
            f"  - Commande        : {context.get('order_id', 'N/A')}",
            f"  - Type de produit : {context.get('incident_type', 'N/A')}",
            f"  - Priorité        : {context.get('priority', 'N/A')}",
            f"  - Confiance       : {context.get('confidence', 'N/A')}",
            "",
            "Résumé :",
            f"{context.get('what_happened', 'Aucune information disponible.')}",
            "",
            "Cause racine :",
            f"{context.get('root_cause', 'Indéterminée')}",
            "",
            "Actions recommandées :",
        ]

        recommendation = context.get("recommendation", "")
        if recommendation:
            for line in recommendation.split("\n"):
                line = line.strip()
                if line:
                    if line.startswith(("-", "*")):
                        lines.append(line)
                    else:
                        lines.append(f"- {line}")
        else:
            lines.append("- Voir le rapport complet en pièce jointe.")

        lines.extend([
            "",
            "Veuillez consulter le rapport complet en pièce jointe.",
            "",
            "Cordialement,",
            "CCU Diagnostic Agent",
            "",
            "--",
            "Ce message est généré automatiquement. Aucune action technique n'est exécutée sur les systèmes de production.",
        ])

        return "\n".join(lines)

    def send_report(
        self,
        incident_id: str,
        confidence_label: str,
        report_path: str,
        recipients: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Envoie le rapport par email avec pièce jointe."""
        recipients = recipients or self.recipients
        # Sécurise et valide chaque destinataire avec la classe Address du stdlib.
        valid_recipients: list[str] = []
        if isinstance(recipients, str):
            recipients = [recipients]
        for addr in recipients:
            clean_addr = str(addr).strip() if addr else ""
            if not clean_addr or "@" not in clean_addr or clean_addr.startswith("@"):
                continue
            try:
                valid_recipients.append(str(Address(display_name="", addr_spec=clean_addr)))
            except Exception:
                logger.warning("Format d'adresse email rejeté : %s", clean_addr)

        if not valid_recipients:
            logger.warning("Aucun destinataire valide pour l'envoi de rapport.")
            return {"sent": False, "reason": "no_valid_recipients", "recipients": []}

        if not self.from_addr or "@" not in self.from_addr or self.from_addr.startswith("@"):
            logger.warning("SMTP_FROM invalide : %s", self.from_addr)
            return {"sent": False, "reason": "invalid_from_address", "recipients": valid_recipients}

        context = context or {}
        context.setdefault("incident_id", incident_id)
        context.setdefault("confidence", confidence_label)
        context.setdefault("report_path", report_path)

        msg = EmailMessage()
        msg["From"] = Address(display_name="CCU Diagnostic Agent", addr_spec=self.from_addr)
        msg["To"] = ", ".join(valid_recipients)
        msg["Subject"] = self.build_subject(context)
        msg.set_content(self.build_body(context))

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
