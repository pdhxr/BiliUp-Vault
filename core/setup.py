from pathlib import Path

from core.configuration import (
    KnowledgeBaseConfigurationError,
    batch_track_since_date,
    configuration_file,
    configure_knowledge_base,
    desktop_port,
    knowledge_base_root,
    set_batch_track_since_date,
    set_desktop_port,
)
import os
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


def desktop_settings() -> dict[str, object]:
    configured_port = desktop_port()
    desktop_mode = os.environ.get("BILIUP_DESKTOP") == "1"
    try:
        current_port = int(os.environ.get("BILIUP_CURRENT_PORT", "8765"))
    except ValueError:
        current_port = 8765
    return {
        "desktop_port": configured_port,
        "config_file": str(configuration_file()),
        "current_port": current_port,
        "desktop_mode": desktop_mode,
        "restart_required": desktop_mode and configured_port != current_port,
    }


def save_desktop_settings(value: object) -> dict[str, object]:
    set_desktop_port(value)
    return desktop_settings()
