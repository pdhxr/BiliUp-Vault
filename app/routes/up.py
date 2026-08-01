from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.configuration import KnowledgeBaseConfigurationError
from core.followings import save_following_and_refresh, set_following_scheduled_tracking
from core.following_delete import delete_followings
from core.runtime import opencli_status
from core.up_management import list_up_management
from core.up_search import OpenCliSearchError, search_up


router = APIRouter(prefix="/api")


class SearchRequest(BaseModel):
    nickname: str = Field(min_length=1, max_length=100)


class FollowingRequest(BaseModel):
    uid: str = Field(min_length=1, max_length=32)
    nickname: str = Field(min_length=1, max_length=100)
    bio: str = ""


class DeleteFollowingsRequest(BaseModel):
    up_ids: list[str] = Field(min_length=1, max_length=50)


class TrackingSettingRequest(BaseModel):
    up_id: str = Field(min_length=1, max_length=32)
    scheduled_tracking: bool


@router.get("/runtime-status")
def runtime_status() -> dict[str, object]:
    return opencli_status()


@router.get("/followings")
def get_followings() -> list[dict[str, object]]:
    try:
        return list_up_management()
    except KnowledgeBaseConfigurationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=500, detail="无法读取视频知识库中的 UP 列表") from exc


@router.post("/up-search")
def up_search(request: SearchRequest) -> list[dict[str, str]]:
    nickname = request.nickname.strip()
    if not nickname:
        raise HTTPException(status_code=422, detail="请输入 UP 主昵称")
    try:
        return search_up(nickname)
    except OpenCliSearchError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/followings")
def add_following(request: FollowingRequest) -> dict[str, object]:
    nickname = request.nickname.strip()
    uid = request.uid.strip()
    if not uid or not nickname:
        raise HTTPException(status_code=422, detail="UP ID 和昵称不能为空")
    try:
        record, action, video_sync = save_following_and_refresh(uid, nickname, request.bio)
    except KnowledgeBaseConfigurationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=500, detail="无法写入视频知识库，请重新选择目录") from exc
    return {"action": action, "record": record, "video_sync": video_sync}


@router.post("/followings/delete")
def remove_followings(request: DeleteFollowingsRequest) -> dict[str, object]:
    try:
        deleted = delete_followings(request.up_ids)
    except KnowledgeBaseConfigurationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=500, detail="无法删除 UP 主登记信息") from exc
    return {"deleted": deleted, "count": len(deleted)}


@router.post("/followings/tracking")
def update_following_tracking(request: TrackingSettingRequest) -> dict[str, object]:
    try:
        record = set_following_scheduled_tracking(request.up_id, request.scheduled_tracking)
    except KnowledgeBaseConfigurationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail="无法保存自动追踪设置") from exc
    return {
        "up_id": str(record.get("uid", request.up_id)),
        "scheduled_tracking": bool(record.get("scheduled_tracking", False)),
    }
