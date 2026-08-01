import unittest
from pathlib import Path
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

    @patch("app.routes.setup.setup_status", return_value={"configured": False, "message": "请先选择目录"})
    def test_setup_status_route(self, _status) -> None:
        response = self.client.get("/api/setup-status")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["configured"])

    @patch("app.routes.setup.choose_and_configure_library", return_value=Path("/tmp/knowledge-base"))
    def test_select_library_route(self, _select) -> None:
        response = self.client.post("/api/setup/select-library")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["configured"])

    def test_dashboard_places_save_before_scrollable_results(self) -> None:
        response = self.client.get("/")
        html = response.text
        self.assertLess(html.index('id="save"'), html.index('id="results"'))
        self.assertIn("#results { max-height: 330px; overflow-y: auto;", html)
        self.assertIn("search.textContent = searching ? '搜索中…' : '搜索';", html)
        self.assertIn("search.onclick = runSearch;", html)
        self.assertNotIn("query.addEventListener('input'", html)
        self.assertIn('id="setup"', html)
        self.assertIn("checkSetup();", html)

    @patch("app.routes.up.save_following", return_value=({"uid": "1"}, "created"))
    def test_following_route(self, _save) -> None:
        response = self.client.post("/api/followings", json={"uid": "1", "nickname": "UP", "bio": "简介"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["action"], "created")


if __name__ == "__main__":
    unittest.main()
