"""Fusion demo 09 — LaTeX math equation layered over an architecture diagram.

Combines the architecture and math domains: a server topology fades in, then a
LaTeX-rendered equation derivation (Euler's identity) appears above it. Math
scenes require the native ``latex`` + ``dvisvgm`` binaries (not Pyodide-compatible).

Run::

    python examples/09_fusion_math_over_arch.py

If LaTeX is absent the script prints a message and exits gracefully.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from archmotion.animation import Create, FadeIn
from archmotion.core import Scene
from archmotion.domains.architecture import Connection, Node
from archmotion.render.tex import latex_available


def build_scene(equation) -> Scene:
    """Compose an architecture diagram with a math equation derivation above it."""
    scene = Scene(resolution=(960, 540), fps=30)

    gateway = Node("Gateway", center=(300.0, 360.0)).set_fill("#3b82f6")
    db = Node("Database", center=(600.0, 360.0)).set_fill("#10b981")
    link = Connection(gateway, db).set_stroke("#94a3b8", width=2.0)

    scene.add(gateway, db, link)
    scene.play(FadeIn(gateway, db, link, run_time=0.8))
    scene.wait(0.3)

    # Math domain — write the equation progressively above the diagram.
    equation.move_to(480.0, 150.0)
    scene.add(equation)
    scene.play(Create(equation, run_time=1.5))
    scene.wait(0.5)
    return scene


def main() -> None:
    """Build the scene and export SVG + Lottie (requires LaTeX)."""
    if not latex_available():
        print(
            "LaTeX (latex + dvisvgm) is not installed. "
            "Install TeX Live / MiKTeX + dvisvgm to run this example.",
            file=sys.stderr,
        )
        sys.exit(0)

    from archmotion.domains.math import MathText

    equation = MathText(r"e^{i\pi} + 1 = 0", font_size=2.0)

    scene = build_scene(equation)
    out = Path(__file__).resolve().parent / "_fusion_output"
    out.mkdir(exist_ok=True)

    svg = scene.to_svg(title="Fusion 09 — Math over Architecture")
    (out / "fusion_09.svg").write_text(svg, encoding="utf-8")

    lottie = scene.to_lottie(title="Fusion 09 — Math over Architecture")
    (out / "fusion_09.json").write_text(json.dumps(lottie), encoding="utf-8")

    timeline = scene.compile_timeline()
    print(
        f"Built scene: {timeline.total_frames} frames, "
        f"{len(timeline.property_actions)} property actions."
    )
    print(f"Wrote: {out / 'fusion_09.svg'}")
    print(f"Wrote: {out / 'fusion_09.json'}")


if __name__ == "__main__":
    main()
