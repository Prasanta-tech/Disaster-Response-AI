from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


def _load_env() -> None:
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        cleaned = line.strip()
        if not cleaned or cleaned.startswith("#") or "=" not in cleaned:
            continue
        key, value = cleaned.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


_load_env()


@dataclass(frozen=True)
class Settings:
    app_name: str = "DisasterAI Command Center"
    database_url: str = os.getenv(
        "DATABASE_URL", f"sqlite:///{(BASE_DIR / 'disasterai.db').as_posix()}"
    )
    mongo_url: str | None = os.getenv("MONGO_URL")
    mongo_database: str = os.getenv("MONGO_DATABASE", "disasterai")
    gemini_api_key: str | None = os.getenv("GEMINI_API_KEY")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    yolo_model: str = os.getenv("YOLO_MODEL", "yolo11n.pt")
    enable_yolo: bool = os.getenv("ENABLE_YOLO", "false").lower() == "true"
    satellite_provider_url: str | None = os.getenv("SATELLITE_PROVIDER_URL")
    reverse_image_api_url: str | None = os.getenv("REVERSE_IMAGE_API_URL")
    reverse_image_api_key: str | None = os.getenv("REVERSE_IMAGE_API_KEY")
    upload_dir: Path = field(default_factory=lambda: BASE_DIR / "uploads" / "images")
    static_dir: Path = field(default_factory=lambda: BASE_DIR / "static")
    max_upload_bytes: int = int(os.getenv("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))
    correlation_radius_km: float = float(os.getenv("CORRELATION_RADIUS_KM", "5"))
    correlation_window_hours: float = float(os.getenv("CORRELATION_WINDOW_HOURS", "6"))


settings = Settings()
settings.upload_dir.mkdir(parents=True, exist_ok=True)
