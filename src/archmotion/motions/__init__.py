"""User-facing animation classes.

Architectural Note:
    Animations are Phase 3 data declarations. They are NOT executed when
    constructed — they are recorded by Scene.play() and later decomposed
    into ScheduledActions by the Timeline Compiler.

v0.1.0: FadeIn, FadeOut, Transfer, Pulse
v0.2.0: Highlight, ColorShift, ScaleUp, ScaleDown
"""

from __future__ import annotations

from archmotion.motions._animations import (
    ColorShift,
    FadeIn,
    FadeOut,
    Highlight,
    Pulse,
    ScaleDown,
    ScaleUp,
    Transfer,
)

__all__ = [
    "ColorShift",
    "FadeIn",
    "FadeOut",
    "Highlight",
    "Pulse",
    "ScaleDown",
    "ScaleUp",
    "Transfer",
]
