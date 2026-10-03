"""Aspect-preserving canvas and reversible input coordinates."""

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class Canvas:
    """Fit the entire screen inside a canvas, retaining both safe areas."""

    native_width: int
    native_height: int
    width: int
    height: int

    @property
    def viewport(self):
        """Return the image bounds, excluding letterbox bars."""
        scale = min(self.width / self.native_width, self.height / self.native_height)
        w = round(self.native_width * scale)
        h = round(self.native_height * scale)
        return ((self.width - w) // 2, (self.height - h) // 2, w, h)

    def render(self, native):
        """Uniformly resize without cropping any buttons or distorting icons."""
        x, y, w, h = self.viewport
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        frame[y : y + h, x : x + w] = cv2.resize(
            native, (w, h), interpolation=cv2.INTER_AREA
        )
        return frame

    def native_point(self, x, y):
        """Invert the viewport, rejecting taps in letterbox bars."""
        left, top, w, h = self.viewport
        if not left <= x < left + w or not top <= y < top + h:
            raise ValueError("Input is outside the iOS screen (letterbox area).")
        return (
            (x - left) * (self.native_width - 1) / (w - 1),
            (y - top) * (self.native_height - 1) / (h - 1),
        )
