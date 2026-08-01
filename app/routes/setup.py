from fastapi import APIRouter, HTTPException

from core.configuration import KnowledgeBaseConfigurationError
from core.setup import choose_and_configure_library, setup_status


router = APIRouter(prefix="/api")


@router.get("/setup-status")
def get_setup_status() -> dict[str, object]:
    return setup_status()


@router.post("/setup/select-library")
def select_library() -> dict[str, object]:
    try:
        root = choose_and_configure_library()
    except KnowledgeBaseConfigurationError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if root is None:
        return {"configured": False, "cancelled": True, "message": "未选择目录"}
    return {"configured": True, "cancelled": False, "message": "视频知识库目录已设置"}
