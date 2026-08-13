import platform
import subprocess
import sys

from core.version import APP_VERSION


def build_package(target: str) -> None:
    host = platform.system().lower()
    if target == "macos" and host != "darwin":
        raise RuntimeError("macOS 安装包必须在 macOS 上构建")
    if target == "windows" and host != "windows":
        raise RuntimeError("Windows EXE 必须在 Windows 上构建")

    separator = ";" if target == "windows" else ":"
    package_name = f"BiliUp-{APP_VERSION}"
    command = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed",
        "--runtime-hook", "scripts/pyi_rth_stdout.py",
        "--name", package_name, "--add-data", f"app/static{separator}app/static", "app/main.py",
    ]
    subprocess.run(command, check=True)
    if target == "macos":
        subprocess.run([
            "hdiutil", "create", "-volname", package_name, "-srcfolder", f"dist/{package_name}.app",
            "-ov", "-format", "UDZO", f"dist/{package_name}.dmg",
        ], check=True)
