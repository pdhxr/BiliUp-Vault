from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.configuration import KnowledgeBaseConfigurationError
from core.setup import batch_track_settings, choose_and_configure_library, save_batch_track_settings, setup_status


router = APIRouter(prefix="/api")


class BatchTrackSettingsRequest(BaseModel):
    since_date: str = Field(default="", max_length=10)


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


@router.get("/settings/batch-track")
def get_batch_track_settings() -> dict[str, str]:
    try:
        return batch_track_settings()
    except KnowledgeBaseConfigurationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.put("/settings/batch-track")
def update_batch_track_settings(request: BatchTrackSettingsRequest) -> dict[str, str]:
    try:
        return save_batch_track_settings(request.since_date)
    except KnowledgeBaseConfigurationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
