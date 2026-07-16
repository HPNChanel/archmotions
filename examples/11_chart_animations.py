"""Fusion demo 11 — Chart animations: GrowBar, DrawLine, SweepPie.

Showcases the three domain-specific chart reveal animations on live data:
  - GrowBar on a BarChart (bars rise from the baseline)
  - DrawLine on a LineChart (the line draws progressively)
  - SweepPie on a PieChart (slices sweep in)

Run::

    python examples/11_chart_animations.py

Exports SVG + Lottie (no skia/ffmpeg needed).
"""

from __future__ import annotations

import json
from pathlib import Path

from archmotion.animation import DrawLine, FadeIn, GrowBar, SweepPie
from archmotion.core import Scene
from archmotion.domains.charts import BarChart, LineChart, PieChart


def build_scene() -> Scene:
    """Compose three charts, each revealed with its bespoke animation."""
    scene = Scene(resolution=(960, 540), fps=30)

    # BarChart — bars grow from zero height.
    bars = BarChart(
        [3.0, 7.0, 5.0, 9.0],
        origin=(60.0, 200.0),
        height=120.0,
        bar_width=24.0,
        gap=10.0,
    ).set_fill("#3b82f6")

    # LineChart — the line draws progressively.
    line = LineChart(
        [2.0, 4.0, 3.0, 6.0, 5.0, 8.0],
        origin=(380.0, 200.0),
        width=200.0,
        height=120.0,
    ).set_stroke("#10b981", width=2.0)

    # PieChart — slices sweep in.
    pie = PieChart(
        [3.0, 7.0, 5.0, 9.0],
        radius=50.0,
        center=(780.0, 140.0),
    ).set_fill("#f59e0b")

    scene.add(bars, line, pie)

    # Reveal each chart with its signature animation.
    scene.play(GrowBar(bars, run_time=1.0))
    scene.play(DrawLine(line, run_time=1.0))
    scene.play(SweepPie(pie, run_time=1.0))
    scene.wait(0.5)
    return scene


def main() -> None:
    """Build the scene and export SVG + Lottie."""
    scene = build_scene()
    out = Path(__file__).resolve().parent / "_fusion_output"
    out.mkdir(exist_ok=True)

    svg = scene.to_svg(title="Fusion 11 — Chart Animations")
    (out / "fusion_11.svg").write_text(svg, encoding="utf-8")

    lottie = scene.to_lottie(title="Fusion 11 — Chart Animations")
    (out / "fusion_11.json").write_text(json.dumps(lottie), encoding="utf-8")

    timeline = scene.compile_timeline()
    print(
        f"Built scene: {timeline.total_frames} frames, "
        f"{len(timeline.property_actions)} property actions."
    )
    print(f"Wrote: {out / 'fusion_11.svg'}")
    print(f"Wrote: {out / 'fusion_11.json'}")


if __name__ == "__main__":
    main()
