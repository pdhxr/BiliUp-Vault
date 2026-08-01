"""字幕脚本下载、存在性判断和索引状态协调。"""

from pathlib import Path
from threading import Lock, Thread

from core.opencli_videos import OpenCliVideoError, fetch_video_subtitles
from core.repositories.followings import find
from core.repositories.library import find_local_video, set_transcript
from core.repositories.videos import list_videos, mark_transcript


_subtitle_fetching_paths: set[str] = set()
_subtitle_fetching_lock = Lock()
_subtitle_download_lock = Lock()


def transcript_path(video_path: Path) -> Path:
    return video_path.with_name(video_path.stem + "__transcript.md")


def has_transcript(video_path: Path) -> bool:
    try:
        return transcript_path(video_path).is_file() and transcript_path(video_path).stat().st_size > 0
    except OSError:
        return False


def _markdown(video_path: Path, rows: list[dict]) -> str:
    lines = [f"# {video_path.stem}\n", "\n", "| 开始 | 结束 | 字幕 |\n", "|---|---|---|\n"]
    for row in rows:
        content = str(row.get("content", "")).replace("|", "\\|").replace("\n", " ").strip()
        if content:
            lines.append(f"| {row.get('from', '')} | {row.get('to', '')} | {content} |\n")
    return "".join(lines) if len(lines) > 4 else ""


def download_subtitle(bvid: str, video_path: Path) -> bool:
    """下载官方字幕到视频旁的 ``__transcript.md``；字幕失败不影响视频状态。"""
    if not bvid or not video_path.is_file() or has_transcript(video_path):
        return has_transcript(video_path)
    try:
        with _subtitle_download_lock:
            if has_transcript(video_path):
                return True
            rows = fetch_video_subtitles(bvid)
            content = _markdown(video_path, rows)
            if not content:
                return False
            transcript_path(video_path).write_text(content, encoding="utf-8")
            return True
    except (OpenCliVideoError, OSError, ValueError):
        return False


def persist_transcript_state(
    root: Path,
    uid: str,
    nickname: str,
    bvid: str,
    video_path: Path,
    *,
    title: str = "",
    date: str = "",
) -> bool:
    """以本地字幕文件事实同步本地和远端索引。"""
    transcript = has_transcript(video_path)
    set_transcript(root, nickname, bvid=bvid, title=title, date=date, transcript=transcript, uid=uid)
    mark_transcript(root / "UpList", nickname, bvid, transcript)
    return transcript


def queue_missing_subtitle(
    root: Path,
    uid: str,
    nickname: str,
    bvid: str,
    title: str,
    date: str,
    video_path: Path,
) -> bool:
    """为已有本地视频异步补拉字幕，避免同一文件并发重复请求。"""
    if not bvid or not video_path.is_file() or has_transcript(video_path):
        return False
    key = str(video_path.resolve())
    with _subtitle_fetching_lock:
        if key in _subtitle_fetching_paths:
            return False
        _subtitle_fetching_paths.add(key)

    def _fetch() -> None:
        try:
            download_subtitle(bvid, video_path)
            persist_transcript_state(root, uid, nickname, bvid, video_path, title=title, date=date)
        finally:
            with _subtitle_fetching_lock:
                _subtitle_fetching_paths.discard(key)

    Thread(target=_fetch, name=f"biliup-subtitle-{bvid}", daemon=True).start()
    return True


def queue_missing_subtitles_for_up(uid: str, *, root: Path) -> int:
    """扫描一个 UP 已下载但缺少字幕的视频，异步排队补拉。"""
    following = find(uid, root / "UpList")
    if following is None:
        return 0
    nickname = str(following.get("nickname", uid))
    queued = 0
    for video in list_videos(root / "UpList", nickname):
        if not video.get("downloaded") or video.get("transcript"):
            continue
        local = find_local_video(
            root,
            nickname,
            bvid=str(video.get("bvid", "")),
            title=str(video.get("title", "")),
            date=str(video.get("date", "")),
            uid=uid,
        )
        if not local:
            continue
        path = root / str(local.get("relative_path", ""))
        queued += int(queue_missing_subtitle(
            root,
            uid,
            nickname,
            str(video.get("bvid", "")),
            str(video.get("title", "")),
            str(video.get("date", "")),
            path,
        ))
    return queued
