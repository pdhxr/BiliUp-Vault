import os
import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from app.main import create_app


class DesktopSecurityTests(unittest.TestCase):
    def test_health_has_stable_application_identity(self) -> None:
        with patch.dict(os.environ, {"BILIUP_INSTANCE_TOKEN": ""}):
            response = TestClient(create_app()).get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"app": "biliup", "status": "ok"})

    def test_health_reports_desktop_instance_token(self) -> None:
        with patch.dict(os.environ, {"BILIUP_INSTANCE_TOKEN": "instance-123"}):
            response = TestClient(create_app()).get("/api/health")
        self.assertEqual(response.json()["instance"], "instance-123")

    def test_web_mode_does_not_expose_shutdown(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("BILIUP_DESKTOP", None)
            response = TestClient(create_app()).post("/api/desktop/shutdown")
        self.assertEqual(response.status_code, 404)

    def test_desktop_mode_requires_client_header_for_mutations(self) -> None:
        with patch.dict(os.environ, {"BILIUP_DESKTOP": "1"}):
            client = TestClient(create_app())
            missing = client.post("/api/up-search", json={"nickname": "UP"})
            wrong = client.post(
                "/api/up-search",
                json={"nickname": "UP"},
                headers={"X-BiliUp-Client": "wrong"},
            )
        self.assertEqual(missing.status_code, 403)
        self.assertEqual(wrong.status_code, 403)

    @patch("app.routes.up.search_up", return_value=[])
    def test_desktop_mode_accepts_header_and_keeps_get_readable(self, _search) -> None:
        with patch.dict(os.environ, {"BILIUP_DESKTOP": "1"}):
            client = TestClient(create_app())
            mutation = client.post(
                "/api/up-search",
                json={"nickname": "UP"},
                headers={"X-BiliUp-Client": "desktop"},
            )
            health = client.get("/api/health")
        self.assertEqual(mutation.status_code, 200)
        self.assertEqual(health.status_code, 200)

    def test_desktop_shutdown_calls_registered_callback(self) -> None:
        callback = Mock()
        with patch.dict(os.environ, {"BILIUP_DESKTOP": "1"}):
            response = TestClient(create_app(callback)).post(
                "/api/desktop/shutdown",
                headers={"X-BiliUp-Client": "desktop"},
            )
        self.assertEqual(response.status_code, 200)
        callback.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
