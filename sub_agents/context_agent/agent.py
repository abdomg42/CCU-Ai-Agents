"""Agent contexte client."""
import json
from typing import Any

from shared.llm_client import LLMClient
from shared.state import GraphState
from shared.audit_logger import audit_logger
from config.settings import get_settings
from .prompt import CONTEXT_SYSTEM_PROMPT
from .schemas import ContextSchema
from sub_agents.intake_parser.schemas import IncidentSchema


def _as_parsed(incident: dict[str, Any]) -> IncidentSchema:
    return IncidentSchema(**incident) if incident else IncidentSchema()


class ContextAgent:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.llm = LLMClient()
        with open(self.settings.MOCK_CRM, encoding="utf-8") as f:
            self.crm = json.load(f)
        with open(self.settings.MOCK_ORDERS, encoding="utf-8") as f:
            self.orders = json.load(f)

    def run(self, state: GraphState) -> dict[str, Any]:
        parsed = _as_parsed(state.parsed_incident)
        audit_logger.log("context_start", {"parsed": parsed.model_dump()})

        customer = None
        if parsed.customer_id:
            customer = next(
                (c for c in self.crm["customers"] if c["customer_id"] == parsed.customer_id), None
            )
        if not customer and parsed.service_id:
            customer = next(
                (c for c in self.crm["customers"]
                 if any(s["service_id"] == parsed.service_id for s in c.get("subscriptions", []))),
                None,
            )

        order = None
        if parsed.order_id:
            order = next((o for o in self.orders if o["order_id"] == parsed.order_id), None)
        if not order and parsed.service_id:
            order = next(
                (o for o in self.orders if o.get("service_id") == parsed.service_id), None
            )

        subscription = None
        if customer:
            subscription = next(
                (s for s in customer.get("subscriptions", [])
                 if (not parsed.service_id or s.get("service_id") == parsed.service_id)),
                None,
            )

        risk_factors = []
        source_ids = []
        if customer:
            source_ids.append(customer["customer_id"])
        if order:
            source_ids.append(order["order_id"])
            if order.get("status") in ("failed", "acknowledged"):
                risk_factors.append(
                    f"Commande {order['order_id']} en statut {order['status']}"
                )
            if order.get("reason"):
                risk_factors.append(f"Raison commande : {order['reason']}")
        if subscription:
            if subscription.get("status") != "active":
                risk_factors.append(
                    f"Abonnement {subscription.get('service_id')} en statut {subscription.get('status')}"
                )

        result = ContextSchema(
            customer_id=customer["customer_id"] if customer else None,
            customer_name=customer["name"] if customer else None,
            segment=customer["segment"] if customer else None,
            subscription=subscription,
            order=order,
            risk_factors=risk_factors,
            source_ids=source_ids,
        )

        if not self.llm.settings.MOCK_LLM:
            try:
                user_msg = f"Contexte brut : {result.model_dump()}"
                result = self.llm.invoke_structured(CONTEXT_SYSTEM_PROMPT, user_msg, ContextSchema)
            except Exception as exc:
                audit_logger.log("context_llm_fallback", {"error": str(exc)})

        audit_logger.log("context_end", {"result": result.model_dump()})
        return {"customer_context": result.model_dump()}


def run_context(state: GraphState) -> dict[str, Any]:
    return ContextAgent().run(state)
