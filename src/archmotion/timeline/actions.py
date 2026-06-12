"""ScheduledAction — atomic timeline unit produced by the Timeline Compiler.

Architectural Note:
    ScheduledActions are the output of Phase 3. They represent a single
    property change over a time interval. The Renderer (Phase 4) evaluates
    these at any timestamp t using the Parametric O(1) formula:

        value(t) = start_value + (end_value - start_value) × ease(progress)
"""

from __future__ import annotations

from dataclasses import dataclass

from archmotion._types import AnimatableProperty, EasingType
from archmotion.timeline.easing import apply_easing


@dataclass(frozen=True)
class ScheduledAction:
    """An atomic animation applied to a single property of a single object.

    Attributes:
        target_id: ID of the scene object being animated.
        prop: Which visual property changes.
        start_time: Animation start (seconds from timeline origin).
        end_time: Animation end (seconds from timeline origin).
        start_value: Property value at start_time.
        end_value: Property value at end_time.
        easing: Interpolation curve.
    """

    target_id: str
    prop: AnimatableProperty
    start_time: float
    end_time: float
    start_value: float
    end_value: float
    easing: EasingType = EasingType.EASE_IN_OUT

    @property
    def duration(self) -> float:
        """Duration in seconds."""
        return self.end_time - self.start_time

    def value_at(self, current_time: float) -> float:
        """Compute property value at any timestamp — O(1).

        Args:
            current_time: The timestamp to evaluate (seconds).

        Returns:
            Interpolated property value.
        """
        if current_time <= self.start_time:
            return self.start_value
        if current_time >= self.end_time:
            return self.end_value

        progress = (current_time - self.start_time) / self.duration
        eased = apply_easing(progress, self.easing)
        return self.start_value + (self.end_value - self.start_value) * eased

    def is_active_at(self, current_time: float) -> bool:
        """Check if this action is active at the given timestamp.

        Args:
            current_time: The timestamp to check.

        Returns:
            True if start_time <= current_time <= end_time.
        """
        return self.start_time <= current_time <= self.end_time
