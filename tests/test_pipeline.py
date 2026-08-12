"""Tests d'intégration du pipeline."""
from orchestrator.pipeline import run_diagnosis


def test_pipeline_fiber_case():
    incident = {
        "title": "Coupure fibre",
        "description": "Client acc-12345, service svc-fiber-12345, commande ord-2026-001. Coupure Internet.",
    }
    result = run_diagnosis(incident)
    assert result["root_cause"]["cause"] == "Perte de signal fibre optique"
    assert result["ticket_mapping"]["status"] == "created_new"
    assert result["report_path"] is not None
    assert result["remediation_explanation"] is not None


def test_pipeline_billing_undetermined():
    incident = {
        "title": "Écart facture",
        "description": "Client acc-99999, service svc-bill-99999. Écart de 0.03 € sur la facture.",
    }
    result = run_diagnosis(incident)
    assert result["root_cause"]["cause"] == "indéterminée"
    assert result["ticket_mapping"]["status"] == "created_new"
