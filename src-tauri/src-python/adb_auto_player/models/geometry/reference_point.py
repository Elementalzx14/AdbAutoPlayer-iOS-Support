"""Explicit coordinates measured in a game's canonical reference frame."""

from .coordinates import Coordinates
from .point import Point


class ReferencePoint(Point):
    """A fixed UI position requiring layout projection before device input.

    Detected template/OCR coordinates remain ordinary image-space coordinates.
    The distinction prevents applying a tablet projection twice.
    """

    def __eq__(self, other):
        """Compare positions independent of their coordinate-space marker."""
        if not isinstance(other, Coordinates):
            return NotImplemented
        return self.x == other.x and self.y == other.y

    __hash__ = None
