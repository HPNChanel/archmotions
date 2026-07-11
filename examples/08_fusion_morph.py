"""Fusion demo 08 — Cross-domain Transform morphing.

The v2.0 signature feature: an architecture ``Node`` morphs into a geometry
``Circle``, which then morphs into a ``PieChart``. Because every vector graphic
shares point-array Bézier geometry, any two shapes can ``Transform`` into each
other.

Run::

    python examples/08_fusion_morph.py

Exports SVG + Lottie (no skia/ffmpeg needed).
"""

from __future__ import annotations

import json
from pathlib import Path

from archmotion.animation import FadeIn, Transform
from archmotion.core import Scene
from archmotion.domains.architecture import Node
from archmotion.domains.charts import PieChart
from archmotion.domains.geometry import Circle


def build_scene() -> Scene:
    """Morph a node → circle → pie chart (three domains, one scene)."""
    scene = Scene(resolution=(960, 540), fps=30)

    # Start as an architecture node.
    server = Node("Server", center=(480.0, 270.0)).set_fill("#3b82f6")
    scene.add(server)
    scene.play(FadeIn(server, run_time=0.6))
    scene.wait(0.3)

    # Morph into a geometry circle (architecture → geometry fusion).
    scene.play(
        Transform(
            server,
            Circle(radius=70.0, center=(480.0, 270.0)).set_fill("#8b5cf6"),
            run_time=0.8,
        )
    )
    scene.wait(0.2)

    # Morph the circle into a pie chart (geometry → charts fusion).
    scene.play(
        Transform(
            server,
            PieChart(
                [3.0, 7.0, 5.0, 9.0], radius=75.0, center=(480.0, 270.0)
            ).set_fill("#f59e0b"),
            run_time=0.8,
        )
    )
    scene.wait(0.4)
    return scene


def main() -> None:
    """Build the scene and export SVG + Lottie."""
    scene = build_scene()
    out = Path(__file__).resolve().parent / "_fusion_output"
    out.mkdir(exist_ok=True)

    svg = scene.to_svg(title="Fusion 08 — Cross-Domain Morph")
    (out / "fusion_08.svg").write_text(svg, encoding="utf-8")

    lottie = scene.to_lottie(title="Fusion 08 — Cross-Domain Morph")
    (out / "fusion_08.json").write_text(json.dumps(lottie), encoding="utf-8")

    timeline = scene.compile_timeline()
    print(
        f"Built scene: {timeline.total_frames} frames, "
        f"{len(timeline.property_actions)} property actions, "
        f"{len(timeline.morph_actions)} morph actions."
    )
    print(f"Wrote: {out / 'fusion_08.svg'}")
    print(f"Wrote: {out / 'fusion_08.json'}")


if __name__ == "__main__":
    main()
