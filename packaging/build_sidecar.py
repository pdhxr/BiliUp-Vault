import platform
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SIDECAR_NAME = "biliup-backend"


def rust_target() -> str:
    result = subprocess.run(
        ["rustc", "--print", "host-tuple"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    target = result.stdout.strip()
    if not target:
        raise RuntimeError("rustc 未返回当前平台 target")
    return target


def build_sidecar() -> Path:
    target = rust_target()
    extension = ".exe" if platform.system() == "Windows" else ""
    build_dir = PROJECT_ROOT / "build/sidecar"
    dist_dir = PROJECT_ROOT / "dist/sidecar"
    binaries_dir = PROJECT_ROOT / "src-tauri/binaries"
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--name",
        SIDECAR_NAME,
        "--runtime-hook",
        str(PROJECT_ROOT / "scripts/pyi_rth_stdout.py"),
        "--add-data",
        f"{PROJECT_ROOT / 'app/static'}{';' if platform.system() == 'Windows' else ':'}app/static",
        "--workpath",
        str(build_dir),
        "--distpath",
        str(dist_dir),
        "--specpath",
        str(build_dir),
    ]
    if platform.system() == "Windows":
        command.append("--noconsole")
    command.append(str(PROJECT_ROOT / "tools/desktop_entry.py"))
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)

    source = dist_dir / f"{SIDECAR_NAME}{extension}"
    if not source.is_file():
        raise RuntimeError(f"PyInstaller 未生成 sidecar：{source}")
    binaries_dir.mkdir(parents=True, exist_ok=True)
    destination = binaries_dir / f"{SIDECAR_NAME}-{target}{extension}"
    shutil.copy2(source, destination)
    destination.chmod(destination.stat().st_mode | 0o111)
    return destination


if __name__ == "__main__":
    print(build_sidecar())
