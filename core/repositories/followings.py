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
                _write_atomically(json_path, json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
                _write_atomically(markdown_path, _markdown(rows))
                return row, "updated"
        now = _timestamp()
        record = dict(zip(_fields, (normalized_uid, normalized_nickname, normalized_bio, True, now, now)))
        rows.append(record)
        _write_atomically(json_path, json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
        _write_atomically(markdown_path, _markdown(rows))
        return record, "created"
