import json
import re

from core.utils.system.process import run_opencli


class OpenCliSearchError(RuntimeError):
    pass


def _uid_from_url(value: object) -> str:
    match = re.search(r"space\.bilibili\.com/(\d+)", str(value or ""))
    return match.group(1) if match else ""


def _parse_items(output: str) -> list[dict[str, str]]:
    try:
        data = json.loads(output)
    except json.JSONDecodeError as exc:
        raise OpenCliSearchError("OpenCLI 返回的数据无法解析") from exc
    if not isinstance(data, list):
        raise OpenCliSearchError("OpenCLI 返回的数据格式不正确")
    results = []
    for item in data:
        if not isinstance(item, dict):
            continue
        uid = _uid_from_url(item.get("url"))
        nickname = str(item.get("title") or item.get("nickname") or "").strip()
        if not uid or not nickname:
            continue
        results.append({"uid": uid, "nickname": nickname, "bio": str(item.get("author") or item.get("bio") or "").strip() or "-"})
    return results


def search_up(nickname: str) -> list[dict[str, str]]:
    try:
        result = run_opencli(["bilibili", "search", nickname, "--type", "user", "-f", "json"], timeout=30)
    except FileNotFoundError as exc:
        raise OpenCliSearchError("未找到 OpenCLI，请先安装并配置 OpenCLI") from exc
    except TimeoutError as exc:
        raise OpenCliSearchError("UP 主搜索超时，请重试") from exc
    if result.returncode != 0:
        raise OpenCliSearchError("UP 主搜索失败，请确认 OpenCLI 已连接到 B 站")
    return _parse_items(result.stdout)
