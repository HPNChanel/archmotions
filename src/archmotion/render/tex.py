"""LaTeX math → VMobject (via ``latex`` + ``dvisvgm`` → SVG path parsing).

Runs the system ``latex`` and ``dvisvgm`` binaries in a temp dir, extracts the
``<path d="...">`` outlines from the resulting SVG, and parses them into a
:class:`~archmotion.core.vmobject.VMobject` point array. The result is a fully
morphable vector graphic (math text can ``Transform`` into any other shape).

This module imports no skia; it needs the native ``latex`` + ``dvisvgm``
binaries, which are NOT available in Pyodide (math scenes render CLI/MP4 only).
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from xml.etree import ElementTree

from archmotion.core.svg_path import ParsedPath, parse_svg_path
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
            ["latex", "-interaction=nonstopmode", "-halt-on-error",
             "-output-directory", str(work), str(tex_path)],
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
    """Extract and parse all ``<path d=...>`` from an SVG file."""
    tree = ElementTree.parse(svg_path)  # noqa: S314
    root = tree.getroot()
    ns = "{http://www.w3.org/2000/svg}"
    out: list[ParsedPath] = []
    for elem in root.iter():
        tag = elem.tag
        if tag == f"{ns}path" or tag.endswith("}path") or tag == "path":
            d = elem.get("d")
            if d:
                out.append(parse_svg_path(d))
    return out


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
