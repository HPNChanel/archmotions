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

from typing import TYPE_CHECKING

from archmotion.core import easing
from archmotion.core.property import MorphAction, Property, PropertyAction

if TYPE_CHECKING:
    from collections.abc import Iterable

    from archmotion.core.graphic import Graphic
    from archmotion.core.vmobject import VMobject


class Animation:
    """Base animation. Subclasses implement ``targets``, ``compile``, hooks."""

    def __init__(self, run_time: float = 1.0, rate_func: str = easing.DEFAULT_EASING) -> None:
        """Validate run_time and store the easing name."""
        if run_time <= 0:
            msg = f"run_time must be positive, got {run_time}"
            raise ValueError(msg)
        self.run_time = run_time
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
    ) -> None:
        """Store targets + timing for a fade-in."""
        super().__init__(run_time=run_time, rate_func=rate_func)
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
    ) -> None:
        """Store targets + timing for a fade-out."""
        super().__init__(run_time=run_time, rate_func=rate_func)
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

    def __init__(self, target: Graphic, run_time: float = 1.0, rate_func: str = "smooth") -> None:
        """Store the target + timing for a progressive draw."""
        super().__init__(run_time=run_time, rate_func=rate_func)
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
    ) -> None:
        """Store source/target + timing for a point morph."""
        super().__init__(run_time=run_time, rate_func=rate_func)
        self._source = source
        self._target = target
        self._aligned_src: object | None = None
        self._aligned_tgt: object | None = None

    def targets(self) -> list[Graphic]:
        """The source graphic being morphed."""
        return [self._source]

    def begin(self) -> None:
        """Align source/target point arrays for interpolation."""
        self._aligned_src, self._aligned_tgt = self._source.align_with(self._target)

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
                easing=self.rate_func,
            )
        ]
        actions.extend(
            _color_tween(self._source, self._target, start_time, self.run_time, self.rate_func)
        )
        return actions

    def finish(self) -> None:
        """Adopt the target's points + style."""
        if self._aligned_tgt is None:
            msg = "Transform.finish called before begin()."
            raise RuntimeError(msg)
        self._source.points = self._aligned_tgt
        self._source.style = self._target.style


class StateTween(Animation):
    """Tween a graphic from its current state to a captured target state.

    Bakes both transforms into world-space points and morphs them, plus scalar
    tweens for opacity / fill / stroke. After finishing, the source adopts the
    target's world-space points (with identity transform) and style.
    """

    def __init__(
        self,
        source: Graphic,
        target: Graphic,
        run_time: float | None = None,
        rate_func: str = easing.DEFAULT_EASING,
    ) -> None:
        """Store source/target + timing for a state tween."""
        super().__init__(run_time=run_time if run_time is not None else 1.0, rate_func=rate_func)
        self._source = source
        self._target = target
        self._src_world: object | None = None
        self._tgt_world: object | None = None

    def targets(self) -> list[Graphic]:
        """The source graphic."""
        return [self._source]

    def begin(self) -> None:
        """Bake world-space source/target points if both are vector graphics."""
        from archmotion.core.vmobject import VMobject

        if isinstance(self._source, VMobject) and isinstance(self._target, VMobject):
            src, tgt = self._source.align_with(self._target)
            self._src_world = self._source.transform.apply_to_points(src)
            self._tgt_world = self._target.transform.apply_to_points(tgt)
        else:
            self._src_world = None
            self._tgt_world = None

    def compile(self, start_time: float) -> list[PropertyAction | MorphAction]:
        """Emit a MorphAction (points) + opacity/color scalar tweens."""
        actions: list[PropertyAction | MorphAction] = []
        end_time = start_time + self.run_time
        if self._src_world is not None and self._tgt_world is not None:
            actions.append(
                MorphAction(
                    target_id=self._source.id,
                    source=self._src_world,
                    target=self._tgt_world,
                    start_time=start_time,
                    end_time=end_time,
                    easing=self.rate_func,
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
        """Adopt the target's world points, identity transform, opacity + style."""
        from archmotion.core.transform import Transform as AffineTransform
        from archmotion.core.vmobject import VMobject

        if self._tgt_world is not None and isinstance(self._source, VMobject):
            self._source.points = self._tgt_world
            self._source.transform = AffineTransform.identity()
        self._source.opacity = self._target.opacity
        self._source.style = self._target.style


def _parse_hex(color: str | None) -> tuple[float, float, float] | None:
    """Parse a hex color to (R, G, B) floats in [0, 1]; ``None`` if unparseable."""
    if color is None:
        return None
    c = color.lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    if len(c) != 6:
        return (1.0, 1.0, 1.0)
    try:
        return (int(c[0:2], 16) / 255.0, int(c[2:4], 16) / 255.0, int(c[4:6], 16) / 255.0)
    except ValueError:
        return (1.0, 1.0, 1.0)


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
    ) -> None:
        """Store children + stagger; compute total run_time if not given."""
        if not animations:
            msg = "AnimationGroup requires at least one animation."
            raise TypeError(msg)
        self._anims = list(animations)
        self._lag_ratio = lag_ratio
        super().__init__(
            run_time=run_time if run_time is not None else self._compute_duration(),
            rate_func=rate_func,
        )

    def _compute_duration(self) -> float:
        """Total group duration from child run_times + stagger."""
        if not self._anims:
            return 0.0
        last = self._anims[-1]
        stagger = sum(self._lag_ratio * a.run_time for a in self._anims[:-1])
        return stagger + last.run_time

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
        cursor = start_time
        for a in self._anims:
            actions.extend(a.compile(cursor))
            cursor += self._lag_ratio * a.run_time
        return actions

    def finish(self) -> None:
        """Finish every child."""
        for a in self._anims:
            a.finish()
