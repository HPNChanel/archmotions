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
from archmotion.core.vmobject import VMobject

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
    "VMobject",
]
