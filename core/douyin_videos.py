"""抖音单视频链接解析、元数据读取和下载适配。"""

from __future__ import annotations

from datetime import datetime
from html.parser import HTMLParser
import html
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from core.download_files import COVER_SUFFIXES
from core.utils.system.browser import (
    browser_cookie_sources,
    dump_webpage_with_browser,
    isolated_browser_fallback_supported,
)
from core.utils.system.process import run_yt_dlp


class DouyinVideoError(RuntimeError):
    pass


_DOUYIN_URL = re.compile(
    r"(?:https?://)?(?:v\.douyin\.com|(?:www\.)?douyin\.com|(?:www\.)?iesdouyin\.com)/[^\s<>\"']+",
    re.IGNORECASE,
)
_DOUYIN_AUTHOR = re.compile(r"【\s*([^【】]+?)\s*的作品\s*】")
_TRAILING_PUNCTUATION = "，。！？；：、,.!?;:)]}）】》>"
_COVER_HOST_SUFFIXES = ("douyinpic.com", "byteimg.com")
_MAX_COVER_BYTES = 10 * 1024 * 1024
_DIRECT_VIDEO_HOST_SUFFIXES = ("douyinvod.com",)


class _DouyinPageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.sources: list[str] = []
        self._in_title = False
        self.title_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {str(key).lower(): str(value or "") for key, value in attrs}
        if tag.lower() == "meta":
            name = values.get("name") or values.get("property")
            if name and values.get("content"):
                self.meta[name.lower()] = values["content"]
        elif tag.lower() == "source" and values.get("src"):
            self.sources.append(values["src"])
        elif tag.lower() == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_parts.append(data)


def _allowed_direct_video_url(value: str) -> bool:
    parsed = urlparse(str(value or "").strip())
    host = str(parsed.hostname or "").lower()
    return parsed.scheme == "https" and (
        any(host == suffix or host.endswith(f".{suffix}") for suffix in _DIRECT_VIDEO_HOST_SUFFIXES)
        or (host in {"douyin.com", "www.douyin.com"} and parsed.path.startswith("/aweme/v1/play/"))
    )


def _browser_metadata(reference: str) -> dict[str, str]:
    webpage = dump_webpage_with_browser(reference, timeout=75)
    parser = _DouyinPageParser()
    parser.feed(webpage)
    media_url = next((html.unescape(url) for url in parser.sources if _allowed_direct_video_url(url)), "")
    video_id_match = re.search(r"(?:[?&]__vid=|/video/)(\d{8,})", media_url or reference)
    if not video_id_match:
        video_id_match = re.search(r"(?:aweme_id|awemeId)[^0-9]{0,20}(\d{8,})", webpage)
    title = "".join(parser.title_parts).strip()
    if title.endswith(" - 抖音"):
        title = title[:-5].strip()
    description = parser.meta.get("description", "")
    author_date = re.search(r" - (.+?)于(\d{8})发布在抖音", description)
    if not media_url or not video_id_match or not title:
        raise DouyinVideoError("独立浏览器未能读取完整的抖音视频信息")
    return {
        "platform": "douyin",
        "video_id": video_id_match.group(1),
        "title": title,
        "nickname": author_date.group(1).strip() if author_date else "抖音视频",
        "publish_time": author_date.group(2) if author_date else datetime.now().strftime("%Y%m%d"),
        "thumbnail": parser.meta.get("lark:url:video_cover_image_url", ""),
        "horizontal_thumbnail": "",
        "source_url": reference,
        "media_url": media_url,
    }


def extract_douyin_reference(value: str) -> str:
    """从分享文本或纯链接中提取抖音链接。"""
    match = _DOUYIN_URL.search(str(value or "").strip())
    if not match:
        return ""
    reference = match.group(0).rstrip(_TRAILING_PUNCTUATION)
    return reference if reference.lower().startswith(("http://", "https://")) else f"https://{reference}"


def extract_douyin_author(value: str) -> str:
    """从抖音分享文本的 ``【作者的作品】`` 中提取作者名。"""
    match = _DOUYIN_AUTHOR.search(str(value or ""))
    return match.group(1).strip() if match else ""


def _failure_detail(result: subprocess.CompletedProcess[str]) -> str:
    output = " ".join(
        line.strip()
        for line in ((result.stderr or "") + "\n" + (result.stdout or "")).splitlines()
        if line.strip()
    )
    return output[-600:] or f"yt-dlp 退出码 {result.returncode}"


def _run_with_browser_fallback(arguments: list[str], *, timeout: int) -> subprocess.CompletedProcess[str]:
    """优先读取公开页面，失败后依次复用本机浏览器会话重试。"""
    last_result: subprocess.CompletedProcess[str] | None = None
    chrome_cookie_locked = False
    attempts = [[]]
    attempts.extend(["--cookies-from-browser", browser] for browser in browser_cookie_sources())
    for browser_arguments in attempts:
        result = run_yt_dlp([*browser_arguments, *arguments], timeout=timeout)
        if result.returncode == 0:
            return result
        if browser_arguments and browser_arguments[-1] == "chrome":
            detail = f"{result.stderr or ''}\n{result.stdout or ''}".lower()
            chrome_cookie_locked = (
                isolated_browser_fallback_supported()
                and "could not copy chrome cookie database" in detail
            )
        last_result = result
    assert last_result is not None
    if chrome_cookie_locked:
        return subprocess.CompletedProcess(
            last_result.args,
            last_result.returncode,
            stdout=last_result.stdout,
            stderr=(
                "Windows 上 Chrome 正在占用 Cookie 数据库。请完全退出 Chrome（包括后台进程）后重试；"
                "应用也已自动尝试 Edge 和 Firefox，但未能获取可用的抖音 Cookie。"
            ),
        )
    return last_result


def _publish_date(data: dict) -> str:
    upload_date = "".join(character for character in str(data.get("upload_date") or "") if character.isdigit())
    if len(upload_date) >= 8:
        return upload_date[:8]
    try:
        return datetime.fromtimestamp(float(data.get("timestamp"))).astimezone().strftime("%Y%m%d")
    except (TypeError, ValueError, OSError):
        return datetime.now().strftime("%Y%m%d")


def _thumbnail_url(data: dict, thumbnail_id: str) -> str:
    thumbnails = data.get("thumbnails")
    if isinstance(thumbnails, list):
        for thumbnail in thumbnails:
            if not isinstance(thumbnail, dict) or str(thumbnail.get("id")) != thumbnail_id:
                continue
            url = str(thumbnail.get("url") or "").strip()
            if url:
                return url
    return ""


def _website_cover(data: dict) -> str:
    """选择抖音网页作品列表使用的静态 ``cover``，避开原始帧和动态封面。"""
    cover = _thumbnail_url(data, "cover")
    if cover:
        return cover
    return str(data.get("thumbnail") or "").strip()


def _raw_cover_from_aweme(aweme_detail: dict) -> str:
    video = aweme_detail.get("video")
    if not isinstance(video, dict):
        return ""
    raw_cover = video.get("raw_cover")
    if not isinstance(raw_cover, dict):
        return ""
    urls = raw_cover.get("url_list")
    if not isinstance(urls, list):
        return ""
    return next((str(url).strip() for url in urls if str(url).strip()), "")


def _fetch_raw_cover(reference: str) -> str:
    """读取 yt-dlp 尚未透传的抖音 ``video.raw_cover`` 字段。"""
    try:
        from yt_dlp import YoutubeDL
        from yt_dlp.extractor.tiktok import DouyinIE
    except ImportError:
        return ""

    class RawCoverDouyinIE(DouyinIE):
        def _parse_aweme_video_app(self, aweme_detail):
            info = super()._parse_aweme_video_app(aweme_detail)
            if raw_cover := _raw_cover_from_aweme(aweme_detail):
                info.setdefault("thumbnails", []).append({
                    "id": "raw_cover",
                    "url": raw_cover,
                    "preference": -1,
                })
            return info

    for browser in (None, "chrome"):
        options: dict[str, object] = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "socket_timeout": 30,
        }
        if browser:
            options["cookiesfrombrowser"] = (browser, None, None, None)
        try:
            with YoutubeDL(options) as downloader:
                info = RawCoverDouyinIE(downloader).extract(reference)
            if isinstance(info, dict) and (raw_cover := _thumbnail_url(info, "raw_cover")):
                return raw_cover
        except Exception:
            continue
    return ""


def fetch_douyin_metadata(reference: str) -> dict[str, str]:
    """通过 yt-dlp 读取单条抖音视频的标准化元数据。"""
    try:
        result = _run_with_browser_fallback(
            ["--dump-single-json", "--no-playlist", "--no-warnings", reference],
            timeout=120,
        )
    except FileNotFoundError as exc:
        raise DouyinVideoError("未找到 yt-dlp，请先安装并配置 yt-dlp") from exc
    except subprocess.TimeoutExpired as exc:
        raise DouyinVideoError("抖音视频信息获取超时，请重试") from exc
    if result.returncode != 0:
        try:
            return _browser_metadata(reference)
        except (FileNotFoundError, OSError, RuntimeError, DouyinVideoError) as browser_exc:
            raise DouyinVideoError(
                f"抖音视频信息获取失败：{_failure_detail(result)}；独立浏览器回退失败：{browser_exc}"
            ) from browser_exc
    try:
        data = json.loads(result.stdout)
    except (json.JSONDecodeError, TypeError) as exc:
        raise DouyinVideoError("yt-dlp 返回的抖音视频信息无法解析") from exc
    if not isinstance(data, dict):
        raise DouyinVideoError("yt-dlp 返回的抖音视频信息格式不正确")
    video_id = str(data.get("id") or "").strip()
    title = str(data.get("title") or data.get("description") or "").strip()
    if not video_id or not title:
        raise DouyinVideoError("yt-dlp 未返回完整的抖音视频信息")
    raw_cover = _thumbnail_url(data, "raw_cover")
    if not raw_cover:
        raw_cover = _fetch_raw_cover(f"https://www.douyin.com/video/{video_id}")
    return {
        "platform": "douyin",
        "video_id": video_id,
        "title": title,
        "nickname": str(data.get("uploader") or data.get("creator") or "抖音视频").strip(),
        "publish_time": _publish_date(data),
        "thumbnail": _website_cover(data),
        "horizontal_thumbnail": raw_cover,
        "source_url": reference,
    }


def _download_direct_video(media_url: str, video_id: str, output_directory: Path) -> str:
    if not _allowed_direct_video_url(media_url):
        raise DouyinVideoError("抖音页面返回了不受信任的视频地址")
    target = output_directory / f"{video_id}.mp4"
    temporary = output_directory / f"{video_id}.mp4.part"
    request = Request(media_url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.douyin.com/"})
    try:
        with urlopen(request, timeout=30) as response, temporary.open("wb") as output:
            content_type = str(response.headers.get("Content-Type", "")).lower()
            if "video" not in content_type and "octet-stream" not in content_type:
                raise DouyinVideoError("抖音媒体地址未返回视频内容")
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
        if temporary.stat().st_size <= 0:
            raise DouyinVideoError("抖音视频内容为空")
        os.replace(temporary, target)
        return str(target)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def download_douyin_video(
    reference: str,
    output_directory: Path,
    *,
    media_url: str = "",
    video_id: str = "",
) -> str:
    """下载单条抖音视频，不让 yt-dlp 自动选择封面，也不请求字幕。"""
    if media_url and video_id:
        return _download_direct_video(media_url, video_id, output_directory)
    output_template = output_directory / "%(id)s.%(ext)s"
    try:
        result = _run_with_browser_fallback(
            [
                "--no-playlist",
                "--no-warnings",
                "--merge-output-format", "mp4",
                "-f", "best[ext=mp4]/best",
                "-o", str(output_template),
                reference,
            ],
            timeout=3600,
        )
    except FileNotFoundError as exc:
        raise DouyinVideoError("未找到 yt-dlp，请先安装并配置 yt-dlp") from exc
    except subprocess.TimeoutExpired as exc:
        raise DouyinVideoError("抖音视频下载超时，请重试") from exc
    if result.returncode != 0:
        try:
            metadata = _browser_metadata(reference)
            return _download_direct_video(metadata["media_url"], metadata["video_id"], output_directory)
        except (FileNotFoundError, OSError, RuntimeError, DouyinVideoError) as browser_exc:
            raise DouyinVideoError(
                f"抖音视频下载失败：{_failure_detail(result)}；独立浏览器回退失败：{browser_exc}"
            ) from browser_exc
    return (result.stdout or "") + (result.stderr or "")


def _cover_suffix(content: bytes) -> str:
    if content.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return ".webp"
    return ""


def _allowed_cover_url(value: str) -> bool:
    parsed = urlparse(str(value or "").strip())
    host = str(parsed.hostname or "").lower()
    return parsed.scheme in {"http", "https"} and any(
        host == suffix or host.endswith(f".{suffix}")
        for suffix in _COVER_HOST_SUFFIXES
    )


def download_douyin_cover(
    thumbnail_url: str,
    video_path: Path,
    *,
    variant: str = "cover",
    replace: bool = False,
) -> bool:
    """下载抖音作品列表封面或作者上传的原始封面。"""
    if variant not in {"cover", "horizontal"}:
        raise ValueError(f"不支持的抖音封面类型：{variant}")
    target_stem = f"{video_path.stem}_cover" if variant == "cover" else f"{video_path.stem}_cover_horizontal"
    existing = any(
        video_path.with_name(f"{target_stem}{suffix}").is_file()
        for suffix in COVER_SUFFIXES
    )
    if not replace and existing:
        return True
    if not _allowed_cover_url(thumbnail_url):
        return False
    request = Request(
        thumbnail_url,
        headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.douyin.com/"},
    )
    try:
        with urlopen(request, timeout=15) as response:
            if not _allowed_cover_url(response.geturl()):
                return False
            content_length = int(response.headers.get("Content-Length", "0") or 0)
            if content_length > _MAX_COVER_BYTES:
                return False
            content = response.read(_MAX_COVER_BYTES + 1)
        suffix = _cover_suffix(content)
        if not suffix or len(content) > _MAX_COVER_BYTES:
            return False
        target = video_path.with_name(f"{target_stem}{suffix}")
        with tempfile.NamedTemporaryFile("wb", dir=video_path.parent, delete=False) as handle:
            handle.write(content)
            temporary = Path(handle.name)
        try:
            os.replace(temporary, target)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
        for old_suffix in COVER_SUFFIXES - {suffix}:
            video_path.with_name(f"{target_stem}{old_suffix}").unlink(missing_ok=True)
        return True
    except (OSError, TimeoutError, URLError, ValueError):
        return False


def remove_douyin_horizontal_cover(video_path: Path) -> None:
    """移除旧版本曾保存的 ``origin_cover`` 视频帧。"""
    for suffix in COVER_SUFFIXES:
        video_path.with_name(f"{video_path.stem}_cover_horizontal{suffix}").unlink(missing_ok=True)
