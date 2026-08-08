"""单视频下载用例。

单视频与已登记 UP 的下载共用 OpenCLI 适配、文件发现、重命名、字幕和进度
组件；它只负责把结果保存到知识库的 ``OtherVideos`` 索引。
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import re
from pathlib import Path
from threading import Event

from core.configuration import knowledge_base_root
from core.download_files import directory_snapshot, expected_video_name, find_video_file, remove_partial_files, rename_video
from core.download_progress import get_progress, now_iso, set_progress, watch_download_size
from core.opencli_videos import OpenCliVideoError, download_video, fetch_video_metadata
from core.repositories.library import find_other_video, record_other_download
from core.subtitle_download import download_subtitle, has_transcript


_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="biliup-single-download")
_DOWNLOAD_QUALITIES = ("best", "720p", "480p")
_MAX_DOWNLOAD_ATTEMPTS = 3
_BV_PATTERN = re.compile(r"^BV[A-Za-z0-9]{6,}$", re.IGNORECASE)


def _validate_reference(value: str) -> str:
    reference = str(value or "").strip()
    if not reference:
        raise ValueError("请输入 B 站视频链接或 BV 号")
    if _BV_PATTERN.fullmatch(reference):
        return reference
    if re.match(r"^https?://(?:www\.)?bilibili\.com/video/", reference, re.IGNORECASE):
        return reference
    if re.match(r"^https?://b23\.tv/", reference, re.IGNORECASE):
        return reference
    raise ValueError("请输入有效的 B 站视频链接、b23.tv 短链接或 BV 号")


def _date_from_metadata(value: object) -> str:
    digits = "".join(character for character in str(value or "") if character.isdigit())
    if len(digits) >= 8:
        return digits[:8]
    return datetime.now().strftime("%Y%m%d")


def _download_directory(root: Path) -> Path:
    """单视频沿用参考项目，直接保存到知识库的 OtherVideos 根目录。"""
    return root / "OtherVideos"


def _run_job(metadata: dict[str, str]) -> None:
    bvid = metadata["bvid"]
    title = metadata["title"]
    nickname = metadata.get("nickname") or "单视频"
    date = _date_from_metadata(metadata.get("publish_time"))
    try:
        root = knowledge_base_root()
        directory = _download_directory(root)
        directory.mkdir(parents=True, exist_ok=True)
        before = directory_snapshot(directory)
        set_progress(bvid, status="downloading", title=title, started_at=now_iso())
        stop_monitor = Event()
        monitor = watch_download_size(bvid, directory, before, stop_monitor)
        source = None
        last_error = ""
        try:
            for attempt in range(_MAX_DOWNLOAD_ATTEMPTS):
                quality = _DOWNLOAD_QUALITIES[min(attempt, len(_DOWNLOAD_QUALITIES) - 1)]
                try:
                    download_video(bvid, str(directory), quality=quality)
                except OpenCliVideoError as exc:
                    last_error = str(exc)
                source = find_video_file(directory, bvid, before)
                if source is not None:
                    break
                if not last_error:
                    last_error = "OpenCLI 下载完成，但未找到视频文件"
                if attempt + 1 < _MAX_DOWNLOAD_ATTEMPTS:
                    remove_partial_files(directory, bvid)
        finally:
            stop_monitor.set()
            monitor.join(timeout=1)
        if source is None:
            raise OpenCliVideoError(last_error or "OpenCLI 下载完成，但未找到视频文件")
        target = rename_video(source, directory, nickname, "single-video", title, date)
        transcript = download_subtitle(bvid, target)
        entry = record_other_download(
            root,
            target,
            bvid=bvid,
            title=title,
            date=date,
            transcript=transcript,
        )
        set_progress(
            bvid,
            status="success",
            title=title,
            file_path=entry["relative_path"],
            size_bytes=entry["size_bytes"],
            finished_at=now_iso(),
        )
    except Exception as exc:
        set_progress(bvid, status="failed", title=title, error=str(exc), finished_at=now_iso())


def _run_existing_job(metadata: dict[str, str], existing: dict[str, object], root: Path) -> None:
    bvid = metadata["bvid"]
    title = metadata["title"]
    date = _date_from_metadata(metadata.get("publish_time"))
    local_path = root / str(existing["relative_path"])
    try:
        transcript = download_subtitle(bvid, local_path)
        entry = existing
        if transcript != bool(existing.get("transcript")):
            entry = record_other_download(
                root,
                local_path,
                bvid=bvid,
                title=title,
                date=date,
                transcript=transcript,
            )
        set_progress(
            bvid,
            status="success",
            title=title,
            file_path=entry["relative_path"],
            size_bytes=entry["size_bytes"],
            finished_at=now_iso(),
        )
    except Exception as exc:
        set_progress(bvid, status="failed", title=title, error=str(exc), finished_at=now_iso())


def queue_single_video_download(video_ref: str) -> dict[str, object]:
    """解析并异步提交单视频下载，返回可由统一进度接口查询的任务。"""
    reference = _validate_reference(video_ref)
    metadata = fetch_video_metadata(reference)
    bvid = str(metadata.get("bvid", "")).strip()
    title = str(metadata.get("title", "")).strip()
    if not bvid or not title:
        raise OpenCliVideoError("OpenCLI 未返回完整的视频信息")
    current = get_progress(bvid)
    if current.get("status") in {"queued", "downloading"}:
        return current
    root = knowledge_base_root()
    date = _date_from_metadata(metadata.get("publish_time"))
    existing = find_other_video(root, bvid=bvid, title=title, date=date)
    if existing:
        if existing.get("transcript") and has_transcript(root / str(existing["relative_path"])):
            return set_progress(
                bvid,
                status="success",
                title=title,
                file_path=existing["relative_path"],
                size_bytes=existing["size_bytes"],
                finished_at=now_iso(),
            )
        job = set_progress(
            bvid,
            status="queued",
            title=title,
            started_at=now_iso(),
            finished_at="",
            error="",
            size_bytes=existing["size_bytes"],
        )
        _executor.submit(_run_existing_job, metadata, existing, root)
        return job
    job = set_progress(
        bvid,
        status="queued",
        title=title,
        started_at=now_iso(),
        finished_at="",
        error="",
        size_bytes=0,
    )
    _executor.submit(_run_job, metadata)
    return job
