import os
import platform
import subprocess
from pathlib import Path


class DirectoryPickerError(RuntimeError):
    pass


def application_config_directory() -> Path:
    system = platform.system()
    if system == "Darwin":
        return Path.home() / "Library/Application Support/BiliUp"
    if system == "Windows":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "BiliUp"
        return Path.home() / "AppData/Local/BiliUp"
    raise DirectoryPickerError("当前系统不受支持")


def choose_directory() -> Path | None:
    system = platform.system()
    if system == "Darwin":
        result = subprocess.run(
            ["osascript", "-e", 'POSIX path of (choose folder with prompt "选择视频知识库目录")'],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return Path(result.stdout.strip())
        if "-128" in result.stderr:
            return None
        raise DirectoryPickerError("无法打开目录选择器")
    if system == "Windows":
        script = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            "$dialog = New-Object System.Windows.Forms.FolderBrowserDialog; "
            "$dialog.Description = '选择视频知识库目录'; "
            "if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) "
            "{ [Console]::Out.Write($dialog.SelectedPath) }"
        )
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-STA", "-Command", script],
            capture_output=True,
            text=True,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if result.returncode != 0:
            raise DirectoryPickerError("无法打开目录选择器")
        selected = result.stdout.strip()
        return Path(selected) if selected else None
    raise DirectoryPickerError("当前系统不受支持")
