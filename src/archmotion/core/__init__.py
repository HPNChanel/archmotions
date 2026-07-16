"""ArchMotion v2.0 Core — Manim-style multi-domain graphics foundation.

This package is deliberately skia-free (numpy + pure Python only) so the
geometry, property, animation, and scene layers run anywhere (CLI, Pyodide).
The skia-dependent renderer lives in ``archmotion.render`` and is imported
lazily.
"""

from archmotion.core.camera import Camera
from archmotion.core.graphic import AnimateBuilder, Graphic
from archmotion.core.property import (
    CompiledTimeline,
    FrameSnapshot,
    MorphAction,
    Property,
    PropertyAction,
)
from archmotion.core.scene import Scene
from archmotion.core.style import Style
from archmotion.core.transform import Transform
from archmotion.core.vgroup import VGroup
from archmotion.core.vmobject import VMobject


def __getattr__(name: str) -> object:
    """Load updater helpers lazily to keep ``core`` independent of animation."""
    if name in {"ValueTracker", "always_redraw"}:
        from archmotion.core.updaters import ValueTracker, always_redraw

        return {"ValueTracker": ValueTracker, "always_redraw": always_redraw}[name]
    raise AttributeError(name)


__all__ = [
    "AnimateBuilder",
    "Camera",
    "CompiledTimeline",
    "FrameSnapshot",
    "Graphic",
    "MorphAction",
    "Property",
    "PropertyAction",
    "Scene",
    "Style",
    "Transform",
    "VGroup",
    "VMobject",
    "ValueTracker",
    "always_redraw",
]
