"""从知识库中的既有视频文件补建本地 videos.jsonl。"""

from core.repositories.followings import find
from core.repositories.library import index_existing_videos, library_up_dir
from core.download_files import expected_video_name


def index_existing_up_videos(root, uid: str, videos: list[dict]) -> int:
    following = find(uid, root / "UpList")
    if following is None:
        return 0
    nickname = str(following.get("nickname", uid))
    up_directory = library_up_dir(root, nickname, uid)
    if not up_directory.is_dir():
        return 0
    candidates = []
    for video in videos:
        title = str(video.get("title", "")).strip()
        date = "".join(character for character in str(video.get("date") or video.get("pub_time", "")) if character.isdigit())[:8]
        bvid = str(video.get("bvid", "")).strip()
        if not title or not date or not bvid:
            continue
        filename = expected_video_name(nickname, uid, title, date)
        match = next((item for item in up_directory.rglob(filename) if item.is_file()), None)
        if match:
            candidates.append({"path": match, "bvid": bvid, "title": title, "date": date})
    return index_existing_videos(root, nickname, candidates, uid=uid)
