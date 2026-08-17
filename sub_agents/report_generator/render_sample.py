"""Sample script to render a diagnostic PDF using the pure Python renderer."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sub_agents.report_generator.pdf_renderer import generate_diagnostic_report


def build_sample_data() -> dict:
    """Returns a sample dictionary structure for the CCU diagnostic report."""
    return {
        "title": "Rapport de diagnostic CCU",
        "report_id": "REP-CCU-2026-0001",
        "generated_at": "2026-08-12T14:30:00+00:00",
        "incident_id": "INC-CCU-2026-0001",
        "client_id": "acc-12345",
        "order_id": "ord-2026-001",
        "product_type": "Fibre Pro 500",
        "category": "network",
        "priority": "P2",
        "detected_at": "2026-08-12T14:25:00+00:00",
        "what_happened": (
            "Le client acc-12345 signale une coupure Internet totale sur le service svc-fiber-12345. "
            "La commande associée ord-2026-001 est bloquée en provisioning CPE."
        ),
        "confidence_level": "medium",
        "confidence_label": "medium",
        "root_cause": "Perte de signal fibre optique sur l'OLT desservant le site client",
        "sources": [
            "log-olt-001 (RX power < -28 dBm)",
            "TICK-2025-014 (incident fibre similaire)",
            "ord-2026-001 (provisioning bloqué)",
        ],
        "mapping_status": "linked_to_existing",
        "mapping_ticket_id": "TICK-2025-014",
        "mapping_score": "0.91",
        "recommendation": (
            "Un technicien terrain doit être envoyé pour inspecter et ré-épisser la fibre au PTO. "
            "Aucune action automatique n'est effectuée par l'agent de diagnostic."
        ),
    }


def main() -> None:
    output_path = Path("reports/sample_report.pdf")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    data = build_sample_data()
    generate_diagnostic_report(data, output_path)
    print(f"Sample PDF written to {output_path}")


if __name__ == "__main__":
    main()
