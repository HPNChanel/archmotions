"""Timeline Compiler -- converts play() calls into ScheduledActions.

Architectural Note:
    Phase 3 receives the list of play_call dicts from Scene and decomposes
    each high-level animation (FadeIn, Transfer, Pulse) into atomic
    ScheduledActions with absolute timestamps.

    Decomposition rules:
        FadeIn   -> OPACITY 0.0 -> 1.0 (per target)
        FadeOut  -> OPACITY 1.0 -> 0.0 (per target)
        Transfer -> PATH_PROGRESS 0.0 -> 1.0 (on a virtual packet ID)
        Pulse    -> GLOW_INTENSITY 0.0 -> peak -> 0.0 (2 actions: ramp up + down)

    Output: CompiledTimeline with sorted actions and total frame count.

    Complexity: O(P * T) where P = play_calls, T = avg targets per animation.
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field

from archmotion._types import AnimatableProperty, EasingType
from archmotion.api.connections import Connection
from archmotion.api.primitives import Node
from archmotion.motions._animations import (
    ColorShift,
    FadeIn,
    FadeOut,
    Highlight,
    Pulse,
    ScaleDown,
    ScaleUp,
    Transfer,
    _parse_hex_color,
)
from archmotion.timeline.actions import ScheduledAction


# ──────────────────────────────────────────────
# Output Data Structure
# ──────────────────────────────────────────────


@dataclass(frozen=True)
class TransferMeta:
    """Metadata for a Transfer animation (packet rendering info).

    The Renderer needs this to know which connection path to draw the
    packet on, what label to display, and what color to use.

    Attributes:
        packet_id: Unique ID for the virtual packet scene object.
        connection_ids: Ordered list of Connection IDs the packet traverses.
        payload: Text label on the packet.
        reverse: Whether the packet travels in reverse direction.
        packet_color: Override color for the packet (None = theme default).
    """

    packet_id: str
    connection_ids: tuple[str, ...]
    payload: str
    reverse: bool
    packet_color: str | None


@dataclass(frozen=True)
class CompiledTimeline:
    """Output of Phase 3: all animations decomposed into atomic actions.

    Attributes:
        actions: All ScheduledActions sorted by start_time.
        total_duration: Total timeline duration in seconds.
        total_frames: Total frame count (ceil(duration * fps)).
        fps: Frames per second.
        transfer_metas: Metadata for Transfer animations (for Renderer).
    """

    actions: tuple[ScheduledAction, ...]
    total_duration: float
    total_frames: int
    fps: int
    transfer_metas: tuple[TransferMeta, ...] = ()

    def actions_at(self, frame_index: int) -> list[ScheduledAction]:
        """Get all actions active at a specific frame -- O(A) scan.

        Args:
            frame_index: Zero-based frame index.

        Returns:
            List of ScheduledActions active at this frame's timestamp.
        """
        if frame_index < 0 or frame_index >= self.total_frames:
            return []

        current_time = frame_index / self.fps
        return [a for a in self.actions if a.is_active_at(current_time)]

    def snapshot_at(self, frame_index: int) -> dict[str, dict[AnimatableProperty, float]]:
        """Compute the full property snapshot at a specific frame.

        Returns a dict mapping target_id -> {property -> value}.
        This is what the Renderer uses to paint each frame.

        Args:
            frame_index: Zero-based frame index.

        Returns:
            Nested dict of target states.
        """
        if frame_index < 0 or frame_index >= self.total_frames:
            return {}

        current_time = frame_index / self.fps
        snapshot: dict[str, dict[AnimatableProperty, float]] = {}

        for action in self.actions:
            if action.is_active_at(current_time):
                target = snapshot.setdefault(action.target_id, {})
                target[action.prop] = action.value_at(current_time)

        return snapshot


# ──────────────────────────────────────────────
# Type alias for play_call dict
# ──────────────────────────────────────────────

PlayCall = dict[str, object]
"""A dict with keys: 'animation', 'start_time', 'duration'."""

Animation = FadeIn | FadeOut | Transfer | Pulse | Highlight | ColorShift | ScaleUp | ScaleDown
"""Union of all supported animation types."""


# ──────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────


def compile_timeline(
    play_calls: list[PlayCall],
    total_duration: float,
    fps: int,
) -> CompiledTimeline:
    """Compile play_calls into a CompiledTimeline.

    This is the main entry point for Phase 3 of the pipeline.

    Args:
        play_calls: List of dicts from Scene._play_calls.
        total_duration: Total timeline duration from Scene.total_duration.
        fps: Frame rate from Scene.fps.

    Returns:
        CompiledTimeline with decomposed ScheduledActions.
    """
    all_actions: list[ScheduledAction] = []
    all_transfer_metas: list[TransferMeta] = []

    for call in play_calls:
        animation = call["animation"]
        start_time = float(call["start_time"])  # type: ignore[arg-type]
        duration = float(call["duration"])  # type: ignore[arg-type]

        actions, metas = _decompose(animation, start_time, duration)
        all_actions.extend(actions)
        all_transfer_metas.extend(metas)

    # Sort by start_time, then by target_id for deterministic ordering
    all_actions.sort(key=lambda a: (a.start_time, a.target_id))

    total_frames = max(1, math.ceil(total_duration * fps))

    return CompiledTimeline(
        actions=tuple(all_actions),
        total_duration=total_duration,
        total_frames=total_frames,
        fps=fps,
        transfer_metas=tuple(all_transfer_metas),
    )


# ──────────────────────────────────────────────
# Decomposition Dispatcher
# ──────────────────────────────────────────────


def _decompose(
    animation: object,
    start_time: float,
    duration: float,
) -> tuple[list[ScheduledAction], list[TransferMeta]]:
    """Dispatch animation to the correct decomposition function.

    Returns:
        Tuple of (actions, transfer_metas).
    """
    if isinstance(animation, FadeIn):
        return _decompose_fade_in(animation, start_time, duration), []
    if isinstance(animation, FadeOut):
        return _decompose_fade_out(animation, start_time, duration), []
    if isinstance(animation, Transfer):
        return _decompose_transfer(animation, start_time, duration)
    if isinstance(animation, Pulse):
        return _decompose_pulse(animation, start_time, duration), []
    if isinstance(animation, Highlight):
        return _decompose_highlight(animation, start_time, duration), []
    if isinstance(animation, ColorShift):
        return _decompose_colorshift(animation, start_time, duration), []
    if isinstance(animation, (ScaleUp, ScaleDown)):
        return _decompose_scale(animation, start_time, duration), []

    msg = f"Unknown animation type: {type(animation).__name__}"
    raise TypeError(msg)


# ──────────────────────────────────────────────
# FadeIn Decomposition
# ──────────────────────────────────────────────


def _decompose_fade_in(
    anim: FadeIn,
    start_time: float,
    duration: float,
) -> list[ScheduledAction]:
    """FadeIn -> OPACITY 0.0 -> 1.0 for each target.

    Each target gets its own ScheduledAction so they can be
    individually evaluated by the Renderer.
    """
    end_time = start_time + duration
    actions: list[ScheduledAction] = []

    for target in anim.targets:
        actions.append(
            ScheduledAction(
                target_id=target.id,
                prop=AnimatableProperty.OPACITY,
                start_time=start_time,
                end_time=end_time,
                start_value=0.0,
                end_value=1.0,
                easing=anim.easing,
            )
        )

    return actions


# ──────────────────────────────────────────────
# FadeOut Decomposition
# ──────────────────────────────────────────────


def _decompose_fade_out(
    anim: FadeOut,
    start_time: float,
    duration: float,
) -> list[ScheduledAction]:
    """FadeOut -> OPACITY 1.0 -> 0.0 for each target."""
    end_time = start_time + duration
    actions: list[ScheduledAction] = []

    for target in anim.targets:
        actions.append(
            ScheduledAction(
                target_id=target.id,
                prop=AnimatableProperty.OPACITY,
                start_time=start_time,
                end_time=end_time,
                start_value=1.0,
                end_value=0.0,
                easing=anim.easing,
            )
        )

    return actions


# ──────────────────────────────────────────────
# Transfer Decomposition
# ──────────────────────────────────────────────


def _decompose_transfer(
    anim: Transfer,
    start_time: float,
    duration: float,
) -> tuple[list[ScheduledAction], list[TransferMeta]]:
    """Transfer -> PATH_PROGRESS 0.0 -> 1.0 on a virtual packet.

    A unique packet_id is generated. The Renderer uses TransferMeta
    to find the connection path and draw the packet at the correct
    interpolated position along that path.
    """
    end_time = start_time + duration
    packet_id = f"packet_{uuid.uuid4().hex[:8]}"

    # Collect connection IDs
    if isinstance(anim.connection, list):
        conn_ids = tuple(c.id for c in anim.connection)
    else:
        conn_ids = (anim.connection.id,)

    # PATH_PROGRESS: 0.0 -> 1.0 (or 1.0 -> 0.0 if reverse)
    start_val = 1.0 if anim.reverse else 0.0
    end_val = 0.0 if anim.reverse else 1.0

    action = ScheduledAction(
        target_id=packet_id,
        prop=AnimatableProperty.PATH_PROGRESS,
        start_time=start_time,
        end_time=end_time,
        start_value=start_val,
        end_value=end_val,
        easing=anim.easing,
    )

    meta = TransferMeta(
        packet_id=packet_id,
        connection_ids=conn_ids,
        payload=anim.payload,
        reverse=anim.reverse,
        packet_color=anim.packet_color,
    )

    return [action], [meta]


# ──────────────────────────────────────────────
# Pulse Decomposition
# ──────────────────────────────────────────────


def _decompose_pulse(
    anim: Pulse,
    start_time: float,
    duration: float,
) -> list[ScheduledAction]:
    """Pulse -> GLOW_INTENSITY ramp up then down.

    Split into 2 half-duration actions:
        1. 0.0 -> intensity (first half, ease_in)
        2. intensity -> 0.0 (second half, ease_out)
    """
    mid_time = start_time + duration / 2
    end_time = start_time + duration

    ramp_up = ScheduledAction(
        target_id=anim.target.id,
        prop=AnimatableProperty.GLOW_INTENSITY,
        start_time=start_time,
        end_time=mid_time,
        start_value=0.0,
        end_value=anim.intensity,
        easing=EasingType.EASE_IN,
    )

    ramp_down = ScheduledAction(
        target_id=anim.target.id,
        prop=AnimatableProperty.GLOW_INTENSITY,
        start_time=mid_time,
        end_time=end_time,
        start_value=anim.intensity,
        end_value=0.0,
        easing=EasingType.EASE_OUT,
    )

    return [ramp_up, ramp_down]


# ──────────────────────────────────────────────
# Highlight Decomposition
# ──────────────────────────────────────────────


def _decompose_highlight(
    anim: Highlight,
    start_time: float,
    duration: float,
) -> list[ScheduledAction]:
    """Highlight -> GLOW_INTENSITY 0.0 -> intensity (ramp up, then hold).

    Unlike Pulse (which fades back), Highlight holds at peak intensity
    for the entire duration. We split into:
        1. Quick ramp up (first 15% of duration)
        2. Hold at peak (remaining 85% of duration)
    """
    ramp_end = start_time + duration * 0.15
    end_time = start_time + duration

    # Quick ramp up
    ramp_up = ScheduledAction(
        target_id=anim.target.id,
        prop=AnimatableProperty.GLOW_INTENSITY,
        start_time=start_time,
        end_time=ramp_end,
        start_value=0.0,
        end_value=anim.intensity,
        easing=anim.easing,
    )

    # Hold at peak intensity
    hold = ScheduledAction(
        target_id=anim.target.id,
        prop=AnimatableProperty.GLOW_INTENSITY,
        start_time=ramp_end,
        end_time=end_time,
        start_value=anim.intensity,
        end_value=anim.intensity,
        easing=EasingType.LINEAR,
    )

    return [ramp_up, hold]


# ──────────────────────────────────────────────
# ColorShift Decomposition
# ──────────────────────────────────────────────


def _decompose_colorshift(
    anim: ColorShift,
    start_time: float,
    duration: float,
) -> list[ScheduledAction]:
    """ColorShift -> 3 actions for COLOR_R, COLOR_G, COLOR_B.

    Each channel is interpolated independently from from_color to to_color.
    """
    end_time = start_time + duration
    from_rgb = _parse_hex_color(anim.from_color)
    to_rgb = _parse_hex_color(anim.to_color)

    actions: list[ScheduledAction] = []
    channels = (
        (AnimatableProperty.COLOR_R, from_rgb[0], to_rgb[0]),
        (AnimatableProperty.COLOR_G, from_rgb[1], to_rgb[1]),
        (AnimatableProperty.COLOR_B, from_rgb[2], to_rgb[2]),
    )

    for prop, start_val, end_val in channels:
        actions.append(
            ScheduledAction(
                target_id=anim.target.id,
                prop=prop,
                start_time=start_time,
                end_time=end_time,
                start_value=start_val,
                end_value=end_val,
                easing=anim.easing,
            )
        )

    return actions


# ──────────────────────────────────────────────
# Scale Decomposition (shared by ScaleUp / ScaleDown)
# ──────────────────────────────────────────────


def _decompose_scale(
    anim: ScaleUp | ScaleDown,
    start_time: float,
    duration: float,
) -> list[ScheduledAction]:
    """ScaleUp/ScaleDown -> SCALE 1.0 -> factor."""
    end_time = start_time + duration

    return [
        ScheduledAction(
            target_id=anim.target.id,
            prop=AnimatableProperty.SCALE,
            start_time=start_time,
            end_time=end_time,
            start_value=1.0,
            end_value=anim.factor,
            easing=anim.easing,
        )
    ]
