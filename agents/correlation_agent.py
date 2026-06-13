from __future__ import annotations

import math
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any
from uuid import uuid4

from agents.gemini_client import generate_json
from config import settings


def _distance_km(a_lat: float, a_lon: float, b_lat: float, b_lon: float) -> float:
    radius = 6371.0
    dlat = math.radians(b_lat - a_lat)
    dlon = math.radians(b_lon - a_lon)
    value = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(a_lat))
        * math.cos(math.radians(b_lat))
        * math.sin(dlon / 2) ** 2
    )
    return radius * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))


def _as_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def run(incident: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    evidence = []
    incident_time = _as_utc(incident["reported_at"])
    for candidate in candidates:
        candidate_time = _as_utc(candidate["timestamp"])
        distance = _distance_km(
            incident["latitude"], incident["longitude"],
            candidate["location"]["latitude"], candidate["location"]["longitude"],
        )
        hours = abs((incident_time - candidate_time).total_seconds()) / 3600
        text_similarity = SequenceMatcher(
            None, incident["raw_text"].lower(), candidate["raw_text"].lower()
        ).ratio()
        image_similarity = 0.0
        current_hash = incident.get("verification", {}).get("perceptual_hash")
        prior_hash = candidate.get("agent_outputs", {}).get("verification", {}).get("perceptual_hash")
        if current_hash and prior_hash:
            image_similarity = 1 - sum(a != b for a, b in zip(current_hash, prior_hash)) / len(current_hash)
        if distance <= settings.correlation_radius_km and hours <= settings.correlation_window_hours:
            location_similarity = max(0.0, 1 - distance / settings.correlation_radius_km)
            time_similarity = max(0.0, 1 - hours / settings.correlation_window_hours)
            combined_score = (
                text_similarity * 0.4
                + image_similarity * 0.15
                + location_similarity * 0.3
                + time_similarity * 0.15
            )
            evidence.append({
                "incident_id": candidate["incident_id"],
                "master_incident_id": candidate.get("master_incident_id"),
                "distance_km": round(distance, 3),
                "time_difference_hours": round(hours, 2),
                "text_similarity": round(text_similarity, 3),
                "image_similarity": round(image_similarity, 3),
                "location_similarity": round(location_similarity, 3),
                "time_similarity": round(time_similarity, 3),
                "combined_score": round(combined_score, 3),
            })
    gemini_result = generate_json(
        "You are an incident correlation agent. Decide duplicates conservatively from supplied evidence.",
        f"""New report: {incident['raw_text']}
Candidate evidence: {evidence}
Return JSON: duplicate (boolean), matched_incident_id, confidence_score, rationale.""",
    )
    if gemini_result:
        duplicate = bool(gemini_result.get("duplicate"))
        match = next(
            (item for item in candidates if item["incident_id"] == gemini_result.get("matched_incident_id")),
            None,
        )
        master_id = (
            (match.get("master_incident_id") or match["incident_id"]) if duplicate and match
            else f"MASTER-{uuid4().hex[:10].upper()}"
        )
        return {"engine": "Gemini", "master_incident_id": master_id, "candidates": evidence, **gemini_result}
    best = max(
        evidence,
        key=lambda item: item["combined_score"],
        default=None,
    )
    duplicate = bool(
        best
        and (
            best["combined_score"] >= 0.64
            or best["text_similarity"] >= 0.82
            or best["image_similarity"] >= 0.9
        )
    )
    match = next((item for item in candidates if best and item["incident_id"] == best["incident_id"]), None)
    master_id = (
        (match.get("master_incident_id") or match["incident_id"]) if duplicate and match
        else f"MASTER-{uuid4().hex[:10].upper()}"
    )
    return {
        "engine": "Deterministic fallback (Gemini unavailable)",
        "duplicate": duplicate,
        "matched_incident_id": best["incident_id"] if duplicate else None,
        "master_incident_id": master_id,
        "confidence_score": round(best["combined_score"] * 100 if best else 0, 1),
        "candidates": evidence,
    }
