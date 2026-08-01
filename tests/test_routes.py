import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import create_app


class RouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(create_app())

    @patch("app.routes.up.search_up", return_value=[{"uid": "1", "nickname": "UP", "bio": "简介"}])
    def test_search_route(self, _search) -> None:
        response = self.client.post("/api/up-search", json={"nickname": "UP"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["uid"], "1")

    @patch("app.routes.up.opencli_status", return_value={"installed": False, "ready": False, "message": "未安装"})
    def test_runtime_status_route(self, _status) -> None:
        response = self.client.get("/api/runtime-status")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["ready"])

    @patch("app.routes.up.save_following", return_value=({"uid": "1"}, "created"))
    def test_following_route(self, _save) -> None:
        response = self.client.post("/api/followings", json={"uid": "1", "nickname": "UP", "bio": "简介"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["action"], "created")


if __name__ == "__main__":
    unittest.main()
