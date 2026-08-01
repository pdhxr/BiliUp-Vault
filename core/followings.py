from core.configuration import knowledge_base_root
from core.repositories.followings import save


def save_following(uid: str, nickname: str, bio: str) -> tuple[dict, str]:
    return save(uid, nickname, bio, knowledge_base_root() / "UpList")
