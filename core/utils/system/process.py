import os
import platform
import shutil
import signal
import subprocess
import time
from threading import Event, Lock
from pathlib import Path


_managed_processes: set[subprocess.Popen] = set()
_managed_processes_lock = Lock()


class ProcessCancelledError(RuntimeError):
    """The caller cancelled a managed subprocess before it completed."""


def _terminate_process(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill.exe", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
    deadline = time.monotonic() + 0.5
    while time.monotonic() < deadline and process.poll() is None:
        time.sleep(0.02)
    if os.name != "nt" and process.poll() is None:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def _run_managed(
    command: list[str],
    *,
    timeout: int,
    text: bool,
    encoding: str | None = None,
    env: dict[str, str] | None = None,
    cancel_event: Event | None = None,
) -> subprocess.CompletedProcess:
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=text,
        encoding=encoding,
        env=env,
        **({"start_new_session": True} if os.name != "nt" else {}),
        **({"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}),
    )
    with _managed_processes_lock:
        _managed_processes.add(process)
    try:
        if cancel_event is None:
            stdout, stderr = process.communicate(timeout=timeout)
        else:
            deadline = time.monotonic() + timeout
            while True:
                if cancel_event.is_set():
                    _terminate_process(process)
                    process.communicate()
                    raise ProcessCancelledError("子进程已取消")
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(command, timeout)
                try:
                    stdout, stderr = process.communicate(timeout=min(0.2, remaining))
                    break
                except subprocess.TimeoutExpired:
                    continue
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()
        raise
    finally:
        with _managed_processes_lock:
            _managed_processes.discard(process)
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def terminate_managed_processes() -> None:
    with _managed_processes_lock:
        processes = list(_managed_processes)
    for process in processes:
        if process.poll() is not None:
            continue
        if os.name == "nt":
            subprocess.run(
                ["taskkill.exe", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True,
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        else:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                continue
    deadline = time.monotonic() + 0.5
    while time.monotonic() < deadline and any(process.poll() is None for process in processes):
        time.sleep(0.02)
    if os.name != "nt":
        for process in processes:
            if process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass


def _candidate_paths() -> list[Path]:
    system = platform.system()
    candidates: list[Path] = []
    if system == "Darwin":
        candidates.extend((
            Path("/opt/homebrew/bin/opencli"),
            Path("/usr/local/bin/opencli"),
            Path.home() / ".volta/bin/opencli",
            Path.home() / ".local/bin/opencli",
        ))
        candidates.extend(sorted((Path.home() / ".nvm/versions/node").glob("*/bin/opencli"), reverse=True))
    elif system == "Windows":
        app_data = os.environ.get("APPDATA")
        if app_data:
            candidates.extend((Path(app_data) / "npm/opencli.cmd", Path(app_data) / "npm/opencli"))
        program_files = os.environ.get("ProgramFiles")
        if program_files:
            candidates.extend((Path(program_files) / "nodejs/opencli.cmd", Path(program_files) / "nodejs/opencli"))
    else:
        candidates.extend((Path("/usr/local/bin/opencli"), Path.home() / ".local/bin/opencli"))
    return candidates


def _yt_dlp_candidate_paths() -> list[Path]:
    system = platform.system()
    candidates: list[Path] = []
    if system == "Darwin":
        candidates.extend((
            Path("/opt/homebrew/bin/yt-dlp"),
            Path("/usr/local/bin/yt-dlp"),
            Path.home() / ".local/bin/yt-dlp",
        ))
    elif system == "Windows":
        app_data = os.environ.get("APPDATA")
        if app_data:
            candidates.extend((
                Path(app_data) / "npm/yt-dlp.exe",
                Path(app_data) / "npm/yt-dlp.cmd",
                Path(app_data) / "npm/yt-dlp",
            ))
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            candidates.extend((
                Path(local_app_data) / "Programs/yt-dlp/yt-dlp.exe",
                Path(local_app_data) / "Microsoft/WinGet/Links/yt-dlp.exe",
            ))
    else:
        candidates.extend((Path("/usr/local/bin/yt-dlp"), Path.home() / ".local/bin/yt-dlp"))
    return candidates


def find_opencli() -> Path | None:
    discovered = shutil.which("opencli")
    if discovered:
        return Path(discovered)
    for candidate in _candidate_paths():
        if candidate.is_file():
            return candidate
    return None


def find_yt_dlp() -> Path | None:
    discovered = shutil.which("yt-dlp")
    if discovered:
        return Path(discovered)
    for candidate in _yt_dlp_candidate_paths():
        if candidate.is_file():
            return candidate
    return None


def _process_environment(executable: Path) -> dict[str, str]:
    environment = os.environ.copy()
    directories = [str(executable.parent)]
    if platform.system() == "Darwin":
        directories.extend(("/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin"))
    existing = environment.get("PATH", "")
    if existing:
        directories.append(existing)
    environment["PATH"] = os.pathsep.join(dict.fromkeys(directories))
    return environment


def run_opencli(
    arguments: list[str],
    timeout: int,
    *,
    cancel_event: Event | None = None,
) -> subprocess.CompletedProcess[str]:
    executable = find_opencli()
    if executable is None:
        raise FileNotFoundError("opencli")
    command = [str(executable), *arguments]
    if os.name == "nt":
        command = [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", *command]
    return _run_managed(
        command,
        text=True,
        encoding="utf-8",
        timeout=timeout,
        env=_process_environment(executable),
        cancel_event=cancel_event,
    )


def run_yt_dlp(arguments: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    """Run yt-dlp without opening a console window on Windows."""
    executable = find_yt_dlp()
    if executable is None:
        raise FileNotFoundError("yt-dlp")
    command = [str(executable), *arguments]
    if os.name == "nt" and executable.suffix.lower() in {".cmd", ".bat"}:
        command = [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", *command]
    return _run_managed(
        command,
        text=True,
        encoding="utf-8",
        timeout=timeout,
        env=_process_environment(executable),
    )


def _run_media_tool(name: str, arguments: list[str], timeout: int) -> subprocess.CompletedProcess[bytes]:
    executable = shutil.which(name)
    if not executable:
        raise FileNotFoundError(name)
    return _run_managed(
        [executable, *arguments],
        text=False,
        timeout=timeout,
    )


def run_ffmpeg(arguments: list[str], timeout: int) -> subprocess.CompletedProcess[bytes]:
    """Run FFmpeg without opening a console window on Windows."""
    return _run_media_tool("ffmpeg", arguments, timeout)


def run_ffprobe(arguments: list[str], timeout: int) -> subprocess.CompletedProcess[bytes]:
    """Run FFprobe without opening a console window on Windows."""
    return _run_media_tool("ffprobe", arguments, timeout)
