"""Graphic — the base scene object.

A :class:`Graphic` owns an affine :class:`~archmotion.core.transform.Transform`,
a :class:`~archmotion.core.style.Style`, an opacity, an id, a z-order, and an
optional scene-graph parent/children. Concrete vector shapes subclass
:class:`~archmotion.core.vmobject.VMobject`.

The fluent transform/style methods (``shift``, ``scale``, ``set_fill`` ...)
mutate the receiver in place and return ``self`` for chaining.
"""

from __future__ import annotations

import copy as _copy
import uuid
from typing import TYPE_CHECKING, Any, ClassVar

from archmotion.core.style import Style
from archmotion.core.transform import Transform
from archmotion.layout.bbox import BoundingBox

if TYPE_CHECKING:
    from collections.abc import Iterable

    from archmotion.animation.base import Animation

Z_DEFAULT = 0


class Graphic:
    """Base scene-graph object."""

    def __init__(
        self,
        *,
        id: str | None = None,
        z_index: int = Z_DEFAULT,
        transform: Transform | None = None,
        style: Style | None = None,
        opacity: float = 1.0,
    ) -> None:
        """Initialize id, transform, style, opacity and an empty child list."""
        self.id: str = id or uuid.uuid4().hex[:8]
        self.z_index: int = z_index
        self.transform: Transform = transform if transform is not None else Transform.identity()
        self.style: Style = style if style is not None else Style()
        self.opacity: float = opacity
        self._parent: Graphic | None = None
        self._children: list[Graphic] = []

    # ── scene graph ──────────────────────────────────────────────

    @property
    def parent(self) -> Graphic | None:
        """Parent graphic, if any."""
        return self._parent

    @property
    def children(self) -> list[Graphic]:
        """Child graphics (read-only view)."""
        return list(self._children)

    def add(self, *children: Graphic) -> Graphic:
        """Attach children. Returns self for chaining."""
        for child in children:
            if child._parent is not None and child._parent is not self:
                child._parent._children.remove(child)
            child._parent = self
            self._children.append(child)
        return self

    def remove(self, *children: Graphic) -> Graphic:
        """Detach children. Returns self for chaining."""
        for child in children:
            if child in self._children:
                self._children.remove(child)
                child._parent = None
        return self

    # ── fluent transforms ────────────────────────────────────────

    def shift(self, x: float, y: float) -> Graphic:
        """Translate by ``(x, y)``."""
        self.transform = Transform.translation(x, y).compose(self.transform)
        return self

    def move_to(self, x: float, y: float) -> Graphic:
        """Move so the bounding-box center lands on ``(x, y)``."""
        bbox = self.bounding_box()
        cx, cy = bbox.center
        self.shift(x - cx, y - cy)
        return self

    def scale(self, sx: float, sy: float | None = None) -> Graphic:
        """Scale about the bounding-box center."""
        cx, cy = self.bounding_box().center
        sy_eff = sx if sy is None else sy
        to_origin = Transform.translation(-cx, -cy)
        scaler = Transform.scaling(sx, sy_eff)
        back = Transform.translation(cx, cy)
        self.transform = back.compose(scaler).compose(to_origin).compose(self.transform)
        return self

    def rotate(self, angle_deg: float) -> Graphic:
        """Rotate about the bounding-box center."""
        cx, cy = self.bounding_box().center
        to_origin = Transform.translation(-cx, -cy)
        rot = Transform.rotation(angle_deg)
        back = Transform.translation(cx, cy)
        self.transform = back.compose(rot).compose(to_origin).compose(self.transform)
        return self

    # ── fluent style ─────────────────────────────────────────────

    def set_opacity(self, opacity: float) -> Graphic:
        """Set overall opacity [0.0, 1.0]."""
        self.opacity = opacity
        return self

    def set_fill(self, color: str | None = None, opacity: float | None = None) -> Graphic:
        """Set fill color and/or opacity."""
        self.style = self.style.with_fill(color, opacity)
        return self

    def set_stroke(
        self,
        color: str | None = None,
        width: float | None = None,
        opacity: float | None = None,
    ) -> Graphic:
        """Set stroke color, width, and/or opacity."""
        self.style = self.style.with_stroke(color, width, opacity)
        return self

    def set_color(self, color: str) -> Graphic:
        """Set both fill and stroke color."""
        self.style = self.style.with_fill(color).with_stroke(color)
        return self

    def set_z(self, z_index: int) -> Graphic:
        """Set the z-index (paint order)."""
        self.z_index = z_index
        return self

    # ── geometry ─────────────────────────────────────────────────

    def bounding_box(self) -> BoundingBox:
        """Axis-aligned bounding box (overridden by VMobject for point data)."""
        if self._children:
            return _union_boxes(c.bounding_box() for c in self._children)
        # Point-less, child-less graphic: a zero box at the transform origin.
        origin = self.transform.apply_to_point((0.0, 0.0))
        return BoundingBox(origin[0], origin[1], 0.0, 0.0)

    # ── copy ─────────────────────────────────────────────────────

    def copy(self) -> Graphic:
        """Deep copy (points, style, transform, children) with a fresh id."""
        clone = _copy.copy(self)
        clone.id = uuid.uuid4().hex[:8]
        clone.transform = _copy.copy(self.transform)
        clone.style = self.style  # frozen dataclass — safe to share
        clone._parent = None
        clone._children = [c.copy() for c in self._children]
        for c in clone._children:
            c._parent = clone
        return clone

    # ── animation builder ────────────────────────────────────────

    @property
    def animate(self) -> AnimateBuilder:
        """Return a builder that captures transform/style changes as a tween.

        ``g.animate.shift(10, 0).set_fill("#f00")`` records the changes on a
        clone; passing the builder to ``Scene.play`` tweens the graphic from its
        current state to the captured target state.
        """
        return AnimateBuilder(self)

    def __repr__(self) -> str:
        """Concise developer representation."""
        return f"{type(self).__name__}(id={self.id!r}, z={self.z_index})"


class AnimateBuilder:
    """Captures fluent mutations on a clone; builds a state-tween Animation."""

    _DELEGATED: ClassVar[set[str]] = {
        "shift", "move_to", "scale", "rotate",
        "set_opacity", "set_fill", "set_stroke", "set_color", "set_z",
    }

    def __init__(self, graphic: Graphic) -> None:
        """Capture a working clone of ``graphic``."""
        self._source = graphic
        self._clone: Graphic = graphic.copy()
        self._run_time: float | None = None
        self._rate_func: str = "smooth"

    def __getattr__(self, name: str) -> Any:  # noqa: ANN401
        """Delegate a transform/style method to the clone, returning self."""
        if name in AnimateBuilder._DELEGATED:
            method = getattr(self._clone, name)

            def _invoke(*args: Any, **kwargs: Any) -> AnimateBuilder:  # noqa: ANN401
                method(*args, **kwargs)
                return self

            return _invoke
        raise AttributeError(name)

    def set_run_time(self, run_time: float) -> AnimateBuilder:
        """Set the tween duration (seconds)."""
        self._run_time = run_time
        return self

    def set_rate(self, rate_func: str) -> AnimateBuilder:
        """Set the easing name (e.g. ``'smooth'``, ``'linear'``)."""
        self._rate_func = rate_func
        return self

    @property
    def target(self) -> Graphic:
        """The captured end-state graphic (clone)."""
        return self._clone

    def build(self) -> Animation:
        """Build the :class:`~archmotion.animation.base.Animation` (lazy import)."""
        from archmotion.animation.base import StateTween

        return StateTween(
            self._source,
            self._clone,
            run_time=self._run_time,
            rate_func=self._rate_func,
        )


def _union_boxes(boxes: Iterable[BoundingBox]) -> BoundingBox:
    """Compute the union bounding box of an iterable of boxes."""
    xs0: list[float] = []
    ys0: list[float] = []
    xs1: list[float] = []
    ys1: list[float] = []
    for b in boxes:
        xs0.append(b.x)
        ys0.append(b.y)
        xs1.append(b.x + b.width)
        ys1.append(b.y + b.height)
    x = min(xs0)
    y = min(ys0)
    x1 = max(xs1)
    y1 = max(ys1)
    return BoundingBox(x, y, max(0.0, x1 - x), max(0.0, y1 - y))
