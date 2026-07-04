"""SVG path ``d`` string parser → VMobject point array (pure Python).

Parses the subset of SVG path commands emitted by ``dvisvgm`` (LaTeX output)
and common vector tools: ``M/m L/l H/h V/v C/c Q/q Z/z``. Arc (``A/a``) is not
supported (dvisvgm emits cubic Beziers). The result is a flat point array +
contour starts usable by any :class:`~archmotion.core.vmobject.VMobject`.

Output layout matches the VMobject convention: each contour starts with an
anchor followed by cubic triplets ``[h1, h2, end]``. Lines become degenerate
cubics; quadratics are converted to cubics.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

_COMMAND_RE = re.compile(r"([MmLlHhVvCcQqZz])|(-?\d*\.?\d+(?:[eE][+-]?\d+)?)")

@dataclass(frozen=True)
class ParsedPath:
    """Result of parsing an SVG ``d`` string.

    Attributes:
        points: Flat list of (x, y) tuples.
        contour_starts: Indices into ``points`` where each contour begins.
    """

    points: list[tuple[float, float]]
    contour_starts: list[int]


def parse_svg_path(d: str) -> ParsedPath:
    """Parse an SVG path ``d`` attribute into points + contour starts."""
    tokens = _COMMAND_RE.findall(d)
    cmds = _tokenize(tokens)
    points: list[tuple[float, float]] = []
    contour_starts: list[int] = []
    cx = cy = 0.0
    start_x = start_y = 0.0

    for cmd, args in cmds:
        rel = cmd.islower()
        c = cmd.upper()
        nxt = _consumer(args)
        if c == "M":
            x, y = _pair(nxt, cx, cy, rel)
            cx = cy = 0.0  # rel offsets rebase to the new subpath origin below
            cx, cy = x, y
            start_x, start_y = cx, cy
            contour_starts.append(len(points))
            points.append((cx, cy))
            # Implicit LineTos for any remaining pairs.
            cx, cy = _run_lines(nxt, points, cx, cy, rel)
        elif c == "L":
            cx, cy = _run_lines(nxt, points, cx, cy, rel)
        elif c in ("H", "V"):
            cx, cy = _run_hv(c, nxt, points, cx, cy, rel)
        elif c == "C":
            cx, cy = _run_cubic(nxt, points, cx, cy, rel)
        elif c == "Q":
            cx, cy = _run_quad(nxt, points, cx, cy, rel)
        elif c == "Z":
            _append_line(points, (cx, cy), (start_x, start_y))
            cx, cy = start_x, start_y
    return ParsedPath(points=points, contour_starts=contour_starts)


def _tokenize(tokens: list[tuple[str, str]]) -> list[tuple[str, list[float]]]:
    """Group raw regex tokens into (command, [numbers]) pairs."""
    out: list[tuple[str, list[float]]] = []
    i = 0
    while i < len(tokens):
        cmd, _num = tokens[i]
        if cmd:
            args: list[float] = []
            i += 1
            while i < len(tokens) and not tokens[i][0]:
                args.append(float(tokens[i][1]))
                i += 1
            out.append((cmd, args))
        else:
            i += 1
    return out


def _consumer(args: list[float]) -> Callable[[], float]:
    """Return a next-value callable over a list of floats."""
    it: Iterator[float] = iter(args)

    def _next() -> float:
        return next(it)

    return _next


def _pair(nxt: Callable[[], float], cx: float, cy: float, rel: bool) -> tuple[float, float]:
    """Read one (x, y) pair, applying relative offset if needed."""
    x = nxt()
    y = nxt()
    if rel:
        return x + cx, y + cy
    return x, y


def _append_line(
    points: list[tuple[float, float]], p0: tuple[float, float], end: tuple[float, float]
) -> None:
    """Append a straight line as a degenerate cubic triplet."""
    h1 = (p0[0] + (end[0] - p0[0]) / 3.0, p0[1] + (end[1] - p0[1]) / 3.0)
    h2 = (p0[0] + 2.0 * (end[0] - p0[0]) / 3.0, p0[1] + 2.0 * (end[1] - p0[1]) / 3.0)
    points.extend([h1, h2, end])


def _run_lines(
    nxt: Callable[[], float],
    points: list[tuple[float, float]],
    cx: float,
    cy: float,
    rel: bool,
) -> tuple[float, float]:
    """Consume (x, y) pairs as LineTo segments; return the final point."""
    while True:
        try:
            x, y = _pair(nxt, cx, cy, rel)
        except StopIteration:
            return cx, cy
        _append_line(points, (cx, cy), (x, y))
        cx, cy = x, y


def _run_hv(
    cmd: str,
    nxt: Callable[[], float],
    points: list[tuple[float, float]],
    cx: float,
    cy: float,
    rel: bool,
) -> tuple[float, float]:
    """Consume scalars as horizontal/vertical LineTos."""
    while True:
        try:
            v = nxt()
        except StopIteration:
            return cx, cy
        if cmd == "H":
            x = v + cx if rel else v
            y = cy
        else:
            x = cx
            y = v + cy if rel else v
        _append_line(points, (cx, cy), (x, y))
        cx, cy = x, y


def _run_cubic(
    nxt: Callable[[], float],
    points: list[tuple[float, float]],
    cx: float,
    cy: float,
    rel: bool,
) -> tuple[float, float]:
    """Consume cubic Bezier segments (6 numbers each)."""
    while True:
        try:
            x1, y1 = _pair(nxt, cx, cy, rel)
            x2, y2 = _pair(nxt, cx, cy, rel)
            x, y = _pair(nxt, cx, cy, rel)
        except StopIteration:
            return cx, cy
        points.extend([(x1, y1), (x2, y2), (x, y)])
        cx, cy = x, y


def _run_quad(
    nxt: Callable[[], float],
    points: list[tuple[float, float]],
    cx: float,
    cy: float,
    rel: bool,
) -> tuple[float, float]:
    """Consume quadratic Bezier segments, converted to cubics."""
    while True:
        try:
            qx, qy = _pair(nxt, cx, cy, rel)
            x, y = _pair(nxt, cx, cy, rel)
        except StopIteration:
            return cx, cy
        h1 = (cx + 2.0 / 3.0 * (qx - cx), cy + 2.0 / 3.0 * (qy - cy))
        h2 = (x + 2.0 / 3.0 * (qx - x), y + 2.0 / 3.0 * (qy - y))
        points.extend([h1, h2, (x, y)])
        cx, cy = x, y
