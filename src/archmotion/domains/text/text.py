"""Text domain — render a string as glyph-outline points (morphable text)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from archmotion.core.vgroup import VGroup
from archmotion.core.vmobject import VMobject

if TYPE_CHECKING:
    from collections.abc import Sequence


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
        from archmotion.render.text_glyphs import glyph_points

        points, starts = glyph_points(
            self.text, family=self.family, size=self.size, bold=self.bold, italic=self.italic
        )
        self._pts = points
        self._contour_starts = starts
        self._last = points[-1] if points else None


class Paragraph(VGroup):
    r"""Multi-line text rendered as a vertical stack of ``Text`` lines.

    Accepts a multi-line string (split on ``\n``) or a list of line strings.
    Each line is a separate :class:`Text` child, positioned below the previous
    one by ``line_spacing`` x the line height.
    """

    def __init__(
        self,
        text: str | Sequence[str],
        *,
        line_spacing: float = 1.2,
        family: str = "Arial",
        size: float = 40.0,
        bold: bool = False,
        italic: bool = False,
    ) -> None:
        """Split text into lines and build stacked ``Text`` children."""
        lines = text.split("\n") if isinstance(text, str) else list(text)
        self.lines = lines
        self.line_spacing = line_spacing

        children: list[Text] = []
        for i, line_text in enumerate(lines):
            line = Text(
                line_text,
                family=family,
                size=size,
                bold=bold,
                italic=italic,
            )
            # Stack downward (y grows downward in ArchMotion's coordinate space).
            line.shift(0.0, i * size * line_spacing)
            children.append(line)
        super().__init__(*children)
