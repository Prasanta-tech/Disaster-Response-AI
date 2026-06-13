from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from pymongo import MongoClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from config import settings
from database.models import Base, IncidentRecord


engine_options = {"pool_pre_ping": True}
if settings.database_url.startswith("sqlite"):
    engine_options["connect_args"] = {"check_same_thread": False}
    if settings.database_url.endswith(":memory:"):
        engine_options["poolclass"] = StaticPool

engine = create_engine(settings.database_url, **engine_options)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db() -> None:
    Base.metadata.create_all(engine)


@contextmanager
def db_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def save_incident(record: IncidentRecord) -> IncidentRecord:
    with db_session() as session:
        session.add(record)
        session.flush()
        session.refresh(record)
        return record


def update_incident(record: IncidentRecord) -> IncidentRecord:
    with db_session() as session:
        merged = session.merge(record)
        session.flush()
        session.refresh(merged)
        return merged


def get_incident(incident_id: str) -> IncidentRecord | None:
    with db_session() as session:
        return session.get(IncidentRecord, incident_id)


def list_incidents(limit: int = 250) -> list[IncidentRecord]:
    with db_session() as session:
        statement = select(IncidentRecord).order_by(IncidentRecord.received_at.desc()).limit(limit)
        return list(session.scalars(statement))


def mirror_to_mongo(document: dict) -> None:
    if not settings.mongo_url:
        return
    client = MongoClient(settings.mongo_url, serverSelectionTimeoutMS=1500)
    try:
        client[settings.mongo_database]["incident_audit"].replace_one(
            {"incident_id": document["incident_id"]}, document, upsert=True
        )
    finally:
        client.close()
