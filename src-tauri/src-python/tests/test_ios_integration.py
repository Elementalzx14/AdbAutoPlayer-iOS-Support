"""Device routing tests; no USB access or game actions."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from adb_auto_player.device.ios import integration
from adb_auto_player.device.task_dispatch import execute_for_device
from adb_auto_player.models.pydantic.adb_settings import AdbSettings


def test_old_android_settings_remain_android(tmp_path):
    config = tmp_path / "ADB.toml"
    config.write_text('[device]\nid = "old-device"\n')
    settings = AdbSettings.from_toml(config)
    assert not settings.ios.enabled
    assert settings.device.id == "old-device"


def test_ios_settings_only_select_the_device(tmp_path):
    config = tmp_path / "ADB.toml"
    config.write_text("[ios]\nenabled = true\nstages = 1\nminutes = 5\nattempts = 2\n")
    settings = AdbSettings.from_toml(config)
    assert settings.ios.enabled
    assert set(type(settings.ios).model_fields) == {"enabled", "python_path"}


def test_android_dispatch_is_unchanged():
    with (
        patch(
            "adb_auto_player.device.task_dispatch.SettingsLoader.adb_settings",
            return_value=AdbSettings(),
        ),
        patch(
            "adb_auto_player.util.Execute.find_command_and_execute", return_value=True
        ) as android,
    ):
        assert execute_for_device("AFKStages", {}) is True
        android.assert_called_once_with("AFKStages", {})


@pytest.mark.parametrize(
    "command",
    ["AFKStages", "SeasonAFKStages", "DurasTrials", "SeasonLegendTrial", "Dailies"],
)
def test_ios_uses_the_original_task_dispatcher(command):
    with (
        patch(
            "adb_auto_player.device.task_dispatch.SettingsLoader.adb_settings",
            return_value=AdbSettings(ios={"enabled": True}),
        ),
        patch(
            "adb_auto_player.util.Execute.find_command_and_execute", return_value=True
        ) as shared,
        patch("adb_auto_player.device.ios.controller.IOSController.close_all") as close,
    ):
        assert execute_for_device(command, {}) is True
        shared.assert_called_once_with(command, {})
        close.assert_called_once()


def test_ios_keeps_the_original_menu_and_settings_file():
    from adb_auto_player.tauri_helpers import menu

    with patch.object(
        menu.SettingsLoader,
        "adb_settings",
        return_value=AdbSettings(ios={"enabled": True}),
    ):
        metadata = menu.get_game_metadata()
        assert metadata.settings_file == "AFKJourney.toml"
        game = integration.game_menu()
        labels = {option.label for option in game.menu_options}
        assert {"AFK Stages", "Dura's Trials", "Season Legend Trial"} <= labels
        assert game.settings_file == "AFKJourney.toml"
        schema = metadata.gui_metadata.settings_class.model_json_schema()
        assert {"AFK Stages", "Dura's Trials", "Legend Trial"} <= schema[
            "properties"
        ].keys()


def test_game_chooses_device_backend_without_changing_settings():
    from adb_auto_player.games.afk_journey.base import AFKJourneyBase
    from adb_auto_player.device.ios.controller import IOSController

    with patch(
        "adb_auto_player.game.game.SettingsLoader.adb_settings",
        return_value=AdbSettings(ios={"enabled": True}),
    ):
        game = AFKJourneyBase()
        assert isinstance(game.device, IOSController)
        assert game.device.resolution == game.base_resolution


def test_usb_status_never_opens_a_tunnel():
    with (
        patch.object(integration, "worker_command", return_value=["worker"]),
        patch.object(integration.subprocess, "run") as devices,
    ):
        devices.return_value = SimpleNamespace(
            returncode=0, stdout='{"connected": true}'
        )
        assert integration.connected_device() == "iPhone (USB)"
        assert devices.call_args.args[0] == ["worker", "--status"]
        devices.return_value.stdout = '{"connected": false}'
        assert integration.connected_device() is None


def test_profiles_cannot_control_usb_concurrently(tmp_path):
    from adb_auto_player.device.ios.usb_lock import exclusive_run

    with exclusive_run(tmp_path):
        with pytest.raises(RuntimeError, match="already active"):
            with exclusive_run(tmp_path):
                pytest.fail("Second run acquired the same phone")


def test_stop_prevents_any_device_request():
    from adb_auto_player.device.ios.controller import IOSController
    from adb_auto_player.models.device import Resolution

    with patch.object(IOSController, "stop_requested", return_value=True):
        device = IOSController(Resolution(1080, 1920))
        with patch.object(device, "_connect") as connect:
            with pytest.raises(KeyboardInterrupt):
                device.request("tap", x=50, y=50)
            connect.assert_not_called()


def test_saved_device_mode_invalidates_profile_cache(tmp_path):
    # Exercise the real desktop invalidator without importing the native UI module.
    import ast
    from pathlib import Path
    from adb_auto_player.file_loader import SettingsLoader
    from adb_auto_player.models.decorators import CacheGroup
    from adb_auto_player.tauri_context import TauriContext

    entrypoint = Path(__file__).parents[1] / "adb_auto_player/__main__.py"
    module = ast.parse(entrypoint.read_text(encoding="utf-8"))
    invalidator = next(
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == "_cache_clear"
    )
    namespace = {
        "CacheGroup": CacheGroup,
        "SettingsLoader": SettingsLoader,
        "CACHE_REGISTRY": {},
    }
    exec(
        compile(
            ast.Module(body=[invalidator], type_ignores=[]), str(entrypoint), "exec"
        ),
        namespace,
    )
    previous_profile = TauriContext.get_profile_index()
    TauriContext.set_profile_index(97)
    try:
        with patch.object(SettingsLoader, "get_app_config_dir", return_value=tmp_path):
            path = tmp_path / "ADB.toml"
            path.write_text("[ios]\nenabled = false\n")
            assert not SettingsLoader.adb_settings().ios.enabled
            path.write_text("[ios]\nenabled = true\n")
            assert not SettingsLoader.adb_settings().ios.enabled
            namespace["_cache_clear"](CacheGroup.ADB_SETTINGS, 97)
            assert SettingsLoader.adb_settings().ios.enabled
    finally:
        SettingsLoader.adb_settings.cache_clear(97)
        TauriContext.set_profile_index(previous_profile)
