import json
import os
import tempfile
from datetime import date, datetime
from pathlib import Path

from core.utils.system.directories import application_config_directory


class KnowledgeBaseConfigurationError(RuntimeError):
    pass


DEFAULT_DESKTOP_PORT = 8765
MIN_DESKTOP_PORT = 1024
MAX_DESKTOP_PORT = 65535


def _normalize_batch_track_since_date(value: object) -> str:
    """把配置中的追踪起始日期统一保存为 HTML date 可读取的格式。"""
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        if len(text) == 8 and text.isdigit():
            return datetime.strptime(text, "%Y%m%d").date().isoformat()
        return date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise KnowledgeBaseConfigurationError("批量追踪起始日期无效，请选择 YYYY-MM-DD 日期") from exc


def configuration_file() -> Path:
    return application_config_directory() / "config.json"


def _read_configuration(target: Path, *, require_library: bool = False) -> dict[str, object]:
    if not target.is_file():
        if require_library:
            raise KnowledgeBaseConfigurationError("请先选择视频知识库目录")
        return {}
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise KnowledgeBaseConfigurationError("视频知识库配置无效，请重新选择目录") from exc
    if not isinstance(data, dict):
        raise KnowledgeBaseConfigurationError("视频知识库配置无效，请重新选择目录")
    if require_library and not data.get("knowledge_base_root"):
        raise KnowledgeBaseConfigurationError("视频知识库配置无效，请重新选择目录")
    return data


def _normalize_desktop_port(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise KnowledgeBaseConfigurationError("桌面端口必须是整数")
    if not MIN_DESKTOP_PORT <= value <= MAX_DESKTOP_PORT:
        raise KnowledgeBaseConfigurationError(f"桌面端口必须在 {MIN_DESKTOP_PORT}–{MAX_DESKTOP_PORT} 之间")
    return value


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
    settings: dict[str, object] = {"version": 1, "batch_track_since_date": ""}
    if target.is_file():
        try:
            settings.update(_read_configuration(target))
        except KnowledgeBaseConfigurationError:
            pass
        try:
            settings["batch_track_since_date"] = _normalize_batch_track_since_date(settings.get("batch_track_since_date"))
        except KnowledgeBaseConfigurationError:
            settings["batch_track_since_date"] = ""
    settings["version"] = 1
    settings["knowledge_base_root"] = str(root)
    _write_atomically(target, json.dumps(settings, ensure_ascii=False, indent=2) + "\n")
    return root


def knowledge_base_root(config_file: Path | None = None) -> Path:
    target = config_file or configuration_file()
    try:
        data = _read_configuration(target, require_library=True)
        root = Path(str(data["knowledge_base_root"]))
    except (KeyError, TypeError) as exc:
        raise KnowledgeBaseConfigurationError("视频知识库配置无效，请重新选择目录") from exc
    _ensure_writable(root)
    return root


def batch_track_since_date(config_file: Path | None = None) -> str:
    """读取批量追踪起始日期；未设置时返回空字符串。"""
    target = config_file or configuration_file()
    try:
        data = _read_configuration(target, require_library=True)
        return _normalize_batch_track_since_date(data.get("batch_track_since_date"))
    except KnowledgeBaseConfigurationError:
        raise
    except (TypeError, ValueError) as exc:
        raise KnowledgeBaseConfigurationError("视频知识库配置无效，请重新选择目录") from exc


def set_batch_track_since_date(value: object, config_file: Path | None = None) -> str:
    """保存批量追踪起始日期，同时保留配置中的其他字段。"""
    target = config_file or configuration_file()
    normalized = _normalize_batch_track_since_date(value)
    data = _read_configuration(target, require_library=True)
    data["batch_track_since_date"] = normalized
    _write_atomically(target, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    return normalized


def desktop_port(config_file: Path | None = None) -> int:
    target = config_file or configuration_file()
    data = _read_configuration(target)
    if "desktop_port" not in data:
        return DEFAULT_DESKTOP_PORT
    return _normalize_desktop_port(data["desktop_port"])


def set_desktop_port(value: object, config_file: Path | None = None) -> int:
    target = config_file or configuration_file()
    normalized = _normalize_desktop_port(value)
    data = _read_configuration(target, require_library=True)
    data["desktop_port"] = normalized
    _write_atomically(target, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    return normalized
