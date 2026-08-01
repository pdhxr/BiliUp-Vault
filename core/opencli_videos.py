import json
import re
import subprocess

from core.utils.system.process import run_opencli


class OpenCliVideoError(RuntimeError):
    pass


def _parse_json_output(output: str) -> object:
    """从 OpenCLI 输出中提取 JSON，兼容前后带日志或终端控制文本。"""
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        for index, character in enumerate(output):
            if character not in "[{":
                continue
            try:
                value, _ = decoder.raw_decode(output[index:])
                return value
            except json.JSONDecodeError:
                continue
    raise OpenCliVideoError("OpenCLI 返回的数据无法解析")


def _bvid_from_url(value: object) -> str:
    match = re.search(r"/(BV[A-Za-z0-9]+)", str(value or ""))
    return match.group(1) if match else ""


def _items(output: str) -> list[dict]:
    data = _parse_json_output(output)
    if isinstance(data, dict):
        data = data.get("items", data.get("data", []))
    if not isinstance(data, list):
        raise OpenCliVideoError("OpenCLI 返回的视频数据格式不正确")
    result = []
    for item in data:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url", ""))
        bvid = str(item.get("bvid") or item.get("bv_id") or _bvid_from_url(url)).strip()
        title = str(item.get("title") or "").strip()
        if not bvid or not title:
            continue
        result.append(
            {
                "title": title,
                "url": url,
                "bvid": bvid,
                "pub_time": item.get("date") or item.get("pubdate") or "",
                "date": item.get("date") or item.get("pubdate") or "",
            }
        )
    return result


def _subtitle_items(output: str) -> list[dict]:
    data = _parse_json_output(output)
    if isinstance(data, dict):
        for key in ("items", "data", "subtitles", "results"):
            candidate = data.get(key)
            if isinstance(candidate, list):
                data = candidate
                break
    if not isinstance(data, list):
        raise OpenCliVideoError("OpenCLI 返回的字幕数据格式不正确")
    result = []
    for item in data:
        if not isinstance(item, dict):
            continue
        content = str(item.get("content") or item.get("text") or item.get("subtitle") or "").strip()
        if not content:
            continue
        result.append({
            "from": item.get("from", item.get("start", "")),
            "to": item.get("to", item.get("end", "")),
            "content": content,
        })
    return result


def fetch_user_videos(uid: str, *, page: int = 1, limit: int = 50) -> list[dict]:
    try:
        result = run_opencli(
            [
                "bilibili", "user-videos", str(uid), "-f", "json",
                "--limit", str(limit), "--page", str(page), "--window", "background",
            ],
            timeout=120,
        )
    except FileNotFoundError as exc:
        raise OpenCliVideoError("未找到 OpenCLI，请先安装并配置 OpenCLI") from exc
    except subprocess.TimeoutExpired as exc:
        raise OpenCliVideoError("UP 主视频列表获取超时，请重试") from exc
    if result.returncode != 0:
        raise OpenCliVideoError("UP 主视频列表获取失败，请确认 OpenCLI 已连接到 B 站")
    return _items(result.stdout)


def fetch_video_subtitles(bvid: str) -> list[dict]:
    """通过 OpenCLI 获取视频官方字幕片段。"""
    try:
        result = run_opencli(
            ["bilibili", "subtitle", str(bvid), "-f", "json", "--window", "background"],
            timeout=120,
        )
    except FileNotFoundError as exc:
        raise OpenCliVideoError("未找到 OpenCLI，请先安装并配置 OpenCLI") from exc
    except subprocess.TimeoutExpired as exc:
        raise OpenCliVideoError("视频字幕获取超时，请重试") from exc
    if result.returncode != 0:
        raise OpenCliVideoError("视频字幕获取失败，请确认 OpenCLI 已连接到 B 站")
    return _subtitle_items((result.stdout or "") + "\n" + (result.stderr or ""))


def download_video(bvid: str, output_directory: str, *, quality: str = "best") -> str:
    return _download_video_with_quality(bvid, output_directory, quality)


def _download_video_with_quality(bvid: str, output_directory: str, quality: str) -> str:
    try:
        result = run_opencli(
            [
                "bilibili", "download", bvid, "--output", output_directory,
                "--quality", quality, "--window", "background",
            ],
            timeout=3600,
        )
    except FileNotFoundError as exc:
        raise OpenCliVideoError("未找到 OpenCLI，请先安装并配置 OpenCLI") from exc
    except subprocess.TimeoutExpired as exc:
        raise OpenCliVideoError("视频下载超时，请重试") from exc
    output = ((result.stdout or "") + "\n" + (result.stderr or "")).strip()
    if result.returncode != 0 or _download_output_failed(output):
        detail = _download_error_detail(output, result.returncode)
        raise OpenCliVideoError(f"视频下载失败：{detail}")
    return output


def _download_output_failed(output: str) -> bool:
    """OpenCLI 可能在命令成功退出时返回一行 status=failed 的结果。"""
    lowered = output.lower()
    if "yt-dlp not installed" in lowered:
        return True
    return bool(
        re.search(r"(?:status|状态)\s*(?:[:|=]|is)?\s*(?:failed|failure|error|失败)", output, re.IGNORECASE)
        or re.search(r"[|│]\s*(?:failed|failure|error|失败)\s*[|│]", output, re.IGNORECASE)
        or "✗" in output
    )


def _download_error_detail(output: str, returncode: int) -> str:
    detail = " ".join(line.strip() for line in output.splitlines() if line.strip())
    if not detail:
        return f"OpenCLI 退出码 {returncode}，请检查 yt-dlp、B 站登录状态和网络连接"
    return detail[-600:]
