import json
import shutil
import unittest
from pathlib import Path

from core.repositories.followings import save
from core.up_search import _parse_items
from core.utils.system.resources import resource_path


class CoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path("tmp/test-followings")
        shutil.rmtree(self.root, ignore_errors=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def test_normalizes_opencli_user_result(self) -> None:
        rows = _parse_items(json.dumps([{
            "title": "示例 UP", "author": "示例简介", "url": "https://space.bilibili.com/123456",
        }]))
        self.assertEqual(rows, [{"uid": "123456", "nickname": "示例 UP", "bio": "示例简介"}])

    def test_source_resource_path_is_relative(self) -> None:
        self.assertEqual(resource_path("app/static"), Path("app/static"))

    def test_save_updates_existing_uid_and_rebuilds_markdown(self) -> None:
        first, action = save("123", "初始昵称", "第一行\n第二行", self.root)
        updated, update_action = save("123", "新昵称", "新简介", self.root)
        rows = json.loads((self.root / "followings.json").read_text(encoding="utf-8"))
        markdown = (self.root / "bilibili-up-followings.md").read_text(encoding="utf-8")
        self.assertEqual(action, "created")
        self.assertEqual(update_action, "updated")
        self.assertEqual(len(rows), 1)
        self.assertEqual(updated["created_at"], first["created_at"])
        self.assertIn("| 1 | 新昵称 | 123 | 新简介 |", markdown)


if __name__ == "__main__":
    unittest.main()
