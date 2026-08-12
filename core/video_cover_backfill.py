"""为追踪范围内的本地 UP 视频补齐缺失封面。"""

from collections.abc import Callable
from pathlib import Path

from core.cover_download import ensure_video_cover
from core.repositories.followings import find
from core.repositories.library import find_local_video, record_download
from core.video_errors import FollowingNotFoundError
from core.video_reconcile import reconcile_up_videos


def _date_key(value: object) -> str:
    return "".join(character for character in str(value or "") if character.isdigit())[:8]


def backfill_covers_for_up(
    uid: str,
    since_date: str,
    *,
    root: Path,
    on_progress: Callable[[int, int, int], None] | None = None,
) -> dict[str, int]:
    """补齐期限内已下载视频的封面，不重新下载视频。"""
    following = find(uid, root / "UpList")
    if following is None:
        raise FollowingNotFoundError(f"未找到 UP {uid}")
    nickname = str(following.get("nickname", uid))
    cutoff = _date_key(since_date)
    rows = reconcile_up_videos(uid, root=root)
    candidates: list[tuple[dict, dict, Path]] = []
    for video in rows:
        video_date = _date_key(video.get("date") or video.get("pub_time"))
        if not video.get("downloaded") or video.get("cover") or not video_date or video_date < cutoff:
            continue
        local = find_local_video(
            root,
            nickname,
            bvid=str(video.get("bvid", "")),
            title=str(video.get("title", "")),
            date=str(video.get("date") or video.get("pub_time") or ""),
            uid=uid,
        )
        if local is None:
            continue
        video_path = root / str(local["relative_path"])
        candidates.append((video, local, video_path))

    total = len(candidates)
    succeeded = 0
    failed = 0
    if on_progress:
        on_progress(0, total, 0)
    for completed, (video, local, video_path) in enumerate(candidates, 1):
        bvid = str(video.get("bvid", ""))
        if ensure_video_cover(bvid, video_path):
            succeeded += 1
            record_download(
                root,
                nickname,
                video_path,
                bvid=bvid,
                title=str(video.get("title", "")),
                date=str(video.get("date") or video.get("pub_time") or ""),
                transcript=bool(local.get("transcript", False)),
                uid=uid,
            )
        else:
            failed += 1
        if on_progress:
            on_progress(completed, total, failed)

    if candidates:
        reconcile_up_videos(uid, root=root)
    return {"total": total, "succeeded": succeeded, "failed": failed}
