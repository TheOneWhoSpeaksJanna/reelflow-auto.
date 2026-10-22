"""Run with: python -m unittest discover -s tests -v"""
import os
import tempfile
import unittest

tmp = tempfile.TemporaryDirectory()
os.environ["DATABASE_PATH"] = tmp.name + "/queue.sqlite3"
os.environ["DISABLE_WORKER"] = "1"
os.environ["APP_PASSWORD"] = "test-password"
os.environ["SECRET_KEY"] = "unit-test-secret"
os.environ["COOKIE_SECURE"] = "0"
from app import app


class ReelFlowTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def login(self):
        result = self.client.post("/login", data={"password": "test-password"})
        self.assertEqual(result.status_code, 302)
        with self.client.session_transaction() as sess:
            return sess["csrf"]

    def test_unauthorized(self):
        self.assertEqual(self.client.get("/api/state").status_code, 401)

    def test_health(self):
        self.assertEqual(self.client.get("/healthz").json["status"], "ok")

    def test_import_and_duplicates(self):
        csrf = self.login()
        body = {"links": "https://example.com/owned-video.mp4", "rights": True}
        headers = {"X-CSRF-Token": csrf}
        first = self.client.post("/api/import", json=body, headers=headers)
        self.assertTrue(first.json["ok"])
        second = self.client.post("/api/import", json=body, headers=headers)
        self.assertEqual(second.json["added"], 0)
        state = self.client.get("/api/state").json
        self.assertGreaterEqual(state["counts"].get("pending", 0), 1)

    def test_cannot_import_without_rights(self):
        csrf = self.login()
        result = self.client.post("/api/import", json={
            "links": "https://example.com/video.mp4", "rights": False},
            headers={"X-CSRF-Token": csrf})
        self.assertEqual(result.status_code, 400)

    def test_youtube_requires_media(self):
        csrf = self.login()
        result = self.client.post("/api/import", json={
            "links": "https://www.youtube.com/watch?v=abc123def45",
            "rights": True}, headers={"X-CSRF-Token": csrf})
        self.assertEqual(result.json["requires_media"], 1)

    def test_csrf(self):
        self.login()
        result = self.client.post("/api/control", json={"action": "pause"})
        self.assertEqual(result.status_code, 403)


if __name__ == "__main__":
    unittest.main()
