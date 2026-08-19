import unittest
from pathlib import Path
from unittest.mock import patch

from core.douyin_videos import _raw_cover_from_aweme, download_douyin_cover, remove_douyin_horizontal_cover


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


if __name__ == "__main__":
    unittest.main()
