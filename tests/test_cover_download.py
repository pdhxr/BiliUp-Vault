import unittest
from pathlib import Path
from unittest.mock import patch

from core.cover_download import download_cover, ensure_video_cover


class _Response:
    def __init__(self, content: bytes, content_type: str) -> None:
        self.content = content
        self.headers = {
            "Content-Type": content_type,
            "Content-Length": str(len(content)),
        }

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def read(self, _limit: int) -> bytes:
        return self.content


class CoverDownloadTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path("tmp/test-cover-download")
        self.root.mkdir(parents=True, exist_ok=True)
        self.video = self.root / "示例 UP_20260810_视频.mp4"
        self.video.write_bytes(b"video")

    def tearDown(self) -> None:
        for path in self.root.iterdir():
            path.unlink()
        self.root.rmdir()

    @patch("core.cover_download.urlopen")
    def test_downloads_jpeg_from_first_cdn_mirror(self, open_url) -> None:
        content = b"\xff\xd8\xff" + b"cover"
        open_url.return_value = _Response(content, "image/jpeg")

        downloaded = download_cover(
            "http://i1.hdslb.com/bfs/archive/example.jpg",
            self.video,
        )

        self.assertTrue(downloaded)
        self.assertEqual(
            self.video.with_name(self.video.stem + "_cover.jpg").read_bytes(),
            content,
        )
        self.assertEqual(open_url.call_args.args[0].full_url, "https://i0.hdslb.com/bfs/archive/example.jpg")

    @patch("core.cover_download.urlopen")
    def test_rejects_non_image_response(self, open_url) -> None:
        open_url.return_value = _Response(b"<html>error</html>", "text/html")

        self.assertFalse(download_cover("https://i1.hdslb.com/bfs/archive/example.jpg", self.video))
        self.assertFalse(self.video.with_name(self.video.stem + "_cover.jpg").exists())
        self.assertEqual(open_url.call_count, 3)

    @patch("core.cover_download.download_cover", return_value=True)
    @patch("core.cover_download.fetch_video_metadata", return_value={
        "thumbnail": "https://i1.hdslb.com/bfs/archive/example.jpg",
    })
    def test_fetches_metadata_when_thumbnail_url_is_missing(self, metadata, download) -> None:
        self.assertTrue(ensure_video_cover("BV1abc", self.video))
        metadata.assert_called_once_with("BV1abc")
        download.assert_called_once_with("https://i1.hdslb.com/bfs/archive/example.jpg", self.video)


if __name__ == "__main__":
    unittest.main()
