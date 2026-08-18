from datetime import datetime, timedelta
from pathlib import Path
from threading import Event, Lock, Thread

from core.download_files import VIDEO_SUFFIXES


_progress: dict[str, dict[str, object]] = {}
_progress_lock = Lock()
_terminal_statuses = {"success", "failed", "cancelled"}
_video_suffixes = VIDEO_SUFFIXES | {".part"}


def now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def set_progress(bvid: str, **values: object) -> dict[str, object]:
    key = str(bvid).upper()
    with _progress_lock:
        current = _progress.setdefault(key, {"bvid": str(bvid), "status": "queued"})
        current.update(values)
        return dict(current)


def get_progress(bvid: str) -> dict[str, object]:
    key = str(bvid).upper()
    with _progress_lock:
        return dict(_progress.get(key, {}))


def _download_size(directory: Path, bvid: str, before: set[Path]) -> int:
    try:
        files = [
            path for path in directory.iterdir()
            if path.is_file() and path.suffix.lower() in _video_suffixes
        ]
    except OSError:
        return 0
    key = str(bvid).lower()
    current_files = [path for path in files if key in path.name.lower() or path not in before]
    total = 0
    for path in current_files:
        try:
            total += path.stat().st_size
        except OSError:
            continue
    return total


def watch_download_size(
    bvid: str,
    directory: Path,
    before: set[Path],
    stop_event: Event,
    interval: float = 0.5,
) -> Thread:
    def watch() -> None:
        while not stop_event.wait(interval):
            size_bytes = _download_size(directory, bvid, before)
            if size_bytes:
                set_progress(bvid, size_bytes=size_bytes)

    thread = Thread(target=watch, name=f"biliup-progress-{str(bvid).upper()}", daemon=True)
    thread.start()
    return thread


def progress_rows(bvids: list[str] | None = None, max_age_minutes: int = 30) -> list[dict[str, object]]:
    selected = {str(value).upper() for value in bvids or []}
    now = datetime.now().astimezone()
    stale: list[str] = []
    with _progress_lock:
        rows = []
        for key, value in _progress.items():
            if selected and key not in selected:
                continue
            if value.get("status") in _terminal_statuses:
                timestamp = value.get("finished_at") or value.get("started_at")
                try:
                    finished = datetime.fromisoformat(str(timestamp))
                except (TypeError, ValueError):
                    finished = now
                if now - finished > timedelta(minutes=max_age_minutes):
                    stale.append(key)
                    continue
            rows.append(dict(value))
        for key in stale:
            _progress.pop(key, None)
    return rows


def active_progress_count(rows: list[dict[str, object]]) -> int:
    return sum(1 for row in rows if row.get("status") in {"queued", "downloading"})
