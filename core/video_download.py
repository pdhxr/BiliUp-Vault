from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from threading import Event

from core.configuration import knowledge_base_root
from core.download_files import (
    directory_snapshot,
    expected_video_name,
    find_video_file,
    remove_partial_files,
    rename_video_artifacts,
    rename_video,
)
from core.download_progress import get_progress, now_iso, set_progress, watch_download_size
from core.opencli_videos import OpenCliVideoError, download_video
from core.repositories.followings import find, update_video_stats
from core.repositories.library import find_local_video, record_download, set_transcript
from core.repositories.videos import downloaded_count, list_videos, mark_downloaded, safe_video_directory_name
from core.subtitle_download import download_subtitle
from core.video_errors import FollowingNotFoundError


_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="biliup-download")
_MAX_DOWNLOAD_ATTEMPTS = 3
_DOWNLOAD_QUALITIES = ("best", "720p", "480p")


def _ensure_subtitle(bvid: str, video_path: Path) -> bool:
    """下载后尝试补拉官方字幕；字幕服务失败不影响视频下载。"""
    return download_subtitle(bvid, video_path)


def _download_directory(root: Path, following: dict, uid: str, date: str) -> Path:
    nickname = safe_video_directory_name(str(following.get("nickname", "")), uid)
    month = str(date).replace("-", "")[:6] or "unknown-date"
    return root / "SortedMp4" / nickname / month


def _download_one(uid: str, bvid: str) -> None:
    root = knowledge_base_root()
    following = find(uid, root / "UpList")
    if following is None:
        raise FollowingNotFoundError(f"未找到 UP {uid}")
    nickname = str(following.get("nickname", uid))
    videos = list_videos(root / "UpList", nickname)
    video = next((row for row in videos if str(row.get("bvid", "")).upper() == bvid.upper()), None)
    if video is None:
        raise ValueError(f"未找到视频 {bvid}，请先刷新视频列表")
    title = str(video.get("title", ""))
    date = str(video.get("date") or video.get("pub_time", "")).strip()[:10].replace("-", "") or datetime.now().strftime("%Y%m%d")
    directory = _download_directory(root, following, uid, date)
    directory.mkdir(parents=True, exist_ok=True)
    expected = directory / expected_video_name(nickname, uid, title, date)
    indexed = find_local_video(root, nickname, bvid=bvid, title=title, date=date, uid=uid)
    if indexed:
        local_path = root / str(indexed["relative_path"])
        transcript = _ensure_subtitle(bvid, local_path)
        set_transcript(
            root,
            nickname,
            bvid=bvid,
            title=title,
            date=date,
            transcript=transcript,
            uid=uid,
        )
        rows = mark_downloaded(
            root / "UpList",
            nickname,
            bvid,
            str(indexed["original_filename"]),
            transcript=transcript,
        )
        update_video_stats(
            uid,
            total_count=len(rows),
            synced_count=len(rows),
            downloaded_count=downloaded_count(rows),
            last_sync_at=str(following.get("last_sync_at", "")),
            root=root / "UpList",
        )
        set_progress(
            bvid,
            status="success",
            title=title,
            file_path=str(indexed["relative_path"]),
            size_bytes=local_path.stat().st_size,
            finished_at=now_iso(),
        )
        return
    if expected.is_file() and expected.stat().st_size > 0:
        relative_path = expected.relative_to(root).as_posix()
        transcript = _ensure_subtitle(bvid, expected)
        record_download(root, nickname, expected, bvid=bvid, title=title, date=date, transcript=transcript, uid=uid)
        rows = mark_downloaded(root / "UpList", nickname, bvid, relative_path, transcript=transcript)
        update_video_stats(
            uid,
            total_count=len(rows),
            synced_count=len(rows),
            downloaded_count=downloaded_count(rows),
            last_sync_at=str(following.get("last_sync_at", "")),
            root=root / "UpList",
        )
        set_progress(
            bvid,
            status="success",
            title=title,
            file_path=relative_path,
            size_bytes=expected.stat().st_size,
            finished_at=now_iso(),
        )
        return

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
    target = rename_video(source, directory, nickname, uid, title, date)
    rename_video_artifacts(directory, bvid, target)
    relative_path = target.relative_to(root).as_posix()
    transcript = _ensure_subtitle(bvid, target)
    record_download(root, nickname, target, bvid=bvid, title=title, date=date, transcript=transcript, uid=uid)
    rows = mark_downloaded(root / "UpList", nickname, bvid, relative_path, transcript=transcript)
    update_video_stats(
        uid,
        total_count=len(rows),
        synced_count=len(rows),
        downloaded_count=downloaded_count(rows),
        last_sync_at=str(following.get("last_sync_at", "")),
        root=root / "UpList",
    )
    set_progress(
        bvid,
        status="success",
        file_path=relative_path,
        size_bytes=target.stat().st_size,
        finished_at=now_iso(),
    )


def queue_downloads(uid: str, bvids: list[str]) -> list[dict[str, object]]:
    root = knowledge_base_root()
    if find(uid, root / "UpList") is None:
        raise FollowingNotFoundError(f"未找到 UP {uid}")
    nickname = str(find(uid, root / "UpList").get("nickname", uid))
    videos = {str(row.get("bvid", "")).upper(): row for row in list_videos(root / "UpList", nickname)}
    jobs = []
    for raw_bvid in dict.fromkeys(str(value).strip() for value in bvids if str(value).strip()):
        lookup_key = raw_bvid.upper()
        video = videos.get(lookup_key)
        if video is None:
            raise ValueError(f"未找到视频 {raw_bvid}，请先刷新视频列表")
        # BV 号大小写敏感：索引查找可以忽略大小写，但传给 OpenCLI 必须使用
        # JSONL 中保存的原始拼写，不能把 BV1abc 改成 BV1ABC。
        bvid = str(video.get("bvid") or raw_bvid).strip()
        current = get_progress(bvid)
        if current.get("status") == "downloading":
            jobs.append(dict(current))
            continue
        job = set_progress(
            bvid,
            status="queued",
            title=video.get("title", ""),
            started_at=now_iso(),
            finished_at="",
            error="",
            size_bytes=0,
        )
        jobs.append(job)
        _executor.submit(_run_job, uid, bvid)
    return jobs


def _run_job(uid: str, bvid: str) -> None:
    try:
        _download_one(uid, bvid)
    except Exception as exc:
        set_progress(bvid, status="failed", error=str(exc), finished_at=now_iso())
