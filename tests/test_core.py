import json
import shutil
import subprocess
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.configuration import (
    batch_track_since_date,
    configure_knowledge_base,
    knowledge_base_root,
    set_batch_track_since_date,
)
from core.download_progress import progress_rows, set_progress
from core.download_files import fix_hevc_tag
from core.followings import save_following
from core.followings import save_following_and_refresh
from core.following_delete import delete_followings
from core.opencli_videos import DOWNLOAD_QUALITY_FALLBACKS, OpenCliVideoError, _items, download_video, fetch_user_videos, fetch_video_metadata, fetch_video_subtitles
from core.repositories.followings import list_rows, save, set_scheduled_tracking
from core.repositories.library import list_local_videos, record_download, record_other_download
from core.single_video_download import _run_job as run_single_video_job, queue_single_video_download
from core.repositories.videos import list_videos, mark_downloaded, merge_videos
from core.subtitle_download import download_subtitle, has_transcript
from core.up_search import _parse_items, search_up
from core.video_download import _download_one, queue_downloads
from core.video_batch_track_download import _run as run_batch_track_download
from core.video_batch_track_download import start_batch_track_download
from core.video_cover_backfill import backfill_covers_for_up
from core.video_reconcile import reconcile_up_videos
from core.video_sync import refresh_up_videos, refresh_up_videos_with_details
from core.utils.system.directories import choose_directory, open_directory
from core.utils.system.resources import resource_path
from core.utils.system.process import find_opencli, run_ffmpeg, run_opencli
from core.utils.system.network import ServicePortError, available_local_port, prepare_biliup_port, stop_existing_biliup_services


class CoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path("tmp/test-followings")
        shutil.rmtree(self.root, ignore_errors=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    @patch("core.video_cover_backfill.ensure_video_cover")
    def test_cover_backfill_processes_every_missing_cover_in_tracking_range(self, ensure_cover) -> None:
        library_root = self.root / "library"
        save("123", "示例 UP", "简介", library_root / "UpList")
        merge_videos(
            library_root / "UpList",
            "示例 UP",
            [
                {"bvid": "BVnew1", "title": "范围内一", "pub_time": "2026-07-20"},
                {"bvid": "BVnew2", "title": "范围内二", "pub_time": "2026-07-21"},
                {"bvid": "BVold", "title": "范围外", "pub_time": "2026-06-30"},
            ],
        )
        for bvid, title, date in (
            ("BVnew1", "范围内一", "20260720"),
            ("BVnew2", "范围内二", "20260721"),
            ("BVold", "范围外", "20260630"),
        ):
            video_path = library_root / "SortedMp4" / "示例 UP" / date[:6] / f"{title}.mp4"
            video_path.parent.mkdir(parents=True, exist_ok=True)
            video_path.write_bytes(b"video")
            record_download(
                library_root,
                "示例 UP",
                video_path,
                bvid=bvid,
                title=title,
                date=date,
                transcript=False,
                uid="123",
            )
            mark_downloaded(library_root / "UpList", "示例 UP", bvid, video_path.name)

        def create_cover(_bvid, video_path):
            video_path.with_name(f"{video_path.stem}_cover.jpg").write_bytes(b"image")
            return True

        ensure_cover.side_effect = create_cover
        progress = []
        result = backfill_covers_for_up(
            "123",
            "20260701",
            root=library_root,
            on_progress=lambda done, total, failed: progress.append((done, total, failed)),
        )

        self.assertEqual(result, {"total": 2, "succeeded": 2, "failed": 0})
        self.assertEqual(ensure_cover.call_count, 2)
        self.assertEqual(progress[-1], (2, 2, 0))
        rows = {row["bvid"]: row for row in list_videos(library_root / "UpList", "示例 UP")}
        self.assertTrue(rows["BVnew1"]["cover"])
        self.assertTrue(rows["BVnew2"]["cover"])
        self.assertFalse(rows["BVold"]["cover"])

    def test_normalizes_opencli_user_result(self) -> None:
        rows = _parse_items(json.dumps([{
            "title": "示例 UP", "author": "示例简介", "url": "https://space.bilibili.com/123456",
        }]))
        self.assertEqual(rows, [{"uid": "123456", "nickname": "示例 UP", "bio": "示例简介"}])

    @patch("core.up_search.run_opencli")
    def test_search_requests_background_opencli_browser(self, run) -> None:
        run.return_value = subprocess.CompletedProcess(
            [], 0, stdout=json.dumps([{"title": "示例 UP", "author": "简介", "url": "https://space.bilibili.com/123"}]), stderr=""
        )
        search_up("示例")
        self.assertEqual(run.call_args.args[0][-2:], ["--window", "background"])

    @patch("core.opencli_videos.run_opencli")
    def test_video_commands_request_background_opencli_browser(self, run) -> None:
        run.side_effect = [
            subprocess.CompletedProcess([], 0, stdout="[]", stderr=""),
            subprocess.CompletedProcess([], 0, stdout="status: success", stderr=""),
        ]
        fetch_user_videos("123")
        download_video("BV1abc", str(self.root / "downloads"))
        self.assertEqual(run.call_args_list[0].args[0][-2:], ["--window", "background"])
        self.assertEqual(run.call_args_list[1].args[0][-2:], ["--window", "background"])

    @patch("core.opencli_videos.run_opencli")
    def test_single_video_metadata_normalizes_field_list(self, run) -> None:
        run.return_value = subprocess.CompletedProcess(
            [], 0,
            stdout=json.dumps([
                {"field": "bvid", "value": "BV1abc234567"},
                {"field": "title", "value": "单视频"},
                {"field": "author", "value": "示例 UP (mid: 123)"},
                {"field": "publish_time", "value": "2026-07-31 04:00"},
                {"field": "thumbnail", "value": "https://i0.hdslb.com/bfs/archive/example.jpg"},
            ]),
            stderr="",
        )
        metadata = fetch_video_metadata("BV1abc234567")
        self.assertEqual(metadata["nickname"], "示例 UP")
        self.assertEqual(metadata["publish_time"], "2026-07-31 04:00")
        self.assertEqual(metadata["thumbnail"], "https://i0.hdslb.com/bfs/archive/example.jpg")
        self.assertEqual(run.call_args.args[0][-2:], ["--window", "background"])

    @patch("core.opencli_videos.run_opencli")
    def test_single_video_metadata_reports_invalid_bvid_case(self, run) -> None:
        run.return_value = subprocess.CompletedProcess(
            [], 1, stdout="", stderr="error:\n  code: COMMAND_EXEC\n  message: 'Bilibili view API failed: 啥都木有 (-404)'",
        )

        with self.assertRaisesRegex(OpenCliVideoError, "检查 BV 号及大小写"):
            fetch_video_metadata("BV1CBuQ6rEhQ")

    def test_other_video_record_uses_dedicated_index(self) -> None:
        library_root = self.root / "library"
        video = library_root / "OtherVideos/示例 UP_20260731_单视频.mp4"
        video.parent.mkdir(parents=True, exist_ok=True)
        video.write_bytes(b"video")
        record_other_download(
            library_root,
            video,
            bvid="BV1abc234567",
            title="单视频",
            date="20260731",
            transcript=False,
        )
        self.assertTrue((library_root / "OtherVideos/videos.jsonl").is_file())
        self.assertEqual(
            json.loads((library_root / "OtherVideos/videos.jsonl").read_text(encoding="utf-8"))["bvid"],
            "BV1abc234567",
        )

    @patch("core.single_video_download._executor.submit")
    @patch("core.single_video_download.fetch_video_metadata", return_value={
        "bvid": "BV1abc234567",
        "title": "单视频",
        "nickname": "示例 UP",
        "publish_time": "2026-07-31 04:00",
    })
    @patch("core.single_video_download.knowledge_base_root")
    def test_single_video_download_queues_reusable_background_job(self, configured_root, _metadata, submit) -> None:
        configured_root.return_value = self.root / "library"
        job = queue_single_video_download("BV1abc234567")
        self.assertEqual(job["status"], "queued")
        submit.assert_called_once()

    @patch("core.single_video_download.fix_hevc_tag", return_value=False)
    @patch("core.single_video_download.download_subtitle", return_value=False)
    @patch("core.single_video_download.ensure_video_cover")
    @patch("core.single_video_download.download_video")
    @patch("core.single_video_download.knowledge_base_root")
    def test_single_video_download_saves_metadata_cover(self, configured_root, opencli_download, cover, _subtitle, fix_tag) -> None:
        library_root = self.root / "library"
        configured_root.return_value = library_root

        def fake_download(bvid: str, output_directory: str, *, quality: str) -> str:
            Path(output_directory, f"{bvid}_视频.mp4").write_bytes(b"video")
            return "status: success"

        def save_cover(_bvid: str, video_path: Path, thumbnail_url: str) -> bool:
            self.assertEqual(thumbnail_url, "https://i1.hdslb.com/bfs/archive/example.jpg")
            video_path.with_name(video_path.stem + "_cover.jpg").write_bytes(b"cover")
            return True

        opencli_download.side_effect = fake_download
        cover.side_effect = save_cover
        run_single_video_job({
            "bvid": "BV1abc234567",
            "title": "视频",
            "nickname": "示例 UP",
            "publish_time": "2026-08-10 02:46",
            "thumbnail": "https://i1.hdslb.com/bfs/archive/example.jpg",
        })

        row = json.loads((library_root / "OtherVideos/videos.jsonl").read_text(encoding="utf-8"))
        self.assertTrue(row["cover"])
        cover.assert_called_once()
        fixed_path = library_root / "OtherVideos/示例 UP_20260810_视频.mp4"
        fix_tag.assert_called_once_with(fixed_path)

    def test_source_resource_path_is_relative(self) -> None:
        self.assertEqual(resource_path("app/static"), Path("app/static"))

    @patch("core.utils.system.process.shutil.which", return_value=None)
    @patch("core.utils.system.process._candidate_paths")
    def test_finds_opencli_outside_process_path(self, candidates, _which) -> None:
        executable = self.root / "bin/opencli"
        executable.parent.mkdir(parents=True, exist_ok=True)
        executable.write_text("", encoding="utf-8")
        candidates.return_value = [executable]
        self.assertEqual(find_opencli(), executable)

    @patch("core.utils.system.process.subprocess.run")
    @patch("core.utils.system.process.find_opencli", return_value=Path("tmp/bin/opencli"))
    def test_run_opencli_adds_executable_directory_to_path(self, _find, run) -> None:
        run.return_value.returncode = 0
        run_opencli(["--version"], timeout=5)
        self.assertTrue(run.call_args.kwargs["env"]["PATH"].startswith("tmp/bin"))

    @patch("core.utils.system.network.socket.socket")
    def test_occupied_preferred_port_uses_available_port(self, socket_factory) -> None:
        occupied = MagicMock()
        available = MagicMock()
        occupied.__enter__.return_value.bind.side_effect = OSError("occupied")
        available.__enter__.return_value.getsockname.return_value = ("127.0.0.1", 54321)
        socket_factory.side_effect = (occupied, available)
        self.assertEqual(available_local_port(8765), 54321)

    @patch("core.utils.system.network._terminate_process")
    @patch("core.utils.system.network._listener_pids", return_value=[12345])
    @patch("core.utils.system.network._is_biliup_service", return_value=True)
    @patch("core.utils.system.network._is_port_listening", side_effect=[True, False, False])
    def test_fixed_port_replaces_existing_biliup_service(self, listening, _biliup, pids, terminate) -> None:
        self.assertEqual(prepare_biliup_port(8765), 8765)
        pids.assert_called_once_with(8765)
        terminate.assert_called_once_with(12345)
        self.assertEqual(listening.call_count, 3)

    @patch("core.utils.system.network._is_biliup_service", return_value=False)
    @patch("core.utils.system.network._is_port_listening", return_value=True)
    def test_fixed_port_never_terminates_an_unrelated_service(self, _listening, _biliup) -> None:
        with self.assertRaisesRegex(ServicePortError, "其他程序占用"):
            prepare_biliup_port(8765)

    @patch("core.utils.system.network._terminate_process")
    @patch("core.utils.system.network._is_port_listening", return_value=False)
    @patch("core.utils.system.network._is_biliup_service", side_effect=lambda port: port == 58924)
    @patch("core.utils.system.network._listening_instances", return_value=[(101, 58924), (202, 9000)])
    def test_stops_only_identified_biliup_service_on_old_random_port(self, _instances, _biliup, _listening, terminate) -> None:
        self.assertEqual(stop_existing_biliup_services(), 1)
        terminate.assert_called_once_with(101)

    def test_save_updates_existing_uid_and_rebuilds_markdown(self) -> None:
        first, action = save("123", "初始昵称", "第一行\n第二行", self.root)
        updated, update_action = save("123", "新昵称", "新简介", self.root)
        rows = json.loads((self.root / "followings.json").read_text(encoding="utf-8"))
        markdown = (self.root / "bilibili-up-followings.md").read_text(encoding="utf-8")
        self.assertEqual(action, "created")
        self.assertEqual(update_action, "updated")
        self.assertEqual(len(rows), 1)
        self.assertEqual(updated["created_at"], first["created_at"])
        self.assertIn("| 1 | 新昵称 | 123 | 新简介 |", markdown)

    @patch("core.following_delete.knowledge_base_root")
    def test_delete_following_removes_registration_and_index_but_keeps_video(self, configured_root) -> None:
        library_root = self.root / "library"
        up_list = library_root / "UpList"
        save("123", "示例 UP", "简介", up_list)
        merge_videos(
            up_list,
            "示例 UP",
            [{"bvid": "BV1abc", "title": "视频", "url": "", "pub_time": "2026-08-01"}],
        )
        video_file = library_root / "SortedMp4/示例 UP/示例 UP_20260801_视频.mp4"
        video_file.parent.mkdir(parents=True, exist_ok=True)
        video_file.write_bytes(b"video")
        record_download(
            library_root,
            "示例 UP",
            video_file,
            bvid="BV1abc",
            date="20260801",
            title="视频",
            transcript=False,
            uid="123",
        )
        configured_root.return_value = library_root

        self.assertEqual(delete_followings(["123"]), ["123"])
        self.assertEqual(json.loads((up_list / "followings.json").read_text(encoding="utf-8")), [])
        self.assertFalse((up_list / "示例 UP.jsonl").exists())
        self.assertTrue(video_file.is_file())
        self.assertTrue((library_root / "SortedMp4/示例 UP/videos.jsonl").is_file())

    def test_list_rows_maps_following_records_to_management_columns(self) -> None:
        save("123", "示例 UP", "示例简介", self.root)
        rows = list_rows(self.root)
        self.assertEqual(rows[0]["up_id"], "123")
        self.assertEqual(rows[0]["nickname"], "示例 UP")
        self.assertEqual(rows[0]["total_count"], 0)
        self.assertEqual(rows[0]["downloaded_count"], 0)
        self.assertTrue(rows[0]["last_sync_time"])

    def test_video_repository_merges_and_marks_downloaded(self) -> None:
        incoming = [{"bvid": "BV1abc", "title": "第一个视频", "url": "https://b23.tv/BV1abc", "pub_time": "2026-08-01"}]
        rows = merge_videos(self.root, "示例 UP", incoming)
        self.assertEqual(rows[0]["bvid"], "BV1abc")
        rows = mark_downloaded(self.root, "示例 UP", "BV1abc", "SortedMp4/示例/视频.mp4")
        self.assertTrue(rows[0]["downloaded"])
        self.assertTrue((self.root / "示例 UP.jsonl").is_file())

    @patch("core.opencli_videos.run_opencli")
    def test_fetch_video_subtitles_uses_background_opencli_and_normalizes_rows(self, run) -> None:
        run.return_value = subprocess.CompletedProcess(
            [], 0,
            stdout='notice\\n[{"from": "0", "to": "1", "content": "第一句"}]',
            stderr="",
        )
        rows = fetch_video_subtitles("BV1abc")
        self.assertEqual(rows, [{"from": "0", "to": "1", "content": "第一句"}])
        self.assertEqual(run.call_args.args[0][-2:], ["--window", "background"])

    @patch("core.subtitle_download.fetch_video_subtitles", return_value=[
        {"from": "0", "to": "1", "content": "第一句 | 说明"},
    ])
    def test_download_subtitle_writes_sidecar_markdown(self, _fetch) -> None:
        video = self.root / "SortedMp4/示例 UP/202608/示例 UP_20260801_视频.mp4"
        video.parent.mkdir(parents=True, exist_ok=True)
        video.write_bytes(b"video")
        self.assertTrue(download_subtitle("BV1abc", video))
        transcript = video.with_name(video.stem + "__transcript.md")
        self.assertTrue(has_transcript(video))
        self.assertIn("第一句 \\| 说明", transcript.read_text(encoding="utf-8"))

    @patch("core.subtitle_download.fetch_video_subtitles")
    def test_download_subtitle_retries_transient_opencli_failure(self, fetch) -> None:
        fetch.side_effect = [
            OpenCliVideoError("字幕查询失败"),
            [{"from": "0", "to": "1", "content": "重试后成功"}],
        ]
        video = self.root / "OtherVideos/视频.mp4"
        video.parent.mkdir(parents=True, exist_ok=True)
        video.write_bytes(b"video")

        self.assertTrue(download_subtitle("BV1abc", video))
        self.assertEqual(fetch.call_count, 2)
        self.assertTrue(has_transcript(video))

    def test_video_index_uses_reference_local_library_fields(self) -> None:
        library_root = self.root / "library"
        video = library_root / "SortedMp4/火星船长1989/202607/火星船长1989_20260731_科技-红利双星系统.mp4"
        video.parent.mkdir(parents=True, exist_ok=True)
        video.write_bytes(b"video")
        record_download(
            library_root,
            "火星船长1989",
            video,
            bvid="BV19UGw6hEV1",
            date="20260731",
            title="科技-红利双星系统",
            transcript=True,
        )
        rows = merge_videos(
            self.root,
            "另一个 UP",
            [{"bvid": "BV19UGw6hEV1", "date": "20260731", "title": "视频"}],
        )
        self.assertEqual(
            set(json.loads((library_root / "SortedMp4/火星船长1989/videos.jsonl").read_text(encoding="utf-8")).keys()),
            {"bvid", "date", "title", "relative_path", "original_filename", "size_bytes", "transcript", "cover", "scanned_at", "index"},
        )
        self.assertEqual(list_local_videos(library_root, "火星船长1989")[0]["relative_path"], "SortedMp4/火星船长1989/202607/火星船长1989_20260731_科技-红利双星系统.mp4")
        self.assertEqual(rows[0]["date"], "20260731")

    @patch("core.video_reconcile.knowledge_base_root")
    def test_reconcile_updates_remote_tracking_from_local_index(self, configured_root) -> None:
        library_root = self.root / "library"
        up_list = library_root / "UpList"
        save("123", "示例 UP", "简介", up_list)
        merge_videos(
            up_list,
            "示例 UP",
            [{"bvid": "BV1abc", "date": "20260731", "title": "视频", "url": "https://b23.tv/BV1abc"}],
        )
        video = library_root / "SortedMp4/示例 UP/202607/示例 UP_20260731_视频.mp4"
        video.parent.mkdir(parents=True, exist_ok=True)
        video.write_bytes(b"video")
        video.with_name(video.stem + "__transcript.md").write_text("# 视频\n", encoding="utf-8")
        video.with_name(video.stem + "_cover.jpg").write_bytes(b"cover")
        record_download(library_root, "示例 UP", video, bvid="BV1abc", date="20260731", title="视频", transcript=False)
        configured_root.return_value = library_root

        rows = reconcile_up_videos("123")
        self.assertTrue(rows[0]["downloaded"])
        self.assertEqual(rows[0]["local_filename"], video.name)
        self.assertTrue(rows[0]["transcript"])
        self.assertTrue(rows[0]["cover"])
        self.assertTrue(list_local_videos(library_root, "示例 UP", "123")[0]["transcript"])
        self.assertTrue(list_local_videos(library_root, "示例 UP", "123")[0]["cover"])

    @patch("core.video_download._executor.submit")
    @patch("core.video_download.knowledge_base_root")
    def test_queue_download_preserves_case_sensitive_bvid(self, configured_root, submit) -> None:
        library_root = self.root / "library"
        save("123", "示例 UP", "简介", library_root / "UpList")
        merge_videos(
            library_root / "UpList",
            "示例 UP",
            [{"bvid": "BV19UGw6hEV1", "date": "20260731", "title": "视频"}],
        )
        configured_root.return_value = library_root
        jobs = queue_downloads("123", ["BV19UGW6HEV1"])
        self.assertEqual(jobs[0]["bvid"], "BV19UGw6hEV1")
        self.assertEqual(submit.call_args.args[1:], ("123", "BV19UGw6hEV1"))

    @patch("core.video_download.ensure_video_cover", return_value=False)
    @patch("core.video_download._ensure_subtitle")
    @patch("core.video_download.knowledge_base_root")
    def test_single_download_updates_local_transcript_for_existing_video(self, configured_root, ensure_subtitle, _cover) -> None:
        library_root = self.root / "library"
        up_list = library_root / "UpList"
        save("123", "示例 UP", "简介", up_list)
        merge_videos(
            up_list,
            "示例 UP",
            [{"bvid": "BV1abc", "date": "20260731", "title": "视频"}],
        )
        video = library_root / "SortedMp4/示例 UP/202607/示例 UP_20260731_视频.mp4"
        video.parent.mkdir(parents=True, exist_ok=True)
        video.write_bytes(b"video")
        record_download(
            library_root,
            "示例 UP",
            video,
            bvid="BV1abc",
            date="20260731",
            title="视频",
            transcript=False,
            uid="123",
        )
        configured_root.return_value = library_root

        def save_subtitle(_bvid: str, video_path: Path) -> bool:
            video_path.with_name(video_path.stem + "__transcript.md").write_text("# 视频\n", encoding="utf-8")
            return True

        ensure_subtitle.side_effect = save_subtitle
        _download_one("123", "BV1abc")

        local_row = list_local_videos(library_root, "示例 UP", "123")[0]
        remote_row = list_videos(up_list, "示例 UP")[0]
        self.assertTrue(local_row["transcript"])
        self.assertTrue(remote_row["transcript"])
        self.assertTrue(video.with_name(video.stem + "__transcript.md").is_file())

    def test_download_progress_records_status_and_size(self) -> None:
        set_progress("BVprogress", status="downloading", title="下载中的视频", size_bytes=2048)
        rows = progress_rows(["bvprogress"])
        self.assertEqual(rows[0]["status"], "downloading")
        self.assertEqual(rows[0]["size_bytes"], 2048)

    def test_download_quality_prefers_low_resolution_with_safe_fallbacks(self) -> None:
        self.assertEqual(DOWNLOAD_QUALITY_FALLBACKS, ("480p", "720p", "1080p", "best"))

    @patch("core.download_files.run_ffmpeg")
    @patch("core.download_files.run_ffprobe")
    def test_fix_hevc_tag_replaces_mp4_after_successful_stream_copy(self, run_ffprobe, run_ffmpeg) -> None:
        video = self.root / "video.mp4"
        video.parent.mkdir(parents=True, exist_ok=True)
        video.write_bytes(b"original")
        run_ffprobe.return_value = subprocess.CompletedProcess(
            [], 0, stdout=b'{"streams":[{"codec_name":"hevc","codec_tag_string":"hev1"}]}', stderr=b""
        )

        def successful_remux(arguments: list[str], *, timeout: int):
            Path(arguments[-1]).write_bytes(b"remuxed")
            return subprocess.CompletedProcess(arguments, 0, stdout=b"", stderr=b"")

        run_ffmpeg.side_effect = successful_remux
        self.assertTrue(fix_hevc_tag(video))
        self.assertEqual(video.read_bytes(), b"remuxed")
        arguments = run_ffmpeg.call_args.args[0]
        self.assertEqual(arguments[arguments.index("-c") + 1], "copy")
        self.assertEqual(arguments[arguments.index("-tag:v") + 1], "hvc1")

    @patch("core.download_files.run_ffmpeg")
    @patch("core.download_files.run_ffprobe")
    def test_fix_hevc_tag_failure_preserves_original_and_removes_temporary(self, run_ffprobe, run_ffmpeg) -> None:
        video = self.root / "video.mp4"
        video.parent.mkdir(parents=True, exist_ok=True)
        video.write_bytes(b"original")
        run_ffprobe.return_value = subprocess.CompletedProcess(
            [], 0, stdout=b'{"streams":[{"codec_name":"hevc","codec_tag_string":"hev1"}]}', stderr=b""
        )

        def failed_remux(arguments: list[str], *, timeout: int):
            Path(arguments[-1]).write_bytes(b"invalid")
            return subprocess.CompletedProcess(arguments, 1, stdout=b"", stderr=b"failed")

        run_ffmpeg.side_effect = failed_remux
        self.assertFalse(fix_hevc_tag(video))
        self.assertEqual(video.read_bytes(), b"original")
        self.assertFalse(video.with_suffix(".tmp.mp4").exists())

    @patch("core.download_files.run_ffmpeg", side_effect=FileNotFoundError("ffmpeg"))
    @patch("core.download_files.run_ffprobe")
    def test_fix_hevc_tag_missing_ffmpeg_does_not_raise(self, run_ffprobe, _run_ffmpeg) -> None:
        video = self.root / "video.mp4"
        video.parent.mkdir(parents=True, exist_ok=True)
        video.write_bytes(b"original")
        run_ffprobe.return_value = subprocess.CompletedProcess(
            [], 0, stdout=b'{"streams":[{"codec_name":"hevc","codec_tag_string":"hev1"}]}', stderr=b""
        )
        self.assertFalse(fix_hevc_tag(video))
        self.assertEqual(video.read_bytes(), b"original")

    @patch("core.download_files.run_ffmpeg")
    @patch("core.download_files.run_ffprobe")
    def test_fix_hevc_tag_rejects_missing_output_file(self, run_ffprobe, run_ffmpeg) -> None:
        video = self.root / "video.mp4"
        video.parent.mkdir(parents=True, exist_ok=True)
        video.write_bytes(b"original")
        run_ffprobe.return_value = subprocess.CompletedProcess(
            [], 0, stdout=b'{"streams":[{"codec_name":"hevc","codec_tag_string":"hev1"}]}', stderr=b""
        )
        run_ffmpeg.return_value = subprocess.CompletedProcess([], 0, stdout=b"", stderr=b"")
        self.assertFalse(fix_hevc_tag(video))
        self.assertEqual(video.read_bytes(), b"original")

    @patch("core.download_files.run_ffmpeg")
    @patch("core.download_files.run_ffprobe")
    def test_fix_hevc_tag_skips_non_mp4(self, run_ffprobe, run_ffmpeg) -> None:
        video = self.root / "video.webm"
        video.parent.mkdir(parents=True, exist_ok=True)
        video.write_bytes(b"video")
        self.assertFalse(fix_hevc_tag(video))
        run_ffprobe.assert_not_called()
        run_ffmpeg.assert_not_called()

    @patch("core.download_files.run_ffmpeg")
    @patch("core.download_files.run_ffprobe")
    def test_fix_hevc_tag_only_remuxes_hevc_with_hev1_tag(self, run_ffprobe, run_ffmpeg) -> None:
        video = self.root / "video.mp4"
        video.parent.mkdir(parents=True, exist_ok=True)
        video.write_bytes(b"original")
        for codec_name, codec_tag in (("h264", "avc1"), ("hevc", "hvc1")):
            with self.subTest(codec_name=codec_name, codec_tag=codec_tag):
                run_ffprobe.return_value = subprocess.CompletedProcess(
                    [],
                    0,
                    stdout=json.dumps({"streams": [{"codec_name": codec_name, "codec_tag_string": codec_tag}]}).encode(),
                    stderr=b"",
                )
                self.assertFalse(fix_hevc_tag(video))
        run_ffmpeg.assert_not_called()

    @patch("core.utils.system.process.subprocess.run")
    @patch("core.utils.system.process.shutil.which", return_value="C:/ffmpeg/bin/ffmpeg.exe")
    def test_ffmpeg_uses_no_window_flag_on_windows(self, _which, run) -> None:
        run.return_value = subprocess.CompletedProcess([], 0, stdout=b"", stderr=b"")
        with (
            patch("core.utils.system.process.os.name", "nt"),
            patch.object(subprocess, "CREATE_NO_WINDOW", 0x08000000, create=True),
        ):
            run_ffmpeg(["-version"], timeout=5)
        self.assertEqual(run.call_args.kwargs["creationflags"], 0x08000000)

    @patch("core.video_download.fix_hevc_tag", return_value=False)
    @patch("core.video_download._ensure_subtitle", return_value=False)
    @patch("core.video_download.download_video")
    @patch("core.video_download.knowledge_base_root")
    def test_single_download_retries_and_accepts_generated_file(self, configured_root, opencli_download, _subtitle, fix_tag) -> None:
        library_root = self.root / "library"
        save("123", "示例 UP", "简介", library_root / "UpList")
        merge_videos(
            library_root / "UpList",
            "示例 UP",
            [{"bvid": "BV1abc", "title": "第一个视频", "url": "", "pub_time": "2026-08-01"}],
        )
        configured_root.return_value = library_root

        def fake_download(bvid: str, output_directory: str, *, quality: str) -> str:
            output = Path(output_directory)
            if opencli_download.call_count == 1:
                (output / f"{bvid}.part").write_bytes(b"partial")
                raise OpenCliVideoError("视频下载超时，请重试")
            (output / f"{bvid}_第一个视频.mp4").write_bytes(b"video")
            (output / f"{bvid}_封面.jpg").write_bytes(b"cover")
            (output / f"{bvid}_第一个视频.f30280.m4a").write_bytes(b"audio")
            return "status: success"

        opencli_download.side_effect = fake_download
        _download_one("123", "BV1abc")

        row = list_videos(library_root / "UpList", "示例 UP")[0]
        self.assertTrue(row["downloaded"])
        local_path = library_root / "SortedMp4/示例 UP/202608/示例 UP_20260801_第一个视频.mp4"
        self.assertTrue(local_path.is_file())
        self.assertTrue(local_path.with_name(local_path.stem + "_cover.jpg").is_file())
        self.assertTrue(local_path.with_suffix(".m4a").is_file())
        self.assertFalse((local_path.parent / "BV1abc_封面.jpg").exists())
        self.assertFalse((local_path.parent / "BV1abc_第一个视频.f30280.m4a").exists())
        local_row = list_local_videos(library_root, "示例 UP")[0]
        self.assertEqual(local_row["relative_path"], "SortedMp4/示例 UP/202608/示例 UP_20260801_第一个视频.mp4")
        self.assertEqual(local_row["original_filename"], local_path.name)
        self.assertEqual(opencli_download.call_args_list[0].kwargs["quality"], "480p")
        self.assertEqual(opencli_download.call_args_list[1].kwargs["quality"], "720p")
        fix_tag.assert_called_once_with(local_path)

    @patch("core.opencli_videos.run_opencli")
    def test_download_reports_opencli_result_failure(self, run) -> None:
        run.return_value = subprocess.CompletedProcess(
            [], 0, stdout="bvid | status | size\nBV1abc | failed | yt-dlp not installed", stderr=""
        )
        with self.assertRaisesRegex(OpenCliVideoError, "yt-dlp not installed"):
            download_video("BV1abc", str(self.root / "downloads"))
        self.assertIn("--quality", run.call_args.args[0])

    def test_opencli_video_items_are_normalized(self) -> None:
        rows = _items(json.dumps([{"title": "视频", "url": "https://www.bilibili.com/video/BV1xyz", "date": "20260801"}]))
        self.assertEqual(rows[0]["bvid"], "BV1xyz")
        self.assertEqual(rows[0]["pub_time"], "20260801")

    @patch("core.video_sync.fetch_user_videos", return_value=[{"bvid": "BV1xyz", "title": "视频", "url": "https://b23.tv/BV1xyz", "pub_time": "2026-08-01"}])
    @patch("core.video_sync.knowledge_base_root")
    def test_refresh_up_videos_persists_index_and_stats(self, configured_root, _fetch) -> None:
        library_root = self.root / "library"
        save("123", "示例 UP", "简介", library_root / "UpList")
        configured_root.return_value = library_root
        rows = refresh_up_videos("123")
        record = json.loads((library_root / "UpList/followings.json").read_text(encoding="utf-8"))[0]
        self.assertEqual(rows[0]["bvid"], "BV1xyz")
        self.assertEqual(record["total_count"], 1)
        self.assertEqual(record["synced_count"], 1)

    @patch("core.video_sync.knowledge_base_root")
    @patch("core.video_sync.fetch_user_videos")
    def test_refresh_up_videos_fetches_older_pages_until_boundary(self, fetch, configured_root) -> None:
        library_root = self.root / "library"
        save("123", "示例 UP", "简介", library_root / "UpList")
        existing = [
            {"bvid": f"BV{i:03d}", "title": f"旧视频{i}", "url": "", "pub_time": "2026-07-01"}
            for i in range(50)
        ]
        merge_videos(library_root / "UpList", "示例 UP", existing)
        configured_root.return_value = library_root
        fetch.side_effect = [
            existing,
            [{"bvid": "BVnew", "title": "更早视频", "url": "", "pub_time": "2026-06-01"}],
        ]

        rows = refresh_up_videos("123")

        self.assertEqual(len(rows), 51)
        self.assertEqual(fetch.call_count, 2)
        self.assertEqual(fetch.call_args_list[0].kwargs["page"], 1)
        self.assertEqual(fetch.call_args_list[1].kwargs["page"], 2)

    @patch("core.video_sync.knowledge_base_root")
    @patch("core.video_sync.fetch_user_videos")
    def test_refresh_continues_past_full_pages_without_new_rows(self, fetch, configured_root) -> None:
        library_root = self.root / "library"
        save("123", "量子菠萝_", "简介", library_root / "UpList")
        existing_page = [
            {"bvid": f"BV{i:03d}", "title": f"已有视频{i}", "url": "", "pub_time": "2026-07-01"}
            for i in range(50)
        ]
        merge_videos(library_root / "UpList", "量子菠萝_", existing_page)
        configured_root.return_value = library_root
        fetch.side_effect = [
            existing_page,
            existing_page,
            [{"bvid": "BVjune", "title": "六月视频", "url": "", "pub_time": "2026-06-15"}],
        ]

        rows = refresh_up_videos("123")

        self.assertEqual(fetch.call_count, 3)
        self.assertIn("BVjune", {row["bvid"] for row in rows})

    @patch("core.video_sync.knowledge_base_root")
    @patch("core.video_sync.fetch_user_videos")
    def test_video_refresh_details_honor_cutoff_date(self, fetch, configured_root) -> None:
        library_root = self.root / "library"
        save("123", "示例 UP", "简介", library_root / "UpList")
        configured_root.return_value = library_root
        fetch.return_value = [
            {"bvid": "BVnew", "title": "截止日期内", "url": "", "pub_time": "2026-07-20"},
            {"bvid": "BVold", "title": "截止日期前", "url": "", "pub_time": "2026-07-01"},
        ]

        details = refresh_up_videos_with_details("123", since_date="2026-07-15")

        self.assertEqual(details["added_count"], 1)
        self.assertEqual([row["bvid"] for row in details["new_videos"]], ["BVnew"])
        self.assertEqual(fetch.call_count, 1)
        self.assertEqual(list_videos(library_root / "UpList", "示例 UP")[0]["bvid"], "BVnew")

    @patch("core.video_batch_track_download.get_progress", return_value={"status": "success"})
    @patch("core.video_batch_track_download.queue_downloads", return_value=[{"bvid": "BVnew", "status": "queued"}])
    @patch(
        "core.video_batch_track_download.refresh_up_videos_with_details",
        return_value={
            "rows": [{"bvid": "BVnew", "title": "新视频", "date": "20260720", "downloaded": False}],
            "added_count": 1,
            "pages": 1,
            "new_videos": [{"bvid": "BVnew", "title": "新视频", "date": "20260720"}],
        },
    )
    def test_batch_track_download_tracks_new_videos_then_queues_downloads(
        self, refresh, queue, progress
    ) -> None:
        library_root = self.root / "library"
        save("123", "示例 UP", "简介", library_root / "UpList")
        with patch("core.video_batch_track_download.knowledge_base_root", return_value=library_root):
            run_batch_track_download([{"up_id": "123", "nickname": "示例 UP"}], "20260701")

        from core.video_batch_track_download import batch_track_download_progress

        state = batch_track_download_progress()
        self.assertFalse(state["running"])
        self.assertEqual(state["phase"], "completed")
        self.assertEqual(state["added_total"], 1)
        self.assertEqual(state["download_total"], 1)
        self.assertEqual(state["download_done"], 1)
        self.assertEqual(state["results"][0]["new_videos"][0]["bvid"], "BVnew")
        self.assertEqual(state["results"][0]["pending_videos"][0]["bvid"], "BVnew")
        refresh.assert_called_once_with("123", since_date="20260701")
        queue.assert_called_once_with("123", ["BVnew"])
        progress.assert_called()

    @patch("core.video_batch_track_download.get_progress", return_value={"status": "success"})
    @patch(
        "core.video_batch_track_download.queue_downloads",
        return_value=[
            {"bvid": "BVold", "status": "queued"},
            {"bvid": "BVnew", "status": "queued"},
        ],
    )
    @patch(
        "core.video_batch_track_download.refresh_up_videos_with_details",
        return_value={
            "rows": [
                {"bvid": "BVold", "title": "已有但未下载", "date": "20260720", "downloaded": False},
                {"bvid": "BVdone", "title": "已经下载", "date": "20260721", "downloaded": True},
                {"bvid": "BVbefore", "title": "期限前", "date": "20260701", "downloaded": False},
                {"bvid": "BVnew", "title": "新视频", "date": "20260725", "downloaded": False},
            ],
            "added_count": 1,
            "pages": 1,
            "new_videos": [{"bvid": "BVnew", "title": "新视频", "date": "20260725"}],
        },
    )
    def test_batch_track_download_queues_all_pending_videos_after_cutoff(
        self, refresh, queue, progress
    ) -> None:
        library_root = self.root / "library"
        save("123", "示例 UP", "简介", library_root / "UpList")
        with patch("core.video_batch_track_download.knowledge_base_root", return_value=library_root):
            run_batch_track_download([{"up_id": "123", "nickname": "示例 UP"}], "20260715")

        from core.video_batch_track_download import batch_track_download_progress

        state = batch_track_download_progress()
        self.assertEqual(state["download_total"], 2)
        self.assertEqual(state["download_done"], 2)
        self.assertEqual(
            [video["bvid"] for video in state["results"][0]["pending_videos"]],
            ["BVold", "BVnew"],
        )
        refresh.assert_called_once_with("123", since_date="20260715")
        queue.assert_called_once_with("123", ["BVold", "BVnew"])
        progress.assert_called()
        from core.video_batch_track_download import _state, _state_lock
        with _state_lock:
            _state.update({"added_total": 0, "download_total": 0, "download_done": 0, "download_failed": 0})

    @patch("core.video_batch_track_download.Thread")
    @patch("core.video_batch_track_download.batch_track_since_date", return_value="2026-07-01")
    @patch("core.video_batch_track_download.knowledge_base_root")
    def test_batch_track_start_uses_config_date_for_auto_column_ids(self, configured_root, _date, thread) -> None:
        library_root = self.root / "library"
        save("123", "未启用 UP", "简介", library_root / "UpList")
        save("456", "已启用 UP", "简介", library_root / "UpList")
        # 前端只把“自动追踪下载”列已勾选的 UID 传入；后端不再按主表复选框或记录字段二次筛选。
        set_scheduled_tracking("123", False, library_root / "UpList")
        configured_root.return_value = library_root

        result = start_batch_track_download(["123", "456"])

        self.assertEqual(result["since_date"], "20260701")
        self.assertEqual(result["total"], 2)
        self.assertNotIn("skipped_ids", result)
        thread.assert_called_once()
        thread.return_value.start.assert_called_once_with()
        from core.video_batch_track_download import _state, _state_lock
        with _state_lock:
            _state["running"] = False

    def test_configured_knowledge_base_is_written_outside_project(self) -> None:
        library_root = self.root / "knowledge-base"
        configuration = self.root / "app-data/config.json"
        library_root.mkdir(parents=True)
        configured = configure_knowledge_base(library_root, configuration)
        self.assertEqual(configured, library_root.resolve())
        self.assertEqual(knowledge_base_root(configuration), library_root.resolve())
        self.assertEqual(json.loads(configuration.read_text(encoding="utf-8"))["knowledge_base_root"], str(library_root.resolve()))

    def test_batch_track_date_is_saved_in_application_config(self) -> None:
        library_root = self.root / "knowledge-base"
        configuration = self.root / "app-data/config.json"
        library_root.mkdir(parents=True)
        configure_knowledge_base(library_root, configuration)

        self.assertEqual(batch_track_since_date(configuration), "")
        self.assertEqual(set_batch_track_since_date("2026-07-01", configuration), "2026-07-01")
        data = json.loads(configuration.read_text(encoding="utf-8"))
        self.assertEqual(data["knowledge_base_root"], str(library_root.resolve()))
        self.assertEqual(data["batch_track_since_date"], "2026-07-01")
        self.assertEqual(batch_track_since_date(configuration), "2026-07-01")

    def test_scheduled_tracking_setting_is_persisted_in_followings(self) -> None:
        save("123", "示例 UP", "简介", self.root)
        updated = set_scheduled_tracking("123", False, self.root)
        self.assertFalse(updated["scheduled_tracking"])
        self.assertFalse(list_rows(self.root)[0]["scheduled_tracking"])
        self.assertFalse(json.loads((self.root / "followings.json").read_text(encoding="utf-8"))[0]["scheduled_tracking"])

    @patch("core.followings.knowledge_base_root")
    def test_save_following_uses_configured_knowledge_base(self, configured_root) -> None:
        configured_root.return_value = self.root / "knowledge-base"
        save_following("456", "测试 UP", "测试简介")

    @patch("core.followings.save", return_value=({"uid": "456", "nickname": "测试 UP"}, "created"))
    @patch("core.followings.refresh_up_videos_with_stats", return_value=([{"bvid": "BV1", "title": "视频"}], 1, 1))
    @patch("core.followings.knowledge_base_root")
    def test_adding_following_refreshes_initial_videos(self, configured_root, _refresh, _save) -> None:
        configured_root.return_value = self.root / "knowledge-base"
        record, action, sync = save_following_and_refresh("456", "测试 UP", "测试简介")
        self.assertEqual(action, "created")
        self.assertEqual(record["uid"], "456")
        self.assertEqual(sync["status"], "ok")
        self.assertEqual(sync["video_count"], 1)

    @patch("core.utils.system.directories.subprocess.run")
    @patch("core.utils.system.directories.platform.system", return_value="Darwin")
    def test_macos_directory_picker_returns_selected_directory(self, _system, run) -> None:
        run.return_value = subprocess.CompletedProcess([], 0, stdout="/tmp/knowledge-base/\n", stderr="")
        self.assertEqual(choose_directory(), Path("/tmp/knowledge-base"))

    @patch("core.utils.system.directories.subprocess.Popen")
    @patch("core.utils.system.directories.platform.system", return_value="Windows")
    def test_open_directory_uses_windows_file_manager(self, _system, popen) -> None:
        open_directory(Path("tmp/test-library"))
        self.assertEqual(popen.call_args.args[0][0], "explorer.exe")


if __name__ == "__main__":
    unittest.main()
