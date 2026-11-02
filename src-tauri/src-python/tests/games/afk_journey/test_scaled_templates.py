"""Shared assets retain shape, crop constraints, and dim-overlay rejection."""

from types import SimpleNamespace

import cv2
import numpy as np
import pytest
from adb_auto_player.games.afk_journey.scaled_templates import ScaledTemplates
from adb_auto_player.models.image_manipulation import CropRegions
from adb_auto_player.models.template_matching import MatchMode


def _position(point):
    return point.x, point.y


@pytest.mark.parametrize("grayscale", [False, True])
def test_uniform_original_asset_matches_with_full_frame_offset(grayscale):
    template = np.random.default_rng(3).integers(40, 250, (100, 180, 3), dtype=np.uint8)
    matcher = ScaledTemplates(SimpleNamespace(_load_image=lambda name: template))
    frame = np.zeros((1920, 1080, 3), np.uint8)
    variant = matcher.variants("control.png", 1080, 1554)[2]
    h, w = variant.shape[:2]
    frame[1400 : 1400 + h, 700 : 700 + w] = variant
    result = matcher.match(
        "control.png",
        frame,
        (0, 183, 1080, 1554),
        CropRegions(top=0.6),
        0.8,
        grayscale,
        MatchMode.BEST,
    )
    assert result is not None
    assert _position(result.box.top_left) == (700, 1400)
    assert result.box.width == w
    assert result.box.height == h
    assert (
        matcher.match(
            "control.png",
            frame,
            (0, 183, 1080, 1554),
            CropRegions(bottom=0.6),
            0.8,
            grayscale,
            MatchMode.BEST,
        )
        is None
    )
    assert (
        matcher.match(
            "control.png",
            (frame * 0.4).astype(np.uint8),
            (0, 183, 1080, 1554),
            CropRegions(),
            0.8,
            grayscale,
            MatchMode.BEST,
        )
        is None
    )


def test_stretched_template_and_blank_frame_do_not_match():
    template = np.random.default_rng(6).integers(0, 255, (60, 140, 3), dtype=np.uint8)
    matcher = ScaledTemplates(SimpleNamespace(_load_image=lambda name: template))
    frame = np.zeros((1920, 1080, 3), np.uint8)
    frame[1300:1340, 400:540] = cv2.resize(template, (140, 40))
    assert (
        matcher.match(
            "control.png",
            frame,
            (0, 183, 1080, 1554),
            CropRegions(),
            0.8,
            False,
            MatchMode.BEST,
        )
        is None
    )


def test_repeated_controls_have_full_frame_coordinates_without_scale_duplicates():
    template = np.random.default_rng(5).integers(0, 255, (40, 60, 3), dtype=np.uint8)
    matcher = ScaledTemplates(SimpleNamespace(_load_image=lambda name: template))
    frame = np.zeros((1920, 1080, 3), np.uint8)
    variant = matcher.variants("control.png", 1080, 1554)[2]
    h, w = variant.shape[:2]
    for x, y in [(200, 1300), (700, 1400)]:
        frame[y : y + h, x : x + w] = variant
    results = matcher.match_all(
        "control.png", frame, (0, 183, 1080, 1554), CropRegions(top=0.6), 0.9, False, 10
    )
    assert sorted((m.box.top_left.x, m.box.top_left.y) for m in results) == [
        (200, 1300),
        (700, 1400),
    ]


def test_ocr_derived_pixel_crop_is_not_projected_twice():
    frame = np.zeros((1920, 1080, 3), np.uint8)
    crop, offset = ScaledTemplates.region(
        frame,
        (0, 183, 1080, 1554),
        CropRegions(left=200, top=1400, right=700, bottom=400),
    )
    assert _position(offset) == (200, 1400)
    assert crop.shape == (120, 180, 3)


def test_difference_search_preserves_full_frame_coordinates():
    template = np.zeros((40, 40, 3), np.uint8)
    matcher = ScaledTemplates(SimpleNamespace(_load_image=lambda name: template))
    frame = np.zeros((1920, 1080, 3), np.uint8)
    frame[1400:1432, 700:732] = 255
    result = matcher.worst(
        "empty.png", frame, (0, 183, 1080, 1554), CropRegions(top=0.6), False
    )
    assert result is not None
    assert _position(result.box.top_left) == (700, 1400)
    assert (
        matcher.worst(
            "empty.png", frame * 0, (0, 183, 1080, 1554), CropRegions(), False
        )
        is None
    )


@pytest.mark.parametrize(
    "model,viewport",
    [("iPhone18,2", (98, 0, 884, 1920)), ("iPad13,16", (0, 183, 1080, 1554))],
)
def test_shared_asset_policy_applies_to_phones_and_tablets(model, viewport):
    from unittest.mock import MagicMock, patch

    from adb_auto_player.file_loader import SettingsLoader
    from adb_auto_player.games.afk_journey.base import AFKJourneyBase
    from adb_auto_player.models.pydantic.adb_settings import AdbSettings

    with patch.object(
        SettingsLoader, "adb_settings", return_value=AdbSettings(ios={"enabled": True})
    ):
        game = AFKJourneyBase()
        game._device = SimpleNamespace(metadata={"model": model, "viewport": viewport})
        original = np.random.default_rng(2).integers(
            0, 255, (48, 72, 3), dtype=np.uint8
        )
        game._load_image = lambda name: original
        game.get_screenshot = MagicMock()
        variant = game.layout.matcher.shared_templates.variants(
            "shared/button.png", viewport[2], viewport[3]
        )[2]
        frame = np.zeros((1920, 1080, 3), np.uint8)
        frame[800 : 800 + variant.shape[0], 400 : 400 + variant.shape[1]] = variant
        result = game.game_find_template_match(
            "shared/button.png",
            screenshot=frame,
            crop_regions=CropRegions(top=0.2, left=0.2, bottom=0.2),
        )
        assert result is not None and _position(result.box.top_left) == (400, 800)
        game.get_screenshot.assert_not_called()
