from core.configuration import knowledge_base_root
from core.opencli_videos import OpenCliVideoError
from core.repositories.followings import find, save, set_scheduled_tracking
from core.video_sync import refresh_up_videos_with_stats


def save_following(uid: str, nickname: str, bio: str) -> tuple[dict, str]:
    return save(uid, nickname, bio, knowledge_base_root() / "UpList")


def set_following_scheduled_tracking(uid: str, enabled: bool) -> dict:
    """更新 UP 主是否参与批量追踪和下载。"""
    return set_scheduled_tracking(uid, enabled, knowledge_base_root() / "UpList")


def save_following_and_refresh(uid: str, nickname: str, bio: str) -> tuple[dict, str, dict[str, object]]:
    """登记 UP 后立即同步首批视频，并返回初始视频统计。"""
    root = knowledge_base_root()
    record, action = save(uid, nickname, bio, root / "UpList")
    try:
        # 添加阶段只拉取首批，保证确认写入后很快能看到视频；完整历史由“刷新列表”负责。
        rows, added, pages = refresh_up_videos_with_stats(uid, page=1, limit=50, max_pages=1, max_new_videos=20)
    except (OpenCliVideoError, OSError, ValueError) as exc:
        # UP 登记已经成功，不能因为首次同步失败而丢失登记。
        return record, action, {
            "status": "error",
            "video_count": 0,
            "added_count": 0,
            "pages": 0,
            "message": str(exc),
        }
    return find(uid, root / "UpList") or record, action, {
        "status": "ok",
        "video_count": len(rows),
        "added_count": added,
        "pages": pages,
        "message": "",
    }
