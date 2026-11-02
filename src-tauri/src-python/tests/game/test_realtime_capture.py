"""Reaction-based tasks stop before using an unsuitable capture path."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import cv2
import numpy as np
import pytest
from adb_auto_player.exceptions import AutoPlayerWarningError
from adb_auto_player.game._lifecycle_mixin import _LifecycleMixin
from adb_auto_player.game._screenshot_mixin import _ScreenshotMixin


def test_reaction_task_rejects_screenshot_fallback_without_tapping():
    game = SimpleNamespace(
        get_screenshot=MagicMock(),
        tap=MagicMock(),
        device=SimpleNamespace(
            realtime_capture_ready=False, supports_offscreen_taps=False
        ),
    )
    with pytest.raises(AutoPlayerWarningError, match="needs video capture"):
        _LifecycleMixin.assert_frame_and_input_delay_below_threshold(game)
    game.tap.assert_not_called()


def test_video_benchmark_skips_unsupported_offscreen_taps():
    game = SimpleNamespace(
        get_screenshot=MagicMock(),
        tap=MagicMock(),
        device=SimpleNamespace(
            realtime_capture_ready=True, supports_offscreen_taps=False
        ),
    )
    _LifecycleMixin.assert_frame_and_input_delay_below_threshold(game)
    assert game._realtime_capture_required is True
    game.tap.assert_not_called()


@pytest.mark.parametrize("required", [False, True])
def test_video_loss_stops_reaction_tasks_but_normal_tasks_can_use_screenshots(required):
    pixels = np.zeros((20, 10, 3), np.uint8)
    _, encoded = cv2.imencode(".bmp", pixels)
    game = SimpleNamespace(
        _raise_if_game_closed=MagicMock(),
        _stream=None,
        _realtime_capture_required=required,
        package_name_prefixes=[],
        _apply_vertical_offset_to_screenshot=lambda image: image,
        device=SimpleNamespace(
            realtime_capture_ready=False,
            screenshot=MagicMock(return_value=encoded.tobytes()),
        ),
    )
    if required:
        with pytest.raises(
            AutoPlayerWarningError, match="Video capture was interrupted"
        ):
            _ScreenshotMixin.get_screenshot(game)
    else:
        assert _ScreenshotMixin.get_screenshot(game).shape == (20, 10, 3)
    game.device.screenshot.assert_called_once()
