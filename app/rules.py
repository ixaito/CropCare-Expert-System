import json
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent / "data"


def load_questions() -> list[dict[str, Any]]:
    with open(DATA_DIR / "questions.json", "r", encoding="utf-8") as file:
        return json.load(file)


def load_rules() -> list[dict[str, Any]]:
    with open(DATA_DIR / "rules.json", "r", encoding="utf-8") as file:
        return json.load(file)


def dependency_is_met(question: dict[str, Any], answers: dict[str, Any]) -> bool:
    depends_on = question.get("depends_on")
    if not depends_on:
        return True
    for field, expected_value in depends_on.items():
        if answers.get(field) != expected_value:
            return False
    return True


def next_question(answers: dict[str, Any]) -> dict[str, Any] | None:
    for question in load_questions():
        if question["id"] not in answers and dependency_is_met(question, answers):
            return question
    return None


def condition_matches(condition: dict[str, Any], answers: dict[str, Any]) -> bool:
    field = condition["field"]
    actual_value = answers.get(field)

    if "value" in condition:
        return actual_value == condition["value"]

    if "value_in" in condition:
        return actual_value in condition["value_in"]

    return False


def score_rule(rule: dict[str, Any], answers: dict[str, Any]) -> dict[str, Any]:
    total_weight = sum(item.get("weight", 0) for item in rule.get("conditions", []))
    matched_weight = 0
    matched_evidence: list[str] = []
    missing_evidence: list[str] = []

    for condition in rule.get("conditions", []):
        field = condition["field"]
        weight = condition.get("weight", 0)
        if condition_matches(condition, answers):
            matched_weight += weight
            matched_evidence.append(f"{field}: {answers.get(field)}")
        else:
            if field in answers:
                missing_evidence.append(f"{field}: {answers.get(field)}")

    confidence = round((matched_weight / total_weight) * 100, 2) if total_weight else 0
    return {
        "id": rule["id"],
        "name": rule["name"],
        "description": rule["description"],
        "recommendation": rule["base_recommendation"],
        "consult_expert_when": rule["consult_expert_when"],
        "confidence": confidence,
        "matched_weight": matched_weight,
        "total_weight": total_weight,
        "matched_evidence": matched_evidence,
        "missing_or_conflicting_evidence": missing_evidence,
    }


def severity_message(answers: dict[str, Any]) -> str:
    severity = answers.get("severity")
    if severity == "Severe":
        return "The issue is marked as severe. Treat this as urgent and consider expert consultation."
    if severity == "Moderate":
        return "The issue is moderate. Start treatment early and monitor the crop closely."
    if severity == "Mild":
        return "The issue is mild. Early action and monitoring may prevent further spread."
    return "Severity is uncertain. Monitor symptoms and consider expert advice if the problem spreads."


def diagnose(answers: dict[str, Any]) -> dict[str, Any]:
    scored = [score_rule(rule, answers) for rule in load_rules()]
    scored.sort(key=lambda item: item["confidence"], reverse=True)

    top_matches = [item for item in scored if item["confidence"] > 0][:3]
    primary = top_matches[0] if top_matches else None

    if primary is None or primary["confidence"] < 35:
        decision = "Uncertain diagnosis"
        summary = "The provided symptoms are not enough for a confident rule-based diagnosis."
        recommendation = (
            "Review the plant again, answer more symptom questions if possible, isolate badly affected plants, "
            "and consult an agricultural expert if the problem is spreading."
        )
    else:
        decision = primary["name"]
        summary = primary["description"]
        recommendation = primary["recommendation"]

    return {
        "decision": decision,
        "summary": summary,
        "confidence": primary["confidence"] if primary else 0,
        "severity_note": severity_message(answers),
        "recommendation": recommendation,
        "expert_note": primary["consult_expert_when"] if primary else "Consult an expert when symptoms are severe, unclear, or spreading.",
        "top_matches": top_matches,
        "answers": answers,
    }
