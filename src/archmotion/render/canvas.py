"""Skia Canvas abstraction for frame rendering.

Canonical home for the skia canvas wrapper + color utilities (v2.0).

CONTAINMENT: This module is the ONLY place that imports skia-python.
All Skia Surface/Canvas lifecycle management happens here.

Architectural Note:
    SkiaCanvas wraps the create -> draw -> snapshot -> dispose cycle.
    It is designed to be used in worker processes (multiprocessing),
    so each instance manages its own Surface independently.

    The hex_to_color4f() utility converts CSS hex colors (#RRGGBB or
    #RRGGBBAA) to skia.Color4f, which is the only color format Skia accepts.
"""

from __future__ import annotations

import skia

from archmotion.core.color import color_to_rgba01
from archmotion.errors import SkiaAllocationError

# ──────────────────────────────────────────────
# Color Utilities
# ──────────────────────────────────────────────


def hex_to_color4f(hex_color: str, opacity: float = 1.0) -> skia.Color4f:
    """Convert CSS hex color to skia.Color4f.

    Supports #RGB, #RRGGBB, and #RRGGBBAA formats.

    Args:
        hex_color: CSS hex color string (e.g., '#cdd6f4', '#00000066').
        opacity: Override opacity multiplier [0.0, 1.0].

    Returns:
        skia.Color4f instance.
    """
    r, g, b, a = color_to_rgba01(hex_color, opacity)
    return skia.Color4f(r, g, b, a)


def rgba_to_color4f(
    rgba: tuple[float, float, float, float],
    opacity: float = 1.0,
) -> skia.Color4f:
    """Convert RGBA tuple (0-1 floats) to skia.Color4f.

    Args:
        rgba: (R, G, B, A) tuple with values in [0.0, 1.0].
        opacity: Additional opacity multiplier.

    Returns:
        skia.Color4f instance.
    """
    return skia.Color4f(rgba[0], rgba[1], rgba[2], rgba[3] * opacity)


# ──────────────────────────────────────────────
# Skia Canvas Wrapper
# ──────────────────────────────────────────────


class SkiaCanvas:
    """Managed Skia Surface + Canvas for frame rendering.

    Encapsulates the create -> draw -> snapshot -> dispose lifecycle.
    Designed for use in multiprocessing worker functions.

    Usage:
        canvas = SkiaCanvas(1920, 1080)
        try:
            canvas.clear(bg_color)
            # ... draw operations using canvas.native ...
            raw_bytes = canvas.snapshot()
        finally:
            canvas.dispose()
    """

    __slots__ = ("_canvas", "_height", "_surface", "_width")

    def __init__(self, width: int, height: int) -> None:
        """Allocate a Skia raster surface.

        Args:
            width: Surface width in pixels.
            height: Surface height in pixels.

        Raises:
            SkiaAllocationError: If Skia cannot allocate the surface.
        """
        self._width = width
        self._height = height

        # ``N32`` is platform-native: BGRA on Windows and commonly RGBA on
        # Unix.  Downstream consumers (Pillow and FFmpeg) require one stable
        # byte contract, so allocate the raster surface explicitly as RGBA.
        image_info = skia.ImageInfo.Make(
            width,
            height,
            skia.ColorType.kRGBA_8888_ColorType,
            skia.AlphaType.kPremul_AlphaType,
        )
        self._surface = skia.Surface.MakeRaster(image_info)
        if self._surface is None:
            raise SkiaAllocationError(width, height)

        self._canvas = self._surface.getCanvas()
        if self._canvas is None:
            raise SkiaAllocationError(width, height)

    @property
    def width(self) -> int:
        """Surface width in pixels."""
        return self._width

    @property
    def height(self) -> int:
        """Surface height in pixels."""
        return self._height

    @property
    def native(self) -> skia.Canvas:
        """Access the underlying skia.Canvas for draw commands."""
        return self._canvas

    def clear(self, color: skia.Color4f) -> None:
        """Fill entire canvas with a solid color.

        Args:
            color: Background color as skia.Color4f.
        """
        self._canvas.clear(color)

    def snapshot(self) -> bytes:
        """Extract raw RGBA bytes from the current canvas state.

        Returns:
            Raw pixel data as bytes (width * height * 4).
        """
        image = self._surface.makeImageSnapshot()
        return bytes(image.tobytes())

    def dispose(self) -> None:
        """Release Skia resources.

        Must be called when done rendering to avoid memory leaks.
        Safe to call multiple times.
        """
        self._canvas = None
        self._surface = None

    def save_layer(self, opacity: float) -> None:
        """Push a transparent layer for opacity compositing.

        Args:
            opacity: Layer opacity [0.0, 1.0].
        """
        paint = skia.Paint()
        paint.setAlphaf(opacity)
        self._canvas.saveLayer(None, paint)

    def restore(self) -> None:
        """Pop the previously saved layer."""
        self._canvas.restore()


# ──────────────────────────────────────────────
# Font Factory
# ──────────────────────────────────────────────


def make_font(family: str, size: float) -> skia.Font:
    """Create a Skia Font with the given family and size.

    Falls back to Arial if the requested font family is not available.

    Args:
        family: Font family name (e.g., 'Fira Code').
        size: Font size in points.

    Returns:
        skia.Font instance.
    """
    typeface = skia.Typeface(family)
    # Skia returns a default typeface if family not found,
    # so we always get a valid typeface.
    return skia.Font(typeface, size)
