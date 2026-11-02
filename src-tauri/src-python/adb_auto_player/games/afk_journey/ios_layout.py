"""iPhone visual equivalents for the existing AFK Journey task engine.

Only recognition and navigation vary; battle policies remain in AFKJourneyBase.
Coordinates use the same logical canvas and inverse touch mapping as IOSController.
"""

import json
import logging
from dataclasses import replace
from datetime import datetime, timezone
from functools import cached_property, lru_cache
from pathlib import Path

import cv2
import numpy as np

from adb_auto_player.exceptions import GameActionFailedError
from adb_auto_player.file_loader import SettingsLoader
from adb_auto_player.models import ConfidenceValue
from adb_auto_player.models.geometry import Box, Point, ReferencePoint
from adb_auto_player.models.image_manipulation import CropRegions
from adb_auto_player.models.template_matching import MatchMode, TemplateMatchResult

from .battle_state import Mode
from .scaled_templates import ScaledTemplates


class AppleTemplateMatcher:
    """Image recognition and navigation for one Apple game session."""

    def __init__(self, game):
        self.game = game
        self.shared_templates = ScaledTemplates(game)

    @property
    def _ios_visuals(self):
        folder = Path(__file__).with_name("ios_templates")
        if self._ios_is_tablet:
            folder /= "ipad"
        key = str(folder)
        if key not in self._ios_visual_profiles:
            self._ios_visual_profiles[key] = self._load_ios_visuals(folder)
        return self._ios_visual_profiles[key]

    @cached_property
    def _ios_visual_profiles(self):
        return {}

    @property
    def _ios_is_tablet(self):
        return str(
            getattr(self.game.device, "metadata", {}).get("model", "")
        ).startswith("iPad")

    @staticmethod
    def _load_ios_visuals(folder):
        manifest = json.loads((folder / "manifest.json").read_text())
        return {
            name: (spec, cv2.imread(str(folder / spec["file"])))
            for name, spec in manifest.items()
        }

    def _ios_viewport(self, frame):
        """Use actual image bounds, excluding the transport's letterbox bars."""
        metadata = getattr(self.game.device, "metadata", {})
        return metadata.get("viewport", (0, 0, frame.shape[1], frame.shape[0]))

    def _ios_match(self, name, frame, threshold=None, diagnostics=None):
        if name not in self._ios_visuals:
            return None
        spec, template = self._ios_visuals[name]
        if template is None:
            raise GameActionFailedError("Missing iOS image: " + name)
        vx, vy, vw, vh = self._ios_viewport(frame)
        x1, y1, x2, y2 = [
            round(v * (vw if i % 2 == 0 else vh) + (vx if i % 2 == 0 else vy))
            for i, v in enumerate(spec["region"])
        ]
        rw, rh = spec.get("reference_size", (1080, 1920))
        sx, sy = vw / rw, vh / rh
        if "reference_size" in spec:
            sx = sy = min(sx, sy)
        template = cv2.resize(
            template,
            (
                max(1, round(template.shape[1] * sx)),
                max(1, round(template.shape[0] * sy)),
            ),
            interpolation=cv2.INTER_AREA,
        )
        if "search_region" in spec:
            x1, y1, x2, y2 = [
                round(v * (vw if i % 2 == 0 else vh) + (vx if i % 2 == 0 else vy))
                for i, v in enumerate(spec["search_region"])
            ]
        margin = round(spec["margin_fraction"] * vw)
        vertical_margin = round(spec["margin_fraction"] * rw * vh / rh)
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
        if any(
            self._ios_match(required, frame) is None
            for required in spec.get("requires", [])
        ):
            return None
        return TemplateMatchResult(
            name, ConfidenceValue(score), Box(Point(left + x, top + y), w, h)
        )

    @lru_cache(maxsize=128)
    def _ios_hero_variants(self, name, vw, tablet=False):
        image = self.game._load_image(name)
        scales = np.arange(0.65, 1.36, 0.025) if tablet else np.arange(1.3, 1.61, 0.025)
        # The uniform canvas preserves the original hero icon aspect ratio.
        return [
            cv2.resize(
                image,
                None,
                fx=float(scale * vw / 1080),
                fy=float(scale * vw / 1080),
            )
            for scale in scales
        ]

    def _ios_find_hero(self, name, frame, threshold):
        # The original Android crop targets the formation board. On this iPhone
        # the unobstructed hero portraits are in the row underneath the board.
        vx, vy, vw, vh = self._ios_viewport(frame)
        region = (
            (0.34, 0.65, 0.73, 0.74)
            if self._ios_is_tablet
            else (200 / 1080, 1200 / 1920, 1020 / 1080, 1400 / 1920)
        )
        left, top, right, bottom = [
            round(v * (vw if i % 2 == 0 else vh) + (vx if i % 2 == 0 else vy))
            for i, v in enumerate(region)
        ]
        roi = frame[top:bottom, left:right]
        best = None
        for template in self._ios_hero_variants(name, vw, self._ios_is_tablet):
            h, w = template.shape[:2]
            if roi.shape[0] < h or roi.shape[1] < w:
                continue
            _, score, _, (x, y) = cv2.minMaxLoc(
                cv2.matchTemplate(roi, template, cv2.TM_CCOEFF_NORMED)
            )
            if not np.isfinite(score) or score < float(
                threshold or self.game.default_threshold
            ):
                continue
            if np.abs(roi[y : y + h, x : x + w].astype(float) - template).mean() > 35:
                continue
            if best is None or score > float(best.confidence):
                best = TemplateMatchResult(
                    name, ConfidenceValue(score), Box(Point(left + x, top + y), w, h)
                )
        return best

    def match(
        self,
        template,
        match_mode=MatchMode.BEST,
        threshold=None,
        grayscale=False,
        crop_regions=CropRegions(),
        screenshot=None,
    ):
        name = str(template)
        if not Path(name).suffix and name + ".png" in self._ios_visuals:
            result = self.match(
                name + ".png",
                match_mode,
                threshold,
                grayscale,
                crop_regions,
                screenshot,
            )
            return replace(result, template=name) if result else None
        if name.startswith("ios/") and name not in self._ios_visuals:
            return None
        if name.startswith("heroes/"):
            frame = screenshot if screenshot is not None else self.game.get_screenshot()
            return self._ios_find_hero(name, frame, threshold)
        if name not in self._ios_visuals:
            frame = screenshot if screenshot is not None else self.game.get_screenshot()
            return self.shared_templates.match(
                name,
                frame,
                self._ios_viewport(frame),
                crop_regions,
                threshold or self.game.default_threshold,
                grayscale,
                match_mode,
            )
        frame = screenshot if screenshot is not None else self.game.get_screenshot()
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
            if self.game.battle_state.mode == Mode.SEASON_AFK_STAGES:
                match = self._ios_match("ios/phantimal_next.png", frame, threshold)
                if match:
                    return replace(match, template=name)
        return self._ios_match(name, frame, threshold)

    def capture_debug(self, category="manual"):
        """Save native and normalized pixels plus scores without uploading them."""
        try:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            destination = (
                SettingsLoader.get_app_config_dir().parent / "ios-debug" / stamp
            )
            metadata = self.game.device.capture_debug(destination)
            frame = cv2.imread(str(destination / "normalized.bmp"))
            scores = {}
            for name in self._ios_visuals:
                self._ios_match(name, frame, diagnostics=scores)
            metadata.update(
                {
                    "category": category,
                    "visual_profile": "ipad" if self._ios_is_tablet else "iphone",
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

    def press_back(self):
        frame = self.game.get_screenshot()
        if self._ios_match("ios/chat_panel.png", frame):
            self.game.tap(ReferencePoint(540, 100))
            return
        match = (
            self._ios_match("ios/back.png", frame)
            or self._ios_match("ios/light_back.png", frame)
            or self._ios_match("navigation/resonating_hall_back.png", frame)
            or self._ios_match("ios/battle_modes_back.png", frame)
        )
        if match is None and self._ios_match("battle/copy.png", frame):
            match = self._ios_match("ios/records_close.png", frame)
        if match is None and self._ios_is_tablet:
            match = self.game.game_find_template_match(
                "arcane_labyrinth/back_arrow.png",
                screenshot=frame,
                crop_regions=CropRegions(right=0.75, top=0.75),
            )
        if match is None:
            raise GameActionFailedError(
                "No recognized Apple Back button. Stopped without guessing."
            )
        self.game.tap(match)
