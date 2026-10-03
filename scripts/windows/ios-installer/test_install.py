"""Installer version checks, atomic writes, rollback and interrupted recovery."""

import importlib.util
import json
import sys
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
        # Match the CLI boundary, including Windows short-name temp directories.
        self.root = Path(self.temp.name).resolve()
        self.app = self.root / "app"
        self.payload = self.root / "payload"
        self.app.mkdir()
        (self.payload / "files/Lib/site-packages").mkdir(parents=True)
        (self.app / "Lib/site-packages").mkdir(parents=True)
        self.old = "Lib/site-packages/base.py"
        self.new = "Lib/site-packages/new_dependency.py"
        (self.app / "adb-auto-player.exe").write_bytes(b"official exe")
        (self.app / "python.exe").write_bytes(b"official Python 3.13")
        (self.app / "AFKJourney.toml").write_text("attempts = 7")
        (self.app / self.old).write_text("old backend")
        (self.payload / "files" / self.old).write_text("new backend")
        (self.payload / "files" / self.new).write_text("dependency")
        self.manifest = {
            "format": 2,
            "version": "12.13.0-ios.2",
            "base": {
                name: installer.digest(self.app / name)
                for name in ["adb-auto-player.exe", "python.exe"]
            },
            "files": [
                {
                    "path": name,
                    "current": installer.digest(self.payload / "files" / name),
                    "stock": installer.digest(self.app / name)
                    if (self.app / name).exists()
                    else None,
                }
                for name in [self.old, self.new]
            ],
        }
        (self.payload / "manifest.json").write_text(json.dumps(self.manifest))
        self.addCleanup(patch.stopall)
        patch.object(installer, "idle").start()
        patch.object(installer, "validate_runtime").start()

    def original(self):
        self.assertEqual((self.app / self.old).read_text(), "old backend")
        self.assertFalse((self.app / self.new).exists())
        self.assertEqual((self.app / "AFKJourney.toml").read_text(), "attempts = 7")
        self.assertFalse((self.app / "ios-runtime").exists())
        self.assertFalse((self.app / installer.MARKER).exists())
        self.assertFalse((self.app / installer.PENDING).exists())

    def test_install_restore_preserves_settings_and_shared_python(self):
        installer.install(self.app, self.payload)
        self.assertEqual((self.app / self.old).read_text(), "new backend")
        self.assertEqual(
            (self.app / "python.exe").read_bytes(), b"official Python 3.13"
        )
        self.assertFalse((self.app / "ios-runtime").exists())
        installer.restore(self.app)
        self.original()

    def test_wrong_version_is_rejected(self):
        (self.app / "adb-auto-player.exe").write_bytes(b"wrong")
        with self.assertRaisesRegex(RuntimeError, "12.13.0"):
            installer.install(self.app, self.payload)
        self.original()

    def test_corrupt_payload_is_rejected(self):
        (self.payload / "files" / self.new).write_text("bad")
        with self.assertRaisesRegex(RuntimeError, "damaged"):
            installer.install(self.app, self.payload)
        self.original()

    def test_dependency_validation_failure_rolls_back(self):
        with patch.object(
            installer, "validate_runtime", side_effect=RuntimeError("imports failed")
        ):
            with self.assertRaisesRegex(RuntimeError, "imports failed"):
                installer.install(self.app, self.payload)
        self.original()

    def test_failed_atomic_write_rolls_back(self):
        copy = installer.atomic_copy

        def failing(source, target):
            if Path(source) == self.payload / "files" / self.new:
                raise OSError("write failed")
            return copy(source, target)

        with patch.object(installer, "atomic_copy", side_effect=failing):
            with self.assertRaisesRegex(OSError, "write failed"):
                installer.install(self.app, self.payload)
        self.original()

    def test_restore_rejects_later_app_update(self):
        installer.install(self.app, self.payload)
        (self.app / self.old).write_text("later app update")
        with self.assertRaisesRegex(RuntimeError, "changed since"):
            installer.restore(self.app)
        self.assertEqual((self.app / self.old).read_text(), "later app update")

    def test_restore_validates_backups_before_changing_files(self):
        installer.install(self.app, self.payload)
        state = json.loads((self.app / installer.MARKER).read_text())
        (self.app / state["backup"] / "files" / self.old).write_text("bad backup")
        with self.assertRaisesRegex(RuntimeError, "Backup validation"):
            installer.restore(self.app)
        self.assertEqual((self.app / self.old).read_text(), "new backend")

    def test_interrupted_restore_can_be_retried(self):
        installer.install(self.app, self.payload)
        with patch.object(
            installer, "atomic_copy", side_effect=OSError("disk unavailable")
        ):
            with self.assertRaises(OSError):
                installer.restore(self.app)
        self.assertTrue((self.app / installer.PENDING).exists())
        installer.restore(self.app)
        self.original()

    def test_previous_preview_prompts_restore_before_update(self):
        (self.app / installer.MARKER).write_text('{"files":[]}')
        with self.assertRaisesRegex(RuntimeError, "Restore previous files"):
            installer.check(self.app, self.payload)

    def test_legacy_restore_with_isolated_module_search_path(self):
        target = self.app / "Lib/site-packages/adb_auto_player/legacy.py"
        target.parent.mkdir()
        target.write_text("legacy patch")
        backup = self.app / "ios-support-backups/legacy"
        saved = backup / "files/legacy.py"
        saved.parent.mkdir(parents=True)
        saved.write_text("stock backend")
        (self.app / "ios-runtime").mkdir()
        state = {
            "backup": str(backup.relative_to(self.app)),
            "runtime_existed": False,
            "files": [
                {
                    "path": "legacy.py",
                    "existed": True,
                    "current": installer.digest(target),
                    "backup_hash": installer.digest(saved),
                }
            ],
        }
        (self.app / installer.MARKER).write_text(json.dumps(state))
        helper_dir = Path(__file__).resolve().parent
        search_path = [p for p in sys.path if Path(p).resolve() != helper_dir]
        with patch.object(sys, "path", search_path):
            installer.restore(self.app)
        self.assertEqual(target.read_text(), "stock backend")
        self.assertTrue((backup / "removed-ios-runtime").is_dir())
        self.original()

    def test_path_escape_is_rejected(self):
        for path in ["../outside.py", "..\\outside.py", str(self.root / "outside.py")]:
            with self.assertRaises(ValueError):
                installer.inside(self.app, path)


if __name__ == "__main__":
    unittest.main()
