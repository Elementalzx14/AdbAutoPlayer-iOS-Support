"""Select the profile's device backend before creating any game controller."""

from adb_auto_player.file_loader import SettingsLoader


def execute_for_device(command, commands, stop=None):
    """Dispatch desktop and CLI tasks, keeping Android as the default."""
    from adb_auto_player.util import Execute  # noqa: PLC0415 -- optional runtime

    if not SettingsLoader.adb_settings().ios.enabled:
        return Execute.find_command_and_execute(command, commands)
    from .ios.controller import IOSController  # noqa: PLC0415

    IOSController.stop_requested = staticmethod(stop or (lambda: False))
    try:
        return Execute.find_command_and_execute(command, commands)
    finally:
        IOSController.close_all()
