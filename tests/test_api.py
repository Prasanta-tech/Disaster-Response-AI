from __future__ import annotations

import io
import os
import unittest
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["ENABLE_YOLO"] = "false"

from fastapi.testclient import TestClient
from PIL import Image

from main import app


class DisasterAITestCase(unittest.TestCase):
    def test_complete_incident_flow(self) -> None:
        image_buffer = io.BytesIO()
        Image.new("RGB", (64, 64), "gray").save(image_buffer, format="JPEG")
        created_file: Path | None = None

        try:
            with TestClient(app) as client:
                self.assertEqual(client.get("/api/health").status_code, 200)
                first_response = client.post(
                    "/api/sos",
                    data={
                        "raw_text": "Earthquake damaged buildings and trapped 30 people",
                        "latitude": "20.1",
                        "longitude": "85.1",
                        "timestamp": "2026-06-13T01:00:00+05:30",
                    },
                    files={
                        "image": ("evidence.jpg", image_buffer.getvalue(), "image/jpeg")
                    },
                )
                self.assertEqual(first_response.status_code, 200)
                first = first_response.json()["incident"]
                created_file = Path("uploads/images") / Path(first["media"]["url"]).name

                second_response = client.post(
                    "/api/sos-alert",
                    json={
                        "incident_id": "CLIENT-ID-MUST-BE-IGNORED",
                        "raw_text": (
                            "Building damage after earthquake, around 30 trapped people"
                        ),
                        "location": {
                            "latitude": 20.1005,
                            "longitude": 85.1005,
                        },
                        "timestamp": "2026-06-13T01:10:00+05:30",
                    },
                )
                self.assertEqual(second_response.status_code, 200)
                second = second_response.json()["incident"]

                self.assertTrue(second["incident_id"].startswith("INC-"))
                self.assertNotEqual(
                    second["incident_id"], "CLIENT-ID-MUST-BE-IGNORED"
                )
                self.assertTrue(
                    first["agent_outputs"]["verification"]["perceptual_hash"]
                )
                self.assertTrue(
                    second["agent_outputs"]["correlation"]["duplicate"]
                )
                self.assertEqual(
                    second["master_incident_id"], first["master_incident_id"]
                )
                self.assertEqual(
                    client.get("/api/dashboard/stats").json()["total_incidents"], 2
                )
                status_response = client.patch(
                    f"/api/incidents/{first['incident_id']}/status",
                    json={"status": "Dispatched"},
                )
                self.assertEqual(status_response.status_code, 200)
        finally:
            if created_file and created_file.exists():
                created_file.unlink()


if __name__ == "__main__":
    unittest.main()
