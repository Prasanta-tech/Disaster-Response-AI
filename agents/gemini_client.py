from __future__ import annotations

import json
from typing import Any

from config import settings

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None


def available() -> bool:
    return bool(settings.gemini_api_key and genai)


def generate_json(
    system_instruction: str,
    prompt: str,
    image_bytes: bytes | None = None,
    mime_type: str = "image/jpeg",
) -> dict[str, Any] | None:
    if not available():
        return None
    try:
        client = genai.Client(api_key=settings.gemini_api_key)
        contents: list[Any] = [prompt]
        if image_bytes and types:
            contents.append(types.Part.from_bytes(data=image_bytes, mime_type=mime_type))
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                temperature=0.2,
            ),
        )
        return json.loads(response.text)
    except Exception:
        return None
