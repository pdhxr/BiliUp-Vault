from pathlib import Path

from core.configuration import KnowledgeBaseConfigurationError, configure_knowledge_base, knowledge_base_root
from core.utils.system.directories import DirectoryPickerError, choose_directory


def setup_status() -> dict[str, object]:
    try:
        knowledge_base_root()
    except KnowledgeBaseConfigurationError as exc:
        return {"configured": False, "message": str(exc)}
    return {"configured": True, "message": "视频知识库目录已设置"}


def choose_and_configure_library() -> Path | None:
    try:
        selected = choose_directory()
    except DirectoryPickerError as exc:
        raise KnowledgeBaseConfigurationError("无法打开目录选择器") from exc
    if selected is None:
        return None
    return configure_knowledge_base(selected)
