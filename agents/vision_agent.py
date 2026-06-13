from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from agents.gemini_client import generate_json
from config import settings


TARGET_LABELS = {
    "person", "car", "truck", "bus", "motorcycle", "boat", "traffic light", "fire hydrant"
}


def _yolo_detections(image_path: str) -> tuple[list[dict[str, Any]], str | None]:
    if not settings.enable_yolo:
        return [], "YOLO disabled; set ENABLE_YOLO=true to load the configured model."
    try:
        from ultralytics import YOLO

        model = YOLO(settings.yolo_model)
        result = model.predict(image_path, verbose=False)[0]
        detections = []
        for box in result.boxes:
            label = result.names[int(box.cls[0])]
            if label in TARGET_LABELS:
                detections.append({
                    "label": label,
                    "confidence": round(float(box.conf[0]), 4),
                    "bbox": [round(float(value), 2) for value in box.xyxy[0].tolist()],
                })
        return detections, None
    except Exception as exc:
        return [], f"YOLO unavailable: {exc}"


def run(incident: dict[str, Any]) -> dict[str, Any]:
    image_path = incident.get("image_path")
    if not image_path or not Path(image_path).exists():
        return {
            "status": "not_run",
            "detections": [],
            "damage_assessment": "No image supplied.",
            "affected_population_estimate": 0,
            "confidence_score": 0,
        }
    detections, warning = _yolo_detections(image_path)
    counts = Counter(item["label"] for item in detections)
    image_bytes = Path(image_path).read_bytes()
    prompt = f"""Assess this disaster image. YOLO evidence (standard object classes only):
{dict(counts)}. Return JSON with visual_indicators, damage_assessment,
infrastructure_impact, affected_population_estimate, confidence_score (0-100),
limitations, and evidence_consistency. Treat YOLO as evidence, not final judgment."""
    result = generate_json(
        "You are a disaster vision reasoning agent. Be conservative and evidence-grounded.",
        prompt,
        image_bytes,
        incident.get("media_type", "image/jpeg"),
    )
    if result:
        return {
            "status": "completed",
            "engine": "Gemini vision reasoning with YOLO evidence",
            "detections": detections,
            "yolo_warning": warning,
            **result,
        }
    return {
        "status": "degraded",
        "engine": "YOLO evidence only (Gemini unavailable)",
        "detections": detections,
        "yolo_warning": warning,
        "visual_indicators": list(counts),
        "damage_assessment": "Automated damage reasoning unavailable.",
        "infrastructure_impact": "Unknown",
        "affected_population_estimate": counts.get("person", 0),
        "confidence_score": 20 if detections else 0,
        "limitations": ["Gemini vision reasoning unavailable"],
    }
