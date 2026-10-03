"""iPhone visual equivalents for the existing AFK Journey task engine.

Only recognition and navigation vary; battle policies remain in AFKJourneyBase.
Coordinates use the same logical canvas and inverse touch mapping as IOSController.
"""

import json
import logging
from datetime import datetime, timezone
from dataclasses import replace
from functools import cached_property, lru_cache
from pathlib import Path

import cv2
import numpy as np

from adb_auto_player.exceptions import GameActionFailedError
from adb_auto_player.file_loader import SettingsLoader
from adb_auto_player.models import ConfidenceValue
from adb_auto_player.models.geometry import Box, Point
from adb_auto_player.models.image_manipulation import CropRegions
from adb_auto_player.models.template_matching import MatchMode, TemplateMatchResult

from .battle_state import Mode


class IOSLayoutMixin:
    @property
    def using_ios(self):
        return SettingsLoader.adb_settings().ios.enabled

    @cached_property
    def layout(self):
        from .layout import AppleLayout, AndroidLayout

        return AppleLayout() if self.using_ios else AndroidLayout()

    @cached_property
    def _ios_visuals(self):
        folder = Path(__file__).with_name("ios_templates")
        manifest = json.loads((folder / "manifest.json").read_text())
        return {
            name: (spec, cv2.imread(str(folder / spec["file"])))
            for name, spec in manifest.items()
        }

    def _ios_viewport(self, frame):
        """Use actual image bounds, excluding the transport's letterbox bars."""
        metadata = getattr(self.device, "metadata", {})
        return metadata.get("viewport", (0, 0, frame.shape[1], frame.shape[0]))

    def _ios_match(self, name, frame, threshold=None, diagnostics=None):
        spec, template = self._ios_visuals[name]
        if template is None:
            raise GameActionFailedError("Missing iOS image: " + name)
        vx, vy, vw, vh = self._ios_viewport(frame)
        x1, y1, x2, y2 = [
            round(v * (vw if i % 2 == 0 else vh) + (vx if i % 2 == 0 else vy))
            for i, v in enumerate(spec["region"])
        ]
        template = cv2.resize(
            template,
            (
                max(1, round(template.shape[1] * vw / 1080)),
                max(1, round(template.shape[0] * vh / 1920)),
            ),
            interpolation=cv2.INTER_AREA,
        )
        if "search_region" in spec:
            x1, y1, x2, y2 = [
                round(v * (vw if i % 2 == 0 else vh) + (vx if i % 2 == 0 else vy))
                for i, v in enumerate(spec["search_region"])
            ]
        margin = round(spec["margin_fraction"] * vw)
        vertical_margin = round(spec["margin_fraction"] * 1080 * vh / 1920)
        left, top = max(0, x1 - margin), max(0, y1 - vertical_margin)
        roi = frame[
            top : min(frame.shape[0], y2 + vertical_margin),
            left : min(frame.shape[1], x2 + margin),
        ]
        h, w = template.shape[:2]
        if roi.shape[0] < h or roi.shape[1] < w:
            if diagnostics is not None:
                diagnostics[name] = {
                    "matched": False,
                    "reason": "template exceeds region",
                }
            return None
        _, score, _, point = cv2.minMaxLoc(
            cv2.matchTemplate(roi, template, cv2.TM_CCOEFF_NORMED)
        )
        if diagnostics is not None:
            px, py = point
            difference = float(
                np.abs(roi[py : py + h, px : px + w].astype(float) - template).mean()
            )
            diagnostics[name] = {
                "score": float(score) if np.isfinite(score) else None,
                "threshold": max(spec["threshold"], float(threshold or 0)),
                "mean_color_difference": difference,
                "matched": bool(
                    np.isfinite(score)
                    and score >= max(spec["threshold"], float(threshold or 0))
                    and difference <= 28
                ),
                "position": [left + px, top + py],
            }
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
    def _ios_hero_variants(self, name, vw):
        image = self._load_image(name)
        # The uniform canvas preserves the original hero icon aspect ratio.
        return [
            cv2.resize(
                image,
                None,
                fx=float(scale * vw / 1080),
                fy=float(scale * vw / 1080),
            )
            for scale in np.arange(1.3, 1.61, 0.025)
        ]

    def _ios_find_hero(self, name, frame, threshold):
        # The original Android crop targets the formation board. On this iPhone
        # the unobstructed hero portraits are in the row underneath the board.
        vx, vy, vw, vh = self._ios_viewport(frame)
        left, top = round(vx + vw * (200 / 1080)), round(vy + vh * (1200 / 1920))
        roi = frame[
            top : round(vy + vh * (1400 / 1920)), left : round(vx + vw * (1020 / 1080))
        ]
        best = None
        for template in self._ios_hero_variants(name, vw):
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
            if self.battle_state.mode == Mode.SEASON_AFK_STAGES:
                match = self._ios_match("ios/phantimal_next.png", frame, threshold)
                if match:
                    return replace(match, template=name)
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

    def capture_debug_screenshot(self, category="manual"):
        """Save native and normalized pixels plus scores without uploading them."""
        try:
            if not self.using_ios:
                return super().capture_debug_screenshot(category)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            destination = (
                SettingsLoader.get_app_config_dir().parent / "ios-debug" / stamp
            )
            metadata = self.device.capture_debug(destination)
            frame = cv2.imread(str(destination / "normalized.bmp"))
            scores = {}
            for name in self._ios_visuals:
                self._ios_match(name, frame, diagnostics=scores)
            metadata.update(
                {
                    "category": category,
                    "templates": scores,
                    "note": "Raw visual scores; victory guards still apply during play.",
                }
            )
            (destination / "report.json").write_text(
                json.dumps(metadata, indent=2), encoding="utf-8"
            )
            logging.info(
                "iOS debug capture saved to %s. Review screenshots for account details before sharing.",
                destination,
            )
        except Exception as exc:
            logging.warning("Could not capture iOS diagnostics: %s", exc)

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
