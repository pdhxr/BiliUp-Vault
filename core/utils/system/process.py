import os
import subprocess


def run_opencli(arguments: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    command = ["opencli", *arguments]
    if os.name == "nt":
        command = [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", *command]
    return subprocess.run(command, capture_output=True, text=True, encoding="utf-8", timeout=timeout, check=False)
