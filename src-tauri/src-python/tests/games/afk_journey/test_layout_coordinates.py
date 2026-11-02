"""Keep reference positions and detected screenshot positions distinct."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from adb_auto_player.file_loader import SettingsLoader
from adb_auto_player.games.afk_journey.base import AFKJourneyBase
from adb_auto_player.models import ConfidenceValue
from adb_auto_player.models.geometry import Box, Point, ReferencePoint
from adb_auto_player.models.pydantic.adb_settings import AdbSettings
from adb_auto_player.models.template_matching import TemplateMatchResult


def _position(point):
    return point.x, point.y


@pytest.fixture
def game():
    with patch.object(
        SettingsLoader, "adb_settings", return_value=AdbSettings(ios={"enabled": True})
    ):
        game = AFKJourneyBase()
        game._device = MagicMock()
        game._device.metadata = {"model": "iPad13,16", "viewport": (0, 183, 1080, 1554)}
        game._device.get_display_info.return_value = SimpleNamespace(
            dimensions=(1080, 1920)
        )
        yield game


def test_fixed_tap_and_hold_stay_inside_content(game):
    game.tap(ReferencePoint(550, 1800))
    sent = game.device.tap.call_args.args[0]
    assert _position(sent) == (550, 1640)
    game.hold(ReferencePoint(550, 1800), duration=0.5)
    assert _position(game.device.hold.call_args.kwargs["coordinates"]) == _position(
        sent
    )


def test_detected_controls_are_never_projected_again(game):
    detected = TemplateMatchResult("battle.png", 0.99, Box(Point(810, 1570), 140, 50))
    game.tap(detected)
    assert game.device.tap.call_args.args[0] is detected
    image_point = Point(300, 1500)
    assert game.resolve_input_coordinates(image_point) is image_point


def test_reference_swipe_and_image_swipe_use_distinct_spaces(game):
    game.swipe_up(x=540, sy=1500, ey=700, reference=True)
    start, end = game.device.swipe.call_args.args
    assert _position(start) == (540, 1397)
    assert _position(end) == (540, 749)
    game.swipe_right(y=1000, sx=200, ex=900)
    start, end = game.device.swipe.call_args.args
    assert _position(start) == (200, 1000)
    assert _position(end) == (900, 1000)


def test_projection_follows_metadata_when_device_connects(game):
    game.device.metadata = {}
    assert _position(game.resolve_input_coordinates(ReferencePoint(550, 1800))) == (
        550,
        1800,
    )
    game.device.metadata = {"model": "iPad13,16", "viewport": (0, 183, 1080, 1554)}
    assert _position(game.resolve_input_coordinates(ReferencePoint(550, 1800))) == (
        550,
        1640,
    )


def test_reference_edges_never_touch_letterbox(game):
    assert _position(game.resolve_input_coordinates(ReferencePoint(1080, 1920))) == (
        1079,
        1736,
    )
    assert _position(game.resolve_input_coordinates(ReferencePoint(0, 0))) == (0, 183)


def test_offset_from_detected_control_scales_only_the_delta(game):
    assert _position(game.layout.offset_point(game, Point(500, 900), dy=500)) == (
        500,
        1305,
    )


def test_fixed_crop_box_projects_but_detected_box_does_not(game):
    box = Box(ReferencePoint(150, 440), 770, 1180)
    resolved = game.layout.resolve_box(game, box)
    assert _position(resolved.top_left) == (150, 539)
    assert resolved.width == 770
    assert resolved.height == 955
    detected = Box(Point(150, 539), 770, 955)
    assert game.layout.resolve_box(game, detected) is detected


def test_reference_pixel_crops_use_viewport_while_dynamic_pixel_crops_stay_absolute(
    game,
):
    from adb_auto_player.models.image_manipulation import CropRegions

    frame = np.zeros((1920, 1080, 3), np.uint8)
    cropped = game.layout.crop_reference(
        game, frame, CropRegions(left=0.1, right=0.1, top=980, bottom=740)
    )
    assert _position(cropped.offset) == (108, 976)
    assert cropped.image.shape == (162, 864, 3)


@pytest.mark.parametrize("grayscale", [False, True])
@pytest.mark.parametrize("cropped", [False, True])
def test_shared_template_search_keeps_full_frame_and_single_capture(grayscale, cropped):
    from adb_auto_player.game._template_mixin import _TemplateMixin
    from adb_auto_player.models.image_manipulation import CropRegions

    image = np.zeros((100, 120, 3), dtype=np.uint8)
    template = np.random.default_rng(4).integers(0, 255, (10, 12, 3), dtype=np.uint8)
    image[60:70, 70:82] = template
    game = SimpleNamespace(
        get_screenshot=MagicMock(return_value=image),
        default_threshold=ConfidenceValue(0.95),
        _load_image=lambda template, grayscale: pattern,
    )
    import cv2

    pattern = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY) if grayscale else template
    game.game_find_template_match = lambda *a, **kw: (
        _TemplateMixin.game_find_template_match(game, *a, **kw)
    )
    result = _TemplateMixin.find_any_template(
        game,
        ["control.png"],
        grayscale=grayscale,
        crop_regions=CropRegions(left=0.5, top=0.5) if cropped else CropRegions(),
    )
    assert result is not None
    assert _position(result.box.top_left) == (70, 60)
    game.get_screenshot.assert_called_once()
