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

    @patch("app.routes.setup.batch_track_settings", return_value={"since_date": "2026-07-01"})
    def test_batch_track_settings_route(self, _settings) -> None:
        response = self.client.get("/api/settings/batch-track")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["since_date"], "2026-07-01")

    @patch("app.routes.setup.save_batch_track_settings", return_value={"since_date": "2026-07-01"})
    def test_update_batch_track_settings_route(self, _save) -> None:
        response = self.client.put("/api/settings/batch-track", json={"since_date": "2026-07-01"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["since_date"], "2026-07-01")
        _save.assert_called_once_with("2026-07-01")

    @patch("app.routes.setup.choose_and_configure_library", return_value=Path("/tmp/knowledge-base"))
    def test_select_library_route(self, _select) -> None:
        response = self.client.post("/api/setup/select-library")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["configured"])

    def test_dashboard_contains_all_static_tabs(self) -> None:
        response = self.client.get("/")
        html = response.text
        self.assertIn('id="setup"', html)
        self.assertIn("checkSetup();", html)
        self.assertIn('data-tab="up-management"', html)
        self.assertIn('id="btn-add"', html)
        self.assertIn('id="btn-delete"', html)
        self.assertIn('id="add-dialog"', html)
        self.assertIn('id="up-search-form"', html)
        self.assertIn('id="dialog-confirm"', html)
        self.assertIn('id="up-table"', html)
        self.assertIn('id="check-all-ups"', html)
        self.assertIn('class="col-bio">UP简介</th>', html)
        self.assertIn('class="col-tracking">自动追踪下载</th>', html)
        self.assertIn('data-tab="video-download"', html)
        self.assertIn('先在 UP 主管理页签勾选“自动追踪下载”列', html)
        self.assertIn('id="btn-refresh-videos"', html)
        self.assertIn('id="video-table"', html)
        self.assertIn('id="download-progress-panel"', html)
        self.assertIn('id="progress-list"', html)
        self.assertIn('data-tab="other"', html)
        self.assertIn('id="single-video-url"', html)
        self.assertIn('src="/static/js/up_management.js"', html)
        self.assertIn('src="/static/js/up_search.js"', html)
        self.assertIn("function switchTab", html)
        style = self.client.get("/static/css/style.css")
        self.assertEqual(style.status_code, 200)
        self.assertIn(".top-bar", style.text)
        script = self.client.get("/static/js/up_management.js")
        self.assertEqual(script.status_code, 200)
        self.assertIn("/api/followings", script.text)
        search_script = self.client.get("/static/js/up_search.js")
        self.assertEqual(search_script.status_code, 200)
        self.assertIn("/api/up-search", search_script.text)
        self.assertIn("搜索中…", search_script.text)
        management_script = self.client.get("/static/js/up_management.js")
        self.assertEqual(management_script.status_code, 200)
        self.assertIn("checkAll.indeterminate", management_script.text)
        self.assertIn("checkAll.addEventListener", management_script.text)
        self.assertIn("getSelectedIds", management_script.text)
        self.assertIn("getSelectedAutoTrackIds", management_script.text)
        self.assertIn(".tracking-checkbox:checked", management_script.text)
        self.assertIn('data-up-id="${escapeHtml(row.up_id)}"', management_script.text)
        self.assertIn("/api/followings/tracking", management_script.text)
        self.assertIn("batchSyncButton.disabled = syncing", management_script.text)
        self.assertIn("同步中…", management_script.text)
        self.assertIn("/api/followings/delete", management_script.text)
        self.assertIn("deleteButton", management_script.text)
        self.assertIn("setSyncing", management_script.text)
        video_script = self.client.get("/static/js/video_download.js")
        self.assertEqual(video_script.status_code, 200)
        self.assertIn("/api/videos/download", video_script.text)
        self.assertIn("video.transcript ? '是' : '否'", video_script.text)
        self.assertIn("正在增量同步", video_script.text)
        self.assertIn("正在追踪第", video_script.text)
        self.assertIn("下载中 ${data.download_done || 0}/${data.download_total || 0}", video_script.text)
        self.assertIn("/api/up/videos/batch-refresh", video_script.text)
        self.assertIn("/api/up/videos/batch-track-download", video_script.text)
        self.assertIn("/api/up/videos/batch-track-download-progress", video_script.text)
        self.assertIn("/api/settings/batch-track", video_script.text)
        self.assertNotIn("batchButton.disabled", video_script.text)
        progress_script = self.client.get("/static/js/download_progress.js")
        self.assertEqual(progress_script.status_code, 200)
        self.assertIn("/api/videos/download-progress", progress_script.text)

    @patch("app.routes.up.save_following_and_refresh", return_value=({"uid": "1"}, "created", {"status": "ok", "video_count": 3, "added_count": 3, "pages": 1, "message": ""}))
    def test_following_route(self, _save) -> None:
        response = self.client.post("/api/followings", json={"uid": "1", "nickname": "UP", "bio": "简介"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["action"], "created")
        self.assertEqual(response.json()["video_sync"]["video_count"], 3)

    @patch("app.routes.up.delete_followings", return_value=["1"])
    def test_delete_followings_route(self, _delete) -> None:
        response = self.client.post("/api/followings/delete", json={"up_ids": ["1"]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"deleted": ["1"], "count": 1})

    @patch("app.routes.up.list_up_management", return_value=[{"up_id": "1", "nickname": "UP", "bio": "简介"}])
    def test_followings_list_route(self, _list) -> None:
        response = self.client.get("/api/followings")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["up_id"], "1")

    @patch("app.routes.up.set_following_scheduled_tracking", return_value={"uid": "1", "scheduled_tracking": True})
    def test_following_tracking_route(self, _set_tracking) -> None:
        response = self.client.post(
            "/api/followings/tracking",
            json={"up_id": "1", "scheduled_tracking": True},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"up_id": "1", "scheduled_tracking": True})

    @patch("app.routes.videos.list_up_videos", return_value=[{"bvid": "BV1", "title": "视频"}])
    def test_video_list_route(self, _list) -> None:
        response = self.client.get("/api/up/1/videos")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["bvid"], "BV1")

    @patch("app.routes.videos.refresh_up_videos", return_value=[{"bvid": "BV1", "title": "视频"}])
    def test_video_refresh_route(self, _refresh) -> None:
        response = self.client.post("/api/up/1/videos/refresh", json={"page": 1, "limit": 50})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["title"], "视频")

    @patch("app.routes.videos.start_batch_sync", return_value={"status": "started", "total": 2})
    def test_batch_video_refresh_route(self, _start) -> None:
        response = self.client.post("/api/up/videos/batch-refresh", json={"up_ids": ["1", "2"]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 2)

    @patch("app.routes.videos.batch_sync_progress", return_value={"running": True, "done": 1, "total": 2})
    def test_batch_video_refresh_progress_route(self, _progress) -> None:
        response = self.client.get("/api/up/videos/batch-refresh-progress")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["running"])

    @patch("app.routes.videos.start_batch_track_download", return_value={"status": "started", "total": 2, "since_date": "20260701"})
    def test_batch_track_download_route(self, _start) -> None:
        response = self.client.post(
            "/api/up/videos/batch-track-download",
            json={"up_ids": ["1", "2"], "since_date": "2026-07-01"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["since_date"], "20260701")
        _start.assert_called_once_with(["1", "2"], "2026-07-01")

    @patch("app.routes.videos.batch_track_download_progress", return_value={"running": True, "phase": "tracking", "done": 1, "total": 2})
    def test_batch_track_download_progress_route(self, _progress) -> None:
        response = self.client.get("/api/up/videos/batch-track-download-progress")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["phase"], "tracking")

    @patch("app.routes.videos.queue_downloads", return_value=[{"bvid": "BV1", "status": "queued"}])
    def test_video_download_route(self, _queue) -> None:
        response = self.client.post("/api/videos/download", json={"up_id": "1", "bvids": ["BV1"]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["jobs"][0]["status"], "queued")

    @patch("app.routes.videos.progress_rows", return_value=[{"bvid": "BV1", "status": "downloading", "size_bytes": 1024}])
    def test_video_download_progress_route(self, _progress) -> None:
        response = self.client.get("/api/videos/download-progress")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["status"], "downloading")


if __name__ == "__main__":
    unittest.main()
