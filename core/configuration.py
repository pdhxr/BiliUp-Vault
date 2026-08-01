import json
import os
import tempfile
from pathlib import Path

from core.utils.system.directories import application_config_directory


class KnowledgeBaseConfigurationError(RuntimeError):
    pass


def configuration_file() -> Path:
    return application_config_directory() / "config.json"


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


def _ensure_writable(directory: Path) -> None:
    if not directory.is_dir():
        raise KnowledgeBaseConfigurationError("请选择一个已存在的目录")
    try:
        with tempfile.NamedTemporaryFile(dir=directory, delete=True):
            pass
    except OSError as exc:
        raise KnowledgeBaseConfigurationError("所选目录不可写，请重新选择") from exc


def configure_knowledge_base(directory: Path, config_file: Path | None = None) -> Path:
    root = directory.expanduser().resolve()
    _ensure_writable(root)
    target = config_file or configuration_file()
    _write_atomically(target, json.dumps({"version": 1, "knowledge_base_root": str(root)}, ensure_ascii=False, indent=2) + "\n")
    return root


def knowledge_base_root(config_file: Path | None = None) -> Path:
    target = config_file or configuration_file()
    if not target.is_file():
        raise KnowledgeBaseConfigurationError("请先选择视频知识库目录")
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        root = Path(str(data["knowledge_base_root"]))
    except (json.JSONDecodeError, KeyError, TypeError, OSError) as exc:
        raise KnowledgeBaseConfigurationError("视频知识库配置无效，请重新选择目录") from exc
    _ensure_writable(root)
    return root
