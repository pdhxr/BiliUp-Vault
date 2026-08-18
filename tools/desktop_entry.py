import argparse
import os
from pathlib import Path

import uvicorn

from core.configuration import MAX_DESKTOP_PORT, MIN_DESKTOP_PORT
from core.shutdown import shutdown_background_work
from core.utils.system.network import ServicePortError, prepare_biliup_port


def _port(value: str) -> int:
    try:
        port = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("端口必须是整数") from exc
    if not MIN_DESKTOP_PORT <= port <= MAX_DESKTOP_PORT:
        raise argparse.ArgumentTypeError(f"端口必须在 {MIN_DESKTOP_PORT}–{MAX_DESKTOP_PORT} 之间")
    return port


def run_desktop(port: int, data_dir: Path, instance_token: str = "") -> None:
    prepare_biliup_port(port)
    target = data_dir.expanduser().resolve()
    target.mkdir(parents=True, exist_ok=True)
    os.environ["BILIUP_DESKTOP"] = "1"
    os.environ["BILIUP_CURRENT_PORT"] = str(port)
    os.environ["BILIUP_DATA_DIR"] = str(target)
    os.environ["BILIUP_INSTANCE_TOKEN"] = instance_token

    from app.main import create_app

    server = uvicorn.Server(uvicorn.Config(
        create_app(lambda: _request_shutdown(server)),
        host="127.0.0.1",
        port=port,
        workers=1,
        log_level="info",
    ))
    try:
        server.run()
    finally:
        shutdown_background_work()


def _request_shutdown(server: uvicorn.Server) -> None:
    shutdown_background_work()
    server.should_exit = True


def main() -> None:
    parser = argparse.ArgumentParser(description="启动 BiliUp 桌面后端")
    parser.add_argument("--port", required=True, type=_port)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--instance-token", default="")
    arguments = parser.parse_args()
    try:
        run_desktop(arguments.port, arguments.data_dir, arguments.instance_token)
    except ServicePortError as exc:
        parser.exit(2, f"BILIUP_STARTUP_ERROR:{exc}\n")


if __name__ == "__main__":
    main()
