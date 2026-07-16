"""Value tracking and dynamic redraw helpers for deterministic 2D scenes."""

from __future__ import annotations

from contextvars import ContextVar, Token
from typing import TYPE_CHECKING

from archmotion.animation.base import Animation
from archmotion.core.graphic import AnimateBuilder, Graphic
from archmotion.core.property import MorphAction, Property, PropertyAction

if TYPE_CHECKING:
    from collections.abc import Callable


_CURRENT_VALUES: ContextVar[dict[str, float] | None] = ContextVar(
    "archmotion_render_values",
    default=None,
)


class ValueTracker(Graphic):
    """A non-paintable scalar whose value can drive per-frame updaters."""

    def __init__(self, value: float = 0.0) -> None:
        """Create a tracker with an authored value."""
        super().__init__()
        self.value = float(value)

    def get_value(self) -> float:
        """Return the render-time value when inside a frame evaluation."""
        values = _CURRENT_VALUES.get()
        if values is not None and self.id in values:
            return values[self.id]
        return self.value

    def set_value(self, value: float) -> ValueTracker:
        """Set the authored scalar value."""
        self.value = float(value)
        return self

    @property
    def animate(self) -> ValueTrackerAnimateBuilder:
        """Capture a target value for :meth:`Scene.play`."""
        return ValueTrackerAnimateBuilder(self)


class ValueTrackerAnimateBuilder(AnimateBuilder):
    """Builder for ``tracker.animate.set_value(...)``."""

    def __init__(self, tracker: ValueTracker) -> None:
        """Capture the tracker without cloning a non-visual graphic."""
        self._tracker = tracker
        self._target = tracker.value
        self._run_time = 1.0
        self._rate_func = "smooth"

    def __getattr__(self, name: str) -> object:
        """Reject visual transform methods on a scalar animation builder."""
        raise AttributeError(name)

    def set_value(self, value: float) -> ValueTrackerAnimateBuilder:
        """Capture the target scalar value."""
        self._target = float(value)
        return self

    def set_run_time(self, run_time: float) -> ValueTrackerAnimateBuilder:
        """Set the generated animation duration."""
        self._run_time = float(run_time)
        return self

    def set_rate(self, rate_func: str) -> ValueTrackerAnimateBuilder:
        """Set the generated easing name."""
        self._rate_func = rate_func
        return self

    def build(self) -> ValueTrackerAnimation:
        """Build the scalar animation."""
        run_time = self._run_time if self._run_time is not None else 1.0
        return ValueTrackerAnimation(
            self._tracker,
            self._target,
            run_time=run_time,
            rate_func=self._rate_func,
        )


class ValueTrackerAnimation(Animation):
    """Interpolate one :class:`ValueTracker` over a timeline interval."""

    def __init__(
        self,
        tracker: ValueTracker,
        target: float,
        *,
        run_time: float = 1.0,
        rate_func: str = "smooth",
    ) -> None:
        super().__init__(run_time=run_time, rate_func=rate_func)
        self._tracker = tracker
        self._source = tracker.value
        self._target = float(target)

    def targets(self) -> list[Graphic]:
        """Return the tracker so the Scene indexes it."""
        return [self._tracker]

    def compile(self, start_time: float) -> list[PropertyAction | MorphAction]:
        """Emit the scalar VALUE action."""
        return [
            PropertyAction(
                target_id=self._tracker.id,
                prop=Property.VALUE,
                start_time=start_time,
                end_time=start_time + self.run_time,
                start_value=self._source,
                end_value=self._target,
                easing=self.rate_func,
            )
        ]

    def finish(self) -> None:
        """Commit the target value for subsequent authoring calls."""
        self._tracker.value = self._target


def always_redraw(factory: Callable[[], Graphic]) -> Graphic:
    """Rebuild a VMobject from ``factory`` before every rendered frame."""
    from archmotion.core.vmobject import VMobject

    graphic = factory()
    if not isinstance(graphic, VMobject):
        raise TypeError("always_redraw currently requires a VMobject factory")

    def _redraw(target: Graphic) -> None:
        replacement = factory()
        if not isinstance(target, VMobject) or not isinstance(replacement, VMobject):
            raise TypeError("always_redraw factory changed its graphic type")
        target.become(replacement)

    graphic.add_updater(_redraw)
    return graphic


def set_render_values(values: dict[str, float]) -> Token[dict[str, float] | None]:
    """Install frame-local ValueTracker values and return a reset token."""
    return _CURRENT_VALUES.set(values)


def reset_render_values(token: Token[dict[str, float] | None]) -> None:
    """Restore the previous frame-local tracker context."""
    _CURRENT_VALUES.reset(token)


__all__ = ["ValueTracker", "always_redraw"]
