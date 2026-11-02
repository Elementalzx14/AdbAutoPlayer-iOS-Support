"""Uniform matching of shared game assets inside an Apple content viewport."""

from functools import lru_cache

import cv2
import numpy as np

from adb_auto_player.image_manipulation import Cropping
from adb_auto_player.models import ConfidenceValue
from adb_auto_player.models.geometry import Point
from adb_auto_player.template_matching import TemplateMatcher

MIN_SHARED_CONFIDENCE = 0.92
MAX_COLOR_DIFFERENCE = 28


class ScaledTemplates:
    """Reuse original assets without stretching their aspect ratio.

    Explicit Apple profiles take precedence. This path searches only the
    caller's region, projected into the content viewport, and returns full
    screenshot coordinates. It does not establish live mode verification.
    """

    def __init__(self, game):
        self.game = game

    @lru_cache(maxsize=128)
    def variants(self, name, width, height):
        """Cache a bounded set of uniformly scaled original assets."""
        image = self.game._load_image(name)
        scale = min(width / 1080, height / 1920)
        sizes = {
            (
                max(1, round(image.shape[1] * scale * factor)),
                max(1, round(image.shape[0] * scale * factor)),
            )
            for factor in np.arange(0.95, 1.076, 0.025)
        }
        return tuple(cv2.resize(image, size) for size in sorted(sizes))

    def match(self, name, frame, viewport, crop_regions, threshold, grayscale, mode):  # noqa: PLR0917
        """Match an original asset, preserving crop offsets and input space."""
        vx, vy, width, height = viewport
        cropped, offset = self.region(frame, viewport, crop_regions)
        best = None
        minimum = ConfidenceValue(max(MIN_SHARED_CONFIDENCE, float(threshold)))
        for template in self.variants(name, width, height):
            if np.std(template) < 1:
                continue
            h, w = template.shape[:2]
            if h > cropped.shape[0] or w > cropped.shape[1]:
                continue
            match = TemplateMatcher.find_template_match(
                base_image=cropped,
                template_image=template,
                match_mode=mode,
                threshold=minimum,
                grayscale=grayscale,
            )
            if match is None:
                continue
            x, y = match.box.top_left.x, match.box.top_left.y
            pixels = cropped[y : y + h, x : x + w]
            if np.abs(pixels.astype(float) - template).mean() > MAX_COLOR_DIFFERENCE:
                continue
            result = match.with_offset(offset).to_template_match_result(template=name)
            if best is None or float(result.confidence) > float(best.confidence):
                best = result
        return best

    @staticmethod
    def region(frame, viewport, crop_regions):
        """Keep OCR-derived pixel crops in screenshot coordinates."""
        values = [
            getattr(crop_regions, side) for side in ("left", "right", "top", "bottom")
        ]
        if any(value.is_pixels and value.value for value in values):
            cropped = Cropping.crop(frame, crop_regions)
            return cropped.image, cropped.offset
        vx, vy, width, height = viewport
        cropped = Cropping.crop(frame[vy : vy + height, vx : vx + width], crop_regions)
        return cropped.image, Point(vx + cropped.offset.x, vy + cropped.offset.y)

    def match_all(
        self, name, frame, viewport, crop_regions, threshold, grayscale, min_distance
    ):  # noqa: PLR0917
        """Find repeated shared controls and suppress duplicates across scales."""
        _, _, width, height = viewport
        cropped, offset = self.region(frame, viewport, crop_regions)
        candidates = []
        for template in self.variants(name, width, height):
            h, w = template.shape[:2]
            if h > cropped.shape[0] or w > cropped.shape[1] or np.std(template) < 1:
                continue
            matches = TemplateMatcher.find_all_template_matches(
                base_image=cropped,
                template_image=template,
                threshold=ConfidenceValue(max(MIN_SHARED_CONFIDENCE, float(threshold))),
                grayscale=grayscale,
                min_distance=min_distance,
            )
            for match in matches:
                x, y = match.box.top_left.x, match.box.top_left.y
                if (
                    np.abs(
                        cropped[y : y + h, x : x + w].astype(float) - template
                    ).mean()
                    <= MAX_COLOR_DIFFERENCE
                ):
                    candidates.append(
                        match.with_offset(offset).to_template_match_result(
                            template=name
                        )
                    )
        results = []
        for candidate in sorted(
            candidates, key=lambda m: float(m.confidence), reverse=True
        ):
            if all(
                candidate.box.top_left.distance_to(m.box.top_left) >= min_distance
                for m in results
            ):
                results.append(candidate)
        return results

    def worst(self, name, frame, viewport, crop_regions, grayscale):
        """Apply the original difference-based search at uniform UI scale."""
        _, _, width, height = viewport
        cropped, offset = self.region(frame, viewport, crop_regions)
        original = self.game._load_image(name)
        scale = min(width / 1080, height / 1920)
        template = cv2.resize(original, None, fx=scale, fy=scale)
        if template.shape[0] > cropped.shape[0] or template.shape[1] > cropped.shape[1]:
            return None
        result = TemplateMatcher.find_worst_template_match(
            cropped, template, grayscale=grayscale
        )
        if result is None:
            return None
        return result.with_offset(offset).to_template_match_result(template=name)
