"""Backward-compatible launcher. The FastAPI application now lives in main.py."""

from main import app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000)
