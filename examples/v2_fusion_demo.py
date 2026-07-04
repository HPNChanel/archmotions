"""ArchMotion v2.0 — Multi-Domain Fusion Demo.

Demonstrates the core differentiator: architecture, geometry, charts, and math
coexisting in ONE scene, with cross-domain ``Transform`` morphing (an
architecture node morphs into a circle; a bar chart morphs into a pie chart).

Run::

    python examples/v2_fusion_demo.py

This builds the scene and exports SVG + Lottie (no skia/ffmpeg needed). MP4
rendering requires skia-python; uncomment the ``scene.render(...)`` call when it
is installed.
"""

from __future__ import annotations

import json
from pathlib import Path

from archmotion.animation import ColorShift, FadeIn, Transform
from archmotion.core import Scene
from archmotion.domains.architecture import Connection, Database, Node
from archmotion.domains.charts import BarChart, PieChart
from archmotion.domains.geometry import Circle


def build_scene() -> Scene:
    """Compose an architecture diagram + a live metric chart in one scene."""
    scene = Scene(resolution=(960, 540), fps=30)

    # Architecture domain.
    gateway = Node("API Gateway", center=(180.0, 270.0)).set_fill("#3b82f6")
    db = Database("Postgres", center=(520.0, 270.0)).set_fill("#10b981")
    link = Connection(gateway, db).set_stroke("#94a3b8", width=2.0)

    # Charts domain — a live-metrics bar chart beside the architecture.
    metrics = BarChart([3.0, 7.0, 5.0, 9.0], origin=(640.0, 420.0), height=120.0).set_fill("#f59e0b")

    scene.add(gateway, db, link, metrics)

    # Introduce the architecture + chart together (fusion).
    scene.play(FadeIn(gateway, db, link, run_time=0.6))
    scene.play(FadeIn(metrics, run_time=0.6))
    scene.wait(0.3)

    # Cross-domain morph: the database transforms into a circle (fusion!).
    scene.play(Transform(db, Circle(radius=55.0).move_to(520.0, 270.0).set_fill("#10b981")))
    scene.wait(0.2)

    # The bar chart morphs into a pie chart.
    scene.play(Transform(metrics, PieChart([3.0, 7.0, 5.0, 9.0], radius=60.0, center=(760.0, 340.0)).set_fill("#f59e0b")))
    scene.wait(0.2)

    # A color shift on the gateway (architecture recipe animation).
    scene.play(ColorShift(gateway, "#3b82f6", "#ef4444", run_time=0.8))
    return scene


def main() -> None:
    """Build the scene and export SVG + Lottie."""
    scene = build_scene()
    out = Path(__file__).resolve().parent / "_fusion_output"
    out.mkdir(exist_ok=True)

    svg = scene.to_svg(title="ArchMotion v2.0 Fusion Demo")
    (out / "fusion.svg").write_text(svg, encoding="utf-8")

    lottie = scene.to_lottie(title="ArchMotion v2.0 Fusion Demo")
    (out / "fusion.json").write_text(json.dumps(lottie), encoding="utf-8")

    timeline = scene.compile_timeline()
    print(f"Built scene: {timeline.total_frames} frames, "
          f"{len(timeline.property_actions)} property actions, "
          f"{len(timeline.morph_actions)} morph actions.")
    print(f"Wrote: {out / 'fusion.svg'}")
    print(f"Wrote: {out / 'fusion.json'}")
    print("Tip: install skia-python + uncomment scene.render() for MP4.")


if __name__ == "__main__":
    main()
