"""Runner d'évaluation sur les incidents golden.

Rejoue chaque cas mocké contre le pipeline complet et compare la cause racine
retournée avec la cause attendue. Produit un rapport pass/fail + accuracy globale.
"""
import glob
import json
import os
import sys
from pathlib import Path

from orchestrator.pipeline import run_diagnosis


ROOT = Path(__file__).resolve().parent


def load_cases() -> list[tuple[str, dict, dict]]:
    cases = []
    for case_dir in sorted(ROOT.iterdir()):
        if case_dir.is_dir() and case_dir.name.startswith("case_"):
            input_path = case_dir / "input.json"
            expected_path = case_dir / "expected.json"
            if input_path.exists() and expected_path.exists():
                with open(input_path, encoding="utf-8") as f:
                    inp = json.load(f)
                with open(expected_path, encoding="utf-8") as f:
                    expected = json.load(f)
                cases.append((case_dir.name, inp, expected))
    return cases


def evaluate() -> int:
    cases = load_cases()
    if not cases:
        print("Aucun cas golden trouvé.")
        return 1

    passed = 0
    results = []

    for name, inp, expected in cases:
        print(f"\n--- {name} ---")
        result = run_diagnosis(inp)
        root_cause = result.get("root_cause", {}) or {}
        actual_cause = root_cause.get("cause", "").strip()
        expected_cause = expected["expected_cause"].strip()
        cause_ok = actual_cause.lower() == expected_cause.lower()

        actual_risk = result.get("risk_level", "").strip()
        expected_risk = expected["expected_risk"].strip()
        risk_ok = actual_risk.lower() == expected_risk.lower()

        validation_ok = (
            result.get("validation_status", "").strip().lower()
            == expected["expected_validation"].strip().lower()
        )

        case_pass = cause_ok and risk_ok and validation_ok
        if case_pass:
            passed += 1

        results.append({
            "case": name,
            "pass": case_pass,
            "expected_cause": expected_cause,
            "actual_cause": actual_cause,
            "expected_risk": expected_risk,
            "actual_risk": actual_risk,
            "validation": result.get("validation_status"),
        })
        status = "PASS" if case_pass else "FAIL"
        print(f"  Cause: {actual_cause!r} (attendu {expected_cause!r}) -> {'OK' if cause_ok else 'KO'}")
        print(f"  Risque: {actual_risk} (attendu {expected_risk}) -> {'OK' if risk_ok else 'KO'}")
        print(f"  Validation: {result.get('validation_status')} -> {'OK' if validation_ok else 'KO'}")
        print(f"  [{status}]")

    accuracy = passed / len(cases) if cases else 0.0
    print(f"\n=== Résumé ===")
    print(f"Cas total: {len(cases)}")
    print(f"Pass: {passed}")
    print(f"Fail: {len(cases) - passed}")
    print(f"Accuracy: {accuracy:.0%}")

    return 0 if passed == len(cases) else 1


if __name__ == "__main__":
    sys.exit(evaluate())
