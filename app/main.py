import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.routes.up import router
from core.utils.system.browser import open_browser_after_start
from core.utils.system.network import available_local_port
from core.utils.system.resources import resource_path


STATIC_DIR = resource_path("app/static")


def create_app() -> FastAPI:
    app = FastAPI(title="BiliUp")
    app.include_router(router)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def dashboard() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    return app


def main() -> None:
    host = "127.0.0.1"
    port = available_local_port()
    open_browser_after_start(f"http://{host}:{port}")
    uvicorn.run(create_app(), host=host, port=port)


if __name__ == "__main__":
    main()
