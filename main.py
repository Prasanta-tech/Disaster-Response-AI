from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from agents.gemini_client import available as gemini_available
from config import settings
from database.db import init_db
from routes.dashboard_routes import router as dashboard_router
from routes.sos_routes import router as sos_router



@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title=settings.app_name, version="2.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=settings.static_dir), name="static")
app.mount("/uploads/images", StaticFiles(directory=settings.upload_dir), name="uploads")
app.include_router(sos_router)
app.include_router(dashboard_router)


@app.get("/")
@app.get("/sos")
def sos_page() -> FileResponse:
    return FileResponse(settings.static_dir / "index.html")


@app.get("/dashboard")
@app.get("/rescue-dashboard")
def dashboard_page() -> FileResponse:
    return FileResponse(settings.static_dir / "dashboard.html")


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "online",
        "service": settings.app_name,
        "gemini_configured": gemini_available(),
        "yolo_enabled": settings.enable_yolo,
        "satellite_provider_configured": bool(settings.satellite_provider_url),
        "database": settings.database_url.split(":", 1)[0],
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)
