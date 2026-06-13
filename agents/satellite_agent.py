from __future__ import annotations

from typing import Any

import httpx

from agents.gemini_client import generate_json
from config import settings


LARGE_SCALE_TYPES = {"flood", "cyclone", "wildfire", "landslide", "earthquake"}


def should_run(disaster_type: str) -> bool:
    lowered = disaster_type.lower()
    return any(item in lowered for item in LARGE_SCALE_TYPES)


def run(incident: dict[str, Any], nlp: dict[str, Any]) -> dict[str, Any]:
    if not should_run(nlp.get("disaster_type", "")):
        return {"status": "not_required", "satellite_confidence_score": 0}
    if not settings.satellite_provider_url:
        return {
            "status": "provider_not_configured",
            "providers": ["Sentinel-2", "NASA", "ISRO Bhuvan"],
            "satellite_confidence_score": 0,
            "note": "Set SATELLITE_PROVIDER_URL to a licensed imagery adapter.",
        }
    try:
        response = httpx.get(
            settings.satellite_provider_url,
            params={
                "lat": incident["latitude"],
                "lon": incident["longitude"],
                "timestamp": incident["reported_at"],
                "disaster_type": nlp["disaster_type"],
            },
            timeout=30,
        )
        response.raise_for_status()
        provider_evidence = response.json()
        reasoning = generate_json(
            "You are a satellite disaster validation agent.",
            f"""Analyze this provider evidence for disaster extent and confidence:
{provider_evidence}
Return JSON with confirmed, affected_area_km2, observed_changes,
satellite_confidence_score (0-100), limitations.""",
        )
        return {
            "status": "completed",
            "provider_evidence": provider_evidence,
            "engine": "Gemini" if reasoning else "Provider evidence only",
            **(reasoning or {"satellite_confidence_score": 0}),
        }
    except Exception as exc:
        return {"status": "failed", "satellite_confidence_score": 0, "error": str(exc)}
