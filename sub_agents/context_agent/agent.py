"""Agent contexte client."""
import json
from typing import Any

from shared.llm_client import LLMClient
from shared.state import GraphState
from shared.audit_logger import audit_logger
from config.settings import get_settings
from tools.crm_client import PostgresCRMClient
from .prompt import CONTEXT_SYSTEM_PROMPT
from .schemas import ContextSchema
from sub_agents.intake_parser.schemas import IncidentSchema


def _as_parsed(incident: dict[str, Any]) -> IncidentSchema:
    return IncidentSchema(**incident) if incident else IncidentSchema()


def _normalize_id(value: str | None) -> str | None:
    """Normalise les IDs pour comparer sans se soucier de la casse."""
    return value.strip().upper() if value else None


def _load_customer_from_postgres(customer_id: str) -> dict[str, Any] | None:
    """Fallback sur la vraie base CRM Postgres quand le mock ne contient pas le client."""
    try:
        with PostgresCRMClient() as client:
            row = client.get_client(customer_id)
        if not row:
            return None
        return {
            "customer_id": row["customer_id"],
            "name": f"Client {row['customer_id']}",
            "segment": "Inconnu",
            "contact": None,
            "account_status": "active",
            "tenure": row.get("tenure"),
            "contract": row.get("contract"),
            "monthly_charges": row.get("monthly_charges"),
            "total_charges": row.get("total_charges"),
            "churn": row.get("churn"),
            "subscriptions": [],
        }
    except Exception as exc:
        audit_logger.log("context_postgres_fallback_error", {"error": str(exc), "customer_id": customer_id})
        return None


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

        customer_id_norm = _normalize_id(parsed.customer_id)
        service_id_norm = _normalize_id(parsed.service_id)
        order_id_norm = _normalize_id(parsed.order_id)

        customer = None
        if customer_id_norm:
            customer = next(
                (c for c in self.crm["customers"] if _normalize_id(c["customer_id"]) == customer_id_norm),
                None,
            )
            # Fallback sur la vraie base CRM Postgres si le client n'est pas dans le mock.
            if not customer:
                customer = _load_customer_from_postgres(parsed.customer_id)
        if not customer and service_id_norm:
            customer = next(
                (c for c in self.crm["customers"]
                 if any(_normalize_id(s.get("service_id")) == service_id_norm for s in c.get("subscriptions", []))),
                None,
            )

        order = None
        if order_id_norm:
            order = next((o for o in self.orders if _normalize_id(o["order_id"]) == order_id_norm), None)
        if not order and service_id_norm:
            order = next(
                (o for o in self.orders if _normalize_id(o.get("service_id")) == service_id_norm),
                None,
            )

        subscription = None
        if customer:
            subscription = next(
                (s for s in customer.get("subscriptions", [])
                 if (not service_id_norm or _normalize_id(s.get("service_id")) == service_id_norm)),
                None,
            )

        risk_factors = []
        source_ids = []
        if customer:
            source_ids.append(customer["customer_id"])
            # Facteurs de risque basés sur le contexte client réel.
            tenure = customer.get("tenure")
            contract = customer.get("contract")
            churn = customer.get("churn")
            monthly_charges = customer.get("monthly_charges")
            if churn == "Yes":
                risk_factors.append("Client marqué churn = Yes")
            if isinstance(tenure, int) and tenure < 12:
                risk_factors.append(f"Client récent ({tenure} mois d'ancienneté)")
            if contract and "month" in contract.lower():
                risk_factors.append(f"Contrat sans engagement ({contract})")
            if isinstance(monthly_charges, (int, float)) and monthly_charges > 80:
                risk_factors.append(f"Revenu mensuel élevé ({monthly_charges:.2f})")
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
