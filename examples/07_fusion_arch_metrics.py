"""Fusion demo 07 — Architecture + live metrics BarChart in one scene.

Demonstrates the v2.0 multi-domain capability: an architecture diagram
coexists with a data-visualization ``BarChart`` that animates in alongside
the system topology.

Run::

    python examples/07_fusion_arch_metrics.py

Exports SVG + Lottie (no skia/ffmpeg needed). MP4 requires skia-python;
uncomment the ``scene.render(...)`` call when it is installed.
"""

from __future__ import annotations

import json
from pathlib import Path

from archmotion.animation import Create, FadeIn
from archmotion.core import Scene
from archmotion.domains.architecture import Connection, Node
from archmotion.domains.charts import BarChart


def build_scene() -> Scene:
    """Compose a 3-node architecture with a live-metrics bar chart beside it."""
    scene = Scene(resolution=(960, 540), fps=30)

    # Architecture domain — a small request pipeline.
    gateway = Node("Gateway", center=(150.0, 270.0)).set_fill("#3b82f6")
    worker = Node("Worker", center=(380.0, 270.0)).set_fill("#8b5cf6")
    cache = Node("Cache", center=(610.0, 270.0)).set_fill("#10b981")
    link1 = Connection(gateway, worker).set_stroke("#94a3b8", width=2.0)
    link2 = Connection(worker, cache).set_stroke("#94a3b8", width=2.0)

    # Charts domain — request throughput metrics beside the architecture.
    metrics = BarChart(
        [4.0, 8.0, 6.0, 9.0, 7.0],
        origin=(720.0, 460.0),
        height=120.0,
        bar_width=24.0,
        gap=10.0,
    ).set_fill("#f59e0b")

    scene.add(gateway, worker, cache, link1, link2, metrics)

    # Introduce the architecture, then draw the metric bars progressively.
    scene.play(FadeIn(gateway, worker, cache, link1, link2, run_time=0.8))
    scene.play(Create(metrics, run_time=1.0))
    scene.wait(0.3)
    return scene


def main() -> None:
    """Build the scene and export SVG + Lottie."""
    scene = build_scene()
    out = Path(__file__).resolve().parent / "_fusion_output"
    out.mkdir(exist_ok=True)

    svg = scene.to_svg(title="Fusion 07 — Architecture + Metrics")
    (out / "fusion_07.svg").write_text(svg, encoding="utf-8")

    lottie = scene.to_lottie(title="Fusion 07 — Architecture + Metrics")
    (out / "fusion_07.json").write_text(json.dumps(lottie), encoding="utf-8")

    timeline = scene.compile_timeline()
    print(
        f"Built scene: {timeline.total_frames} frames, "
        f"{len(timeline.property_actions)} property actions."
    )
    print(f"Wrote: {out / 'fusion_07.svg'}")
    print(f"Wrote: {out / 'fusion_07.json'}")
    print("Tip: install skia-python + uncomment scene.render() for MP4.")


if __name__ == "__main__":
    main()
