"""协调远端追踪清单与本地视频库索引。"""

from core.configuration import knowledge_base_root
from core.repositories.followings import find
from core.repositories.library import find_local_video
from core.repositories.videos import list_videos, reconcile_downloaded
from core.video_index import index_existing_up_videos
from core.video_errors import FollowingNotFoundError


def reconcile_up_videos(uid: str, *, root=None) -> list[dict]:
    root = root or knowledge_base_root()
    following = find(uid, root / "UpList")
    if following is None:
        raise FollowingNotFoundError(f"未找到 UP {uid}")
    nickname = str(following.get("nickname", uid))
    up_list = root / "UpList"
    rows = list_videos(up_list, nickname)
    index_existing_up_videos(root, uid, rows)
    return reconcile_downloaded(
        up_list,
        nickname,
        lambda remote: find_local_video(
            root,
            nickname,
            bvid=str(remote.get("bvid", "")),
            title=str(remote.get("title", "")),
            date=str(remote.get("date", "")),
            uid=uid,
        ),
    )
