"""LaTeX math → VMobject (via ``latex`` + ``dvisvgm`` → SVG path parsing).

Runs the system ``latex`` and ``dvisvgm`` binaries in a temp dir, extracts the
``<path d="...">`` outlines from the resulting SVG, and parses them into a
:class:`~archmotion.core.vmobject.VMobject` point array. The result is a fully
morphable vector graphic (math text can ``Transform`` into any other shape).

This module imports no skia; it needs the native ``latex`` + ``dvisvgm``
binaries, which are NOT available in Pyodide (math scenes render CLI/MP4 only).
"""

from __future__ import annotations

import math
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from xml.etree import ElementTree

from archmotion.core.svg_path import ParsedPath, parse_svg_path
from archmotion.core.transform import Transform
from archmotion.core.vmobject import VMobject

_TEX_TEMPLATE = r"""\documentclass[12pt]{standalone}
\usepackage{amsmath,amssymb}
\begin{document}
$%s$
\end{document}
"""


def latex_available() -> bool:
    """Return True if both ``latex`` and ``dvisvgm`` binaries are on PATH."""
    return shutil.which("latex") is not None and shutil.which("dvisvgm") is not None


def tex_to_vmobject(latex_expr: str, *, font_size: float = 1.0) -> VMobject:
    r"""Compile a LaTeX math expression into a morphable VMobject.

    Args:
        latex_expr: LaTeX math body (e.g. ``r"e^{i\pi} + 1 = 0"``).
        font_size: Optional uniform scale applied to the resulting points.

    Raises:
        RuntimeError: If ``latex``/``dvisvgm`` are unavailable or compilation
            fails.
    """
    if not latex_available():
        msg = "latex + dvisvgm are required for tex rendering (not found on PATH)."
        raise RuntimeError(msg)

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        tex_path = work / "expr.tex"
        tex_path.write_text(_TEX_TEMPLATE % latex_expr, encoding="utf-8")

        _run(
            [
                "latex",
                "-interaction=nonstopmode",
                "-halt-on-error",
                "-output-directory",
                str(work),
                str(tex_path),
            ],
            work,
        )
        dvi = work / "expr.dvi"
        svg_path = work / "expr.svg"
        _run(
            ["dvisvgm", "--no-fonts", "--exact-bbox", "-o", str(svg_path), str(dvi)],
            work,
        )
        paths = _extract_paths(svg_path)

    obj = VMobject()
    for parsed in paths:
        _apply_parsed(obj, parsed, font_size)
    return obj


def _run(cmd: list[str], cwd: Path) -> None:
    """Run a subprocess, raising RuntimeError with stderr on failure."""
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        stderr = proc.stderr.decode(errors="replace") if proc.stderr else ""
        msg = f"Command {' '.join(cmd)} failed:\n{stderr[-800:]}"
        raise RuntimeError(msg)


def _extract_paths(svg_path: Path) -> list[ParsedPath]:
    """Resolve SVG paths, including dvisvgm ``defs/use`` glyph placement."""
    tree = ElementTree.parse(svg_path)  # noqa: S314
    root = tree.getroot()
    definitions = {
        element_id: element
        for element in root.iter()
        if (element_id := element.get("id")) is not None
    }
    out: list[ParsedPath] = []

    def walk(
        element: ElementTree.Element,
        parent_transform: Transform,
        *,
        from_reference: bool = False,
        reference_stack: frozenset[str] = frozenset(),
    ) -> None:
        local = _parse_transform(element.get("transform"))
        transform = parent_transform.compose(local)
        tag = _local_name(element.tag)
        if tag == "defs" and not from_reference:
            return
        if tag == "use":
            href = element.get("href") or element.get("{http://www.w3.org/1999/xlink}href")
            if not href or not href.startswith("#"):
                return
            reference_id = href[1:]
            if reference_id in reference_stack:
                raise RuntimeError(f"Circular SVG reference: {reference_id}")
            referenced = definitions.get(reference_id)
            if referenced is None:
                raise RuntimeError(f"Unknown SVG reference: {href}")
            x = _svg_number(element.get("x"), 0.0)
            y = _svg_number(element.get("y"), 0.0)
            placement = transform.compose(Transform.translation(x, y))
            walk(
                referenced,
                placement,
                from_reference=True,
                reference_stack=reference_stack | {reference_id},
            )
            return
        if tag == "path":
            d = element.get("d")
            if d:
                out.append(_transform_parsed(parse_svg_path(d), transform))
            return
        for child in element:
            walk(
                child,
                transform,
                from_reference=from_reference,
                reference_stack=reference_stack,
            )

    walk(root, Transform.identity())
    return out


_TRANSFORM_RE = re.compile(r"([A-Za-z]+)\s*\(([^)]*)\)")
_NUMBER_RE = re.compile(r"[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?")


def _parse_transform(value: str | None) -> Transform:
    """Parse common SVG affine transform functions into one matrix."""
    result = Transform.identity()
    if not value:
        return result
    for name, raw_args in _TRANSFORM_RE.findall(value):
        args = [float(item) for item in _NUMBER_RE.findall(raw_args)]
        lowered = name.lower()
        if lowered == "matrix" and len(args) == 6:
            a, b, c, d, e, f = args
            operation = Transform([[a, c, e], [b, d, f], [0.0, 0.0, 1.0]])
        elif lowered == "translate" and 1 <= len(args) <= 2:
            operation = Transform.translation(args[0], args[1] if len(args) == 2 else 0.0)
        elif lowered == "scale" and 1 <= len(args) <= 2:
            operation = Transform.scaling(args[0], args[1] if len(args) == 2 else None)
        elif lowered == "rotate" and len(args) in {1, 3}:
            rotation = Transform.rotation(args[0])
            if len(args) == 3:
                cx, cy = args[1], args[2]
                operation = (
                    Transform.translation(cx, cy)
                    .compose(rotation)
                    .compose(Transform.translation(-cx, -cy))
                )
            else:
                operation = rotation
        elif lowered == "skewx" and len(args) == 1:
            operation = Transform(
                [[1.0, math.tan(math.radians(args[0])), 0.0], [0.0, 1.0, 0.0], [0, 0, 1]]
            )
        elif lowered == "skewy" and len(args) == 1:
            operation = Transform(
                [[1.0, 0.0, 0.0], [math.tan(math.radians(args[0])), 1.0, 0.0], [0, 0, 1]]
            )
        else:
            raise RuntimeError(f"Unsupported SVG transform: {name}({raw_args})")
        result = result.compose(operation)
    return result


def _transform_parsed(parsed: ParsedPath, transform: Transform) -> ParsedPath:
    """Apply an affine transform without changing path topology."""
    points = transform.apply_to_points(parsed.points)
    return ParsedPath(
        points=[(float(point[0]), float(point[1])) for point in points],
        contour_starts=list(parsed.contour_starts),
    )


def _local_name(tag: str) -> str:
    """Strip an optional XML namespace from an element name."""
    return tag.rsplit("}", 1)[-1]


def _svg_number(value: str | None, default: float) -> float:
    """Parse a numeric SVG attribute, tolerating a unit suffix."""
    if value is None:
        return default
    match = _NUMBER_RE.search(value)
    return float(match.group(0)) if match else default


def _apply_parsed(obj: VMobject, parsed: ParsedPath, scale: float) -> None:
    """Append a parsed SVG path as one or more contours on ``obj``."""
    pts = parsed.points
    if not pts:
        return
    scaled = [(p[0] * scale, p[1] * scale) for p in pts]
    starts = [*parsed.contour_starts, len(scaled)]
    for ci in range(len(parsed.contour_starts)):
        start = parsed.contour_starts[ci]
        end = starts[ci + 1]
        if end - start < 1:
            continue
        obj._contour_starts.append(len(obj._pts))
        obj._pts.extend(scaled[start:end])
    obj._last = obj._pts[-1] if obj._pts else None
