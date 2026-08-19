import platform
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import webbrowser

from core.utils.system.process import _process_environment, _run_managed


def open_browser_after_start(url: str) -> None:
    timer = threading.Timer(0.8, webbrowser.open, args=(url,))
    timer.daemon = True
    timer.start()


def _headless_browser_candidates() -> list[Path]:
    system = platform.system()
    if system == "Windows":
        return [
            Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
            Path("C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"),
            Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"),
            Path("C:/Program Files/Microsoft/Edge/Application/msedge.exe"),
        ]
    if system == "Darwin":
        return [
            Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
            Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
            Path.home() / "Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ]
    return [Path("/usr/bin/google-chrome"), Path("/usr/bin/chromium"), Path("/usr/bin/microsoft-edge")]


def find_headless_browser() -> Path | None:
    for name in ("google-chrome", "chrome", "chromium", "microsoft-edge", "msedge"):
        if discovered := shutil.which(name):
            return Path(discovered)
    return next((candidate for candidate in _headless_browser_candidates() if candidate.is_file()), None)


def dump_webpage_with_browser(url: str, *, timeout: int = 45) -> str:
    """Render a public page in an isolated Chromium profile and return its final DOM."""
    executable = find_headless_browser()
    if executable is None:
        raise FileNotFoundError("Chrome or Edge")
    with tempfile.TemporaryDirectory(prefix="biliup-browser-", ignore_cleanup_errors=True) as profile:
        result = _run_managed(
            [
                str(executable),
                "--headless=new",
                "--disable-gpu",
                "--disable-background-networking",
                "--disable-component-update",
                "--no-first-run",
                "--no-default-browser-check",
                "--autoplay-policy=no-user-gesture-required",
                "--window-size=1280,900",
                "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
                f"--user-data-dir={profile}",
                "--virtual-time-budget=25000",
                "--dump-dom",
                str(url),
            ],
            text=True,
            encoding="utf-8",
            timeout=timeout,
            env=_process_environment(executable),
        )
    if result.returncode != 0 or not str(result.stdout or "").strip():
        raise RuntimeError("浏览器未返回抖音页面内容")
    return str(result.stdout)
