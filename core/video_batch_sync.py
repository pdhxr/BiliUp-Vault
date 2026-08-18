from datetime import datetime
from threading import Event, Lock, Thread

from core.configuration import knowledge_base_root
from core.opencli_videos import OpenCliCancelledError
from core.repositories.followings import find, set_next_sync_page
from core.video_errors import FollowingNotFoundError
from core.video_sync import refresh_up_videos_with_stats


_state: dict[str, object] = {
    "running": False,
    "total": 0,
    "done": 0,
    "current_up": "",
    "current_up_id": "",
    "current_page": 0,
    "max_pages": 0,
    "added_total": 0,
    "errors": 0,
    "cancel_requested": False,
    "cancelled": False,
    "started_at": "",
    "finished_at": "",
    "results": [],
}
_state_lock = Lock()
_cancel_event = Event()


def _now() -> str:
    return datetime.now().astimezone().isoformat()


def _copy_state_unlocked() -> dict[str, object]:
    return {key: (list(value) if key == "results" else value) for key, value in _state.items()}


def _snapshot() -> dict[str, object]:
    with _state_lock:
        return _copy_state_unlocked()


def _set(**values: object) -> None:
    with _state_lock:
        _state.update(values)


def start_batch_sync(
    up_ids: list[str],
    *,
    max_pages: int = 5,
    max_new_videos: int = 20,
    limit: int = 50,
    continue_history: bool = False,
) -> dict[str, object]:
    ids = list(dict.fromkeys(str(value).strip() for value in up_ids if str(value).strip()))
    if not ids:
        raise ValueError("至少选择一个 UP 主")
    with _state_lock:
        if _state["running"]:
            return {"status": "busy", "current": _copy_state_unlocked()}

    root = knowledge_base_root()
    queue: list[dict[str, str]] = []
    for uid in ids:
        following = find(uid, root / "UpList")
        if following is None:
            raise FollowingNotFoundError(f"未找到 UP {uid}")
        synced_count = max(0, int(following.get("synced_count", 0) or 0))
        fallback_page = (synced_count + limit - 1) // limit + 1 if synced_count else 1
        next_page = max(1, int(following.get("next_sync_page", fallback_page) or fallback_page))
        queue.append({
            "up_id": uid,
            "nickname": str(following.get("nickname", uid)),
            "page": next_page if continue_history else 1,
        })

    with _state_lock:
        if _state["running"]:
            return {"status": "busy", "current": _copy_state_unlocked()}
        _cancel_event.clear()
        _state.update({
            "running": True,
            "total": len(queue),
            "done": 0,
            "current_up": "",
            "current_up_id": "",
            "current_page": 0,
            "max_pages": max_pages,
            "added_total": 0,
            "errors": 0,
            "cancel_requested": False,
            "cancelled": False,
            "started_at": _now(),
            "finished_at": "",
            "results": [],
        })
    Thread(
        target=_run_batch,
        args=(queue, max_pages, max_new_videos, limit, continue_history),
        name="biliup-video-sync",
        daemon=True,
    ).start()
    return {"status": "started", "total": len(queue)}


def _run_batch(
    queue: list[dict[str, object]],
    max_pages: int,
    max_new_videos: int,
    limit: int,
    continue_history: bool,
) -> None:
    try:
        for item in queue:
            if _cancel_event.is_set():
                break
            uid = item["up_id"]
            nickname = item["nickname"]
            page = int(item["page"])
            _set(current_up=nickname, current_up_id=uid, current_page=0)
            completed = False
            try:
                page_size = 0

                def record_page(_current_page: int, size: int) -> None:
                    nonlocal page_size
                    page_size = size

                _, added, pages = refresh_up_videos_with_stats(
                    uid,
                    page=page,
                    limit=limit,
                    max_pages=max_pages,
                    max_new_videos=max_new_videos,
                    on_page=lambda current_page: _set(current_page=current_page),
                    on_page_result=record_page,
                    cancel_event=_cancel_event,
                )
                if continue_history:
                    set_next_sync_page(
                        uid,
                        1 if page_size < limit else page + pages,
                        knowledge_base_root() / "UpList",
                    )
                with _state_lock:
                    results = list(_state["results"])
                    results.append({
                        "up_id": uid,
                        "nickname": nickname,
                        "added": added,
                        "pages": pages,
                        "status": "ok",
                    })
                    _state["results"] = results
                    _state["added_total"] = int(_state["added_total"]) + added
                completed = True
            except OpenCliCancelledError:
                with _state_lock:
                    results = list(_state["results"])
                    results.append({
                        "up_id": uid,
                        "nickname": nickname,
                        "status": "cancelled",
                    })
                    _state["results"] = results
                break
            except Exception as exc:
                with _state_lock:
                    results = list(_state["results"])
                    results.append({
                        "up_id": uid,
                        "nickname": nickname,
                        "status": "error",
                        "error": str(exc),
                    })
                    _state["results"] = results
                    _state["errors"] = int(_state["errors"]) + 1
                completed = True
            finally:
                if completed:
                    with _state_lock:
                        _state["done"] = int(_state["done"]) + 1
    finally:
        _set(
            running=False,
            current_up="",
            current_up_id="",
            current_page=0,
            cancel_requested=False,
            cancelled=_cancel_event.is_set(),
            finished_at=_now(),
        )


def batch_sync_progress() -> dict[str, object]:
    return _snapshot()


def request_batch_sync_cancel() -> dict[str, object]:
    with _state_lock:
        if not _state["running"]:
            return {"status": "idle", "current": _copy_state_unlocked()}
        _cancel_event.set()
        _state["cancel_requested"] = True
        return {"status": "stopping", "current": _copy_state_unlocked()}
