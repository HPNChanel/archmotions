"""Animation base, groups, and the ``.animate`` state-tween (v2.0 core).

Model
-----
Every animation is *compiled* into atomic parametric actions
(:class:`~archmotion.core.property.PropertyAction` /
:class:`~archmotion.core.property.MorphAction`) that the renderer evaluates at
any timestamp — keeping rendering stateless and parallelizable (same as v1.0).

Three hooks:

- ``begin()`` — set the graphic's start state (e.g. opacity 0 for FadeIn),
- ``compile(start_time)`` — emit actions for the timeline,
- ``finish()`` — commit the end state as the new base.

``AnimationGroup`` staggers children by ``lag_ratio`` (0 = parallel, 1 =
sequential). ``StateTween`` powers the ``g.animate.shift(...).set_fill(...)``
builder by morphing world-space points + tweening style/opacity.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

import numpy as np

from archmotion.core import easing
from archmotion.core.property import MorphAction, Property, PropertyAction

if TYPE_CHECKING:
    from collections.abc import Iterable

    from archmotion.core.graphic import Graphic
    from archmotion.core.vmobject import VMobject


class Animation:
    """Base animation. Subclasses implement ``targets``, ``compile``, hooks."""

    def __init__(
        self,
        run_time: float = 1.0,
        rate_func: str = easing.DEFAULT_EASING,
        duration: float | None = None,
    ) -> None:
        """Validate run_time and store the easing name.

        ``duration`` is a v1-compat alias for ``run_time`` (takes precedence if
        given).
        """
        rt = duration if duration is not None else run_time
        if rt <= 0:
            msg = f"run_time must be positive, got {rt}"
            raise ValueError(msg)
        self.run_time = rt
        self.rate_func = rate_func

    def targets(self) -> list[Graphic]:
        """Graphics affected by this animation (for begin/finish)."""
        return []

    def begin(self) -> None:
        """Set start state on targets (called once before the timeline runs)."""

    def compile(self, start_time: float) -> list[PropertyAction | MorphAction]:
        """Emit parametric actions spanning ``[start_time, start_time+run_time]``."""
        return []

    def finish(self) -> None:
        """Commit the end state as the new base (called once after rendering)."""

    @property
    def end_time(self) -> float:
        """Placeholder; actual end depends on the assigned start_time."""
        return self.run_time


def _scalar(
    target_id: str,
    prop: Property,
    start_time: float,
    end_time: float,
    start_value: float,
    end_value: float,
    rate_func: str,
) -> PropertyAction:
    """Build a single scalar PropertyAction."""
    return PropertyAction(
        target_id=target_id,
        prop=prop,
        start_time=start_time,
        end_time=end_time,
        start_value=start_value,
        end_value=end_value,
        easing=rate_func,
    )


class FadeIn(Animation):
    """Fade targets in (opacity 0 → 1)."""

    def __init__(
        self,
        *targets: Graphic,
        run_time: float = 0.5,
        rate_func: str = "ease_out",
        duration: float | None = None,
    ) -> None:
        """Store targets + timing for a fade-in."""
        super().__init__(run_time=run_time, rate_func=rate_func, duration=duration)
        if not targets:
            msg = "FadeIn requires at least one target."
            raise TypeError(msg)
        self._targets = list(targets)

    def targets(self) -> list[Graphic]:
        """The graphics being faded in."""
        return self._targets

    def begin(self) -> None:
        """Hide targets (opacity 0) before the fade begins."""
        for g in self._targets:
            g.opacity = 0.0

    def compile(self, start_time: float) -> list[PropertyAction | MorphAction]:
        """Emit opacity 0 → 1 actions per target."""
        end_time = start_time + self.run_time
        return [
            _scalar(g.id, Property.OPACITY, start_time, end_time, 0.0, 1.0, self.rate_func)
            for g in self._targets
        ]

    def finish(self) -> None:
        """Reveal targets (opacity 1)."""
        for g in self._targets:
            g.opacity = 1.0


class FadeOut(Animation):
    """Fade targets out (opacity 1 → 0)."""

    def __init__(
        self,
        *targets: Graphic,
        run_time: float = 0.5,
        rate_func: str = "ease_in",
        duration: float | None = None,
    ) -> None:
        """Store targets + timing for a fade-out."""
        super().__init__(run_time=run_time, rate_func=rate_func, duration=duration)
        if not targets:
            msg = "FadeOut requires at least one target."
            raise TypeError(msg)
        self._targets = list(targets)

    def targets(self) -> list[Graphic]:
        """The graphics being faded out."""
        return self._targets

    def compile(self, start_time: float) -> list[PropertyAction | MorphAction]:
        """Emit opacity 1 → 0 actions per target."""
        end_time = start_time + self.run_time
        return [
            _scalar(g.id, Property.OPACITY, start_time, end_time, 1.0, 0.0, self.rate_func)
            for g in self._targets
        ]

    def finish(self) -> None:
        """Hide targets (opacity 0)."""
        for g in self._targets:
            g.opacity = 0.0


class Create(Animation):
    """Progressively draw a vector graphic's outline (stroke 0 → 1)."""

    def __init__(
        self,
        target: Graphic,
        run_time: float = 1.0,
        rate_func: str = "smooth",
        duration: float | None = None,
    ) -> None:
        """Store the target + timing for a progressive draw."""
        super().__init__(run_time=run_time, rate_func=rate_func, duration=duration)
        self._target = target

    def targets(self) -> list[Graphic]:
        """The graphic being created."""
        return [self._target]

    def compile(self, start_time: float) -> list[PropertyAction | MorphAction]:
        """Emit a CREATE_PROGRESS 0 → 1 action."""
        end_time = start_time + self.run_time
        return [
            _scalar(
                self._target.id,
                Property.CREATE_PROGRESS,
                start_time,
                end_time,
                0.0,
                1.0,
                self.rate_func,
            )
        ]

    def finish(self) -> None:
        """Mark the target fully drawn (opacity 1)."""
        self._target.opacity = 1.0


class Transform(Animation):
    """Morph ``source`` into ``target`` (point interpolation + color tween).

    After finishing, ``source`` adopts ``target``'s points + style.
    """

    def __init__(
        self,
        source: VMobject,
        target: VMobject,
        run_time: float = 1.0,
        rate_func: str = "smooth",
        duration: float | None = None,
    ) -> None:
        """Store source/target + timing for a point morph."""
        super().__init__(run_time=run_time, rate_func=rate_func, duration=duration)
        self._source = source
        self._target = target
        self._aligned_src: object | None = None
        self._aligned_tgt: object | None = None
        self._contour_starts: tuple[int, ...] = ()

    def targets(self) -> list[Graphic]:
        """The source graphic being morphed."""
        return [self._source]

    def begin(self) -> None:
        """Align source/target point arrays for interpolation."""
        (
            self._aligned_src,
            self._aligned_tgt,
            self._contour_starts,
        ) = self._source.align_with_topology(self._target)

    def compile(self, start_time: float) -> list[PropertyAction | MorphAction]:
        """Emit a MorphAction + color tween."""
        if self._aligned_src is None or self._aligned_tgt is None:
            msg = "Transform.compile called before begin()."
            raise RuntimeError(msg)
        actions: list[PropertyAction | MorphAction] = [
            MorphAction(
                target_id=self._source.id,
                source=self._aligned_src,
                target=self._aligned_tgt,
                start_time=start_time,
                end_time=start_time + self.run_time,
                contour_starts=self._contour_starts,
                easing=self.rate_func,
            )
        ]
        actions.extend(
            _transform_tween(
                self._source,
                self._target,
                start_time,
                self.run_time,
                self.rate_func,
            )
        )
        actions.extend(
            _color_tween(self._source, self._target, start_time, self.run_time, self.rate_func)
        )
        return actions

    def finish(self) -> None:
        """Adopt the target's points + style."""
        if self._aligned_tgt is None:
            msg = "Transform.finish called before begin()."
            raise RuntimeError(msg)
        self._source.set_points_and_contours(self._aligned_tgt, self._contour_starts)
        self._source.transform = self._target.transform
        self._source.style = self._target.style


class StateTween(Animation):
    """Tween a graphic without flattening its scene-graph hierarchy."""

    def __init__(
        self,
        source: Graphic,
        target: Graphic,
        run_time: float | None = None,
        rate_func: str = easing.DEFAULT_EASING,
        duration: float | None = None,
    ) -> None:
        """Store source/target + timing for a state tween."""
        super().__init__(
            run_time=run_time if run_time is not None else 1.0,
            rate_func=rate_func,
            duration=duration,
        )
        self._source = source
        self._target = target
        self._src_points: object | None = None
        self._tgt_points: object | None = None
        self._contour_starts: tuple[int, ...] = ()

    def targets(self) -> list[Graphic]:
        """The source graphic."""
        return [self._source]

    def begin(self) -> None:
        """Align local point topology if both objects are vector graphics."""
        from archmotion.core.vmobject import VMobject

        if isinstance(self._source, VMobject) and isinstance(self._target, VMobject):
            (
                self._src_points,
                self._tgt_points,
                self._contour_starts,
            ) = self._source.align_with_topology(self._target)
        else:
            self._src_points = None
            self._tgt_points = None

    def compile(self, start_time: float) -> list[PropertyAction | MorphAction]:
        """Emit a MorphAction (points) + opacity/color scalar tweens."""
        actions: list[PropertyAction | MorphAction] = []
        end_time = start_time + self.run_time
        if self._src_points is not None and self._tgt_points is not None:
            actions.append(
                MorphAction(
                    target_id=self._source.id,
                    source=self._src_points,
                    target=self._tgt_points,
                    start_time=start_time,
                    end_time=end_time,
                    contour_starts=self._contour_starts,
                    easing=self.rate_func,
                )
            )
        actions.extend(
            _transform_tween(
                self._source,
                self._target,
                start_time,
                self.run_time,
                self.rate_func,
            )
        )
        actions.append(
            _scalar(
                self._source.id,
                Property.OPACITY,
                start_time,
                end_time,
                self._source.opacity,
                self._target.opacity,
                self.rate_func,
            )
        )
        actions.extend(
            _color_tween(self._source, self._target, start_time, self.run_time, self.rate_func)
        )
        return actions

    def finish(self) -> None:
        """Adopt the target's local points, transform, opacity and style."""
        from archmotion.core.vmobject import VMobject

        if self._tgt_points is not None and isinstance(self._source, VMobject):
            self._source.set_points_and_contours(self._tgt_points, self._contour_starts)
        self._source.transform = self._target.transform
        self._source.opacity = self._target.opacity
        self._source.style = self._target.style


class Write(Create):
    """Progressively reveal a text/code/math graphic's glyph outlines.

    Uses ``CREATE_PROGRESS`` path-trimming — the outline is drawn continuously,
    revealing glyphs in reading order. Semantically equivalent to
    :class:`Create` but documented for text/code/math reveal.

    For a true per-glyph typewriter effect, split the text into per-character
    ``Text`` VMobjects and stagger them in an :class:`AnimationGroup`.
    """

    def __init__(
        self,
        target: Graphic,
        run_time: float = 1.0,
        rate_func: str = "smooth",
        duration: float | None = None,
    ) -> None:
        """Store the target + timing for a progressive text reveal."""
        super().__init__(target, run_time=run_time, rate_func=rate_func, duration=duration)


class Uncreate(Animation):
    """Reverse of :class:`Create` — progressively erase a graphic's outline (1 → 0)."""

    def __init__(
        self,
        target: Graphic,
        run_time: float = 1.0,
        rate_func: str = "smooth",
        duration: float | None = None,
    ) -> None:
        """Store the target + timing for a progressive erase."""
        super().__init__(run_time=run_time, rate_func=rate_func, duration=duration)
        self._target = target

    def targets(self) -> list[Graphic]:
        """The graphic being erased."""
        return [self._target]

    def compile(self, start_time: float) -> list[PropertyAction | MorphAction]:
        """Emit a CREATE_PROGRESS 1 → 0 action."""
        end_time = start_time + self.run_time
        return [
            _scalar(
                self._target.id,
                Property.CREATE_PROGRESS,
                start_time,
                end_time,
                1.0,
                0.0,
                self.rate_func,
            )
        ]

    def finish(self) -> None:
        """Hide the target (opacity 0)."""
        self._target.opacity = 0.0


class DrawBorderThenFill(Animation):
    """Draw the stroke outline first, then fill the interior.

    Phase 1 (first half): ``CREATE_PROGRESS`` 0 → 1 (stroke draws progressively).
    Phase 2 (second half): ``FILL_OPACITY`` 0 → original (fill fades in).
    """

    def __init__(
        self,
        target: Graphic,
        run_time: float = 1.0,
        rate_func: str = "smooth",
        duration: float | None = None,
    ) -> None:
        """Store the target + timing for a border-then-fill reveal."""
        super().__init__(run_time=run_time, rate_func=rate_func, duration=duration)
        self._target = target
        self._orig_fill_opacity: float = 1.0

    def targets(self) -> list[Graphic]:
        """The graphic being revealed."""
        return [self._target]

    def begin(self) -> None:
        """Capture the target's original fill opacity; suppress fill for phase 1."""
        self._orig_fill_opacity = self._target.style.fill_opacity

    def compile(self, start_time: float) -> list[PropertyAction | MorphAction]:
        """Emit a two-phase action sequence: stroke then fill."""
        half = start_time + self.run_time / 2
        end_time = start_time + self.run_time
        return [
            _scalar(
                self._target.id,
                Property.CREATE_PROGRESS,
                start_time,
                half,
                0.0,
                1.0,
                self.rate_func,
            ),
            _scalar(
                self._target.id,
                Property.FILL_OPACITY,
                half,
                end_time,
                0.0,
                self._orig_fill_opacity,
                self.rate_func,
            ),
        ]

    def finish(self) -> None:
        """Restore the fill opacity."""
        self._target.opacity = 1.0


class Typewriter(Write):
    """Approximate per-glyph typewriter reveal.

    Uses ``CREATE_PROGRESS`` path-trimming with a linear (constant-speed) rate
    that approximates discrete glyph reveal. Not a true per-glyph effect (path
    trimming sweeps continuously); for exact per-glyph, split text manually.
    """

    def __init__(
        self,
        target: Graphic,
        run_time: float = 1.0,
        duration: float | None = None,
    ) -> None:
        """Store the target + timing for a typewriter-style reveal."""
        super().__init__(target, run_time=run_time, rate_func="linear", duration=duration)


class ReplacementTransform(Transform):
    """Like :class:`Transform` but commits the target's original points at finish.

    The morph itself uses aligned (resampled) points for smoothness, but after
    finishing, the source adopts the target's **original** (non-resampled)
    point array — so the final shape is exact, not an interpolation artifact.
    """

    def finish(self) -> None:
        """Commit the target's original points + style (not aligned/resampled)."""
        self._source.set_points_and_contours(
            self._target.points,
            self._target.contour_starts,
        )
        self._source.transform = self._target.transform
        self._source.style = self._target.style


class GrowFromCenter(Animation):
    """Scale a target from 0 to its full size, centered (scale + opacity 0 → 1)."""

    def __init__(
        self,
        target: Graphic,
        run_time: float = 1.0,
        rate_func: str = "smooth",
        duration: float | None = None,
    ) -> None:
        """Store the target + timing for a centered grow-in."""
        super().__init__(run_time=run_time, rate_func=rate_func, duration=duration)
        self._target = target

    def targets(self) -> list[Graphic]:
        """The target being grown."""
        return [self._target]

    def compile(self, start_time: float) -> list[PropertyAction | MorphAction]:
        """Emit SCALE 0 → 1 + OPACITY 0 → 1 actions."""
        end_time = start_time + self.run_time
        return [
            _scalar(
                self._target.id, Property.SCALE, start_time, end_time, 0.0, 1.0, self.rate_func
            ),
            _scalar(
                self._target.id, Property.OPACITY, start_time, end_time, 0.0, 1.0, self.rate_func
            ),
        ]

    def finish(self) -> None:
        """Restore opacity to 1.0."""
        self._target.opacity = 1.0


class GrowFromEdge(Animation):
    """Scale a target from 0 → 1 while keeping the specified edge stationary.

    The centered ``SCALE`` transform grows the graphic from its center; a
    paired ``POSITION_X``/``POSITION_Y`` tween compensates so the chosen edge
    (``"left"``, ``"right"``, ``"top"``, ``"bottom"``) stays fixed.
    """

    _EDGES = ("left", "right", "top", "bottom")

    def __init__(
        self,
        target: Graphic,
        edge: str = "bottom",
        run_time: float = 1.0,
        rate_func: str = "smooth",
        duration: float | None = None,
    ) -> None:
        """Store the target + edge + timing for an anchored grow-in."""
        super().__init__(run_time=run_time, rate_func=rate_func, duration=duration)
        if edge not in self._EDGES:
            msg = f"edge must be one of {self._EDGES}, got '{edge}'"
            raise ValueError(msg)
        self._target = target
        self._edge = edge
        self._pos_start: tuple[float | None, float | None] = (None, None)
        self._pos_end: tuple[float, float] = (0.0, 0.0)

    def targets(self) -> list[Graphic]:
        """The target being grown."""
        return [self._target]

    def begin(self) -> None:
        """Compute the position offset that keeps the edge fixed at scale 0."""
        from archmotion.core.vmobject import VMobject

        if not isinstance(self._target, VMobject):
            self._pos_start = (None, None)
            return
        bbox = self._target.bounding_box()
        cx, cy = bbox.center
        edge_map = {
            "left": (bbox.x, None),
            "right": (bbox.x + bbox.width, None),
            "top": (None, bbox.y),
            "bottom": (None, bbox.y + bbox.height),
        }
        self._pos_start = edge_map[self._edge]
        self._pos_end = (cx, cy)

    def compile(self, start_time: float) -> list[PropertyAction | MorphAction]:
        """Emit SCALE + OPACITY + POSITION tweens."""
        end_time = start_time + self.run_time
        actions: list[PropertyAction | MorphAction] = [
            _scalar(
                self._target.id, Property.SCALE, start_time, end_time, 0.0, 1.0, self.rate_func
            ),
            _scalar(
                self._target.id, Property.OPACITY, start_time, end_time, 0.0, 1.0, self.rate_func
            ),
        ]
        if self._pos_start[0] is not None:
            actions.append(
                _scalar(
                    self._target.id,
                    Property.POSITION_X,
                    start_time,
                    end_time,
                    self._pos_start[0],
                    self._pos_end[0],
                    self.rate_func,
                )
            )
        if self._pos_start[1] is not None:
            actions.append(
                _scalar(
                    self._target.id,
                    Property.POSITION_Y,
                    start_time,
                    end_time,
                    self._pos_start[1],
                    self._pos_end[1],
                    self.rate_func,
                )
            )
        return actions

    def finish(self) -> None:
        """Restore opacity to 1.0."""
        self._target.opacity = 1.0


class GrowBar(Animation):
    """Grow a bar (``Rectangle`` / chart bar) from zero height to full.

    Uses a :class:`~archmotion.core.property.MorphAction` from a collapsed
    (zero-height) point variant to the bar's full points — the bottom edge stays
    fixed while the top rises.
    """

    def __init__(
        self,
        target: Graphic,
        run_time: float = 1.0,
        rate_func: str = "smooth",
        duration: float | None = None,
    ) -> None:
        """Store the target + timing for a vertical bar grow."""
        super().__init__(run_time=run_time, rate_func=rate_func, duration=duration)
        self._target = target
        self._full_points: object | None = None
        self._zero_points: object | None = None

    def targets(self) -> list[Graphic]:
        """The bar being grown."""
        return [self._target]

    def begin(self) -> None:
        """Capture full-height points and build a zero-height variant."""
        from archmotion.core.vmobject import VMobject

        if not isinstance(self._target, VMobject):
            return
        pts = self._target.points
        self._full_points = pts
        ys = pts[:, 1]
        # ArchMotion uses a y-down canvas, so the visual bottom is max(Y).
        bottom_y = float(ys.max())
        # Collapse all Y to the bottom; X stays the same.
        collapsed = pts.copy()
        collapsed[:, 1] = bottom_y
        self._zero_points = collapsed

    def compile(self, start_time: float) -> list[PropertyAction | MorphAction]:
        """Emit a MorphAction from zero-height to full-height points."""
        if self._zero_points is None or self._full_points is None:
            msg = "GrowBar.compile called before begin() or on a non-VMobject target."
            raise RuntimeError(msg)
        end_time = start_time + self.run_time
        return [
            MorphAction(
                target_id=self._target.id,
                source=self._zero_points,
                target=self._full_points,
                start_time=start_time,
                end_time=end_time,
                easing=self.rate_func,
            )
        ]

    def finish(self) -> None:
        """Commit the full-height points."""
        from archmotion.core.vmobject import VMobject

        if self._full_points is not None and isinstance(self._target, VMobject):
            self._target.points = self._full_points


def _parse_hex(color: str | None) -> tuple[float, float, float] | None:
    """Parse a supported color to (R, G, B) floats; preserve ``None``."""
    if color is None:
        return None
    from archmotion.core.color import color_to_rgb01

    return color_to_rgb01(color)


def _color_tween(
    source: Graphic,
    target: Graphic,
    start_time: float,
    run_time: float,
    rate_func: str,
) -> Iterable[PropertyAction]:
    """Emit fill-RGB scalar tweens when source/target fill colors differ."""
    end_time = start_time + run_time
    actions: list[PropertyAction] = []
    src_fill = _parse_hex(source.style.fill_color)
    tgt_fill = _parse_hex(target.style.fill_color)
    if src_fill and tgt_fill and src_fill != tgt_fill:
        for prop, sv, tv in (
            (Property.FILL_R, src_fill[0], tgt_fill[0]),
            (Property.FILL_G, src_fill[1], tgt_fill[1]),
            (Property.FILL_B, src_fill[2], tgt_fill[2]),
        ):
            actions.append(_scalar(source.id, prop, start_time, end_time, sv, tv, rate_func))
    return actions


_TRANSFORM_PROPERTIES = (
    Property.TRANSFORM_A,
    Property.TRANSFORM_B,
    Property.TRANSFORM_C,
    Property.TRANSFORM_D,
    Property.TRANSFORM_TX,
    Property.TRANSFORM_TY,
)


def _transform_values(graphic: Graphic) -> tuple[float, ...]:
    """Flatten a local affine matrix into the six renderable components."""
    matrix = np.asarray(graphic.transform.matrix, dtype=np.float64)
    return (
        float(matrix[0, 0]),
        float(matrix[1, 0]),
        float(matrix[0, 1]),
        float(matrix[1, 1]),
        float(matrix[0, 2]),
        float(matrix[1, 2]),
    )


def _transform_tween(
    source: Graphic,
    target: Graphic,
    start_time: float,
    run_time: float,
    rate_func: str,
) -> list[PropertyAction]:
    """Emit a complete local-affine tween, including unchanged components."""
    end_time = start_time + run_time
    source_values = _transform_values(source)
    target_values = _transform_values(target)
    return [
        _scalar(source.id, prop, start_time, end_time, start, end, rate_func)
        for prop, start, end in zip(
            _TRANSFORM_PROPERTIES,
            source_values,
            target_values,
            strict=True,
        )
    ]


class AnimationGroup(Animation):
    """Play multiple animations, staggered by ``lag_ratio``.

    ``lag_ratio`` = 0 → fully parallel; 1 → fully sequential.
    """

    def __init__(
        self,
        *animations: Animation,
        lag_ratio: float = 0.0,
        run_time: float | None = None,
        rate_func: str = easing.DEFAULT_EASING,
        duration: float | None = None,
    ) -> None:
        """Store children + stagger; compute total run_time if not given."""
        if not animations:
            msg = "AnimationGroup requires at least one animation."
            raise TypeError(msg)
        if lag_ratio < 0:
            raise ValueError(f"lag_ratio must be non-negative, got {lag_ratio}")
        self._anims = list(animations)
        self._lag_ratio = lag_ratio
        self._natural_duration = self._compute_duration()
        requested = duration if duration is not None else run_time
        super().__init__(
            run_time=requested if requested is not None else self._natural_duration,
            rate_func=rate_func,
        )

    def _compute_duration(self) -> float:
        """Total group duration from child run_times + stagger."""
        if not self._anims:
            return 0.0
        cursor = 0.0
        end = 0.0
        for animation in self._anims:
            end = max(end, cursor + animation.run_time)
            cursor += self._lag_ratio * animation.run_time
        return end

    def targets(self) -> list[Graphic]:
        """All child targets."""
        out: list[Graphic] = []
        for a in self._anims:
            out.extend(a.targets())
        return out

    def begin(self) -> None:
        """Begin every child."""
        for a in self._anims:
            a.begin()

    def compile(self, start_time: float) -> list[PropertyAction | MorphAction]:
        """Compile children at staggered start times."""
        actions: list[PropertyAction | MorphAction] = []
        cursor = 0.0
        scale = self.run_time / self._natural_duration
        for a in self._anims:
            for action in a.compile(cursor):
                actions.append(_retime_action(action, start_time, scale))
            cursor += self._lag_ratio * a.run_time
        return actions

    def finish(self) -> None:
        """Finish every child."""
        for a in self._anims:
            a.finish()


class Succession(AnimationGroup):
    """Play child animations one after another."""

    def __init__(self, *animations: Animation, run_time: float | None = None) -> None:
        """Create a sequential animation composition."""
        super().__init__(*animations, lag_ratio=1.0, run_time=run_time)


class LaggedStart(AnimationGroup):
    """Play child animations with a configurable stagger."""

    def __init__(
        self,
        *animations: Animation,
        lag_ratio: float = 0.1,
        run_time: float | None = None,
    ) -> None:
        """Create a staggered animation composition."""
        super().__init__(*animations, lag_ratio=lag_ratio, run_time=run_time)


def _retime_action(
    action: PropertyAction | MorphAction,
    group_start: float,
    scale: float,
) -> PropertyAction | MorphAction:
    """Scale an action's local schedule into its parent group schedule."""
    return replace(
        action,
        start_time=group_start + action.start_time * scale,
        end_time=group_start + action.end_time * scale,
    )
