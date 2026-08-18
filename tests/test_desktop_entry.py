import os
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.desktop_entry import run_desktop


class DesktopEntryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path("tmp/test-desktop-entry")
        shutil.rmtree(self.root, ignore_errors=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    @patch("tools.desktop_entry.shutdown_background_work")
    @patch("tools.desktop_entry.uvicorn.Server")
    @patch("tools.desktop_entry.prepare_biliup_port", return_value=8765)
    def test_desktop_backend_prepares_port_before_starting(self, prepare, server_factory, _shutdown) -> None:
        with patch.dict(os.environ, {}, clear=False):
            run_desktop(8765, self.root, "instance-123")
            self.assertEqual(os.environ["BILIUP_INSTANCE_TOKEN"], "instance-123")

        prepare.assert_called_once_with(8765)
        server_factory.return_value.run.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
