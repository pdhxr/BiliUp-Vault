from pathlib import Path

from core.configuration import (
    KnowledgeBaseConfigurationError,
    batch_track_since_date,
    configure_knowledge_base,
    knowledge_base_root,
    set_batch_track_since_date,
)
from core.utils.system.directories import DirectoryPickerError, choose_directory


def setup_status() -> dict[str, object]:
    try:
        root = knowledge_base_root()
    except KnowledgeBaseConfigurationError as exc:
        return {"configured": False, "message": str(exc)}
    return {
        "configured": True,
        "message": "视频知识库目录已设置",
        "knowledge_base_root": str(root),
    }


def choose_and_configure_library() -> Path | None:
    try:
        selected = choose_directory()
    except DirectoryPickerError as exc:
        raise KnowledgeBaseConfigurationError("无法打开目录选择器") from exc
    if selected is None:
        return None
    return configure_knowledge_base(selected)


def batch_track_settings() -> dict[str, str]:
    return {"since_date": batch_track_since_date()}


def save_batch_track_settings(since_date: str) -> dict[str, str]:
    return {"since_date": set_batch_track_since_date(since_date)}
