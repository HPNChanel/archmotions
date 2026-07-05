"""Text glyph extraction: skia font → VMobject point array.

The skia layer (`glyph_points`) iterates each glyph's outline via
``Path.RawIter`` and feeds the verb stream into the pure-Python
:func:`verbs_to_contours`, which converts move/line/quad/conic/cubic/close verbs
into ArchMotion's cubic-triplet point array. ``verbs_to_contours`` is skia-free
and unit-tested; ``glyph_points`` is exercised wherever skia-python is installed
(the v2.0 design keeps skia out of the pure-Python export path).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from archmotion.core.pathops import line_triplet, quad_to_cubic

if TYPE_CHECKING:
    from collections.abc import Iterable

# Verb codes (match skia.Path.Verb). Declared as plain ints so the helper has no
# skia dependency and is unit-testable with synthetic data.
MOVE = 0
LINE = 1
QUAD = 2
CONIC = 3
CUBIC = 4
CLOSE = 5
DONE = 6

VerbEntry = tuple[int, list[tuple[float, float]]]


def verbs_to_contours(verb_seq: Iterable[VerbEntry]) -> tuple[list[tuple[float, float]], list[int]]:
    """Convert a verb stream into a point array + contour starts.

    Each entry is ``(verb_code, coords)`` where ``coords`` is the list of
    ``(x, y)`` points associated with the verb (as returned by skia's
    ``RawIter`` — the start point is included as ``coords[0]``). Lines become
    degenerate cubics; quadratics are converted to cubics; conics are
    approximated as quadratics (glyphs rarely use them).
    """
    points: list[tuple[float, float]] = []
    contour_starts: list[int] = []
    anchor: tuple[float, float] | None = None
    last: tuple[float, float] | None = None

    for verb, coords in verb_seq:
        if verb == MOVE:
            anchor = coords[0]
            contour_starts.append(len(points))
            points.append(anchor)
            last = anchor
            continue
        if last is None:
            msg = "Path verb before any moveTo."
            raise RuntimeError(msg)
        if verb == LINE:
            end = coords[-1]
            points.extend(line_triplet(last, end))
            last = end
        elif verb in (QUAD, CONIC):
            start, ctrl, end = coords[0], coords[1], coords[2]
            points.extend(quad_to_cubic(start, ctrl, end))
            last = end
        elif verb == CUBIC:
            c1, c2, end = coords[1], coords[2], coords[3]
            points.extend([(c1[0], c1[1]), (c2[0], c2[1]), (end[0], end[1])])
            last = end
        elif verb == CLOSE:
            if anchor is None:
                msg = "Close verb before any moveTo."
                raise RuntimeError(msg)
            points.extend(line_triplet(last, anchor))
            last = anchor
        elif verb == DONE:
            break
    return points, contour_starts


def glyph_points(
    text: str,
    *,
    family: str = "Arial",
    size: float = 40.0,
    bold: bool = False,
    italic: bool = False,
) -> tuple[list[tuple[float, float]], list[int]]:
    """Extract glyph outlines for ``text`` into a point array (skia required).

    Glyphs are laid out left-to-right using their advance widths; coordinates
    are kept in skia's native orientation (cap height at negative y, descenders
    at positive y — already correct for ArchMotion's y-down space). Returns
    ``(points, contour_starts)`` ready for a :class:`~archmotion.core.vmobject.VMobject`.
    """
    import skia

    typeface = _make_typeface(family, bold, italic)
    font = skia.Font(typeface, size)
    glyph_ids = font.textToGlyphs(text)
    if not glyph_ids:
        return [], []
    widths = font.getWidths(glyph_ids)

    all_points: list[tuple[float, float]] = []
    all_starts: list[int] = []
    x_offset = 0.0
    for gid, advance in zip(glyph_ids, widths, strict=True):
        path = font.getPath(gid)
        if path is not None:
            verb_seq = _iter_skia_path(path)
            pts, starts = verbs_to_contours(verb_seq)
            base = len(all_points)
            for start in starts:
                all_starts.append(base + start)
            for sx, sy in pts:
                all_points.append((x_offset + sx, sy))
        x_offset += advance
    return all_points, all_starts


def _make_typeface(family: str, bold: bool, italic: bool) -> object:
    """Build a skia Typeface honoring bold/italic flags."""
    import skia

    if not bold and not italic:
        return skia.Typeface(family)
    weight = skia.FontStyle.kBold_Weight if bold else skia.FontStyle.kNormal_Weight
    slant = skia.FontStyle.kItalic_Slant if italic else skia.FontStyle.kUpright_Slant
    return skia.Typeface(family, skia.FontStyle(weight, 5, slant))


def _iter_skia_path(path: Any) -> list[VerbEntry]:  # noqa: ANN401
    """Iterate a skia.Path's RawIter into plain (verb, coords) entries."""
    import skia

    raw = path.RawIter(path)
    done = int(skia.Path.Verb.kDone_Verb)
    out: list[VerbEntry] = []
    while True:
        verb, pts = raw.next()
        iv = int(verb)
        if iv == done:
            break
        coords = [(float(p.x()), float(p.y())) for p in pts]
        out.append((iv, coords))
    return out
