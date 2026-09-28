"""iPhone visual equivalents for the existing AFK Journey task engine.

Only recognition and navigation vary; battle policies remain in AFKJourneyBase.
Coordinates use the same logical canvas and inverse touch mapping as IOSController.
"""

import json
from dataclasses import replace
from functools import cached_property, lru_cache
from pathlib import Path

import cv2
import numpy as np

from adb_auto_player.exceptions import GameActionFailedError
from adb_auto_player.file_loader import SettingsLoader
from adb_auto_player.image_manipulation import IO
from adb_auto_player.models import ConfidenceValue
from adb_auto_player.models.geometry import Box, Point
from adb_auto_player.models.image_manipulation import CropRegions
from adb_auto_player.models.template_matching import MatchMode, TemplateMatchResult


class IOSLayoutMixin:
    @property
    def using_ios(self):
        return SettingsLoader.adb_settings().ios.enabled

    @cached_property
    def _ios_visuals(self):
        folder = Path(__file__).with_name("ios_templates")
        manifest = json.loads((folder / "manifest.json").read_text())
        return {
            name: (spec, cv2.imread(str(folder / spec["file"])))
            for name, spec in manifest.items()
        }

    def _ios_match(self, name, frame, threshold=None):
        spec, template = self._ios_visuals[name]
        if template is None:
            raise GameActionFailedError("Missing iOS image: " + name)
        x1, y1, x2, y2 = spec["box"]
        margin = spec["margin"]
        left, top = max(0, x1 - margin), max(0, y1 - margin)
        roi = frame[
            top : min(frame.shape[0], y2 + margin),
            left : min(frame.shape[1], x2 + margin),
        ]
        h, w = template.shape[:2]
        if roi.shape[0] < h or roi.shape[1] < w:
            return None
        _, score, _, point = cv2.minMaxLoc(
            cv2.matchTemplate(roi, template, cv2.TM_CCOEFF_NORMED)
        )
        # A caller's looser Android threshold must not weaken the iOS profile.
        if not np.isfinite(score) or score < max(
            spec["threshold"], float(threshold or 0)
        ):
            return None
        x, y = point
        if np.abs(roi[y : y + h, x : x + w].astype(float) - template).mean() > 28:
            return None  # reject controls dimmed by a blocking popup
        return TemplateMatchResult(
            name, ConfidenceValue(score), Box(Point(left + x, top + y), w, h)
        )

    @lru_cache(maxsize=128)
    def _load_image(self, template, grayscale=False):
        # This upstream navigation guard was added after the installed 12.12.2
        # release. Ship its unchanged asset with the compatibility module.
        if (
            str(template) == "battle_modes/coming_soon.png"
            and not (self.template_dir / template).exists()
        ):
            return IO.load_image(
                Path(__file__).with_name("ios_templates") / "coming_soon_source.png",
                grayscale=grayscale,
            )
        return super()._load_image(template, grayscale)

    @lru_cache(maxsize=128)
    def _ios_hero_variants(self, name):
        image = self._load_image(name)
        # Portrait icons scale with phone width. The logical canvas has a
        # different aspect ratio, so apply the same vertical mapping to assets.
        return [
            cv2.resize(image, None, fx=float(scale), fy=float(scale * 0.818))
            for scale in np.arange(1.3, 1.61, 0.025)
        ]

    def _ios_find_hero(self, name, frame, threshold):
        # The original Android crop targets the formation board. On this iPhone
        # the unobstructed hero portraits are in the row underneath the board.
        left, top = 200, 1200
        roi = frame[top:1400, left:1020]
        best = None
        for template in self._ios_hero_variants(name):
            h, w = template.shape[:2]
            if roi.shape[0] < h or roi.shape[1] < w:
                continue
            _, score, _, (x, y) = cv2.minMaxLoc(
                cv2.matchTemplate(roi, template, cv2.TM_CCOEFF_NORMED)
            )
            if not np.isfinite(score) or score < float(
                threshold or self.default_threshold
            ):
                continue
            if np.abs(roi[y : y + h, x : x + w].astype(float) - template).mean() > 35:
                continue
            if best is None or score > float(best.confidence):
                best = TemplateMatchResult(
                    name, ConfidenceValue(score), Box(Point(left + x, top + y), w, h)
                )
        return best

    def game_find_template_match(
        self,
        template,
        match_mode=MatchMode.BEST,
        threshold=None,
        grayscale=False,
        crop_regions=CropRegions(),
        screenshot=None,
    ):
        name = str(template)
        if self.using_ios and name.startswith("heroes/"):
            frame = screenshot if screenshot is not None else self.get_screenshot()
            return self._ios_find_hero(name, frame, threshold)
        if not self.using_ios or name not in self._ios_visuals:
            return super().game_find_template_match(
                template, match_mode, threshold, grayscale, crop_regions, screenshot
            )
        frame = screenshot if screenshot is not None else self.get_screenshot()
        # iOS uses its measured search regions, not Android aspect-ratio crops.
        if name == "next.png":
            if self._ios_match("ios/trial_rewards.png", frame):
                match = self._ios_match("ios/next.png", frame, threshold)
                return replace(match, template=name) if match else None
            if not all(
                self._ios_match(key, frame)
                for key in ("ios/victory_rewards.png", "ios/victory_progress.png")
            ):
                return None
        return self._ios_match(name, frame, threshold)

    def find_any_template(
        self,
        templates,
        match_mode=MatchMode.BEST,
        threshold=None,
        grayscale=False,
        crop_regions=CropRegions(),
        screenshot=None,
    ):
        if not self.using_ios:
            return super().find_any_template(
                templates, match_mode, threshold, grayscale, crop_regions, screenshot
            )
        frame = screenshot if screenshot is not None else self.get_screenshot()
        for template in templates:
            result = self.game_find_template_match(
                template,
                match_mode,
                threshold or self.default_threshold,
                grayscale,
                crop_regions,
                frame,
            )
            if result is not None:
                return result
        return None

    def press_back_button(self):
        if not self.using_ios:
            return super().press_back_button()
        frame = self.get_screenshot()
        match = self._ios_match("ios/back.png", frame) or self._ios_match(
            "navigation/resonating_hall_back.png", frame
        )
        if match is None and self._ios_match("battle/copy.png", frame):
            match = self._ios_match("ios/records_close.png", frame)
        if match is None:
            raise GameActionFailedError(
                "No recognized iPhone Back button. Stopped without guessing."
            )
        self.tap(match)
