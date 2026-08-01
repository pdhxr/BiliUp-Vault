"""下载文件的发现、临时文件清理和命名操作。"""

from pathlib import Path

from core.repositories.videos import safe_video_directory_name


VIDEO_SUFFIXES = {".mp4", ".mkv", ".flv", ".webm"}


def directory_snapshot(directory: Path) -> set[Path]:
    """返回下载前目录快照，供识别本次新生成的文件。"""
    return set(directory.iterdir())


def find_video_file(directory: Path, bvid: str, before: set[Path]) -> Path | None:
    """查找 OpenCLI 生成的最终视频文件。

    OpenCLI/yt-dlp 的最终文件名通常包含 BV 号，但合并后的文件名也可能
    只保留视频标题，因此同时兼容 BV 号匹配和本次新文件匹配。`.part`
    文件明确排除，避免把未完成下载登记为成功。
    """
    try:
        files = [
            path for path in directory.iterdir()
            if path.is_file() and path.suffix.lower() in VIDEO_SUFFIXES
        ]
    except OSError:
        return None

    def usable(path: Path) -> bool:
        try:
            return path.stat().st_size > 0
        except OSError:
            return False

    files = [path for path in files if usable(path)]
    key = str(bvid).lower()
    matching = [path for path in files if key in path.name.lower()]
    if matching:
        return max(matching, key=lambda path: path.stat().st_mtime)
    new_files = [path for path in files if path not in before]
    return max(new_files, key=lambda path: path.stat().st_mtime) if new_files else None


def remove_partial_files(directory: Path, bvid: str) -> None:
    """清理指定 BV 号的未完成分片，为下一次重试准备目录。"""
    key = str(bvid).lower()
    try:
        paths = list(directory.iterdir())
    except OSError:
        return
    for path in paths:
        if not path.is_file() or path.suffix.lower() != ".part" or key not in path.name.lower():
            continue
        try:
            path.unlink()
        except OSError:
            continue


def expected_video_name(nickname: str, uid: str, title: str, date: str, suffix: str = ".mp4") -> str:
    safe_nickname = safe_video_directory_name(nickname, uid)
    safe_date = str(date).replace("-", "") or "unknown-date"
    safe_title = safe_video_directory_name(title, "video")[:160]
    return f"{safe_nickname}_{safe_date}_{safe_title}{suffix.lower()}"


def rename_video(source: Path, directory: Path, nickname: str, uid: str, title: str, date: str) -> Path:
    """按知识库约定重命名视频，并返回最终路径。"""
    target = directory / expected_video_name(nickname, uid, title, date, source.suffix)
    if source == target:
        return target
    if target.exists():
        source.unlink()
        return target
    source.replace(target)
    return target
