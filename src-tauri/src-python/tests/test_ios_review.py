"""Pure geometry, diagnostics and application-identity regression tests."""

from pathlib import Path
from unittest.mock import patch
import numpy as np
import pytest
from adb_auto_player.device.ios.geometry import Canvas
from adb_auto_player.device.ios.bundles import resolve_bundle
from adb_auto_player.device.ios import integration
from adb_auto_player.device.ios.controller import IOSController
from adb_auto_player.device.adb import AdbController
from adb_auto_player.device.protocol import DeviceController
from adb_auto_player.models.device import Resolution
from adb_auto_player.models.pydantic.adb_settings import AdbSettings


@pytest.mark.parametrize(
    "size", [(1320, 2868), (1179, 2556), (1170, 2532), (750, 1334), (2048, 2732)]
)
def test_canvas_roundtrip_preserves_entire_native_screen(size):
    canvas = Canvas(*size, 1080, 1920)
    left, top, w, h = canvas.viewport
    assert canvas.native_point(left, top) == (0, 0)
    assert canvas.native_point(left + w - 1, top + h - 1) == (size[0] - 1, size[1] - 1)
    assert abs(w / h - size[0] / size[1]) < 0.002
    frame = canvas.render(np.full((size[1], size[0], 3), 255, np.uint8))
    assert frame.shape == (1920, 1080, 3)
    assert np.all(frame[top : top + h, left : left + w] == 255)
    if left:
        with pytest.raises(ValueError, match="letterbox"):
            canvas.native_point(left - 1, top)
    if top:
        with pytest.raises(ValueError, match="letterbox"):
            canvas.native_point(left, top - 1)


def test_real_apple_bundle_mapping():
    assert (
        resolve_bundle(["com.farlightgames.igame.gp"]) == "com.farlightgames.igame.ios"
    )
    assert (
        resolve_bundle(["com.farlightgames.igame.ios"]) == "com.farlightgames.igame.ios"
    )
    with pytest.raises(ValueError):
        resolve_bundle(["unknown.game"])


def test_both_controllers_satisfy_common_interface():
    assert isinstance(IOSController(Resolution(1080, 1920)), DeviceController)
    with patch(
        "adb_auto_player.device.adb.adb_controller.AdbDeviceWrapper.create_from_settings"
    ):
        assert isinstance(AdbController(), DeviceController)


def test_shared_runtime_is_preferred_without_custom_path():
    with (
        patch.object(
            integration.SettingsLoader, "adb_settings", return_value=AdbSettings()
        ),
        patch.object(integration.importlib.util, "find_spec", return_value=object()),
    ):
        assert integration.worker_command()[0] == str(Path(integration.sys.executable))


def test_explicit_legacy_runtime_still_wins(tmp_path):
    runtime = tmp_path / "python.exe"
    runtime.touch()
    with patch.object(
        integration.SettingsLoader,
        "adb_settings",
        return_value=AdbSettings(ios={"python_path": str(runtime)}),
    ):
        assert integration.worker_command()[0] == str(runtime)


def test_missing_runtime_has_actionable_error(tmp_path):
    with patch.object(
        integration.SettingsLoader,
        "adb_settings",
        return_value=AdbSettings(ios={"python_path": str(tmp_path / "missing.exe")}),
    ):
        with pytest.raises(RuntimeError, match="runtime is missing"):
            integration.worker_command()


def test_connection_errors_distinguish_unplug_from_locked():
    from adb_auto_player.device.ios.device_worker import device_error

    assert "disconnected" in device_error(
        RuntimeError("Connect exactly one unlocked, trusted iPhone by USB.")
    )
    assert device_error(RuntimeError("Device locked")).startswith("Unlock")
    assert "Trust This Computer" in device_error(
        RuntimeError("InvalidHostID pairing failed")
    )
    assert "operation rejected" in device_error(ValueError("letterbox"))


def test_diagnostics_do_not_mask_original_errors():
    from adb_auto_player.games.afk_journey.base import AFKJourneyBase
    from adb_auto_player.file_loader import SettingsLoader

    with patch.object(
        SettingsLoader, "adb_settings", side_effect=RuntimeError("Config unavailable")
    ):
        AFKJourneyBase().capture_debug_screenshot("failure")


def test_failed_template_report_includes_score_and_threshold():
    from adb_auto_player.games.afk_journey.base import AFKJourneyBase
    from adb_auto_player.file_loader import SettingsLoader

    with patch.object(
        SettingsLoader, "adb_settings", return_value=AdbSettings(ios={"enabled": True})
    ):
        game = AFKJourneyBase()
        report = {}
        assert (
            game._ios_match(
                "battle/battle.png",
                np.zeros((1920, 1080, 3), np.uint8),
                diagnostics=report,
            )
            is None
        )
        assert report["battle/battle.png"]["matched"] is False
        assert "score" in report["battle/battle.png"]
        assert report["battle/battle.png"]["threshold"] >= 0.91


def test_locked_device_rejects_input_before_touch(tmp_path):
    pytest.importorskip("pymobiledevice3")
    import asyncio
    from unittest.mock import AsyncMock
    from types import SimpleNamespace
    from adb_auto_player.device.ios.phone import Phone, DeviceLockedError

    phone = Phone(tmp_path)
    phone.lockdown = SimpleNamespace(get_value=AsyncMock(return_value=True))
    with pytest.raises(DeviceLockedError, match="Unlock"):
        asyncio.run(phone.tap(1, 1, 1320, 2868))
    assert phone.hid is None
    phone.lockdown.get_value.return_value = False
    asyncio.run(phone.ensure_unlocked())
