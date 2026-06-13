from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from agents.orchestrator import run as run_orchestrator
from config import settings
from database.db import list_incidents, mirror_to_mongo, save_incident, update_incident
from database.models import IncidentRecord
from routes.realtime import manager


router = APIRouter(prefix="/api", tags=["SOS"])


class SOSPayload(BaseModel):
    incident_id: str | None = None
    location: dict[str, Any] = Field(default_factory=dict)
    raw_text: str
    media_attached: bool = False
    media: dict[str, Any] | None = None
    timestamp: str | None = None


def _parse_timestamp(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _save_data_url(media: dict[str, Any] | None, incident_id: str) -> tuple[str | None, str | None]:
    if not media or not media.get("data_url"):
        return None, None
    header, encoded = media["data_url"].split(",", 1)
    mime_type = media.get("type") or header.split(";")[0].replace("data:", "")
    if not mime_type.startswith("image/"):
        return None, mime_type
    suffix = Path(media.get("name", "image.jpg")).suffix or ".jpg"
    path = settings.upload_dir / f"{incident_id}{suffix.lower()}"
    data = base64.b64decode(encoded, validate=True)
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(413, "Image exceeds upload limit")
    path.write_bytes(data)
    return str(path), mime_type


async def _process(payload: SOSPayload, image_path: str | None, media_type: str | None) -> dict:
    text = payload.raw_text.strip()
    if not text:
        raise HTTPException(400, "SOS message cannot be empty")
    incident_id = payload.incident_id or f"INC-{datetime.now():%Y%m%d}-{uuid4().hex[:8].upper()}"
    location = payload.location
    reported_at = _parse_timestamp(payload.timestamp).astimezone(timezone.utc)
    media_metadata = None
    if payload.media:
        media_metadata = {
            key: value for key, value in payload.media.items() if key != "data_url"
        }
    record = IncidentRecord(
        incident_id=incident_id,
        raw_text=text,
        image_path=image_path,
        latitude=float(location.get("latitude", 0)),
        longitude=float(location.get("longitude", 0)),
        accuracy_meters=float(location.get("accuracy_meters", 0) or 0),
        location_source=str(location.get("source", "manual")),
        reported_at=reported_at,
        status="Analyzing",
        raw_payload=payload.model_dump(exclude={"media"}) | {"media": media_metadata},
    )
    save_incident(record)
    candidates = [item.as_dict() for item in list_incidents() if item.incident_id != incident_id]
    orchestration_input = {
        "incident_id": incident_id,
        "raw_text": text,
        "image_path": image_path,
        "media_type": media_type,
        "latitude": record.latitude,
        "longitude": record.longitude,
        "reported_at": reported_at.isoformat(),
    }
    result = await run_orchestrator(orchestration_input, candidates)
    record.agent_outputs = result["agent_outputs"]
    record.commander_decision = result["commander_decision"]
    record.master_incident_id = result["agent_outputs"]["correlation"]["master_incident_id"]
    record.status = result["commander_decision"].get("incident_status", "Pending Review")
    record = update_incident(record)
    document = record.as_dict()
    try:
        mirror_to_mongo(document)
    except Exception:
        pass
    await manager.broadcast({"event": "incident.updated", "incident": document})
    return {"status": "success", "incident": document}


@router.post("/sos-alert")
async def receive_json_sos(payload: SOSPayload) -> dict:
    incident_id = f"INC-{datetime.now():%Y%m%d}-{uuid4().hex[:8].upper()}"
    payload = payload.model_copy(update={"incident_id": incident_id})
    image_path, media_type = _save_data_url(payload.media, incident_id)
    return await _process(payload, image_path, media_type)


@router.post("/sos")
async def receive_multipart_sos(
    raw_text: str = Form(...),
    latitude: float = Form(...),
    longitude: float = Form(...),
    timestamp: str | None = Form(None),
    accuracy_meters: float = Form(0),
    image: UploadFile | None = File(None),
) -> dict:
    incident_id = f"INC-{datetime.now():%Y%m%d}-{uuid4().hex[:8].upper()}"
    image_path = None
    media = None
    media_type = None
    if image:
        if not (image.content_type or "").startswith("image/"):
            raise HTTPException(415, "Only image evidence is supported by the intelligence pipeline")
        data = await image.read(settings.max_upload_bytes + 1)
        if len(data) > settings.max_upload_bytes:
            raise HTTPException(413, "Image exceeds upload limit")
        suffix = Path(image.filename or "evidence.jpg").suffix or ".jpg"
        path = settings.upload_dir / f"{incident_id}{suffix.lower()}"
        path.write_bytes(data)
        image_path = str(path)
        media_type = image.content_type
        media = {"name": image.filename, "type": image.content_type, "size": len(data)}
    payload = SOSPayload(
        incident_id=incident_id,
        raw_text=raw_text,
        location={
            "latitude": latitude,
            "longitude": longitude,
            "accuracy_meters": accuracy_meters,
            "source": "multipart",
        },
        timestamp=timestamp,
        media_attached=bool(image),
        media=media,
    )
    return await _process(payload, image_path, media_type)
