"""Code domain — syntax-highlighted code as a group of styled Text spans.

A :class:`CodeBlock` is a :class:`~archmotion.core.vgroup.VGroup` of
:class:`~archmotion.domains.text.text.Text` children, one per source line, each
colored by token type via Pygments. Because it is a group, each line remains an
independently animatable VMobject (e.g. a ``Write`` per line) while the block as
a whole can be moved or scaled together.

Pygments is a pure-Python dependency; ``Text`` itself still needs skia for glyph
extraction, so ``CodeBlock`` renders CLI/MP4 (not Pyodide).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from archmotion.core.style import Style
from archmotion.core.vgroup import VGroup

if TYPE_CHECKING:
    from archmotion._types import Point

# Token-type → color. A compact, readable dark-theme palette.
TOKEN_COLORS: dict[str, str] = {
    "Keyword": "#c678dd",
    "Name.Keyword": "#c678dd",
    "Name.Builtin": "#56b6c2",
    "Name.Function": "#61afef",
    "Name.Class": "#e5c07b",
    "Name.Decorator": "#e5c07b",
    "String": "#98c379",
    "String.Doc": "#7f848e",
    "Comment": "#7f848e",
    "Number": "#d19a66",
    "Operator": "#56b6c2",
    "Punctuation": "#abb2bf",
    "Name": "#e06c75",
    "Text": "#abb2bf",
}

DEFAULT_COLOR = "#abb2bf"
LINE_HEIGHT_FACTOR = 1.25
TAB_SPACES = 4


class CodeBlock(VGroup):
    """Syntax-highlighted source code, one Text child per line."""

    def __init__(
        self,
        code: str,
        *,
        language: str = "python",
        family: str = "Consolas",
        size: float = 22.0,
        origin: Point = (0.0, 0.0),
    ) -> None:
        """Tokenize ``code`` and lay out colored line Text children top-to-bottom."""
        self.code = code
        self.language = language
        self.family = family
        self.size = size
        self.origin = origin
        self.line_height = size * LINE_HEIGHT_FACTOR
        super().__init__()
        self._build_lines()

    def _build_lines(self) -> None:
        """Create one styled Text per source line and stack them vertically."""
        from pygments import lex
        from pygments.lexers import get_lexer_by_name

        from archmotion.domains.text.text import Text

        try:
            lexer = get_lexer_by_name(self.language)
        except Exception:
            self._add_plain_lines(self.code)
            return

        lines = self.code.splitlines() or [""]
        line_height = self.line_height
        x0, y0 = self.origin
        for i, _line in enumerate(lines):
            # y-down: line 0 at top (smallest y).
            y = y0 + i * line_height
            tokens = list(lex(self._line_source(i, lines), lexer))
            segments = _segments_for_tokens(tokens)
            if not segments:
                continue
            line_group = _LineGroup()
            x_cursor = x0
            for text_str, color in segments:
                if not text_str:
                    continue
                span = Text(text_str, family=self.family, size=self.size)
                span.style = Style(fill_color=color, stroke_color=None, stroke_width=0.0)
                _place_span(span, x_cursor, y)
                line_group.add(span)
                x_cursor += _approx_width(text_str, self.size)
            if line_group.children:
                self.add(line_group)

    def _line_source(self, i: int, lines: list[str]) -> str:
        """Return the i-th line with a trailing newline so the lexer flushes."""
        return lines[i] + "\n"

    def _add_plain_lines(self, code: str) -> None:
        """Fallback: render each line as a single unstyled Text span."""
        from archmotion.domains.text.text import Text

        x0, y0 = self.origin
        for i, line in enumerate(code.splitlines() or [""]):
            if not line:
                continue
            span = Text(line, family=self.family, size=self.size)
            span.style = Style(fill_color=DEFAULT_COLOR, stroke_color=None, stroke_width=0.0)
            _place_span(span, x0, y0 + i * self.line_height)
            self.add(span)


class _LineGroup(VGroup):
    """Internal grouping of the spans on a single line (no public API)."""


def _segments_for_tokens(tokens: list[tuple[object, str]]) -> list[tuple[str, str]]:
    """Collapse a Pygments token stream into (text, color) segments per line.

    The lexer runs over a single line (plus newline); we drop the trailing
    newline and map each token to a color via :data:`TOKEN_COLORS`.
    """
    segments: list[tuple[str, str]] = []
    for ttype, value in tokens:
        text = value.replace("\t", " " * TAB_SPACES).replace("\n", "").replace("\r", "")
        if not text:
            continue
        color = _color_for(ttype)
        segments.append((text, color))
    return segments


def _color_for(ttype: object) -> str:
    """Resolve a Pygments token type to a color, walking parent token types."""
    name = str(ttype)
    parts = name.split(".")
    for depth in range(len(parts), 0, -1):
        candidate = ".".join(parts[:depth])
        if candidate in TOKEN_COLORS:
            return TOKEN_COLORS[candidate]
    # Pygments token short names (e.g. Token.Keyword).
    short = parts[-1] if parts else ""
    if short in TOKEN_COLORS:
        return TOKEN_COLORS[short]
    return DEFAULT_COLOR


def _approx_width(text: str, size: float) -> float:
    """Approximate monospace advance width for cursor positioning."""
    return size * 0.6 * len(text)


def _place_span(span: object, x: float, y: float) -> None:
    """Move a Text span's baseline-left to (x, y) using its bounding box."""
    bbox = span.bounding_box()  # type: ignore[attr-defined]
    # Align by the glyph bbox left edge and the baseline (bbox bottom ~ baseline).
    span.shift(x - bbox.x, y - (bbox.y + bbox.height))  # type: ignore[attr-defined]
