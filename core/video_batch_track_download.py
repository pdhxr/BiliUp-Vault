"""批量追踪并下载任务编排。

这里串联两个已有用例：先按截止日期增量同步各个 UP，再下载期限内所有尚未下载的视频。
路由层和静态网页层只通过状态快照与本模块交互。
"""

from datetime import datetime
from threading import Lock, Thread
import time

from core.configuration import batch_track_since_date, knowledge_base_root
from core.download_progress import get_progress
from core.repositories.followings import find
from core.video_download import queue_downloads
from core.video_errors import FollowingNotFoundError
from core.subtitle_download import queue_missing_subtitles_for_up
from core.video_cover_backfill import backfill_covers_for_up
from core.video_sync import refresh_up_videos_with_details


_state: dict[str, object] = {
    "running": False,
    "phase": "idle",
    "total": 0,
    "done": 0,
    "current_up": "",
    "current_up_id": "",
    "since_date": "",
    "added_total": 0,
    "download_total": 0,
    "download_done": 0,
    "download_failed": 0,
    "subtitle_queued": 0,
    "cover_total": 0,
    "cover_done": 0,
    "cover_succeeded": 0,
    "cover_failed": 0,
    "errors": 0,
    "started_at": "",
    "finished_at": "",
    "results": [],
}
_state_lock = Lock()
_cancel_requested = False
_DOWNLOAD_WAIT_SECONDS = 7200


def _now() -> str:
    return datetime.now().astimezone().isoformat()


def _date_key(value: object) -> str:
    return "".join(character for character in str(value or "") if character.isdigit())[:8]


def _copy_state_unlocked() -> dict[str, object]:
    return {
        key: [dict(item) if isinstance(item, dict) else item for item in value]
        if key == "results" and isinstance(value, list)
        else value
        for key, value in _state.items()
    }


def _copy_state() -> dict[str, object]:
    with _state_lock:
        return _copy_state_unlocked()


def _set(**values: object) -> None:
    with _state_lock:
        _state.update(values)


def _append_error(result: dict[str, object], message: str) -> None:
    result["status"] = "error"
    result["error"] = message
    with _state_lock:
        _state["errors"] = int(_state["errors"]) + 1


def _pending_download_videos(rows: object, since_date: str) -> list[dict[str, str]]:
    """筛选期限内仍未下载的视频，作为本次批量下载清单。"""
    if not isinstance(rows, list):
        return []
    pending: list[dict[str, str]] = []
    for video in rows:
        if not isinstance(video, dict) or bool(video.get("downloaded", False)):
            continue
        bvid = str(video.get("bvid", "")).strip()
        video_date = _date_key(video.get("date") or video.get("pub_time"))
        if not bvid or not video_date or (since_date and video_date < since_date):
            continue
        pending.append({
            "bvid": bvid,
            "title": str(video.get("title", "")),
            "date": str(video.get("date") or video.get("pub_time") or ""),
        })
    return pending


def start_batch_track_download(up_ids: list[str], since_date: str = "") -> dict[str, object]:
    """启动后台批量追踪下载；同一时间只允许一个任务运行。"""
    ids = list(dict.fromkeys(str(value).strip() for value in up_ids if str(value).strip()))
    if not ids:
        raise ValueError("至少选择一个 UP 主")
    configured_since_date = since_date.strip() or batch_track_since_date()
    cutoff = _date_key(configured_since_date)
    if len(cutoff) != 8:
        raise ValueError("请先在视频下载页设置批量追踪起始日期")
    with _state_lock:
        if _state["running"]:
            return {"status": "busy", "current": _copy_state_unlocked()}

    root = knowledge_base_root()
    queue: list[dict[str, str]] = []
    for uid in ids:
        following = find(uid, root / "UpList")
        if following is None:
            raise FollowingNotFoundError(f"未找到 UP {uid}")
        queue.append({"up_id": uid, "nickname": str(following.get("nickname", uid))})

    with _state_lock:
        if _state["running"]:
            return {"status": "busy", "current": _copy_state_unlocked()}
        _state.update({
            "running": True,
            "phase": "tracking",
            "total": len(queue),
            "done": 0,
            "current_up": "",
            "current_up_id": "",
            "since_date": cutoff,
            "added_total": 0,
            "download_total": 0,
            "download_done": 0,
            "download_failed": 0,
            "subtitle_queued": 0,
            "cover_total": 0,
            "cover_done": 0,
            "cover_succeeded": 0,
            "cover_failed": 0,
            "errors": 0,
            "started_at": _now(),
            "finished_at": "",
            "results": [],
        })
    global _cancel_requested
    _cancel_requested = False
    Thread(target=_run, args=(queue, cutoff), name="biliup-track-download", daemon=True).start()
    return {"status": "started", "total": len(queue), "since_date": cutoff}


def _run(queue: list[dict[str, str]], since_date: str) -> None:
    global _cancel_requested
    results: list[dict[str, object]] = []
    try:
        for item in queue:
            uid = item["up_id"]
            nickname = item["nickname"]
            result: dict[str, object] = {
                "up_id": uid,
                "nickname": nickname,
                "added": 0,
                "new_videos": [],
                "pending_videos": [],
                "download_jobs": [],
                "subtitle_jobs": 0,
                "cover_total": 0,
                "cover_succeeded": 0,
                "cover_failed": 0,
                "status": "ok",
            }
            _set(current_up=nickname, current_up_id=uid)
            if _cancel_requested:
                result["status"] = "cancelled"
                results.append(result)
                with _state_lock:
                    _state["results"] = list(results)
                    _state["done"] = int(_state["done"]) + 1
                continue
            try:
                details = refresh_up_videos_with_details(uid, since_date=since_date)
                new_videos = [
                    {
                        "bvid": str(video.get("bvid", "")).strip(),
                        "title": str(video.get("title", "")),
                        "date": str(video.get("date") or video.get("pub_time") or ""),
                    }
                    for video in details["new_videos"]
                    if str(video.get("bvid", "")).strip()
                ]
                result["added"] = len(new_videos)
                result["new_videos"] = new_videos
                result["pending_videos"] = _pending_download_videos(details.get("rows"), since_date)
                with _state_lock:
                    _state["added_total"] = int(_state["added_total"]) + len(new_videos)
            except Exception as exc:
                _append_error(result, str(exc))
            results.append(result)
            with _state_lock:
                _state["results"] = list(results)
                _state["done"] = int(_state["done"]) + 1

        for result in results:
            if result.get("status") != "ok":
                continue
            try:
                subtitle_jobs = queue_missing_subtitles_for_up(
                    str(result["up_id"]),
                    root=knowledge_base_root(),
                )
                result["subtitle_jobs"] = subtitle_jobs
                with _state_lock:
                    _state["subtitle_queued"] = int(_state["subtitle_queued"]) + subtitle_jobs
            except Exception:
                # 字幕是可选附加物，补拉失败不影响视频下载任务。
                result["subtitle_jobs"] = 0

        download_tasks: list[tuple[str, str]] = []
        _set(phase="downloading", current_up="", current_up_id="")
        for result in results:
            if result.get("status") != "ok":
                continue
            videos = result.get("pending_videos", [])
            bvids = [str(video.get("bvid", "")) for video in videos if str(video.get("bvid", ""))]
            if not bvids:
                continue
            uid = str(result["up_id"])
            try:
                jobs = queue_downloads(uid, bvids)
                result["download_jobs"] = jobs
                download_tasks.extend((str(job.get("bvid", "")), uid) for job in jobs if job.get("bvid"))
            except Exception as exc:
                _append_error(result, str(exc))
            with _state_lock:
                _state["results"] = list(results)

        download_bvids = list(dict.fromkeys(bvid for bvid, _ in download_tasks))
        _set(download_total=len(download_bvids))
        _wait_for_downloads(download_bvids)
        for result in results:
            jobs = result.get("download_jobs", [])
            if not isinstance(jobs, list):
                continue
            statuses = [get_progress(str(job.get("bvid", ""))).get("status") for job in jobs]
            if any(status == "failed" for status in statuses):
                result["status"] = "error"
            elif statuses and all(status == "success" for status in statuses):
                result["status"] = "ok"
        _set(results=list(results))

        root = knowledge_base_root()
        _set(phase="covering", current_up="", current_up_id="")
        for result in results:
            if result.get("status") not in {"ok", "error"}:
                continue
            uid = str(result["up_id"])
            _set(current_up=str(result["nickname"]), current_up_id=uid)
            cover_state = _copy_state()
            base_done = int(cover_state.get("cover_done", 0))
            base_total = int(cover_state.get("cover_total", 0))
            base_succeeded = int(cover_state.get("cover_succeeded", 0))
            base_failed = int(cover_state.get("cover_failed", 0))

            def update_cover_progress(done: int, total: int, failed: int) -> None:
                _set(
                    cover_done=base_done + done,
                    cover_total=base_total + total,
                    cover_succeeded=base_succeeded + done - failed,
                    cover_failed=base_failed + failed,
                )

            try:
                cover_result = backfill_covers_for_up(
                    uid,
                    since_date,
                    root=root,
                    on_progress=update_cover_progress,
                )
                result.update({
                    "cover_total": cover_result["total"],
                    "cover_succeeded": cover_result["succeeded"],
                    "cover_failed": cover_result["failed"],
                })
            except Exception as exc:
                result["cover_error"] = str(exc)
                with _state_lock:
                    _state["cover_failed"] = int(_state["cover_failed"]) + 1
            _set(results=list(results))
    finally:
        _set(running=False, phase="completed", current_up="", current_up_id="", finished_at=_now())


def _wait_for_downloads(bvids: list[str]) -> None:
    unique_bvids = list(dict.fromkeys(bvids))
    if not unique_bvids:
        _set(download_done=0, download_failed=0)
        return
    deadline = time.monotonic() + _DOWNLOAD_WAIT_SECONDS
    while time.monotonic() < deadline:
        statuses = [get_progress(bvid).get("status") for bvid in unique_bvids]
        done = sum(status == "success" for status in statuses)
        failed = sum(status == "failed" for status in statuses)
        _set(download_done=done, download_failed=failed)
        if done + failed == len(unique_bvids):
            return
        time.sleep(0.5)
    statuses = [get_progress(bvid).get("status") for bvid in unique_bvids]
    done = sum(status == "success" for status in statuses)
    with _state_lock:
        _state["errors"] = int(_state["errors"]) + 1
    _set(download_done=done, download_failed=len(unique_bvids) - done)


def batch_track_download_progress() -> dict[str, object]:
    return _copy_state()
