"""B 站与抖音单视频下载用例，结果统一保存到 ``OtherVideos``。"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import re
from pathlib import Path
from threading import Event

from core.configuration import knowledge_base_root
from core.cover_download import ensure_video_cover
from core.download_files import COVER_SUFFIXES, directory_snapshot, find_video_file, fix_hevc_tag, has_cover_image, remove_partial_files, rename_video, rename_video_artifacts
from core.download_progress import get_progress, now_iso, set_progress, watch_download_size
from core.douyin_videos import download_douyin_cover, download_douyin_video, extract_douyin_author, extract_douyin_reference, fetch_douyin_metadata, remove_douyin_horizontal_cover
from core.opencli_videos import DOWNLOAD_QUALITY_FALLBACKS, OpenCliVideoError, download_video, fetch_video_metadata
from core.repositories.library import find_other_video, record_other_download
from core.subtitle_download import download_subtitle, has_transcript


_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="biliup-single-download")
_BV_PATTERN = re.compile(r"^BV[A-Za-z0-9]{6,}$", re.IGNORECASE)
_BILIBILI_URL = re.compile(
    r"(?:https?://)?(?:(?:www\.)?bilibili\.com/video/|b23\.tv/)[^\s<>\"']+",
    re.IGNORECASE,
)
_TRAILING_URL_PUNCTUATION = "，。！？；：、,.!?;:)]}）】》>"


def _extract_bilibili_reference(value: str) -> str:
    match = _BILIBILI_URL.search(str(value or "").strip())
    if not match:
        return ""
    reference = match.group(0).rstrip(_TRAILING_URL_PUNCTUATION)
    return reference if reference.lower().startswith(("http://", "https://")) else f"https://{reference}"


def _resolve_reference(value: str) -> tuple[str, str]:
    reference = str(value or "").strip()
    if not reference:
        raise ValueError("请输入 B 站或抖音视频链接")
    if _BV_PATTERN.fullmatch(reference):
        return "bilibili", reference
    bilibili_reference = _extract_bilibili_reference(reference)
    if bilibili_reference:
        return "bilibili", bilibili_reference
    douyin_reference = extract_douyin_reference(reference)
    if douyin_reference:
        return "douyin", douyin_reference
    raise ValueError("请输入有效的 B 站链接、BV 号或抖音分享链接")


def _video_id(metadata: dict[str, str]) -> str:
    return str(metadata.get("video_id") or metadata.get("bvid") or "").strip()


def _date_from_metadata(value: object) -> str:
    digits = "".join(character for character in str(value or "") if character.isdigit())
    if len(digits) >= 8:
        return digits[:8]
    return datetime.now().strftime("%Y%m%d")


def _download_directory(root: Path) -> Path:
    """单视频沿用参考项目，直接保存到知识库的 OtherVideos 根目录。"""
    return root / "OtherVideos"


def _run_job(metadata: dict[str, str]) -> None:
    platform = metadata.get("platform") or "bilibili"
    bvid = _video_id(metadata)
    title = metadata["title"]
    nickname = metadata.get("nickname") or "单视频"
    date = _date_from_metadata(metadata.get("publish_time"))
    try:
        root = knowledge_base_root()
        directory = _download_directory(root)
        directory.mkdir(parents=True, exist_ok=True)
        before = directory_snapshot(directory)
        set_progress(
            bvid,
            status="downloading",
            platform=platform,
            video_id=bvid,
            title=title,
            started_at=now_iso(),
        )
        stop_monitor = Event()
        monitor = watch_download_size(bvid, directory, before, stop_monitor)
        source = None
        last_error = ""
        try:
            if platform == "douyin":
                download_douyin_video(
                    metadata["source_url"],
                    directory,
                    media_url=metadata.get("media_url", ""),
                    video_id=bvid,
                )
                source = find_video_file(directory, bvid, before)
                if source is None:
                    last_error = "yt-dlp 下载完成，但未找到抖音视频文件"
            else:
                for attempt, quality in enumerate(DOWNLOAD_QUALITY_FALLBACKS):
                    try:
                        download_video(bvid, str(directory), quality=quality)
                    except OpenCliVideoError as exc:
                        last_error = str(exc)
                    source = find_video_file(directory, bvid, before)
                    if source is not None:
                        break
                    if not last_error:
                        last_error = "OpenCLI 下载完成，但未找到视频文件"
                    if attempt + 1 < len(DOWNLOAD_QUALITY_FALLBACKS):
                        remove_partial_files(directory, bvid)
        finally:
            stop_monitor.set()
            monitor.join(timeout=1)
        if source is None:
            raise OpenCliVideoError(last_error or "OpenCLI 下载完成，但未找到视频文件")
        target = rename_video(source, directory, nickname, "single-video", title, date)
        rename_video_artifacts(directory, bvid, target)
        fix_hevc_tag(target)
        if platform == "douyin":
            download_douyin_cover(metadata.get("thumbnail", ""), target, replace=True)
            remove_douyin_horizontal_cover(target)
            horizontal_thumbnail = metadata.get("horizontal_thumbnail", "")
            if horizontal_thumbnail:
                download_douyin_cover(horizontal_thumbnail, target, variant="horizontal", replace=True)
            transcript = False
        else:
            ensure_video_cover(bvid, target, metadata.get("thumbnail", ""))
            transcript = download_subtitle(bvid, target)
        entry = record_other_download(
            root,
            target,
            bvid=bvid if platform == "bilibili" else "",
            title=title,
            date=date,
            transcript=transcript,
            platform=platform,
            video_id=bvid,
        )
        set_progress(
            bvid,
            status="success",
            platform=platform,
            video_id=bvid,
            title=title,
            file_path=entry["relative_path"],
            size_bytes=entry["size_bytes"],
            finished_at=now_iso(),
        )
    except Exception as exc:
        set_progress(bvid, status="failed", title=title, error=str(exc), finished_at=now_iso())


def _run_existing_job(metadata: dict[str, str], existing: dict[str, object], root: Path) -> None:
    platform = metadata.get("platform") or "bilibili"
    bvid = _video_id(metadata)
    title = metadata["title"]
    date = _date_from_metadata(metadata.get("publish_time"))
    local_path = root / str(existing["relative_path"])
    try:
        if platform == "douyin":
            previous_path = local_path
            local_path = rename_video(
                previous_path,
                previous_path.parent,
                metadata.get("nickname") or "单视频",
                "single-video",
                title,
                date,
            )
            if local_path != previous_path:
                for suffix in COVER_SUFFIXES:
                    for variant in ("cover", "cover_horizontal"):
                        previous_cover = previous_path.with_name(f"{previous_path.stem}_{variant}{suffix}")
                        updated_cover = local_path.with_name(f"{local_path.stem}_{variant}{suffix}")
                        if previous_cover.is_file() and not updated_cover.exists():
                            previous_cover.replace(updated_cover)
            download_douyin_cover(metadata.get("thumbnail", ""), local_path, replace=True)
            remove_douyin_horizontal_cover(local_path)
            horizontal_thumbnail = metadata.get("horizontal_thumbnail", "")
            if horizontal_thumbnail:
                download_douyin_cover(horizontal_thumbnail, local_path, variant="horizontal", replace=True)
            transcript = False
        else:
            ensure_video_cover(bvid, local_path, metadata.get("thumbnail", ""))
            transcript = download_subtitle(bvid, local_path)
        entry = record_other_download(
            root,
            local_path,
            bvid=bvid if platform == "bilibili" else "",
            title=title,
            date=date,
            transcript=transcript,
            platform=platform,
            video_id=bvid,
        )
        set_progress(
            bvid,
            status="success",
            platform=platform,
            video_id=bvid,
            title=title,
            file_path=entry["relative_path"],
            size_bytes=entry["size_bytes"],
            finished_at=now_iso(),
        )
    except Exception as exc:
        set_progress(bvid, status="failed", title=title, error=str(exc), finished_at=now_iso())


def queue_single_video_download(video_ref: str) -> dict[str, object]:
    """解析并异步提交单视频下载，返回可由统一进度接口查询的任务。"""
    platform, reference = _resolve_reference(video_ref)
    if platform == "douyin":
        metadata = fetch_douyin_metadata(reference)
        shared_author = extract_douyin_author(video_ref)
        if shared_author:
            metadata["nickname"] = shared_author
    else:
        metadata = fetch_video_metadata(reference)
        metadata.update({"platform": "bilibili", "video_id": str(metadata.get("bvid", "")), "source_url": reference})
    bvid = _video_id(metadata)
    title = str(metadata.get("title", "")).strip()
    if not bvid or not title:
        raise OpenCliVideoError("视频信息不完整")
    current = get_progress(bvid)
    if current.get("status") in {"queued", "downloading"}:
        return current
    root = knowledge_base_root()
    date = _date_from_metadata(metadata.get("publish_time"))
    existing = find_other_video(root, video_id=bvid, platform=platform, title=title, date=date)
    if existing:
        local_path = root / str(existing["relative_path"])
        if platform != "douyin" and (
            existing.get("transcript")
            and has_transcript(local_path)
            and existing.get("cover")
            and has_cover_image(local_path, bvid)
        ):
            return set_progress(
                bvid,
                status="success",
                platform=platform,
                video_id=bvid,
                title=title,
                file_path=existing["relative_path"],
                size_bytes=existing["size_bytes"],
                finished_at=now_iso(),
            )
        job = set_progress(
            bvid,
            status="queued",
            platform=platform,
            video_id=bvid,
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
        platform=platform,
        video_id=bvid,
        title=title,
        started_at=now_iso(),
        finished_at="",
        error="",
        size_bytes=0,
    )
    _executor.submit(_run_job, metadata)
    return job


def shutdown_single_downloads() -> None:
    _executor.shutdown(wait=False, cancel_futures=True)
