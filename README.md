# DisasterAI Command Center

GenAI-centric multi-agent disaster intelligence platform built with FastAPI,
Gemini, YOLO evidence, SQL persistence, optional MongoDB audit mirroring, and a
real-time WebSocket dashboard.

## Pipeline

```text
Citizen SOS
  -> Orchestrator
  -> NLP + Vision + Verification (parallel)
  -> Correlation
  -> Satellite validation (large-scale disasters)
  -> Resource Planning
  -> AI Disaster Commander
  -> PostgreSQL/SQLite + optional MongoDB audit
  -> REST API + WebSocket dashboard
```

Gemini is the primary reasoning engine. YOLO, metadata checks, reverse-image
search, and satellite providers supply evidence. When Gemini or an evidence
provider is unavailable, outputs are explicitly marked as degraded or not
configured; the application does not fabricate confirmation.

## Project Structure

- `main.py`: FastAPI entry point
- `routes/sos_routes.py`: JSON and multipart SOS ingestion
- `routes/dashboard_routes.py`: incident, stats, status, and WebSocket APIs
- `agents/`: orchestrator and specialist agents
- `database/models.py`: SQLAlchemy incident model
- `database/db.py`: PostgreSQL/SQLite storage and MongoDB audit mirror
- `uploads/images/`: uploaded image evidence
- `static/`: completed Citizen SOS and command dashboard UI
- `config.py`: environment-driven settings

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

Open `http://127.0.0.1:8000/sos` and
`http://127.0.0.1:8000/rescue-dashboard`.

## Configuration

Create `.env` in the project root:

```env
GEMINI_API_KEY=your_key
GEMINI_MODEL=gemini-2.5-flash

# Production PostgreSQL; SQLite is the zero-config development fallback.
DATABASE_URL=postgresql+psycopg://user:password@localhost/disasterai

# Optional immutable/audit-style document mirror.
MONGO_URL=mongodb://localhost:27017
MONGO_DATABASE=disasterai

# YOLO downloads/loads the configured weights only when explicitly enabled.
ENABLE_YOLO=true
YOLO_MODEL=yolo11n.pt

# Adapter endpoints owned/configured by the deployment.
REVERSE_IMAGE_API_URL=https://provider.example/reverse-image
REVERSE_IMAGE_API_KEY=your_key
SATELLITE_PROVIDER_URL=https://provider.example/satellite-evidence
```

The satellite adapter should normalize licensed Sentinel-2, NASA, or ISRO
Bhuvan evidence into JSON. This avoids embedding provider-specific credentials
and licensing assumptions in the command system.

## API

- `POST /api/sos-alert`: backward-compatible JSON SOS payload
- `POST /api/sos`: multipart text, image, GPS, and timestamp
- `GET /api/incidents`
- `GET /api/incident/{incident_id}`
- `GET /api/dashboard/stats`
- `PATCH /api/incidents/{incident_id}/status`
- `WS /api/ws/incidents`
- `GET /api/health`

All AI outputs are recommendations for human incident commanders, not
authorization for autonomous emergency dispatch.
