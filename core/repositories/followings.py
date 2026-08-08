import json
import os
import tempfile
import threading
from datetime import datetime
from pathlib import Path


_lock = threading.RLock()
_fields = ("uid", "nickname", "bio", "scheduled_tracking", "created_at", "last_sync_at")


def _timestamp() -> str:
    return datetime.now().astimezone().isoformat()


def _one_line(value: object) -> str:
    return " ".join(str(value or "").split()) or "-"


def _markdown_value(value: object) -> str:
    return _one_line(value).replace("|", "\\|")


def _write_atomically(path: Path, content: str) -> None:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    try:
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("followings.json 必须是数组")
    return [item for item in data if isinstance(item, dict)]


def _markdown(rows: list[dict]) -> str:
    lines = ["| 序号 | 昵称 | UP ID | 简介 |", "|------|-----------|-----|------|"]
    for index, row in enumerate(rows, 1):
        lines.append(f"| {index} | {_markdown_value(row.get('nickname'))} | {_markdown_value(row.get('uid'))} | {_markdown_value(row.get('bio'))} |")
    return "\n".join(lines) + "\n"


def list_rows(root: Path = Path("UpList")) -> list[dict[str, object]]:
    """读取 UpList 登记数据，并转换为 UP 管理列表所需的行。"""
    rows = _load(root / "followings.json")
    result: list[dict[str, object]] = []
    for row in rows:
        result.append(
            {
                "up_id": str(row.get("uid", "")),
                "nickname": _one_line(row.get("nickname")),
                "bio": _one_line(row.get("bio")),
                "last_sync_time": str(row.get("last_sync_at", "")),
                "total_count": int(row.get("total_count", 0) or 0),
                "synced_count": int(row.get("synced_count", 0) or 0),
                "downloaded_count": int(row.get("downloaded_count", 0) or 0),
                "scheduled_tracking": bool(row.get("scheduled_tracking", False)),
            }
        )
    return result


def find(uid: str, root: Path = Path("UpList")) -> dict | None:
    """按 UID 读取一条已登记 UP 主记录。"""
    normalized_uid = str(uid).strip()
    return next((row for row in _load(root / "followings.json") if str(row.get("uid")) == normalized_uid), None)


def update_video_stats(
    uid: str,
    *,
    total_count: int,
    synced_count: int,
    downloaded_count: int,
    last_sync_at: str,
    root: Path = Path("UpList"),
) -> dict:
    """把视频刷新结果的统计写回 followings.json。"""
    json_path = root / "followings.json"
    markdown_path = root / "bilibili-up-followings.md"
    with _lock:
        rows = _load(json_path)
        normalized_uid = str(uid).strip()
        for row in rows:
            if str(row.get("uid")) != normalized_uid:
                continue
            row["total_count"] = max(0, int(total_count))
            row["synced_count"] = max(0, int(synced_count))
            row["downloaded_count"] = max(0, int(downloaded_count))
            row["last_sync_at"] = last_sync_at
            _write_atomically(json_path, json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
            _write_atomically(markdown_path, _markdown(rows))
            return row
    raise ValueError(f"未找到 UP {normalized_uid}")


def set_next_sync_page(uid: str, page: int, root: Path = Path("UpList")) -> dict:
    """保存手动同步的下一页游标，不暴露到管理列表。"""
    json_path = root / "followings.json"
    markdown_path = root / "bilibili-up-followings.md"
    normalized_uid = str(uid).strip()
    with _lock:
        rows = _load(json_path)
        for row in rows:
            if str(row.get("uid")) != normalized_uid:
                continue
            row["next_sync_page"] = max(1, int(page))
            _write_atomically(json_path, json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
            _write_atomically(markdown_path, _markdown(rows))
            return row
    raise ValueError(f"未找到 UP {normalized_uid}")


def set_scheduled_tracking(uid: str, enabled: bool, root: Path = Path("UpList")) -> dict:
    """更新 UP 主是否参与批量自动追踪下载。"""
    json_path = root / "followings.json"
    markdown_path = root / "bilibili-up-followings.md"
    normalized_uid = str(uid).strip()
    with _lock:
        rows = _load(json_path)
        for row in rows:
            if str(row.get("uid")) != normalized_uid:
                continue
            row["scheduled_tracking"] = bool(enabled)
            _write_atomically(json_path, json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
            _write_atomically(markdown_path, _markdown(rows))
            return row
    raise ValueError(f"未找到 UP {normalized_uid}")


def save(uid: str, nickname: str, bio: str, root: Path = Path("UpList")) -> tuple[dict, str]:
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / "followings.json"
    markdown_path = root / "bilibili-up-followings.md"
    with _lock:
        rows = _load(json_path)
        normalized_uid = str(uid).strip()
        normalized_nickname = _one_line(nickname)
        normalized_bio = _one_line(bio)
        for row in rows:
            if str(row.get("uid")) == normalized_uid:
                row["nickname"] = normalized_nickname
                row["bio"] = normalized_bio
                row.setdefault("scheduled_tracking", True)
                row.setdefault("total_count", 0)
                row.setdefault("synced_count", 0)
                row.setdefault("downloaded_count", 0)
                row.setdefault("next_sync_page", 1)
                _write_atomically(json_path, json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
                _write_atomically(markdown_path, _markdown(rows))
                return row, "updated"
        now = _timestamp()
        record = dict(zip(_fields, (normalized_uid, normalized_nickname, normalized_bio, True, now, now)))
        record.update({"total_count": 0, "synced_count": 0, "downloaded_count": 0, "next_sync_page": 1})
        rows.append(record)
        _write_atomically(json_path, json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
        _write_atomically(markdown_path, _markdown(rows))
        return record, "created"


def delete(root: Path, uids: list[str]) -> list[dict]:
    """删除登记记录并重建派生 Markdown；不触碰视频文件。"""
    json_path = root / "followings.json"
    markdown_path = root / "bilibili-up-followings.md"
    normalized_uids = {str(uid).strip() for uid in uids if str(uid).strip()}
    if not normalized_uids:
        return []
    with _lock:
        rows = _load(json_path)
        deleted = [row for row in rows if str(row.get("uid", "")).strip() in normalized_uids]
        if not deleted:
            return []
        remaining = [row for row in rows if str(row.get("uid", "")).strip() not in normalized_uids]
        _write_atomically(json_path, json.dumps(remaining, ensure_ascii=False, indent=2) + "\n")
        _write_atomically(markdown_path, _markdown(remaining))
        return deleted
