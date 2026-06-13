from __future__ import annotations

from collections import Counter

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from agents.resource_agent import RESOURCE_POOL
from database.db import get_incident, list_incidents, update_incident
from routes.realtime import manager


router = APIRouter(prefix="/api", tags=["Dashboard"])


class StatusUpdate(BaseModel):
    status: str


@router.get("/incidents")
def incidents() -> dict:
    return {"incidents": [item.as_dict() for item in list_incidents()], "resource_pool": RESOURCE_POOL}


@router.get("/incident/{incident_id}")
def incident_detail(incident_id: str) -> dict:
    record = get_incident(incident_id)
    if not record:
        raise HTTPException(404, "Incident not found")
    return record.as_dict()


@router.get("/dashboard/stats")
def dashboard_stats() -> dict:
    items = [item.as_dict() for item in list_incidents()]
    severities = Counter(item["ai_analysis"]["severity"] for item in items)
    return {
        "total_incidents": len(items),
        "active_incidents": sum(item["status"] not in {"Resolved", "Closed"} for item in items),
        "critical_incidents": severities["CRITICAL"],
        "severity_breakdown": severities,
        "estimated_affected_population": sum(
            item["ai_analysis"]["estimated_people"] for item in items
        ),
    }


@router.patch("/incidents/{incident_id}/status")
async def update_status(incident_id: str, payload: StatusUpdate) -> dict:
    record = get_incident(incident_id)
    if not record:
        raise HTTPException(404, "Incident not found")
    record.status = payload.status
    record = update_incident(record)
    document = record.as_dict()
    await manager.broadcast({"event": "incident.status", "incident": document})
    return {"status": "success", "incident": document}


@router.websocket("/ws/incidents")
async def incident_socket(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
