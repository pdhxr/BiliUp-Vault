from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.configuration import KnowledgeBaseConfigurationError
from core.download_progress import progress_rows
from core.opencli_videos import OpenCliVideoError
from core.single_video_download import queue_single_video_download
from core.video_download import queue_downloads
from core.video_batch_sync import batch_sync_progress, start_batch_sync
from core.video_batch_track_download import batch_track_download_progress, start_batch_track_download
from core.video_errors import FollowingNotFoundError
from core.video_sync import list_up_videos


router = APIRouter(prefix="/api")


class RefreshVideosRequest(BaseModel):
    page: int = Field(default=1, ge=1, le=1000)
    limit: int = Field(default=50, ge=1, le=100)


class DownloadVideosRequest(BaseModel):
    up_id: str = Field(min_length=1, max_length=32)
    bvids: list[str] = Field(min_length=1, max_length=50)


class BatchRefreshVideosRequest(BaseModel):
    up_ids: list[str] = Field(min_length=1, max_length=50)


class BatchTrackDownloadRequest(BaseModel):
    up_ids: list[str] = Field(min_length=1, max_length=50)
    since_date: str = Field(default="", max_length=10)


class SingleVideoDownloadRequest(BaseModel):
    url: str = Field(min_length=1, max_length=1000)


def _not_found(exc: FollowingNotFoundError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc))


@router.get("/up/{up_id}/videos")
def get_up_videos(up_id: str) -> list[dict]:
    try:
        return list_up_videos(up_id)
    except FollowingNotFoundError as exc:
        raise _not_found(exc) from exc
    except KnowledgeBaseConfigurationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=500, detail="无法读取 UP 主视频列表") from exc


@router.post("/up/{up_id}/videos/refresh")
def refresh_videos(up_id: str, request: RefreshVideosRequest | None = None) -> dict[str, object]:
    _ = request or RefreshVideosRequest()
    try:
        return start_batch_sync(
            [up_id],
            max_pages=1,
            max_new_videos=30,
            limit=30,
            continue_history=True,
        )
    except FollowingNotFoundError as exc:
        raise _not_found(exc) from exc
    except OpenCliVideoError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except KnowledgeBaseConfigurationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=500, detail="无法保存 UP 主视频列表") from exc


@router.post("/up/videos/batch-refresh")
def batch_refresh_videos(request: BatchRefreshVideosRequest) -> dict[str, object]:
    try:
        return start_batch_sync(request.up_ids)
    except FollowingNotFoundError as exc:
        raise _not_found(exc) from exc
    except KnowledgeBaseConfigurationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/up/videos/batch-refresh-progress")
def get_batch_refresh_progress() -> dict[str, object]:
    return batch_sync_progress()


@router.post("/up/videos/batch-track-download")
def batch_track_download(request: BatchTrackDownloadRequest) -> dict[str, object]:
    try:
        return start_batch_track_download(request.up_ids, request.since_date)
    except FollowingNotFoundError as exc:
        raise _not_found(exc) from exc
    except KnowledgeBaseConfigurationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/up/videos/batch-track-download-progress")
def get_batch_track_download_progress() -> dict[str, object]:
    return batch_track_download_progress()


@router.post("/videos/download")
def download_videos(request: DownloadVideosRequest) -> dict[str, object]:
    try:
        jobs = queue_downloads(request.up_id, request.bvids)
    except FollowingNotFoundError as exc:
        raise _not_found(exc) from exc
    except KnowledgeBaseConfigurationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"jobs": jobs}


@router.post("/single-video/download")
def download_single_video(request: SingleVideoDownloadRequest) -> dict[str, object]:
    try:
        job = queue_single_video_download(request.url)
    except KnowledgeBaseConfigurationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except OpenCliVideoError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail="无法准备单视频下载目录") from exc
    return {"job": job}


@router.get("/videos/download-progress")
def get_download_progress() -> list[dict[str, object]]:
    return progress_rows()
