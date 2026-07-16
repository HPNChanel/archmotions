"""Fusion demo 10 — CodeBlock walkthrough with a data-flow Transfer.

Combines the architecture and code domains: a connection between two nodes
carries a data-flow packet (``Transfer``) while a syntax-highlighted
``CodeBlock`` is progressively written beside it, narrating the data path.

Run::

    python examples/10_fusion_code_walkthrough.py

Exports SVG + Lottie (no skia/ffmpeg needed).
"""

from __future__ import annotations

import json
from pathlib import Path

from archmotion.animation import FadeIn, Transfer, Write
from archmotion.core import Scene
from archmotion.domains.architecture import Connection, Node
from archmotion.domains.code import CodeBlock


def build_scene() -> Scene:
    """Compose a code walkthrough with a live data-flow transfer beside it."""
    scene = Scene(resolution=(960, 540), fps=30)

    # Architecture domain — a producer → consumer pipeline.
    producer = Node("Producer", center=(150.0, 380.0)).set_fill("#3b82f6")
    consumer = Node("Consumer", center=(450.0, 380.0)).set_fill("#8b5cf6")
    link = Connection(producer, consumer, label="stream").set_stroke("#94a3b8", width=2.0)

    # Code domain — the consumer logic, written progressively.
    snippet = CodeBlock(
        "async for event in stream:\n"
        "    await process(event)\n"
        "    ack(event)",
        language="python",
        size=16.0,
        origin=(560.0, 180.0),
    ).set_fill("#10b981")

    scene.add(producer, consumer, link, snippet)

    # Fade in the architecture, then write the code while a packet flows.
    scene.play(FadeIn(producer, consumer, link, run_time=0.8))
    scene.wait(0.2)
    scene.play(Write(snippet, run_time=1.5))
    scene.play(Transfer(link, payload="event", run_time=1.0))
    scene.wait(0.4)
    return scene


def main() -> None:
    """Build the scene and export SVG + Lottie."""
    scene = build_scene()
    out = Path(__file__).resolve().parent / "_fusion_output"
    out.mkdir(exist_ok=True)

    svg = scene.to_svg(title="Fusion 10 — Code Walkthrough + Data Flow")
    (out / "fusion_10.svg").write_text(svg, encoding="utf-8")

    lottie = scene.to_lottie(title="Fusion 10 — Code Walkthrough + Data Flow")
    (out / "fusion_10.json").write_text(json.dumps(lottie), encoding="utf-8")

    timeline = scene.compile_timeline()
    print(
        f"Built scene: {timeline.total_frames} frames, "
        f"{len(timeline.property_actions)} property actions."
    )
    print(f"Wrote: {out / 'fusion_10.svg'}")
    print(f"Wrote: {out / 'fusion_10.json'}")


if __name__ == "__main__":
    main()
