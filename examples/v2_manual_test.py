"""Manual smoke test — renders a multi-domain scene to MP4 + SVG + Lottie.

Run::

    python examples/v2_manual_test.py

Then open the files printed at the end:
    - the .mp4 in any video player
    - the .svg in a browser (shows the final composed scene + CSS keyframes)
    - the .json at https://lottiefiles.com/tools/json-editor (or lottie-web demo)
"""

from __future__ import annotations

import json
from pathlib import Path

from archmotion.animation import ColorShift, Create, FadeIn, Transform
from archmotion.core import Scene
from archmotion.domains.architecture import Connection, Database, Node
from archmotion.domains.charts import BarChart, PieChart
from archmotion.domains.geometry import Circle, Square
from archmotion.domains.text import Text


def build() -> Scene:
    scene = Scene(resolution=(960, 540), fps=30)

    gateway = Node("API Gateway", center=(170.0, 270.0)).set_fill("#3b82f6")
    db = Database("Postgres", center=(470.0, 270.0)).set_fill("#10b981")
    link = Connection(gateway, db).set_stroke("#94a3b8", width=2.0)
    metrics = BarChart([3.0, 7.0, 5.0, 9.0], origin=(620.0, 430.0), height=130.0).set_fill("#f59e0b")
    title = Text("Fusion", size=44, bold=True).move_to(480.0, 70.0).set_fill("#e2e8f0")
    badge = Square(side=40.0).move_to(820.0, 120.0).set_fill("#8b5cf6")

    scene.add(gateway, db, link, metrics, title, badge)
    scene.play(FadeIn(gateway, db, link, title, run_time=0.8))
    scene.play(Create(badge))
    scene.play(FadeIn(metrics))
    scene.wait(0.3)
    # Cross-domain morphs.
    scene.play(Transform(db, Circle(radius=55.0).move_to(470.0, 270.0).set_fill("#10b981")))
    scene.play(Transform(metrics, PieChart([3.0, 7.0, 5.0, 9.0], radius=60.0, center=(740.0, 350.0)).set_fill("#f59e0b")))
    scene.play(Transform(badge, Circle(radius=30.0).move_to(820.0, 120.0).set_fill("#8b5cf6")))
    scene.play(ColorShift(gateway, "#3b82f6", "#ef4444"))
    return scene


def main() -> None:
    out = Path(__file__).resolve().parent / "_manual_output"
    out.mkdir(exist_ok=True)
    scene = build()

    mp4 = scene.render(str(out / "manual.mp4"))
    (out / "manual.svg").write_text(scene.to_svg(title="ArchMotion v2 Manual Test"), encoding="utf-8")
    (out / "manual.json").write_text(json.dumps(scene.to_lottie()), encoding="utf-8")

    tl = scene.compile_timeline()
    print(f"\nRendered {tl.total_frames} frames, "
          f"{len(tl.property_actions)} property actions, "
          f"{len(tl.morph_actions)} morph actions.")
    print(f"MP4:   {mp4}")
    print(f"SVG:   {out / 'manual.svg'}")
    print(f"Lottie:{out / 'manual.json'}")


if __name__ == "__main__":
    main()
