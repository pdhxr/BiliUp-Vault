from datetime import datetime
from threading import Lock, Thread

from core.configuration import knowledge_base_root
from core.repositories.followings import find
from core.video_errors import FollowingNotFoundError
from core.video_sync import refresh_up_videos_with_stats


_state: dict[str, object] = {
    "running": False,
    "total": 0,
    "done": 0,
    "current_up": "",
    "current_up_id": "",
    "added_total": 0,
    "errors": 0,
    "started_at": "",
    "finished_at": "",
    "results": [],
}
_state_lock = Lock()


def _now() -> str:
    return datetime.now().astimezone().isoformat()


def _copy_state() -> dict[str, object]:
    return {key: (list(value) if key == "results" else value) for key, value in _state.items()}


def _snapshot() -> dict[str, object]:
    with _state_lock:
        return _copy_state()


def _set(**values: object) -> None:
    with _state_lock:
        _state.update(values)


def start_batch_sync(up_ids: list[str]) -> dict[str, object]:
    ids = list(dict.fromkeys(str(value).strip() for value in up_ids if str(value).strip()))
    if not ids:
        raise ValueError("至少选择一个 UP 主")
    with _state_lock:
        if _state["running"]:
            return {"status": "busy", "current": _copy_state()}

    root = knowledge_base_root()
    queue: list[dict[str, str]] = []
    for uid in ids:
        following = find(uid, root / "UpList")
        if following is None:
            raise FollowingNotFoundError(f"未找到 UP {uid}")
        queue.append({"up_id": uid, "nickname": str(following.get("nickname", uid))})

    with _state_lock:
        if _state["running"]:
            return {"status": "busy", "current": _copy_state()}
        _state.update({
            "running": True,
            "total": len(queue),
            "done": 0,
            "current_up": "",
            "current_up_id": "",
            "added_total": 0,
            "errors": 0,
            "started_at": _now(),
            "finished_at": "",
            "results": [],
        })
    Thread(target=_run_batch, args=(queue,), name="biliup-video-sync", daemon=True).start()
    return {"status": "started", "total": len(queue)}


def _run_batch(queue: list[dict[str, str]]) -> None:
    try:
        for item in queue:
            uid = item["up_id"]
            nickname = item["nickname"]
            _set(current_up=nickname, current_up_id=uid)
            try:
                _, added, pages = refresh_up_videos_with_stats(uid)
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
            finally:
                with _state_lock:
                    _state["done"] = int(_state["done"]) + 1
    finally:
        _set(running=False, current_up="", current_up_id="", finished_at=_now())


def batch_sync_progress() -> dict[str, object]:
    return _snapshot()
