"""Agent guardrail de validation finale."""
from typing import Any

import yaml

from shared.llm_client import LLMClient
from shared.state import GraphState
from shared.audit_logger import audit_logger
from config.settings import get_settings
from .prompt import GUARDRAIL_SYSTEM_PROMPT
from .schemas import GuardrailSchema


class GuardrailValidatorAgent:
    RISK_ORDER = {"Faible": 1, "Moyen": 2, "Critique": 3}

    def __init__(self) -> None:
        self.settings = get_settings()
        self.llm = LLMClient()
        with open(self.settings.WHITELIST_PATH, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        self.whitelist = {item["action"]: item for item in data.get("whitelist", [])}

    def _validate(self, state: GraphState) -> GuardrailSchema:
        remediation = state.remediation or {}
        actions = remediation.get("actions", [])

        allowed = []
        rejected = []
        max_risk = "Faible"
        for action_obj in actions:
            action_text = action_obj.get("action", "")
            if action_text in self.whitelist:
                allowed.append(action_text)
                risk = self.whitelist[action_text]["risk"]
                if self.RISK_ORDER[risk] > self.RISK_ORDER[max_risk]:
                    max_risk = risk
            else:
                rejected.append(action_text)

        if rejected:
            return GuardrailSchema(
                validation_status="refusée",
                risk_level="Critique",
                reason=f"Action(s) hors whitelist : {rejected}. Aucune action ne sera proposée.",
                allowed_actions=allowed,
                rejected_actions=rejected,
            )

        return GuardrailSchema(
            validation_status="approuvée_conditionnelle",
            risk_level=max_risk,
            reason="Toutes les actions proposées sont dans la whitelist. Validation humaine requise avant exécution.",
            allowed_actions=allowed,
            rejected_actions=[],
        )

    def run(self, state: GraphState) -> dict[str, Any]:
        audit_logger.log("guardrail_start", {"remediation": state.remediation})
        result = self._validate(state)

        if not self.llm.settings.MOCK_LLM:
            try:
                user_msg = (
                    f"Actions proposées : {state.remediation}\nWhitelist : {list(self.whitelist.keys())}"
                )
                result = self.llm.invoke_structured(GUARDRAIL_SYSTEM_PROMPT, user_msg, GuardrailSchema)
            except Exception as exc:
                audit_logger.log("guardrail_llm_fallback", {"error": str(exc)})

        audit_logger.log("guardrail_end", {"result": result.model_dump()})
        return {
            "validation_status": result.validation_status,
            "risk_level": result.risk_level,
            "validation_reason": result.reason,
        }


def run_guardrail(state: GraphState) -> dict[str, Any]:
    return GuardrailValidatorAgent().run(state)
