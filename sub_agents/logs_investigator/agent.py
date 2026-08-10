"""Agent investigateur de logs."""
import json
from typing import Any

from shared.llm_client import LLMClient
from shared.state import GraphState
from shared.audit_logger import audit_logger
from config.settings import get_settings
from .prompt import LOGS_SYSTEM_PROMPT
from .schemas import LogInvestigationSchema
from sub_agents.intake_parser.schemas import IncidentSchema


def _as_parsed(incident: dict[str, Any]) -> IncidentSchema:
    return IncidentSchema(**incident) if incident else IncidentSchema()


class LogsInvestigatorAgent:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.llm = LLMClient()
        with open(self.settings.MOCK_LOGS, encoding="utf-8") as f:
            self.logs = json.load(f)

    def run(self, state: GraphState) -> dict[str, Any]:
        parsed = _as_parsed(state.parsed_incident)
        audit_logger.log("logs_start", {"parsed": parsed.model_dump()})
        relevant = []
        seen = set()

        # Filtrage heuristique sur service_id, order_id, customer_id implicite via order
        for log in self.logs:
            match = False
            if parsed.service_id and log.get("service_id") == parsed.service_id:
                match = True
            if parsed.order_id and log.get("order_id") == parsed.order_id:
                match = True
            if match and log["log_id"] not in seen:
                relevant.append(log)
                seen.add(log["log_id"])

        has_signal = any(log.get("severity") in ("ERROR", "CRITICAL") for log in relevant)

        result = LogInvestigationSchema(
            relevant_logs=relevant,
            summary=self._build_summary(relevant, parsed),
            source_ids=[log["log_id"] for log in relevant],
            has_clear_signal=has_signal and len(relevant) > 0,
        )

        if not self.llm.settings.MOCK_LLM:
            try:
                user_msg = (
                    f"Incident : {parsed.model_dump()}\nLogs pertinents : {relevant}"
                )
                result = self.llm.invoke_structured(LOGS_SYSTEM_PROMPT, user_msg, LogInvestigationSchema)
            except Exception as exc:
                audit_logger.log("logs_llm_fallback", {"error": str(exc)})

        audit_logger.log("logs_end", {"result": result.model_dump()})
        return {"logs": result.model_dump()}

    def _build_summary(self, relevant: list[dict], parsed) -> str:
        if not relevant:
            return f"Aucun log technique trouvé pour {parsed.service_id or parsed.order_id}."
        errors = [l for l in relevant if l.get("severity") == "ERROR"]
        if errors:
            return f"{len(errors)} erreur(s) détectée(s) : " + " ; ".join(
                f"{e['source']} – {e['message']}" for e in errors[:3]
            )
        return f"{len(relevant)} log(s) trouvé(s), aucune erreur critique."


def run_logs(state: GraphState) -> dict[str, Any]:
    return LogsInvestigatorAgent().run(state)
