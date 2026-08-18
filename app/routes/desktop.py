import os
from collections.abc import Callable

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request


router = APIRouter(prefix="/api")


def desktop_mode() -> bool:
    return os.environ.get("BILIUP_DESKTOP") == "1"


@router.get("/health")
def health() -> dict[str, str]:
    result = {"app": "biliup", "status": "ok"}
    instance = os.environ.get("BILIUP_INSTANCE_TOKEN", "").strip()
    if instance:
        result["instance"] = instance
    return result


@router.post("/desktop/shutdown")
def shutdown(request: Request, background_tasks: BackgroundTasks) -> dict[str, bool]:
    if not desktop_mode():
        raise HTTPException(status_code=404, detail="桌面关闭接口未启用")
    callback = getattr(request.app.state, "desktop_shutdown", None)
    if not isinstance(callback, Callable):
        raise HTTPException(status_code=503, detail="桌面关闭接口尚未就绪")
    background_tasks.add_task(callback)
    return {"shutting_down": True}
