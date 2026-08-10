"""Audit logger : trace chaque transition du graphe et chaque appel LLM/mock."""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config.settings import get_settings


class AuditLogger:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.settings.AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        self._logger = logging.getLogger("diagnostic_audit")
        self._logger.setLevel(logging.INFO)
        if not self._logger.handlers:
            handler = logging.FileHandler(self.settings.AUDIT_LOG_PATH)
            handler.setFormatter(logging.Formatter("%(message)s"))
            self._logger.addHandler(handler)
            stdout = logging.StreamHandler()
            stdout.setFormatter(logging.Formatter("%(message)s"))
            self._logger.addHandler(stdout)

    def log(self, event_type: str, payload: dict[str, Any]) -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "payload": payload,
        }
        self._logger.info(json.dumps(entry, ensure_ascii=False, default=str))


audit_logger = AuditLogger()
