import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.routes.setup import router as setup_router
from app.routes.up import router
from app.routes.videos import router as videos_router
from core.utils.system.browser import open_browser_after_start
from core.utils.system.network import BILIUP_PORT, prepare_biliup_port, stop_existing_biliup_services
from core.utils.system.resources import resource_path
from core.version import APP_VERSION


STATIC_DIR = resource_path("app/static")


def create_app() -> FastAPI:
    app = FastAPI(title="BiliUp", version=APP_VERSION)
    app.include_router(router)
    app.include_router(setup_router)
    app.include_router(videos_router)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def dashboard() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    return app


def main() -> None:
    host = "127.0.0.1"
    stop_existing_biliup_services()
    port = prepare_biliup_port(BILIUP_PORT)
    open_browser_after_start(f"http://{host}:{port}")
    uvicorn.run(create_app(), host=host, port=port)


if __name__ == "__main__":
    main()
