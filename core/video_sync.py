from datetime import datetime
from pathlib import Path
from collections.abc import Callable
from threading import Event

from core.configuration import knowledge_base_root
from core.opencli_videos import OpenCliCancelledError, fetch_user_videos
from core.repositories.followings import find, update_video_stats
from core.repositories.videos import downloaded_count, list_videos, merge_videos
from core.video_errors import FollowingNotFoundError
from core.video_reconcile import reconcile_up_videos


def _date_key(value: object) -> str:
    return "".join(character for character in str(value or "") if character.isdigit())[:8]


def _following(uid: str, root: Path) -> dict:
    row = find(uid, root / "UpList")
    if row is None:
        raise FollowingNotFoundError(f"未找到 UP {uid}")
    return row


def list_up_videos(uid: str) -> list[dict]:
    root = knowledge_base_root()
    following = _following(uid, root)
    return reconcile_up_videos(uid, root=root)


def _refresh_up_videos(
    uid: str,
    *,
    page: int = 1,
    limit: int = 50,
    max_pages: int = 5,
    max_new_videos: int = 20,
    since_date: str = "",
    on_page: Callable[[int], None] | None = None,
    on_page_result: Callable[[int, int], None] | None = None,
    cancel_event: Event | None = None,
) -> tuple[list[dict], int, int, list[dict]]:
    root = knowledge_base_root()
    following = _following(uid, root)
    nickname = str(following.get("nickname", uid))
    existing_rows = list_videos(root / "UpList", nickname)
    existing_bvids = {
        str(row.get("bvid", "")).strip().upper()
        for row in existing_rows
        if str(row.get("bvid", "")).strip()
    }
    incoming: list[dict] = []
    pages_fetched = 0
    cutoff = _date_key(since_date)
    for current_page in range(page, page + max_pages):
        if cancel_event is not None and cancel_event.is_set():
            raise OpenCliCancelledError("视频同步已停止")
        if on_page:
            on_page(current_page)
        fresh = fetch_user_videos(
            uid,
            page=current_page,
            limit=limit,
            cancel_event=cancel_event,
        )
        if cancel_event is not None and cancel_event.is_set():
            raise OpenCliCancelledError("视频同步已停止")
        pages_fetched += 1
        if on_page_result:
            on_page_result(current_page, len(fresh))
        if not fresh:
            break

        for video in fresh:
            video_date = _date_key(video.get("date") or video.get("pub_time"))
            if cutoff and video_date and video_date < cutoff:
                continue
            bvid = str(video.get("bvid", "")).strip().upper()
            if not bvid or bvid in existing_bvids:
                continue
            incoming.append(video)
            existing_bvids.add(bvid)
            if len(incoming) >= max_new_videos:
                break

        if len(incoming) >= max_new_videos:
            break
        oldest_on_page = _date_key(fresh[-1].get("date") or fresh[-1].get("pub_time"))
        if cutoff and oldest_on_page and oldest_on_page < cutoff:
            break
        if len(fresh) < limit:
            break

    if cancel_event is not None and cancel_event.is_set():
        raise OpenCliCancelledError("视频同步已停止")
    rows = merge_videos(root / "UpList", nickname, incoming)
    rows = reconcile_up_videos(uid, root=root)
    update_video_stats(
        uid,
        total_count=len(rows),
        synced_count=len(rows),
        downloaded_count=downloaded_count(rows),
        last_sync_at=datetime.now().astimezone().isoformat(),
        root=root / "UpList",
    )
    return rows, len(incoming), pages_fetched, incoming


def refresh_up_videos_with_stats(
    uid: str,
    *,
    page: int = 1,
    limit: int = 50,
    max_pages: int = 5,
    max_new_videos: int = 20,
    since_date: str = "",
    on_page: Callable[[int], None] | None = None,
    on_page_result: Callable[[int, int], None] | None = None,
    cancel_event: Event | None = None,
) -> tuple[list[dict], int, int]:
    rows, added, pages, _ = _refresh_up_videos(
        uid,
        page=page,
        limit=limit,
        max_pages=max_pages,
        max_new_videos=max_new_videos,
        since_date=since_date,
        on_page=on_page,
        on_page_result=on_page_result,
        cancel_event=cancel_event,
    )
    return rows, added, pages


def refresh_up_videos_with_details(
    uid: str,
    *,
    page: int = 1,
    since_date: str = "",
    max_pages: int = 60,
    max_new_videos: int = 10000,
    limit: int = 50,
    cancel_event: Event | None = None,
) -> dict[str, object]:
    rows, added, pages, new_videos = _refresh_up_videos(
        uid,
        page=page,
        limit=limit,
        max_pages=max_pages,
        max_new_videos=max_new_videos,
        since_date=since_date,
        cancel_event=cancel_event,
    )
    return {
        "rows": rows,
        "added_count": added,
        "pages": pages,
        "new_videos": new_videos,
    }


def refresh_up_videos(uid: str, *, page: int = 1, limit: int = 50) -> list[dict]:
    rows, _, _ = refresh_up_videos_with_stats(uid, page=page, limit=limit)
    return rows
