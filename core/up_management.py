from core.configuration import knowledge_base_root
from core.repositories.followings import list_rows


def list_up_management() -> list[dict[str, object]]:
    """返回当前知识库中已登记 UP 主的管理列表。"""
    return list_rows(knowledge_base_root() / "UpList")
