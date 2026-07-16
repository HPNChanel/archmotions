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
import inspect
import math
import uuid
from typing import TYPE_CHECKING, Any, ClassVar

from archmotion.core.style import Style
from archmotion.core.transform import Transform
from archmotion.layout.bbox import BoundingBox

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

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
        self.opacity: float = _checked_opacity(opacity)
        self._parent: Graphic | None = None
        self._children: list[Graphic] = []
        self._updaters: list[Callable[..., None]] = []

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
        """Attach unique, acyclic children. Returns self for chaining."""
        for child in children:
            if not isinstance(child, Graphic):
                msg = f"Only Graphic instances can be added, got {type(child).__name__}."
                raise TypeError(msg)
            if child is self or self in child.family_members():
                msg = "A Graphic cannot contain itself or one of its ancestors."
                raise ValueError(msg)
            if child in self._children:
                continue
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

    # ── per-frame updaters ───────────────────────────────────────

    def add_updater(self, updater: Callable[..., None], *, call_updater: bool = False) -> Graphic:
        """Run ``updater(graphic[, dt])`` before this graphic is painted."""
        if updater not in self._updaters:
            self._updaters.append(updater)
        if call_updater:
            self._call_updater(updater, 0.0)
        return self

    def remove_updater(self, updater: Callable[..., None]) -> Graphic:
        """Remove one updater if present."""
        if updater in self._updaters:
            self._updaters.remove(updater)
        return self

    def clear_updaters(self, *, recursive: bool = True) -> Graphic:
        """Remove updaters from this graphic and optionally descendants."""
        self._updaters.clear()
        if recursive:
            for child in self._children:
                child.clear_updaters(recursive=True)
        return self

    @property
    def has_updaters(self) -> bool:
        """Whether this graphic or a descendant has a per-frame updater."""
        return bool(self._updaters) or any(child.has_updaters for child in self._children)

    def update(self, dt: float, *, recursive: bool = True) -> Graphic:
        """Apply all registered updater functions."""
        for updater in list(self._updaters):
            self._call_updater(updater, dt)
        if recursive:
            for child in self._children:
                child.update(dt, recursive=True)
        return self

    def _call_updater(self, updater: Callable[..., None], dt: float) -> None:
        """Invoke a one- or two-argument updater without masking its errors."""
        parameters = inspect.signature(updater).parameters.values()
        positional = [
            p for p in parameters if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
        ]
        if len(positional) >= 2:
            updater(self, dt)
        else:
            updater(self)

    # ── fluent transforms ────────────────────────────────────────

    def shift(self, x: float, y: float) -> Graphic:
        """Translate by ``(x, y)``."""
        self._apply_world_transform(Transform.translation(x, y))
        return self

    def family_members(self) -> list[Graphic]:
        """Return ``self`` and all descendants in stable pre-order."""
        out = [self]
        for child in self._children:
            out.extend(child.family_members())
        return out

    def get_family(self) -> list[Graphic]:
        """Compatibility alias for :meth:`family_members`."""
        return self.family_members()

    def ancestors(self) -> list[Graphic]:
        """Return ancestors from the root down to the direct parent."""
        out: list[Graphic] = []
        current = self._parent
        while current is not None:
            out.append(current)
            current = current._parent
        out.reverse()
        return out

    def world_transform(self) -> Transform:
        """Compose every local transform from the scene root to ``self``."""
        result = Transform.identity()
        for graphic in [*self.ancestors(), self]:
            result = result.compose(graphic.transform)
        return result

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
        self._apply_world_transform(back.compose(scaler).compose(to_origin))
        return self

    def rotate(self, angle_deg: float) -> Graphic:
        """Rotate about the bounding-box center."""
        cx, cy = self.bounding_box().center
        to_origin = Transform.translation(-cx, -cy)
        rot = Transform.rotation(angle_deg)
        back = Transform.translation(cx, cy)
        self._apply_world_transform(back.compose(rot).compose(to_origin))
        return self

    def _apply_world_transform(self, delta: Transform) -> None:
        """Apply a canvas-space delta while preserving a nested local matrix."""
        if self._parent is None:
            self.transform = delta.compose(self.transform)
            return
        parent_world = self._parent.world_transform()
        self.transform = (
            parent_world.invert().compose(delta).compose(parent_world).compose(self.transform)
        )

    # ── fluent style ─────────────────────────────────────────────

    def set_opacity(self, opacity: float) -> Graphic:
        """Set overall opacity [0.0, 1.0]."""
        self.opacity = _checked_opacity(opacity)
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

    # ── layout helpers ───────────────────────────────────────────

    def next_to(
        self,
        other: Graphic,
        direction: str = "right",
        buff: float = 20.0,
    ) -> Graphic:
        """Place this graphic next to ``other`` in pixel/design space."""
        mine = self.bounding_box()
        theirs = other.bounding_box()
        if direction == "right":
            return self.move_to(theirs.x + theirs.width + buff + mine.width / 2, theirs.center[1])
        if direction == "left":
            return self.move_to(theirs.x - buff - mine.width / 2, theirs.center[1])
        if direction == "down":
            return self.move_to(theirs.center[0], theirs.y + theirs.height + buff + mine.height / 2)
        if direction == "up":
            return self.move_to(theirs.center[0], theirs.y - buff - mine.height / 2)
        msg = "direction must be one of: right, left, down, up"
        raise ValueError(msg)

    def align_to(self, other: Graphic, edge: str = "left") -> Graphic:
        """Align one bounding-box edge or center axis with ``other``."""
        mine = self.bounding_box()
        theirs = other.bounding_box()
        if edge == "left":
            return self.shift(theirs.x - mine.x, 0.0)
        if edge == "right":
            return self.shift(theirs.x + theirs.width - mine.x - mine.width, 0.0)
        if edge == "top":
            return self.shift(0.0, theirs.y - mine.y)
        if edge == "bottom":
            return self.shift(0.0, theirs.y + theirs.height - mine.y - mine.height)
        if edge == "center_x":
            return self.shift(theirs.center[0] - mine.center[0], 0.0)
        if edge == "center_y":
            return self.shift(0.0, theirs.center[1] - mine.center[1])
        msg = "edge must be left, right, top, bottom, center_x, or center_y"
        raise ValueError(msg)

    def arrange(self, direction: str = "right", buff: float = 20.0) -> Graphic:
        """Arrange direct children sequentially along one axis."""
        if not self._children:
            return self
        for previous, current in zip(self._children, self._children[1:], strict=False):
            current.next_to(previous, direction=direction, buff=buff)
        return self

    def arrange_in_grid(
        self,
        *,
        rows: int | None = None,
        cols: int | None = None,
        buff: float = 20.0,
    ) -> Graphic:
        """Arrange direct children in a compact row-major grid."""
        count = len(self._children)
        if count == 0:
            return self
        if rows is None and cols is None:
            cols = math.ceil(math.sqrt(count))
        if cols is None:
            cols = math.ceil(count / max(1, rows or 1))
        if rows is None:
            rows = math.ceil(count / max(1, cols))
        if rows <= 0 or cols <= 0:
            raise ValueError("rows and cols must be positive")
        widths = [child.bounding_box().width for child in self._children]
        heights = [child.bounding_box().height for child in self._children]
        cell_w = max(widths, default=0.0) + buff
        cell_h = max(heights, default=0.0) + buff
        origin = self._children[0].bounding_box().center
        for index, child in enumerate(self._children):
            row, col = divmod(index, cols)
            child.move_to(origin[0] + col * cell_w, origin[1] + row * cell_h)
        return self

    def to_edge(
        self,
        edge: str,
        *,
        frame_size: tuple[int, int] = (1280, 720),
        buff: float = 20.0,
    ) -> Graphic:
        """Move this graphic to a frame edge while preserving the other axis."""
        bbox = self.bounding_box()
        width, height = frame_size
        if edge == "left":
            return self.shift(buff - bbox.x, 0.0)
        if edge == "right":
            return self.shift(width - buff - bbox.x - bbox.width, 0.0)
        if edge == "top":
            return self.shift(0.0, buff - bbox.y)
        if edge == "bottom":
            return self.shift(0.0, height - buff - bbox.y - bbox.height)
        msg = "edge must be one of: left, right, top, bottom"
        raise ValueError(msg)

    # ── geometry ─────────────────────────────────────────────────

    def bounding_box(self) -> BoundingBox:
        """Axis-aligned bounding box (overridden by VMobject for point data)."""
        if self._children:
            return _union_boxes(c.bounding_box() for c in self._children)
        # Point-less, child-less graphic: a zero box at the transform origin.
        origin = self.world_transform().apply_to_point((0.0, 0.0))
        return BoundingBox(origin[0], origin[1], 0.0, 0.0)

    # ── copy ─────────────────────────────────────────────────────

    def copy(self) -> Graphic:
        """Deep copy (points, style, transform, children) with a fresh id."""
        clone = _copy.copy(self)
        clone.id = uuid.uuid4().hex[:8]
        clone.transform = _copy.copy(self.transform)
        clone.style = self.style  # frozen dataclass — safe to share
        clone._parent = None
        clone._updaters = list(self._updaters)
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
        "shift",
        "move_to",
        "scale",
        "rotate",
        "set_opacity",
        "set_fill",
        "set_stroke",
        "set_color",
        "set_z",
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


def _checked_opacity(value: float) -> float:
    """Validate an opacity instead of silently producing invalid Skia alpha."""
    opacity = float(value)
    if not 0.0 <= opacity <= 1.0:
        raise ValueError(f"opacity must be between 0 and 1, got {value}")
    return opacity
