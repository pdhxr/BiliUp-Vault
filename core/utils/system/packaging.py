import platform
import subprocess
import sys


def build_package(target: str) -> None:
    host = platform.system().lower()
    if target == "macos" and host != "darwin":
        raise RuntimeError("macOS 安装包必须在 macOS 上构建")
    if target == "windows" and host != "windows":
        raise RuntimeError("Windows EXE 必须在 Windows 上构建")

    separator = ";" if target == "windows" else ":"
    command = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed",
        "--name", "BiliUp", "--add-data", f"app/static{separator}app/static", "app/main.py",
    ]
    subprocess.run(command, check=True)
    if target == "macos":
        subprocess.run([
            "hdiutil", "create", "-volname", "BiliUp", "-srcfolder", "dist/BiliUp.app",
            "-ov", "-format", "UDZO", "dist/BiliUp.dmg",
        ], check=True)
