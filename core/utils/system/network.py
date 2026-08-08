"""本机服务端口的跨平台管理。"""

import json
import os
import platform
import re
import signal
import socket
import subprocess
import time
from urllib.error import URLError
from urllib.request import urlopen


BILIUP_PORT = 8765


class ServicePortError(RuntimeError):
    """固定服务端口无法安全使用。"""


def available_local_port(preferred: int = 8765) -> int:
    for port in (preferred, 0):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                if port == preferred:
                    continue
                raise
            return int(probe.getsockname()[1])
    raise RuntimeError("无法分配本地服务端口")


def _is_port_listening(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.4)
        return probe.connect_ex(("127.0.0.1", port)) == 0


def _is_biliup_service(port: int) -> bool:
    """通过 FastAPI 的公开元数据确认监听者属于 BiliUp。"""
    try:
        with urlopen(f"http://127.0.0.1:{port}/openapi.json", timeout=0.2) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, ValueError, json.JSONDecodeError):
        return False
    info = data.get("info") if isinstance(data, dict) else None
    return isinstance(info, dict) and info.get("title") == "BiliUp"


def _listener_pids(port: int) -> list[int]:
    system = platform.system()
    if system == "Darwin":
        result = subprocess.run(
            ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
            capture_output=True,
            text=True,
            check=False,
        )
    elif system == "Windows":
        command = (
            f"Get-NetTCPConnection -State Listen -LocalPort {port} "
            "-ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess"
        )
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            check=False,
            **({"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}),
        )
    else:
        raise ServicePortError("当前系统不受支持")
    return sorted({int(line) for line in result.stdout.splitlines() if line.strip().isdigit()})


def _listening_instances() -> list[tuple[int, int]]:
    """返回本机 TCP 监听项的 ``(PID, port)``，仅供 BiliUp 身份探测。"""
    system = platform.system()
    if system == "Darwin":
        result = subprocess.run(
            ["lsof", "-nP", "-iTCP", "-sTCP:LISTEN", "-Fpn"],
            capture_output=True,
            text=True,
            check=False,
        )
        current_pid = 0
        instances: list[tuple[int, int]] = []
        for line in result.stdout.splitlines():
            if line.startswith("p") and line[1:].isdigit():
                current_pid = int(line[1:])
            elif line.startswith("n") and current_pid:
                match = re.search(r":(\d+)$", line[1:])
                if match:
                    instances.append((current_pid, int(match.group(1))))
        return instances
    if system == "Windows":
        command = (
            "Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | "
            "ForEach-Object { '{0} {1}' -f $_.OwningProcess, $_.LocalPort }"
        )
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            check=False,
            **({"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}),
        )
        instances = []
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) == 2 and all(part.isdigit() for part in parts):
                instances.append((int(parts[0]), int(parts[1])))
        return instances
    return []


def _terminate_process(pid: int) -> None:
    if pid == os.getpid():
        raise ServicePortError("拒绝终止当前 BiliUp 启动进程")
    if platform.system() == "Windows":
        result = subprocess.run(
            ["taskkill.exe", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            text=True,
            check=False,
            **({"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}),
        )
        if result.returncode != 0:
            raise ServicePortError(f"无法停止旧的 BiliUp 进程（PID {pid}）")
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    except PermissionError as exc:
        raise ServicePortError(f"没有权限停止旧的 BiliUp 进程（PID {pid}）") from exc


def stop_existing_biliup_services() -> int:
    """停止任意本机端口上可确认身份的旧 BiliUp 服务。"""
    targets = {
        (pid, port)
        for pid, port in _listening_instances()
        if pid != os.getpid() and _is_biliup_service(port)
    }
    for pid in {pid for pid, _ in targets}:
        _terminate_process(pid)
    pending_ports = {port for _, port in targets}
    deadline = time.monotonic() + 5
    while pending_ports and time.monotonic() < deadline:
        pending_ports = {port for port in pending_ports if _is_port_listening(port)}
        if pending_ports:
            time.sleep(0.1)
    if pending_ports:
        ports = ", ".join(str(port) for port in sorted(pending_ports))
        raise ServicePortError(f"旧的 BiliUp 服务未能停止（端口 {ports}）")
    return len(targets)


def prepare_biliup_port(port: int = BILIUP_PORT) -> int:
    """释放固定端口上的旧 BiliUp 服务，供本次启动接管。

    仅当监听者可通过 ``/openapi.json`` 确认是 BiliUp 时才终止，避免误杀
    其他本机程序。
    """
    if not _is_port_listening(port):
        return port
    if not _is_biliup_service(port):
        raise ServicePortError(f"端口 {port} 已被其他程序占用，未自动终止")
    pids = _listener_pids(port)
    if not pids:
        raise ServicePortError(f"无法识别占用端口 {port} 的旧 BiliUp 进程")
    for pid in pids:
        _terminate_process(pid)
    deadline = time.monotonic() + 5
    while _is_port_listening(port) and time.monotonic() < deadline:
        time.sleep(0.1)
    if _is_port_listening(port):
        raise ServicePortError(f"旧的 BiliUp 进程未能释放端口 {port}")
    return port
