from __future__ import annotations

from typing import Any

from agents.gemini_client import generate_json


def run(agent_outputs: dict[str, Any]) -> dict[str, Any]:
    result = generate_json(
        """You are the AI Disaster Commander. Synthesize evidence without overriding uncertainty.
Return confidence_score, situation_summary, rescue_strategy, emergency_response_briefing,
operational_recommendations, public_advisory, active_response_plan, and incident_status.""",
        f"Agent outputs:\n{agent_outputs}",
    )
    if result:
        result["engine"] = "Gemini"
        return result
    nlp = agent_outputs["nlp"]
    verification = agent_outputs["verification"]
    resources = agent_outputs["resource"]["allocation"]
    confidence = round(
        nlp.get("severity_score", 0) * 0.45
        + verification.get("trust_score", 0) * 0.35
        + agent_outputs["vision"].get("confidence_score", 0) * 0.2
    )
    return {
        "engine": "Deterministic fallback (Gemini unavailable)",
        "confidence_score": confidence,
        "situation_summary": f"{nlp.get('severity')} {nlp.get('disaster_type')} citizen report.",
        "rescue_strategy": "Validate scene safety, establish command, triage, rescue, and evacuate.",
        "emergency_response_briefing": f"Dispatch initial resources: {resources}. Maintain evidence verification.",
        "operational_recommendations": nlp.get("immediate_needs", []),
        "public_advisory": "Avoid the affected area and follow official emergency instructions.",
        "active_response_plan": "Initial assessment and dispatch",
        "incident_status": "Pending human command review",
    }
