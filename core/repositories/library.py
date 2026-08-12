"""本地视频库的 JSONL repository。

只有确认文件真实存在且大小大于零时，才写入
``SortedMp4/<UP名称>/videos.jsonl``。视频文件路径相对知识库根目录保存。
"""

from datetime import datetime
import json
import os
import tempfile
from pathlib import Path

from core.download_files import has_cover_image
from core.repositories.videos import safe_video_directory_name


def _timestamp() -> str:
    return datetime.now().astimezone().isoformat()


def _normalize_date(value: object) -> str:
    digits = "".join(character for character in str(value or "") if character.isdigit())
    return digits[:8] if len(digits) >= 8 else digits


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


def library_up_dir(root: Path, nickname: str, uid: str = "unknown-up") -> Path:
    return root / "SortedMp4" / safe_video_directory_name(nickname, uid)


def library_videos_path(root: Path, nickname: str, uid: str = "unknown-up") -> Path:
    return library_up_dir(root, nickname, uid) / "videos.jsonl"


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


def _matches(row: dict, *, bvid: str = "", title: str = "", date: str = "") -> bool:
    if bvid and str(row.get("bvid", "")).upper() == bvid.upper():
        return True
    return _normalize_date(row.get("date")) == _normalize_date(date) and str(row.get("title", "")).strip() == str(title).strip()


def _serialize(rows: list[dict]) -> str:
    rows.sort(key=lambda row: _normalize_date(row.get("date")), reverse=True)
    output: list[str] = []
    for index, row in enumerate(rows, 1):
        row["index"] = index
        output.append(json.dumps(row, ensure_ascii=False) + "\n")
    return "".join(output)


def list_local_videos(root: Path, nickname: str, uid: str = "unknown-up") -> list[dict]:
    return _load(library_videos_path(root, nickname, uid))


def find_local_video(root: Path, nickname: str, *, bvid: str = "", title: str = "", date: str = "", uid: str = "unknown-up") -> dict | None:
    for row in list_local_videos(root, nickname, uid):
        if not _matches(row, bvid=bvid, title=title, date=date):
            continue
        relative_path = str(row.get("relative_path", ""))
        target = root / relative_path
        if target.is_file() and target.stat().st_size > 0:
            return dict(row)
    return None


def find_other_video(root: Path, *, bvid: str = "", title: str = "", date: str = "") -> dict | None:
    """查找 ``OtherVideos`` 索引中仍存在的单视频。"""
    index_path = root / "OtherVideos" / "videos.jsonl"
    for row in _load(index_path):
        if not _matches(row, bvid=bvid, title=title, date=date):
            continue
        relative_path = str(row.get("relative_path", ""))
        target = root / relative_path
        if target.is_file() and target.stat().st_size > 0:
            return dict(row)
    return None


def record_download(
    root: Path,
    nickname: str,
    video_path: Path,
    *,
    bvid: str,
    title: str,
    date: str,
    transcript: bool,
    uid: str = "unknown-up",
) -> dict:
    """登记一个已确认存在的本地视频。"""
    return _record_download(
        library_videos_path(root, nickname, uid),
        root,
        video_path,
        bvid=bvid,
        title=title,
        date=date,
        transcript=transcript,
    )


def record_other_download(
    root: Path,
    video_path: Path,
    *,
    bvid: str,
    title: str,
    date: str,
    transcript: bool,
) -> dict:
    """登记保存到 ``OtherVideos`` 的单视频。"""
    return _record_download(
        root / "OtherVideos" / "videos.jsonl",
        root,
        video_path,
        bvid=bvid,
        title=title,
        date=date,
        transcript=transcript,
    )


def _record_download(
    index_path: Path,
    root: Path,
    video_path: Path,
    *,
    bvid: str,
    title: str,
    date: str,
    transcript: bool,
) -> dict:
    if not video_path.is_file() or video_path.stat().st_size <= 0:
        raise FileNotFoundError(f"下载文件不存在：{video_path}")
    rows = _load(index_path)
    relative_path = video_path.relative_to(root).as_posix()
    entry = {
        "bvid": str(bvid),
        "date": _normalize_date(date),
        "title": str(title),
        "relative_path": relative_path,
        "original_filename": video_path.name,
        "size_bytes": video_path.stat().st_size,
        "transcript": bool(transcript),
        "cover": has_cover_image(video_path, bvid),
        "scanned_at": _timestamp(),
    }
    for index, row in enumerate(rows):
        if _matches(row, bvid=bvid, title=title, date=date):
            entry["index"] = row.get("index", 0)
            rows[index] = entry
            break
    else:
        rows.append(entry)
    _write_atomically(index_path, _serialize(rows))
    return entry


def set_transcript(
    root: Path,
    nickname: str,
    *,
    bvid: str,
    title: str = "",
    date: str = "",
    transcript: bool,
    uid: str = "unknown-up",
) -> dict | None:
    """更新本地视频索引中的字幕脚本状态。"""
    index_path = library_videos_path(root, nickname, uid)
    rows = _load(index_path)
    for row in rows:
        if not _matches(row, bvid=bvid, title=title, date=date):
            continue
        if row.get("transcript") == bool(transcript):
            return dict(row)
        row["transcript"] = bool(transcript)
        _write_atomically(index_path, _serialize(rows))
        return dict(row)
    return None


def index_existing_videos(
    root: Path,
    nickname: str,
    candidates: list[dict],
    *,
    uid: str = "unknown-up",
) -> int:
    """将已存在且有网站元数据对应的视频补入本地索引。"""
    index_path = library_videos_path(root, nickname, uid)
    rows = _load(index_path)
    added = 0
    changed = False
    for candidate in candidates:
        video_path = Path(candidate.get("path", ""))
        if not video_path.is_file() or video_path.stat().st_size <= 0:
            continue
        relative_path = video_path.relative_to(root).as_posix()
        existing = next((
            row for row in rows
            if relative_path == str(row.get("relative_path", ""))
            or _matches(
                row,
                bvid=str(candidate.get("bvid", "")),
                title=str(candidate.get("title", "")),
                date=str(candidate.get("date", "")),
            )
        ), None)
        transcript = video_path.with_name(video_path.stem + "__transcript.md").is_file()
        cover = has_cover_image(video_path, str(candidate.get("bvid", "")))
        if existing is not None:
            if existing.get("transcript") != transcript or existing.get("cover") != cover:
                existing["transcript"] = transcript
                existing["cover"] = cover
                changed = True
            continue
        rows.append(
            {
                "bvid": str(candidate.get("bvid", "")),
                "date": _normalize_date(candidate.get("date", "")),
                "title": str(candidate.get("title", "")),
                "relative_path": relative_path,
                "original_filename": video_path.name,
                "size_bytes": video_path.stat().st_size,
                "transcript": transcript,
                "cover": cover,
                "scanned_at": _timestamp(),
            }
        )
        added += 1
    if added or changed:
        _write_atomically(index_path, _serialize(rows))
    return added
