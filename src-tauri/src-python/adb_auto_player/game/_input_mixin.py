"""Input control mixin — tap, hold, swipe operations."""

import logging
import threading
from dataclasses import dataclass
from enum import StrEnum, auto
from time import sleep

from adb_auto_player.file_loader import SettingsLoader
from adb_auto_player.models.geometry import Coordinates, Point, ReferencePoint

from ._base import _GameBase


class _SwipeDirection(StrEnum):
    UP = auto()
    DOWN = auto()
    LEFT = auto()
    RIGHT = auto()

    @property
    def is_vertical(self) -> bool:
        """Return True if the direction is vertical (UP or DOWN)."""
        return self in {_SwipeDirection.UP, _SwipeDirection.DOWN}

    @property
    def is_increasing(self) -> bool:
        """Return True if the coordinate increases in the direction (DOWN or RIGHT)."""
        return self in {_SwipeDirection.DOWN, _SwipeDirection.RIGHT}


@dataclass
class _SwipeParams:
    direction: _SwipeDirection
    x: int | None = None
    y: int | None = None
    start: int | None = None
    end: int | None = None
    duration: float = 1.0
    reference: bool = False


class _InputMixin(_GameBase):
    """Mixin providing all user-input operations (tap, hold, swipe)."""

    def tap(
        self,
        coordinates: Coordinates,
        scale: bool = False,  # TODO remove later
        blocking: bool = True,
        # Assuming 30 FPS, 1 Tap per Frame
        non_blocking_sleep_duration: float | None = 1 / 30,
        log_message: str | None = None,
        log: bool = True,
    ) -> None:
        """Tap the screen on the given point.

        Args:
            coordinates (Coordinates): Point to click on.
            scale (bool, optional): Deprecated — does nothing.
            blocking (bool, optional): Whether to block until ADB confirms the tap.
            non_blocking_sleep_duration (float, optional): Sleep time in seconds for
                non-blocking taps, needed to not DoS the ADB server.
            log_message (str | None, optional): Custom log message; default if None.
            log (bool, optional): Log the tap command.
        """
        if log:
            log_message = (log_message or "Tapped") + f": {coordinates}"
        else:
            log_message = None

        if blocking:
            self._click(coordinates, log_message)
        else:
            thread = threading.Thread(
                target=self._click,
                args=(coordinates, log_message),
                daemon=True,
            )
            thread.start()
            if non_blocking_sleep_duration is not None:
                sleep(non_blocking_sleep_duration)

    def _click(
        self,
        coordinates: Coordinates,
        log_message: str | None = None,
    ) -> None:
        """Internal click method — logging should be handled by the caller."""
        self.device.tap(
            self._apply_vertical_offset(self.resolve_input_coordinates(coordinates))
        )
        if log_message is not None:
            logging.debug(log_message)

    @staticmethod
    def _apply_vertical_offset(coordinates: Coordinates) -> Coordinates:
        """Translate a screenshot-space point to real device coordinates.

        Counterpart to `_ScreenshotMixin._apply_vertical_offset_to_screenshot`:
        OCR/template coordinates are computed from the offset-corrected
        screenshot, so `vertical_offset` must be added back before sending a
        real tap/swipe to the device.
        """
        offset = SettingsLoader.adb_settings().device.vertical_offset
        if offset == 0:
            return coordinates
        return Point(coordinates.x, coordinates.y + offset)

    def press_back_button(self) -> None:
        """Press the device back button."""
        self.device.press_back_button()

    def swipe(
        self, start: Coordinates, end: Coordinates, duration: float = 1.0
    ) -> None:
        """Swipe between resolved points, including fixed reference coordinates."""
        self.device.swipe(
            self._apply_vertical_offset(self.resolve_input_coordinates(start)),
            self._apply_vertical_offset(self.resolve_input_coordinates(end)),
            duration=duration,
        )

    def swipe_down(
        self,
        x: int | None = None,
        sy: int | None = None,
        ey: int | None = None,
        duration: float = 1.0,
        *,
        reference: bool = False,
    ) -> None:
        """Perform a vertical swipe from top to bottom.

        Args:
            x (int, optional): X-coordinate. Defaults to horizontal center.
            sy (int, optional): Start Y. Defaults to top edge (0).
            ey (int, optional): End Y. Defaults to bottom edge.
            duration (float, optional): Duration in seconds. Defaults to 1.0.
            reference: Interpret positions in the game's reference resolution.
        """
        self._swipe_direction(
            _SwipeParams(
                _SwipeDirection.DOWN,
                x=x,
                start=sy,
                end=ey,
                duration=duration,
                reference=reference,
            )
        )

    def swipe_up(
        self,
        x: int | None = None,
        sy: int | None = None,
        ey: int | None = None,
        duration: float = 1.0,
        *,
        reference: bool = False,
    ) -> None:
        """Perform a vertical swipe from bottom to top.

        Args:
            x (int, optional): X-coordinate. Defaults to horizontal center.
            sy (int, optional): Start Y. Defaults to bottom edge.
            ey (int, optional): End Y. Defaults to top edge (0).
            duration (float, optional): Duration in seconds. Defaults to 1.0.
            reference: Interpret positions in the game's reference resolution.
        """
        self._swipe_direction(
            _SwipeParams(
                _SwipeDirection.UP,
                x=x,
                start=sy,
                end=ey,
                duration=duration,
                reference=reference,
            )
        )

    def swipe_right(
        self,
        y: int | None = None,
        sx: int | None = None,
        ex: int | None = None,
        duration: float = 1.0,
        *,
        reference: bool = False,
    ) -> None:
        """Perform a horizontal swipe from left to right.

        Args:
            y (int, optional): Y-coordinate. Defaults to vertical center.
            sx (int, optional): Start X. Defaults to left edge (0).
            ex (int, optional): End X. Defaults to right edge.
            duration (float, optional): Duration in seconds. Defaults to 1.0.
            reference: Interpret positions in the game's reference resolution.
        """
        self._swipe_direction(
            _SwipeParams(
                _SwipeDirection.RIGHT,
                y=y,
                start=sx,
                end=ex,
                duration=duration,
                reference=reference,
            )
        )

    def swipe_left(
        self,
        y: int | None = None,
        sx: int | None = None,
        ex: int | None = None,
        duration: float = 1.0,
        *,
        reference: bool = False,
    ) -> None:
        """Perform a horizontal swipe from right to left.

        Args:
            y (int, optional): Y-coordinate. Defaults to vertical center.
            sx (int, optional): Start X. Defaults to right edge.
            ex (int, optional): End X. Defaults to left edge (0).
            duration (float, optional): Duration in seconds. Defaults to 1.0.
            reference: Interpret positions in the game's reference resolution.
        """
        self._swipe_direction(
            _SwipeParams(
                _SwipeDirection.LEFT,
                y=y,
                start=sx,
                end=ex,
                duration=duration,
                reference=reference,
            )
        )

    def _swipe_direction(self, params: _SwipeParams) -> None:
        resolution = self.base_resolution if params.reference else self.display_info
        rx, ry = resolution.dimensions
        direction = params.direction

        coord = params.x if direction.is_vertical else params.y
        coord = (
            (rx // 2 if direction.is_vertical else ry // 2) if coord is None else coord
        )

        start = params.start or (
            0 if direction.is_increasing else (ry if direction.is_vertical else rx)
        )
        end = params.end or (
            (ry if direction.is_vertical else rx) if direction.is_increasing else 0
        )

        if (direction.is_increasing and start >= end) or (
            not direction.is_increasing and start <= end
        ):
            raise ValueError(
                f"Start must be {'less' if direction.is_increasing else 'greater'} "
                f"than end to swipe {direction.value}."
            )

        sx, sy, ex, ey = (
            (coord, start, coord, end)
            if direction.is_vertical
            else (start, coord, end, coord)
        )

        logging.debug(f"swipe_{direction} - from ({sx}, {sy}) to ({ex}, {ey})")
        point_type = ReferencePoint if params.reference else Point
        self.swipe(
            point_type(sx, sy),
            point_type(ex, ey),
            duration=params.duration,
        )

    def hold(
        self,
        coordinates: Coordinates,
        duration: float = 3.0,
        blocking: bool = True,
        log: bool = True,
    ) -> threading.Thread | None:
        """Hold a point on the screen.

        Args:
            coordinates (Coordinates): Point on the screen.
            duration (float, optional): Hold duration. Defaults to 3.0.
            blocking (bool, optional): Whether the call blocks.
            log (bool, optional): Log the hold command.
        """
        resolved = self.resolve_input_coordinates(coordinates)
        point = self._apply_vertical_offset(Point(resolved.x, resolved.y))

        if log:
            logging.debug(
                f"hold: ({coordinates.x}, {coordinates.y}) for {duration} seconds"
            )

        if blocking:
            self.device.hold(coordinates=point, duration=duration)
            return None

        thread = threading.Thread(
            target=self.device.hold,
            kwargs={"coordinates": point, "duration": duration},
            daemon=True,
        )
        thread.start()
        return thread
