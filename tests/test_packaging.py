import unittest
from unittest.mock import patch

from core.utils.system.packaging import build_package
from core.version import APP_VERSION


class PackagingTests(unittest.TestCase):
    @patch("core.utils.system.packaging.subprocess.run")
    @patch("core.utils.system.packaging.platform.system", return_value="Darwin")
    def test_macos_build_creates_app_and_dmg(self, _system, run) -> None:
        build_package("macos")
        self.assertEqual(run.call_count, 2)
        self.assertIn("PyInstaller", run.call_args_list[0].args[0])
        self.assertIn(f"BiliUp-{APP_VERSION}", run.call_args_list[0].args[0])
        self.assertEqual(run.call_args_list[1].args[0][0], "hdiutil")
        self.assertIn(f"dist/BiliUp-{APP_VERSION}.dmg", run.call_args_list[1].args[0])


if __name__ == "__main__":
    unittest.main()
