"""ArchMotion Shared Type Aliases and Enumerations.

Architectural Note:
    This module provides type aliases and enums shared across multiple
    Phases. Keeping them in one place avoids circular imports and
    ensures consistency across the pipeline.
"""

from __future__ import annotations

from enum import Enum, auto
from typing import TypeAlias

# ──────────────────────────────────────────────
# Geometric Type Aliases
# ──────────────────────────────────────────────

Point: TypeAlias = tuple[float, float]
"""A 2D point as (x, y) in pixel coordinates."""

Color: TypeAlias = str
"""CSS color name ('red') or hex string ('#ff5733')."""


# ──────────────────────────────────────────────
# Enumerations
# ──────────────────────────────────────────────


class Direction(Enum):
    """Relative positioning direction between nodes.

    Used in Phase 1 (Topology Builder) to record spatial relationships.
    Phase 2 (Layout Resolver) translates these into pixel offsets.
    """

    RIGHT_OF = auto()
    LEFT_OF = auto()
    ABOVE = auto()
    BELOW = auto()


class PrimitiveType(Enum):
    """Type discriminator for scene graph objects.

    Determines rendering shape in Phase 4 (Renderer).
    """

    NODE = auto()
    DATABASE = auto()
    CLOUD = auto()
    QUEUE = auto()
    CACHE = auto()
    USER = auto()
    CONNECTION = auto()
    PACKET = auto()


class EasingType(Enum):
    """Interpolation curve type for animations.

    Each value maps to a mathematical function in `timeline.easing`.
    Default for all animations: EASE_IN_OUT (Cubic Smoothstep).
    """

    LINEAR = auto()
    EASE_IN = auto()
    EASE_OUT = auto()
    EASE_IN_OUT = auto()
    EASE_IN_CUBIC = auto()
    EASE_OUT_CUBIC = auto()
    EASE_OUT_BOUNCE = auto()


class AnimatableProperty(Enum):
    """Properties that can be animated over time.

    Each property maps to a specific visual attribute of a scene object.
    The Timeline Compiler decomposes high-level animations (FadeIn, Transfer)
    into ScheduledActions targeting these atomic properties.
    """

    OPACITY = auto()
    POSITION_X = auto()
    POSITION_Y = auto()
    SCALE = auto()
    COLOR_R = auto()
    COLOR_G = auto()
    COLOR_B = auto()
    GLOW_INTENSITY = auto()
    PATH_PROGRESS = auto()
