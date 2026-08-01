import os
import platform
import shutil
import subprocess
from pathlib import Path


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


def find_opencli() -> Path | None:
    discovered = shutil.which("opencli")
    if discovered:
        return Path(discovered)
    for candidate in _candidate_paths():
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


def run_opencli(arguments: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    executable = find_opencli()
    if executable is None:
        raise FileNotFoundError("opencli")
    command = [str(executable), *arguments]
    if os.name == "nt":
        command = [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", *command]
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout,
        check=False,
        env=_process_environment(executable),
    )
