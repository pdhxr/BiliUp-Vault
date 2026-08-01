from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.followings import save_following
from core.runtime import opencli_status
from core.up_search import OpenCliSearchError, search_up


router = APIRouter(prefix="/api")


class SearchRequest(BaseModel):
    nickname: str = Field(min_length=1, max_length=100)


class FollowingRequest(BaseModel):
    uid: str = Field(min_length=1, max_length=32)
    nickname: str = Field(min_length=1, max_length=100)
    bio: str = ""


@router.get("/runtime-status")
def runtime_status() -> dict[str, object]:
    return opencli_status()


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
    record, action = save_following(uid, nickname, request.bio)
    return {"action": action, "record": record}
