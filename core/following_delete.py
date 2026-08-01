"""UP 主删除用例。"""

from core.configuration import knowledge_base_root
from core.repositories.followings import delete
from core.repositories.videos import video_path


def delete_followings(uids: list[str]) -> list[str]:
    """删除登记和远端追踪清单，保留本地视频索引与实际视频文件。"""
    root = knowledge_base_root() / "UpList"
    deleted = delete(root, uids)
    deleted_uids: list[str] = []
    for record in deleted:
        uid = str(record.get("uid", "")).strip()
        nickname = str(record.get("nickname", "")).strip()
        index_path = video_path(root, nickname)
        if index_path.is_file():
            index_path.unlink()
        if uid:
            deleted_uids.append(uid)
    return deleted_uids
