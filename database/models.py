from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Float, JSON, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class IncidentRecord(Base):
    __tablename__ = "incidents"

    incident_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    master_incident_id: Mapped[str | None] = mapped_column(String(40), index=True)
    raw_text: Mapped[str] = mapped_column(Text)
    image_path: Mapped[str | None] = mapped_column(Text)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    accuracy_meters: Mapped[float] = mapped_column(Float, default=0)
    location_source: Mapped[str] = mapped_column(String(40), default="manual")
    reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    status: Mapped[str] = mapped_column(String(40), default="Analyzing")
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    agent_outputs: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    commander_decision: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    def as_dict(self) -> dict[str, Any]:
        outputs = self.agent_outputs or {}
        commander = self.commander_decision or {}
        nlp = outputs.get("nlp", {})
        resource = outputs.get("resource", {})
        media = self.raw_payload.get("media")
        if self.image_path:
            media = {
                **(media or {}),
                "url": f"/uploads/images/{self.image_path.rsplit('/', 1)[-1]}",
            }
        return {
            "incident_id": self.incident_id,
            "master_incident_id": self.master_incident_id,
            "location": {
                "latitude": self.latitude,
                "longitude": self.longitude,
                "accuracy_meters": self.accuracy_meters,
                "source": self.location_source,
            },
            "raw_text": self.raw_text,
            "media_attached": bool(self.image_path or media),
            "media": media,
            "timestamp": self.reported_at.isoformat(),
            "received_at": self.received_at.isoformat(),
            "status": self.status,
            "agent_outputs": outputs,
            "commander_decision": commander,
            # Compatibility fields consumed by the existing dashboard.
            "ai_analysis": {
                "disaster_type": nlp.get("disaster_type", "Unknown"),
                "severity": nlp.get("severity", "UNKNOWN"),
                "severity_score": nlp.get("severity_score", 0),
                "estimated_people": outputs.get("vision", {}).get(
                    "affected_population_estimate", nlp.get("affected_population", 0)
                ),
                "immediate_needs": nlp.get("immediate_needs", []),
                "engine": nlp.get("engine", "Gemini unavailable"),
            },
            "allocation": resource.get("allocation", {}),
            "briefing": commander.get("emergency_response_briefing", ""),
            "summary": {
                "headline": commander.get("situation_summary", ""),
                "people": outputs.get("vision", {}).get(
                    "affected_population_estimate", nlp.get("affected_population", 0)
                ),
                "needs": nlp.get("immediate_needs", []),
                "media_status": "Evidence received" if self.image_path or media else "No media evidence",
            },
            "notifications": resource.get("notification_plan", []),
        }
