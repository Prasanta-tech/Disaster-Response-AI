from __future__ import annotations

from typing import Any

from agents.gemini_client import generate_json


RESOURCE_POOL = {
    "ambulances": 32,
    "rescue_teams": 80,
    "medical_units": 40,
    "fire_units": 24,
    "heavy_equipment": 18,
    "boats": 30,
    "shelter_beds": 1800,
    "food_kits": 9000,
}


def _fallback(nlp: dict[str, Any], vision: dict[str, Any]) -> dict[str, Any]:
    people = max(
        int(nlp.get("affected_population", 0) or 0),
        int(vision.get("affected_population_estimate", 0) or 0),
    )
    severity = int(nlp.get("severity_score", 40) or 40)
    factor = 1.5 if severity >= 80 else 1 if severity >= 60 else 0.6
    needs = " ".join(nlp.get("immediate_needs", [])).lower()
    allocation = {
        "ambulances": max(1, round(max(people, 10) / 100 * factor)),
        "rescue_teams": max(1, round(max(people, 10) / 80 * factor)),
        "medical_units": max(1, round(max(people, 10) / 150 * factor)),
        "fire_units": 3 if "fire" in needs else 0,
        "heavy_equipment": 2 if any(word in needs for word in ("debris", "equipment")) else 0,
        "boats": 4 if any(word in needs for word in ("boat", "flood", "evacuation")) else 0,
        "shelter_beds": round(people * 0.4),
        "food_kits": max(25, people),
    }
    allocation = {key: min(RESOURCE_POOL[key], value) for key, value in allocation.items()}
    return {
        "engine": "Deterministic fallback (Gemini unavailable)",
        "allocation": allocation,
        "operational_priority": nlp.get("severity", "MEDIUM"),
        "recommendations": nlp.get("immediate_needs", []),
        "notification_plan": [],
    }


def run(agent_outputs: dict[str, Any]) -> dict[str, Any]:
    result = generate_json(
        "You are a disaster resource planning agent. Gemini is the primary planner.",
        f"""Evidence and analysis: {agent_outputs}
Available resource pool: {RESOURCE_POOL}
Return JSON with allocation using exactly the pool keys, operational_priority,
staging_plan, recommendations, constraints, and notification_plan. Never exceed the pool.""",
    )
    if not result:
        return _fallback(agent_outputs["nlp"], agent_outputs["vision"])
    allocation = result.get("allocation", {})
    result["allocation"] = {
        key: max(0, min(limit, int(allocation.get(key, 0) or 0)))
        for key, limit in RESOURCE_POOL.items()
    }
    result["engine"] = "Gemini"
    return result
