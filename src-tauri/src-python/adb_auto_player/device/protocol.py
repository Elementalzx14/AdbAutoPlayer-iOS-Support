"""Operations shared by Android and Apple device controllers."""

from typing import Protocol, runtime_checkable

from adb_auto_player.models.device import DisplayInfo
from adb_auto_player.models.geometry import Coordinates


@runtime_checkable
class DeviceController(Protocol):
    """Transport-independent contract consumed by the game engine."""

    @property
    def identifier(self) -> str:
        """Human-readable device identifier."""
        ...

    def get_display_info(self) -> DisplayInfo:
        """Return the device canvas resolution and orientation."""
        ...

    def screenshot(self, package_name_prefixes=None) -> bytes:
        """Capture encoded screen pixels."""
        ...

    def tap(self, coordinates: Coordinates) -> None:
        """Tap one canvas coordinate."""
        ...

    def swipe(
        self, start_point: Coordinates, end_point: Coordinates, duration=1.0
    ) -> None:
        """Swipe between canvas coordinates."""
        ...

    def hold(self, coordinates: Coordinates, duration=1.0) -> None:
        """Hold one canvas coordinate."""
        ...

    def press_back_button(self) -> None:
        """Navigate back when supported."""
        ...

    def get_running_app(self) -> str | None:
        """Return the active game application identifier."""
        ...

    def start_game(self, package_name: str) -> None:
        """Launch a platform application identifier."""
        ...

    def stop_game(self, package_name: str) -> None:
        """Stop a platform application identifier."""
        ...

    def resolve_display_targeting(self, package_name_prefixes: list[str]) -> None:
        """Select the display or application for this game."""
        ...

    def reset_display_targeting(self) -> None:
        """Forget cached display targeting after a relaunch."""
        ...

    def set_display_size(self, display_size: str) -> None:
        """Request a display resize when supported."""
        ...
