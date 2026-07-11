"""Easing functions keyed by name (v2.0 core).

Keys the registry by string so animations can specify easing without importing
an enum.
"""

from __future__ import annotations

from collections.abc import Callable

EasingFunction = Callable[[float], float]


def linear(t: float) -> float:
    """Constant speed."""
    return t


def smooth(t: float) -> float:
    """Smoothstep (cubic ease-in-out). The default."""
    return t * t * (3.0 - 2.0 * t)


def ease_in(t: float) -> float:
    """Quadratic ease-in."""
    return t * t


def ease_out(t: float) -> float:
    """Quadratic ease-out."""
    return 1.0 - (1.0 - t) ** 2


def ease_in_out(t: float) -> float:
    """Alias for :func:`smooth`."""
    return smooth(t)


def ease_in_cubic(t: float) -> float:
    """Cubic ease-in."""
    return t * t * t


def ease_out_cubic(t: float) -> float:
    """Cubic ease-out."""
    return 1.0 - (1.0 - t) ** 3


def ease_out_bounce(t: float) -> float:
    """Bounce ease-out (bouncing-ball feel)."""
    if t < 1.0 / 2.75:
        return 7.5625 * t * t
    if t < 2.0 / 2.75:
        t -= 1.5 / 2.75
        return 7.5625 * t * t + 0.75
    if t < 2.5 / 2.75:
        t -= 2.25 / 2.75
        return 7.5625 * t * t + 0.9375
    t -= 2.625 / 2.75
    return 7.5625 * t * t + 0.984375


def there_and_back(t: float) -> float:
    """Go to 1 and back to 0 over the interval."""
    return 1.0 - abs(2.0 * t - 1.0)


EASINGS: dict[str, EasingFunction] = {
    "linear": linear,
    "smooth": smooth,
    "ease_in": ease_in,
    "ease_out": ease_out,
    "ease_in_out": ease_in_out,
    "ease_in_cubic": ease_in_cubic,
    "ease_out_cubic": ease_out_cubic,
    "ease_out_bounce": ease_out_bounce,
    "there_and_back": there_and_back,
}

DEFAULT_EASING = "smooth"


def resolve(name: str | None) -> EasingFunction:
    """Look up an easing function by name (falls back to the default)."""
    if name is None:
        return EASINGS[DEFAULT_EASING]
    if name not in EASINGS:
        msg = f"Unknown easing '{name}'. Available: {sorted(EASINGS)}"
        raise KeyError(msg)
    return EASINGS[name]


def apply(progress: float, name: str | None = None) -> float:
    """Apply a named easing to a progress value clamped to [0, 1]."""
    clamped = max(0.0, min(1.0, progress))
    return resolve(name)(clamped)
