"""Text domain — render a string as glyph-outline points (morphable text)."""

from __future__ import annotations

from archmotion.core.vmobject import VMobject


class Text(VMobject):
    """A string rendered as Bezier glyph outlines (a fully morphable VMobject).

    Glyph outlines are extracted via skia-python at construction, so ``Text``
    requires skia (it is not available in Pyodide — text scenes render CLI/MP4).
    Because it is a :class:`~archmotion.core.vmobject.VMobject`, text can be
    ``Transform``-morphed into any other shape.
    """

    def __init__(
        self,
        text: str,
        *,
        family: str = "Arial",
        size: float = 40.0,
        bold: bool = False,
        italic: bool = False,
    ) -> None:
        """Store the text + font config, then extract glyph points."""
        self.text = text
        self.family = family
        self.size = size
        self.bold = bold
        self.italic = italic
        super().__init__()

    def generate_points(self) -> None:
        """Extract glyph outlines and adopt them as this object's points."""
        from archmotion.render.text_glyphs import glyph_points  # noqa: PLC0415

        points, starts = glyph_points(
            self.text, family=self.family, size=self.size, bold=self.bold, italic=self.italic
        )
        self._pts = points  # noqa: SLF001
        self._contour_starts = starts  # noqa: SLF001
        self._last = points[-1] if points else None  # noqa: SLF001
