"""Phase 3 — Easing functions for animation interpolation.

Architectural Note:
    Every easing function has signature `(t: float) -> float` where
    t ∈ [0, 1] (animation progress) and output ∈ [0, 1] (eased value).
    Functions are registered in EASING_FUNCTIONS dict, keyed by EasingType enum.

    These are the mathematical backbone of the Parametric O(1) model:
    given any timestamp, we can compute exact animation state without
    knowing the previous frame — enabling parallel frame rendering.
"""

from __future__ import annotations

from typing import Callable

from archmotion._types import EasingType

EasingFunction = Callable[[float], float]
"""Type alias: receives progress [0,1], returns eased value [0,1]."""


def linear(t: float) -> float:
    """f(t) = t — Constant speed."""
    return t


def ease_in(t: float) -> float:
    """f(t) = t² — Quadratic ease-in. Starts slow, accelerates."""
    return t * t


def ease_out(t: float) -> float:
    """f(t) = 1 - (1-t)² — Quadratic ease-out. Starts fast, decelerates."""
    return 1.0 - (1.0 - t) ** 2


def ease_in_out(t: float) -> float:
    """f(t) = 3t² - 2t³ — Smoothstep (cubic ease-in-out).

    Default easing for all ArchMotion animations.
    Properties: f(0)=0, f(1)=1, f'(0)=0, f'(1)=0.
    """
    return t * t * (3.0 - 2.0 * t)


def ease_in_cubic(t: float) -> float:
    """f(t) = t³ — Cubic ease-in. Very slow start."""
    return t * t * t


def ease_out_cubic(t: float) -> float:
    """f(t) = 1 - (1-t)³ — Cubic ease-out. Very smooth deceleration."""
    return 1.0 - (1.0 - t) ** 3


def ease_out_bounce(t: float) -> float:
    """Bounce ease-out — piecewise quadratic simulating a bouncing ball."""
    if t < 1.0 / 2.75:
        return 7.5625 * t * t
    elif t < 2.0 / 2.75:
        t -= 1.5 / 2.75
        return 7.5625 * t * t + 0.75
    elif t < 2.5 / 2.75:
        t -= 2.25 / 2.75
        return 7.5625 * t * t + 0.9375
    else:
        t -= 2.625 / 2.75
        return 7.5625 * t * t + 0.984375


EASING_FUNCTIONS: dict[EasingType, EasingFunction] = {
    EasingType.LINEAR: linear,
    EasingType.EASE_IN: ease_in,
    EasingType.EASE_OUT: ease_out,
    EasingType.EASE_IN_OUT: ease_in_out,
    EasingType.EASE_IN_CUBIC: ease_in_cubic,
    EasingType.EASE_OUT_CUBIC: ease_out_cubic,
    EasingType.EASE_OUT_BOUNCE: ease_out_bounce,
}
"""Registry mapping EasingType enum → function implementation."""


def apply_easing(progress: float, easing_type: EasingType) -> float:
    """Apply an easing function to a progress value.

    Args:
        progress: Raw animation progress, clamped to [0, 1].
        easing_type: Which easing curve to apply.

    Returns:
        Eased progress value in [0, 1].
    """
    clamped = max(0.0, min(1.0, progress))
    return EASING_FUNCTIONS[easing_type](clamped)
