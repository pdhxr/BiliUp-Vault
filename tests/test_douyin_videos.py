import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.douyin_videos import _browser_metadata, _download_direct_video, _raw_cover_from_aweme, download_douyin_cover, remove_douyin_horizontal_cover


class _Response:
    def __init__(self, content: bytes, url: str) -> None:
        self.content = content
        self.url = url
        self.headers = {"Content-Length": str(len(content))}

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def read(self, _limit: int) -> bytes:
        return self.content

    def geturl(self) -> str:
        return self.url


class DouyinCoverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path("tmp/test-douyin-cover")
        self.root.mkdir(parents=True, exist_ok=True)
        self.video = self.root / "作者_20260812_视频.mp4"
        self.video.write_bytes(b"video")

    def tearDown(self) -> None:
        for path in self.root.iterdir():
            path.unlink()
        self.root.rmdir()

    @patch("core.douyin_videos.urlopen")
    def test_replaces_old_thumbnail_with_selected_website_cover(self, open_url) -> None:
        old_cover = self.video.with_name(self.video.stem + "_cover.webp")
        old_cover.write_bytes(b"RIFFold-WEBP")
        content = b"\xff\xd8\xffwebsite-cover"
        url = "https://p3-sign.douyinpic.com/website-cover.jpeg"
        open_url.return_value = _Response(content, url)

        self.assertTrue(download_douyin_cover(url, self.video, replace=True))
        self.assertFalse(old_cover.exists())
        self.assertEqual(self.video.with_name(self.video.stem + "_cover.jpg").read_bytes(), content)

    @patch("core.douyin_videos.urlopen")
    def test_rejects_cover_outside_douyin_image_hosts(self, open_url) -> None:
        self.assertFalse(download_douyin_cover("https://example.com/cover.jpg", self.video, replace=True))
        open_url.assert_not_called()

    @patch("core.douyin_videos.urlopen")
    def test_saves_raw_cover_as_separate_horizontal_file(self, open_url) -> None:
        content = b"\xff\xd8\xffauthor-uploaded-cover"
        url = "https://p3-sign.douyinpic.com/raw-cover.jpeg"
        open_url.return_value = _Response(content, url)

        self.assertTrue(download_douyin_cover(url, self.video, variant="horizontal", replace=True))
        self.assertEqual(
            self.video.with_name(self.video.stem + "_cover_horizontal.jpg").read_bytes(),
            content,
        )

    def test_extracts_raw_cover_without_falling_back_to_video_frame(self) -> None:
        aweme = {
            "video": {
                "raw_cover": {"url_list": ["https://p3-sign.douyinpic.com/raw-cover.jpeg"]},
                "origin_cover": {"url_list": ["https://p3-sign.douyinpic.com/video-frame.jpeg"]},
            },
        }
        self.assertEqual(
            _raw_cover_from_aweme(aweme),
            "https://p3-sign.douyinpic.com/raw-cover.jpeg",
        )

    def test_removes_old_origin_cover_file(self) -> None:
        old_horizontal = self.video.with_name(self.video.stem + "_cover_horizontal.jpg")
        old_horizontal.write_bytes(b"video-frame")

        remove_douyin_horizontal_cover(self.video)

        self.assertFalse(old_horizontal.exists())

    @patch("core.douyin_videos.dump_webpage_with_browser")
    def test_browser_fallback_extracts_public_page_metadata(self, dump_page) -> None:
        dump_page.return_value = """
            <html><head>
              <title>页面视频标题 - 抖音</title>
              <meta name="description" content="页面视频标题 - 页面作者于20260820发布在抖音，来抖音！">
              <meta name="lark:url:video_cover_image_url" content="https://p3-sign.douyinpic.com/cover.jpeg?a=1&amp;b=2">
            </head><body><script>window.state={"aweme_id":"739000009"};</script>
            <video><source src="https://v26-web.douyinvod.com/video.mp4?a=1&amp;b=2"></video></body></html>
        """
        metadata = _browser_metadata("https://v.douyin.com/example/")
        self.assertEqual(metadata["video_id"], "739000009")
        self.assertEqual(metadata["title"], "页面视频标题")
        self.assertEqual(metadata["nickname"], "页面作者")
        self.assertEqual(metadata["publish_time"], "20260820")
        self.assertEqual(metadata["media_url"], "https://v26-web.douyinvod.com/video.mp4?a=1&b=2")

    @patch("core.douyin_videos.urlopen")
    def test_direct_browser_media_download_is_atomic(self, open_url) -> None:
        response = MagicMock()
        response.headers = {"Content-Type": "video/mp4"}
        response.read.side_effect = [b"video-data", b""]
        response.__enter__.return_value = response
        open_url.return_value = response
        target = _download_direct_video(
            "https://v26-web.douyinvod.com/video.mp4?__vid=739000009",
            "739000009",
            self.root,
        )
        self.assertEqual(Path(target).read_bytes(), b"video-data")
        self.assertFalse((self.root / "739000009.mp4.part").exists())


if __name__ == "__main__":
    unittest.main()
