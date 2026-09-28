"""Exercise installer preflight, preservation, restore, and failure rollback."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "ios_install", Path(__file__).with_name("install.py")
)
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.app = self.root / "app"
        self.payload = self.root / "payload"
        self.package = self.app / "Lib/site-packages/adb_auto_player"
        self.package.mkdir(parents=True)
        (self.payload / "files").mkdir(parents=True)
        (self.payload / "runtime/Scripts").mkdir(parents=True)
        (self.app / "adb-auto-player.exe").write_bytes(b"official exe")
        (self.app / "settings.toml").write_text("attempts = 7")
        (self.app / "ios-runtime").mkdir()
        (self.app / "ios-runtime/old.txt").write_text("old runtime")
        (self.package / "base.py").write_text("old backend")
        (self.payload / "files/base.py").write_text("new backend")
        (self.payload / "files/ios.py").write_text("new module")
        runtime = self.payload / "runtime/Scripts/python.exe"
        runtime.write_bytes(b"test runtime")
        self.manifest = {
            "exe_sha256": installer.digest(self.app / "adb-auto-player.exe"),
            "files": [
                {
                    "path": "base.py",
                    "stock": installer.digest(self.package / "base.py"),
                    "current": installer.digest(self.payload / "files/base.py"),
                },
                {
                    "path": "ios.py",
                    "stock": None,
                    "current": installer.digest(self.payload / "files/ios.py"),
                },
            ],
            "runtime": {"Scripts/python.exe": installer.digest(runtime)},
        }
        (self.payload / "manifest.json").write_text(json.dumps(self.manifest))
        self.addCleanup(patch.stopall)
        patch.object(installer, "idle").start()
        patch.object(installer.subprocess, "run").start()

    def assert_original(self):
        self.assertEqual((self.package / "base.py").read_text(), "old backend")
        self.assertFalse((self.package / "ios.py").exists())
        self.assertEqual((self.app / "settings.toml").read_text(), "attempts = 7")
        self.assertEqual((self.app / "ios-runtime/old.txt").read_text(), "old runtime")
        self.assertFalse((self.app / "ios-support-install.json").exists())

    def test_install_restore_preserves_settings_and_previous_runtime(self):
        installer.install(self.app, self.payload)
        self.assertEqual((self.package / "base.py").read_text(), "new backend")
        self.assertEqual((self.app / "settings.toml").read_text(), "attempts = 7")
        installer.restore(self.app)
        self.assert_original()

    def test_wrong_version_does_not_change_app(self):
        (self.app / "adb-auto-player.exe").write_bytes(b"wrong version")
        with self.assertRaisesRegex(RuntimeError, "12.13.0"):
            installer.install(self.app, self.payload)
        self.assert_original()

    def test_corrupt_payload_does_not_change_app(self):
        (self.payload / "files/ios.py").write_text("corrupt")
        with self.assertRaisesRegex(RuntimeError, "damaged"):
            installer.install(self.app, self.payload)
        self.assert_original()

    def test_copy_failure_rolls_back_files_and_runtime(self):
        original_copy = installer.shutil.copy2

        def fail_new_module(src, dst, *args, **kwargs):
            if Path(src) == self.payload / "files/ios.py":
                raise OSError("Simulated write failure")
            return original_copy(src, dst, *args, **kwargs)

        with patch.object(installer.shutil, "copy2", side_effect=fail_new_module):
            with self.assertRaisesRegex(OSError, "Simulated"):
                installer.install(self.app, self.payload)
        self.assert_original()

    def test_restore_refuses_later_modifications(self):
        installer.install(self.app, self.payload)
        (self.package / "base.py").write_text("later update")
        with self.assertRaisesRegex(RuntimeError, "changed since"):
            installer.restore(self.app)
        self.assertEqual((self.package / "base.py").read_text(), "later update")
        self.assertTrue((self.app / "ios-runtime/Scripts/python.exe").exists())


if __name__ == "__main__":
    unittest.main()
