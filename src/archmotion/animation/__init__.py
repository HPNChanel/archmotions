"""ArchMotion v2.0 animation system (recipe + transform + groups)."""

from archmotion.animation.base import (
    Animation,
    AnimationGroup,
    Create,
    FadeIn,
    FadeOut,
    StateTween,
    Transform,
)
from archmotion.animation.recipes import (
    ColorShift,
    Highlight,
    Pulse,
    Scale,
    ScaleDown,
    ScaleUp,
    Transfer,
)

__all__ = [
    "Animation",
    "AnimationGroup",
    "ColorShift",
    "Create",
    "FadeIn",
    "FadeOut",
    "Highlight",
    "Pulse",
    "Scale",
    "ScaleDown",
    "ScaleUp",
    "StateTween",
    "Transfer",
    "Transform",
]
