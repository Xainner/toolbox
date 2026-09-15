import io
import json
import tempfile
import time
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

import app.main as main


class ToolboxApiTests(unittest.TestCase):
    def setUp(self):
        root = Path(tempfile.mkdtemp(prefix="toolbox-test-"))
        main.DATA_DIR = root
        main.WORK_ROOT = root / "jobs"
        main.WORK_ROOT.mkdir()
        main.DB_PATH = root / "test.db"
        self.client = TestClient(main.app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)

    def image_bytes(self):
        output = io.BytesIO()
        Image.new("RGB", (24, 16), "coral").save(output, "PNG")
        return output.getvalue()

    def test_catalog_has_23_tools_and_extended_metadata(self):
        tools = self.client.get("/api/tools").json()["tools"]
        self.assertEqual(len(tools), 23)
        remove_bg = next(tool for tool in tools if tool["id"] == "remove-bg")
        self.assertEqual(remove_bg["ui_mode"], "mask_editor")
        self.assertTrue(remove_bg["ai"])

    def test_async_job_reaches_success_and_exposes_artifact(self):
        response = self.client.post(
            "/api/tools/convert-image/jobs",
            files={"files": ("sample.png", self.image_bytes(), "image/png")},
            data={"options": json.dumps({"format": "webp", "quality": 80})},
        )
        self.assertEqual(response.status_code, 202)
        job_id = response.json()["job_id"]
        for _ in range(40):
            job = self.client.get(f"/api/jobs/{job_id}").json()
            if job["status"] in {"succeeded", "failed"}:
                break
            time.sleep(0.05)
        self.assertEqual(job["status"], "succeeded")
        self.assertEqual(job["progress"], 100)
        self.assertEqual(job["artifacts"][0]["kind"], "result")
        self.assertEqual(self.client.get(job["artifacts"][0]["url"]).status_code, 200)

    def test_rejects_invalid_image(self):
        response = self.client.post(
            "/api/tools/convert-image/jobs",
            files={"files": ("bad.png", b"not-an-image", "image/png")},
            data={"options": "{}"},
        )
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
