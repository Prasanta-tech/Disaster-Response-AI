from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from PIL import Image, ExifTags
import imagehash

from config import settings


def _metadata(path: str) -> dict[str, Any]:
    try:
        with Image.open(path) as image:
            exif = {
                ExifTags.TAGS.get(key, str(key)): value
                for key, value in image.getexif().items()
            }
        return {
            "present": bool(exif),
            "captured_at": str(exif.get("DateTimeOriginal") or exif.get("DateTime") or ""),
            "gps_present": bool(exif.get("GPSInfo")),
            "software": str(exif.get("Software") or ""),
        }
    except Exception as exc:
        return {"present": False, "error": str(exc)}


def _reverse_search(path: str) -> dict[str, Any]:
    if not settings.reverse_image_api_url:
        return {"status": "not_configured", "matches": []}
    headers = {"Authorization": f"Bearer {settings.reverse_image_api_key}"} if settings.reverse_image_api_key else {}
    try:
        with open(path, "rb") as image_file:
            response = httpx.post(
                settings.reverse_image_api_url,
                files={"image": image_file},
                headers=headers,
                timeout=20,
            )
        response.raise_for_status()
        return {"status": "completed", **response.json()}
    except Exception as exc:
        return {"status": "failed", "matches": [], "error": str(exc)}


def run(incident: dict[str, Any]) -> dict[str, Any]:
    path = incident.get("image_path")
    if not path or not Path(path).exists():
        return {
            "status": "not_run",
            "trust_score": 35,
            "authenticity_score": 0,
            "reason": "No image supplied; report remains unverified.",
        }
    metadata = _metadata(path)
    reverse = _reverse_search(path)
    try:
        with Image.open(path) as image:
            perceptual_hash = str(imagehash.phash(image))
    except Exception as exc:
        return {
            "status": "failed",
            "metadata_checks": metadata,
            "reverse_image_search": reverse,
            "trust_score": 10,
            "authenticity_score": 0,
            "reason": f"Image could not be decoded: {exc}",
        }
    score = 50
    if metadata.get("present"):
        score += 10
    if metadata.get("gps_present"):
        score += 15
    software = metadata.get("software", "").lower()
    ai_hint = any(word in software for word in ("stable diffusion", "midjourney", "dall-e"))
    if ai_hint:
        score -= 35
    if reverse.get("matches"):
        score -= 20
    score = max(0, min(100, score))
    return {
        "status": "completed",
        "metadata_checks": metadata,
        "report_gps_present": bool(incident.get("latitude") is not None),
        "report_timestamp_valid": bool(incident.get("reported_at")),
        "ai_generated_detection": {
            "status": "heuristic_only",
            "suspected": ai_hint,
            "note": "Configure a forensic model for production-grade synthetic image detection.",
        },
        "reverse_image_search": reverse,
        "perceptual_hash": perceptual_hash,
        "trust_score": score,
        "authenticity_score": score,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
