"""Tests du guardrail de contenu (PII)."""
from sub_agents.content_guardrail.pii_sanitizer import sanitize_state_texts
from shared.state import GraphState


def test_pii_sanitizer_replaces_email_and_phone():
    state = GraphState(
        incident={
            "title": "Incident",
            "description": "Contact john.doe@example.com or +33 6 12 34 56 78 for details.",
        },
        parsed_incident={"customer_id": "acc-12345", "order_id": "ord-2026-001"},
    )
    result = sanitize_state_texts(state)
    assert "john.doe@example.com" not in result["what_happened"]
    assert "[EMAIL_REDACTED]" in result["what_happened"]
    assert "+33 6 12 34 56 78" not in result["what_happened"]
    assert "acc-12345" in result["what_happened"]


def test_pii_sanitizer_keeps_technical_ids():
    state = GraphState(
        incident={"title": "Incident", "description": "Client acc-12345, service svc-fiber-12345."},
        parsed_incident={"customer_id": "acc-12345"},
    )
    result = sanitize_state_texts(state)
    assert "acc-12345" in result["what_happened"]
    assert "svc-fiber-12345" in result["what_happened"]
