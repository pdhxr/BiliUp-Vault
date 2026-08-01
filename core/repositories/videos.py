"""B 站远端视频追踪清单的 JSONL repository。

这里对应参考项目的 ``UpList/<UP>.jsonl``，只记录网站元数据和追踪状态；
本地硬盘视频索引由 ``core.repositories.library`` 独立维护。
"""

import json
import os
import re
import tempfile
from pathlib import Path


def video_path(root: Path, nickname: str) -> Path:
    """返回远端追踪清单路径：``UpList/<UP名称>.jsonl``。"""
    filename = safe_video_directory_name(str(nickname).strip(), "unknown-up")
    return root / f"{filename}.jsonl"


def _write_atomically(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    try:
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _normalize_date(value: object) -> str:
    text = str(value or "").strip().replace("/", "-")
    if re.fullmatch(r"\d{8}", text):
        return text
    return text[:10] if len(text) >= 10 and text[4] == "-" else text


def _load(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def _sorted(rows: list[dict]) -> list[dict]:
    rows.sort(key=lambda row: str(row.get("date", row.get("pub_time", ""))), reverse=True)
    for index, row in enumerate(rows, 1):
        row["index"] = index
    return rows


def _public(row: dict) -> dict:
    result = dict(row)
    result["pub_time"] = result.get("date", result.get("pub_time", ""))
    return result


def list_videos(root: Path, nickname: str) -> list[dict]:
    return [_public(row) for row in _sorted(_load(video_path(root, nickname)))]


def merge_videos(root: Path, nickname: str, incoming: list[dict]) -> list[dict]:
    path = video_path(root, nickname)
    existing = {
        str(row.get("bvid", "")).strip().upper(): row
        for row in _load(path)
        if str(row.get("bvid", "")).strip()
    }
    for item in incoming:
        bvid = str(item.get("bvid", "")).strip()
        if not bvid:
            continue
        key = bvid.upper()
        previous = existing.get(key, {})
        date = _normalize_date(item.get("date") or item.get("pub_time") or previous.get("date"))
        title = str(item.get("title", previous.get("title", ""))).strip()
        existing[key] = {
            "index": previous.get("index", 0),
            "date": date,
            "title": title,
            "bvid": bvid,
            "url": str(item.get("url", previous.get("url", ""))),
            "downloaded": bool(previous.get("downloaded", False)),
            "transcript": bool(previous.get("transcript", False)),
            "local_filename": str(previous.get("local_filename", previous.get("file_path", ""))),
        }
    rows = _sorted(list(existing.values()))
    _write_atomically(path, "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))
    return [_public(row) for row in rows]


def mark_downloaded(
    root: Path,
    nickname: str,
    bvid: str,
    file_path: str,
    *,
    transcript: bool | None = None,
) -> list[dict]:
    """更新远端追踪项的下载状态，不写本地视频库字段。"""
    path = video_path(root, nickname)
    rows = _load(path)
    target = next((row for row in rows if str(row.get("bvid", "")).upper() == str(bvid).upper()), None)
    if target is None:
        raise ValueError(f"未找到视频 {bvid}")
    target["downloaded"] = True
    target["local_filename"] = Path(file_path).name
    if transcript is not None:
        target["transcript"] = bool(transcript)
    _write_atomically(path, "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in _sorted(rows)))
    return list_videos(root, nickname)


def mark_transcript(root: Path, nickname: str, bvid: str, transcript: bool) -> list[dict]:
    """更新远端追踪清单中的字幕脚本状态。"""
    path = video_path(root, nickname)
    rows = _load(path)
    target = next((row for row in rows if str(row.get("bvid", "")).upper() == str(bvid).upper()), None)
    if target is None:
        raise ValueError(f"未找到视频 {bvid}")
    target["transcript"] = bool(transcript)
    _write_atomically(path, "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in _sorted(rows)))
    return list_videos(root, nickname)


def reconcile_downloaded(root: Path, nickname: str, local_lookup) -> list[dict]:
    """用本地视频库事实校准远端清单的下载状态。"""
    path = video_path(root, nickname)
    rows = _load(path)
    changed = False
    for row in rows:
        local = local_lookup(row)
        downloaded = bool(local)
        transcript = bool(local.get("transcript", False)) if local else False
        filename = str(local.get("original_filename", "")) if local else ""
        if (
            row.get("downloaded") != downloaded
            or row.get("transcript", False) != transcript
            or row.get("local_filename", "") != filename
        ):
            row["downloaded"] = downloaded
            row["transcript"] = transcript
            row["local_filename"] = filename
            changed = True
    if changed:
        _write_atomically(path, "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in _sorted(rows)))
    return list_videos(root, nickname)


def downloaded_count(rows: list[dict]) -> int:
    return sum(1 for row in rows if row.get("downloaded"))


def safe_video_directory_name(value: str, fallback: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(value).strip()).strip(" .")
    return cleaned or fallback
