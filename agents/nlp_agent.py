from __future__ import annotations

import re
from typing import Any

from agents.gemini_client import generate_json


SYSTEM = """You are the NLP evidence interpretation agent in a disaster command system.
Extract only defensible facts from the citizen report. Return JSON with disaster_type,
severity (LOW/MEDIUM/HIGH/CRITICAL), severity_score (0-100), urgency, affected_entities,
infrastructure_impact, human_impact, affected_population, immediate_needs, and rationale.
Never claim that unprovided evidence was verified."""


def _fallback(text: str) -> dict[str, Any]:
    lowered = text.lower()
    categories = {
        "Flood": ("flood", "submerged", "water rising"),
        "Wildfire": ("wildfire", "forest fire"),
        "Fire": ("fire", "smoke", "burning"),
        "Earthquake": ("earthquake", "tremor"),
        "Landslide": ("landslide", "mudslide"),
        "Cyclone": ("cyclone", "hurricane", "storm"),
        "Structural Collapse": ("collapse", "debris", "damaged building"),
        "Medical Emergency": ("injured", "bleeding", "ambulance"),
    }
    disaster_type = "General Disaster"
    for name, words in categories.items():
        if any(word in lowered for word in words):
            disaster_type = name
            break
    numbers = [int(value) for value in re.findall(r"\b\d{1,6}\b", text)]
    people = min(max(numbers, default=0), 100000)
    critical_words = sum(
        word in lowered for word in ("trapped", "dead", "missing", "critical", "collapse")
    )
    score = min(100, 30 + critical_words * 15 + min(people // 20, 30))
    severity = "CRITICAL" if score >= 80 else "HIGH" if score >= 60 else "MEDIUM"
    needs = []
    for keyword, need in (
        ("injured", "medical aid"),
        ("trapped", "search and rescue"),
        ("fire", "fire suppression"),
        ("flood", "boats and evacuation"),
        ("food", "food"),
        ("water", "drinking water"),
        ("shelter", "temporary shelter"),
        ("debris", "heavy equipment"),
    ):
        if keyword in lowered:
            needs.append(need)
    return {
        "disaster_type": disaster_type,
        "severity": severity,
        "severity_score": score,
        "urgency": "immediate" if score >= 60 else "rapid assessment",
        "affected_entities": [],
        "infrastructure_impact": "Mentioned in report" if any(
            word in lowered for word in ("road", "bridge", "building", "power")
        ) else "Unknown",
        "human_impact": "Citizen-reported impact; unverified",
        "affected_population": people,
        "immediate_needs": needs or ["field assessment"],
        "rationale": "Deterministic degraded-mode extraction; Gemini was unavailable.",
        "engine": "Local fallback (Gemini unavailable)",
    }


def run(incident: dict[str, Any]) -> dict[str, Any]:
    result = generate_json(SYSTEM, f"Citizen report:\n{incident['raw_text']}")
    if not result:
        return _fallback(incident["raw_text"])
    result["engine"] = "Gemini"
    return result
