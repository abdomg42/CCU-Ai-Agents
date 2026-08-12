"""Sample data contract for the incident report template.

Run this script to render a sample PDF:
    python sub_agents/report_generator/render_sample.py
"""
from pathlib import Path

from jinja2 import Environment, FileSystemLoader


TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"


def build_sample_data() -> dict:
    """Returns the exact dictionary structure expected by the Jinja2 template."""
    return {
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
            "Customer acc-12345 reported a complete Internet outage on service svc-fiber-12345. "
            "The associated order ord-2026-001 is blocked in CPE provisioning."
        ),
        "confidence_level": "0.85",
        "confidence_label": "medium",
        "root_cause": "Perte de signal fibre optique",
        "sources": [
            "log-olt-001 (RX power < -28 dBm)",
            "TICK-2025-014 (similar fiber outage)",
            "ord-2026-001 (provisioning blocked)",
        ],
        "mapping_status": "linked_to_existing",
        "mapping_ticket_id": "TICK-2025-014",
        "mapping_score": "0.91",
        "recommendation": (
            "What happened: An optical signal loss was detected on the OLT serving the customer.\n\n"
            "Why: The OLT logs show a low RX power level, correlated with a historically resolved similar incident.\n\n"
            "Recommendation: Dispatch a field technician to inspect and re-terminate the fiber at the PTO. "
            "No automatic action is performed by the diagnostic agent."
        ),
    }


def main() -> None:
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    template = env.get_template("incident_report_template.html")

    data = build_sample_data()
    html = template.render(**data)

    output_path = Path("reports/sample_report.pdf")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        from weasyprint import HTML
        HTML(string=html).write_pdf(str(output_path))
        print(f"Sample PDF written to {output_path}")
    except Exception as exc:
        html_path = output_path.with_suffix(".html")
        html_path.write_text(html, encoding="utf-8")
        print(f"PDF generation failed ({exc}); sample HTML written to {html_path}")


if __name__ == "__main__":
    main()
