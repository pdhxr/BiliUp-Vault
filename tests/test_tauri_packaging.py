import importlib.util
import json
import subprocess
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

from core.version import APP_VERSION


_SCRIPT = Path(__file__).resolve().parents[1] / "packaging/build_sidecar.py"
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location("biliup_build_sidecar", _SCRIPT)
assert _SPEC and _SPEC.loader
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
build_sidecar = _MODULE.build_sidecar
rust_target = _MODULE.rust_target


class TauriPackagingTests(unittest.TestCase):
    def test_release_manifests_match_application_version(self) -> None:
        package = json.loads((_PROJECT_ROOT / "package.json").read_text(encoding="utf-8"))
        cargo = tomllib.loads((_PROJECT_ROOT / "src-tauri/Cargo.toml").read_text(encoding="utf-8"))

        self.assertEqual(package["version"], APP_VERSION)
        self.assertEqual(cargo["package"]["version"], APP_VERSION)

    def test_windows_tauri_runner_invokes_javascript_entry_without_cmd_shim(self) -> None:
        source = (_PROJECT_ROOT / "packaging/run_tauri.mjs").read_text(encoding="utf-8")

        self.assertIn("const command = isWindows ? 'node' : 'node_modules/.bin/tauri';", source)
        self.assertIn(
            "const prefix = isWindows ? ['node_modules/@tauri-apps/cli/tauri.js'] : [];",
            source,
        )
        self.assertIn("spawnSync(command, [...prefix, action", source)
        self.assertNotIn("tauri.cmd", source)

    def test_bundle_declares_platform_icons(self) -> None:
        config = json.loads((_PROJECT_ROOT / "src-tauri/tauri.conf.json").read_text(encoding="utf-8"))
        icons = config["bundle"]["icon"]

        self.assertIn("icons/icon.icns", icons)
        self.assertIn("icons/icon.ico", icons)
        for relative_path in icons:
            self.assertTrue((_PROJECT_ROOT / "src-tauri" / relative_path).is_file())

    @patch.object(_MODULE.subprocess, "run")
    def test_rust_target_uses_host_tuple(self, run) -> None:
        run.return_value = subprocess.CompletedProcess([], 0, stdout="aarch64-apple-darwin\n", stderr="")
        self.assertEqual(rust_target(), "aarch64-apple-darwin")
        self.assertEqual(run.call_args.args[0], ["rustc", "--print", "host-tuple"])

    @patch.object(_MODULE.shutil, "copy2")
    @patch.object(_MODULE.Path, "is_file", return_value=True)
    @patch.object(_MODULE.Path, "chmod")
    @patch.object(_MODULE.Path, "stat")
    @patch.object(_MODULE.Path, "mkdir")
    @patch.object(_MODULE.subprocess, "run")
    @patch.object(_MODULE.platform, "system", return_value="Darwin")
    @patch.object(_MODULE, "rust_target", return_value="aarch64-apple-darwin")
    def test_sidecar_uses_tauri_target_name(
        self, _target, _system, run, _mkdir, stat, _chmod, _is_file, copy
    ) -> None:
        stat.return_value.st_mode = 0o644
        destination = build_sidecar()
        self.assertEqual(destination.name, "biliup-backend-aarch64-apple-darwin")
        self.assertIn("PyInstaller", run.call_args.args[0])
        self.assertEqual(Path(copy.call_args.args[1]).name, destination.name)

    def test_desktop_exit_request_gracefully_stops_sidecar(self) -> None:
        source = (_PROJECT_ROOT / "src-tauri/src/lib.rs").read_text(encoding="utf-8")
        self.assertIn("RunEvent::ExitRequested", source)
        self.assertIn("api.prevent_exit()", source)
        self.assertIn("begin_shutdown(app.clone(), port)", source)
        exit_handler = source.split("RunEvent::Exit =>", 1)[1]
        self.assertIn("request_backend_shutdown(port)", exit_handler)
        self.assertIn("stop_sidecar(app)", exit_handler)


if __name__ == "__main__":
    unittest.main()
