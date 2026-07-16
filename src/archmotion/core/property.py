"""Property model + parametric timeline (v2.0 core).

Animations compile into atomic actions that the renderer evaluates at any
timestamp in O(1) — the same parametric model as v1.0's ``ScheduledAction``,
generalized to:

- a richer :class:`Property` enum (fill/stroke/transform/glow/path/create), and
- :class:`MorphAction` for whole-point-array morphing (cross-domain Transform).

A :class:`CompiledTimeline` is pure data: ``(property_actions, morph_actions,
total_duration, fps)``. ``snapshot_at(frame)`` returns the resolved per-target
state with zero knowledge of how it was produced.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING

import numpy as np

from archmotion.core import easing

if TYPE_CHECKING:
    from numpy.typing import NDArray


class Property(Enum):
    """Scalar visual properties that can be tweened over time."""

    OPACITY = auto()
    SCALE = auto()
    ROTATION = auto()
    POSITION_X = auto()
    POSITION_Y = auto()
    FILL_R = auto()
    FILL_G = auto()
    FILL_B = auto()
    FILL_OPACITY = auto()
    STROKE_R = auto()
    STROKE_G = auto()
    STROKE_B = auto()
    STROKE_WIDTH = auto()
    STROKE_OPACITY = auto()
    GLOW_INTENSITY = auto()
    GLOW_BLUR = auto()
    PATH_PROGRESS = auto()
    CREATE_PROGRESS = auto()
    # Full local affine transform components.  These are emitted by
    # ``graphic.animate`` so nested groups can be evaluated without baking
    # world-space points or destroying the scene hierarchy.
    TRANSFORM_A = auto()
    TRANSFORM_B = auto()
    TRANSFORM_C = auto()
    TRANSFORM_D = auto()
    TRANSFORM_TX = auto()
    TRANSFORM_TY = auto()
    VALUE = auto()


@dataclass(frozen=True)
class PropertyAction:
    """A scalar property tween over a time interval.

    Attributes:
        target_id: ID of the graphic being animated.
        prop: Which scalar property changes.
        start_time / end_time: Interval (seconds from timeline origin).
        start_value / end_value: Property value at the interval endpoints.
        easing: Easing function name.
    """

    target_id: str
    prop: Property
    start_time: float
    end_time: float
    start_value: float
    end_value: float
    easing: str = easing.DEFAULT_EASING

    @property
    def duration(self) -> float:
        """Interval length in seconds."""
        return self.end_time - self.start_time

    def is_active_at(self, t: float) -> bool:
        """Whether this action is active at timestamp ``t``."""
        return self.start_time <= t <= self.end_time

    def value_at(self, t: float) -> float:
        """Interpolated value at ``t`` (clamped outside the interval)."""
        if t <= self.start_time:
            return self.start_value
        if t >= self.end_time:
            return self.end_value
        progress = (t - self.start_time) / self.duration if self.duration > 0 else 1.0
        eased = easing.apply(progress, self.easing)
        return self.start_value + (self.end_value - self.start_value) * eased


@dataclass(frozen=True, eq=False)
class MorphAction:
    """A whole-point-array morph over a time interval (cross-domain Transform).

    ``source`` and ``target`` must be aligned (same shape). The renderer sets
    the graphic's points to ``lerp(source, target, eased(t))``.

    Attributes:
        target_id: ID of the graphic being morphed.
        source: Starting point array ``(N, 2)``.
        target: Ending point array ``(N, 2)``.
        start_time / end_time: Interval (seconds).
        easing: Easing function name.
    """

    target_id: str
    source: object
    target: object
    start_time: float
    end_time: float
    contour_starts: tuple[int, ...] = ()
    easing: str = easing.DEFAULT_EASING

    @property
    def duration(self) -> float:
        """Interval length in seconds."""
        return self.end_time - self.start_time

    def is_active_at(self, t: float) -> bool:
        """Whether this morph is active at timestamp ``t``."""
        return self.start_time <= t <= self.end_time

    def points_at(self, t: float) -> NDArray[np.float64]:
        """Interpolated point array at ``t``."""
        src = np.asarray(self.source, dtype=np.float64)
        tgt = np.asarray(self.target, dtype=np.float64)
        if t <= self.start_time:
            return src
        if t >= self.end_time:
            return tgt
        progress = (t - self.start_time) / self.duration if self.duration > 0 else 1.0
        eased = easing.apply(progress, self.easing)
        return src + (tgt - src) * eased


@dataclass(frozen=True)
class FrameSnapshot:
    """Resolved per-target state at one timestamp.

    Attributes:
        scalars: ``{target_id: {Property: value}}`` of active scalar actions.
        morphs: ``{target_id: point_array}`` of active point morphs.
    """

    scalars: dict[str, dict[Property, float]] = field(default_factory=dict)
    morphs: dict[str, object] = field(default_factory=dict)
    morph_contours: dict[str, tuple[int, ...]] = field(default_factory=dict)


@dataclass(frozen=True)
class CompiledTimeline:
    """Output of timeline compilation — pure, picklable data.

    Attributes:
        property_actions: All scalar actions.
        morph_actions: All point-morph actions.
        total_duration: Timeline length in seconds.
        fps: Frame rate.
    """

    property_actions: tuple[PropertyAction, ...]
    morph_actions: tuple[MorphAction, ...]
    total_duration: float
    fps: int

    @property
    def total_frames(self) -> int:
        """Total frame count."""
        return max(1, math.ceil(self.total_duration * self.fps))

    def snapshot_at(self, t: float) -> FrameSnapshot:
        """Resolve the full per-target state at timestamp ``t`` (seconds).

        Uses *sticky* semantics: for each ``(target, property)`` the latest
        action that has started at or before ``t`` is authoritative (its
        clamped ``value_at``). Before the first action, the first action's
        ``start_value`` applies — so a ``FadeIn`` keeps a target invisible
        until it begins, and a ``Transform`` shows its source points first.
        Properties/graphics with no actions fall back to the graphic's own
        (authored) fields at render time.
        """
        by_key: dict[tuple[str, Property], list[PropertyAction]] = {}
        for action in self.property_actions:
            by_key.setdefault((action.target_id, action.prop), []).append(action)

        scalars: dict[str, dict[Property, float]] = {}
        for (target_id, prop), acts in by_key.items():
            acts.sort(key=lambda a: a.start_time)
            chosen: PropertyAction | None = None
            for a in acts:
                if a.start_time <= t:
                    chosen = a
                else:
                    break
            value = acts[0].start_value if chosen is None else chosen.value_at(t)
            scalars.setdefault(target_id, {})[prop] = value

        morphs_by_target: dict[str, list[MorphAction]] = {}
        for maction in self.morph_actions:
            morphs_by_target.setdefault(maction.target_id, []).append(maction)

        morphs: dict[str, object] = {}
        morph_contours: dict[str, tuple[int, ...]] = {}
        for target_id, ms in morphs_by_target.items():
            ms.sort(key=lambda m: m.start_time)
            morph_chosen: MorphAction | None = None
            for m in ms:
                if m.start_time <= t:
                    morph_chosen = m
                else:
                    break
            if morph_chosen is None:
                morphs[target_id] = ms[0].source
                morph_contours[target_id] = ms[0].contour_starts
            elif t <= morph_chosen.end_time:
                morphs[target_id] = morph_chosen.points_at(t)
                morph_contours[target_id] = morph_chosen.contour_starts
            else:
                morphs[target_id] = morph_chosen.target
                morph_contours[target_id] = morph_chosen.contour_starts

        return FrameSnapshot(
            scalars=scalars,
            morphs=morphs,
            morph_contours=morph_contours,
        )

    def snapshot_at_frame(self, frame_index: int) -> FrameSnapshot:
        """Resolve state at a frame index."""
        return self.snapshot_at(frame_index / self.fps)
