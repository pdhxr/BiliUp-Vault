"""视频封面下载用例。"""

import os
import tempfile
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlparse, urlunparse
from urllib.request import Request, urlopen

from core.download_files import has_cover_image
from core.opencli_videos import OpenCliVideoError, fetch_video_metadata


_CDN_HOSTS = ("i0.hdslb.com", "i1.hdslb.com", "i2.hdslb.com")
_MAX_COVER_BYTES = 10 * 1024 * 1024
_CONTENT_SUFFIXES = {
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}


def _candidate_urls(thumbnail_url: str) -> list[str]:
    parsed = urlparse(str(thumbnail_url or "").strip())
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in _CDN_HOSTS:
        return []
    return [
        urlunparse(("https", host, parsed.path, "", parsed.query, ""))
        for host in _CDN_HOSTS
    ]


def _image_suffix(content_type: str, content: bytes) -> str:
    media_type = content_type.split(";", 1)[0].strip().lower()
    suffix = _CONTENT_SUFFIXES.get(media_type, "")
    if suffix == ".jpg" and content.startswith(b"\xff\xd8\xff"):
        return suffix
    if suffix == ".webp" and content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return suffix
    return ""


def download_cover(thumbnail_url: str, video_path: Path) -> bool:
    """从 B 站封面 CDN 下载图片，并以视频主名原子保存。"""
    if has_cover_image(video_path):
        return True
    for url in _candidate_urls(thumbnail_url):
        request = Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://www.bilibili.com/",
            },
        )
        try:
            with urlopen(request, timeout=15) as response:
                content_length = int(response.headers.get("Content-Length", "0") or 0)
                if content_length > _MAX_COVER_BYTES:
                    continue
                content = response.read(_MAX_COVER_BYTES + 1)
                suffix = _image_suffix(response.headers.get("Content-Type", ""), content)
            if not suffix or not content or len(content) > _MAX_COVER_BYTES:
                continue
            target = video_path.with_name(f"{video_path.stem}_cover{suffix}")
            with tempfile.NamedTemporaryFile("wb", dir=video_path.parent, delete=False) as handle:
                handle.write(content)
                temporary = Path(handle.name)
            try:
                os.replace(temporary, target)
            except BaseException:
                temporary.unlink(missing_ok=True)
                raise
            return True
        except (OSError, TimeoutError, URLError, ValueError):
            continue
    return False


def ensure_video_cover(bvid: str, video_path: Path, thumbnail_url: str = "") -> bool:
    """优先复用已有封面，否则补查视频元数据并下载封面。"""
    if has_cover_image(video_path, bvid):
        return True
    url = str(thumbnail_url or "").strip()
    if not url:
        try:
            url = str(fetch_video_metadata(bvid).get("thumbnail", "")).strip()
        except (OpenCliVideoError, ValueError):
            return False
    return download_cover(url, video_path)
