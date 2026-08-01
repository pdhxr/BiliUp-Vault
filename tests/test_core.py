import json
import shutil
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.repositories.followings import save
from core.up_search import _parse_items
from core.utils.system.resources import resource_path
from core.utils.system.process import find_opencli, run_opencli
from core.utils.system.network import available_local_port


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

    @patch("core.utils.system.process.shutil.which", return_value=None)
    @patch("core.utils.system.process._candidate_paths")
    def test_finds_opencli_outside_process_path(self, candidates, _which) -> None:
        executable = self.root / "bin/opencli"
        executable.parent.mkdir(parents=True, exist_ok=True)
        executable.write_text("", encoding="utf-8")
        candidates.return_value = [executable]
        self.assertEqual(find_opencli(), executable)

    @patch("core.utils.system.process.subprocess.run")
    @patch("core.utils.system.process.find_opencli", return_value=Path("tmp/bin/opencli"))
    def test_run_opencli_adds_executable_directory_to_path(self, _find, run) -> None:
        run.return_value.returncode = 0
        run_opencli(["--version"], timeout=5)
        self.assertTrue(run.call_args.kwargs["env"]["PATH"].startswith("tmp/bin"))

    @patch("core.utils.system.network.socket.socket")
    def test_occupied_preferred_port_uses_available_port(self, socket_factory) -> None:
        occupied = MagicMock()
        available = MagicMock()
        occupied.__enter__.return_value.bind.side_effect = OSError("occupied")
        available.__enter__.return_value.getsockname.return_value = ("127.0.0.1", 54321)
        socket_factory.side_effect = (occupied, available)
        self.assertEqual(available_local_port(8765), 54321)

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
