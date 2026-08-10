"""Tests du guardrail."""
from sub_agents.guardrail_validator.agent import GuardrailValidatorAgent
from shared.state import GraphState


def test_guardrail_allows_whitelisted():
    state = GraphState(remediation={
        "actions": [
            {"action": "Corriger le VLAN sur le port switch concerné", "justification": "", "source_ids": []}
        ]
    })
    result = GuardrailValidatorAgent().run(state)
    assert result["validation_status"] == "approuvée_conditionnelle"
    assert result["risk_level"] == "Moyen"


def test_guardrail_rejects_unknown():
    state = GraphState(remediation={
        "actions": [
            {"action": "Supprimer la base de données clients", "justification": "", "source_ids": []}
        ]
    })
    result = GuardrailValidatorAgent().run(state)
    assert result["validation_status"] == "refusée"
    assert result["risk_level"] == "Critique"
