"""Animation class implementations.

Each animation class validates its parameters at construction time.
The Timeline Compiler decomposes these into atomic ScheduledAction objects.

v0.1.0: FadeIn, FadeOut, Transfer, Pulse
v0.2.0: Highlight, ColorShift, ScaleUp, ScaleDown
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Union

from archmotion._types import EasingType
from archmotion.api.connections import Connection
from archmotion.api.primitives import Node
from archmotion.constants import (
    DEFAULT_COLORSHIFT_DURATION,
    DEFAULT_FADE_DURATION,
    DEFAULT_HIGHLIGHT_DURATION,
    DEFAULT_PULSE_DURATION,
    DEFAULT_PULSE_INTENSITY,
    DEFAULT_SCALE_DURATION,
    DEFAULT_SCALE_FACTOR,
    DEFAULT_TRANSFER_DURATION,
    MAX_DURATION,
    MAX_PAYLOAD_LENGTH,
    MAX_SCALE_FACTOR,
    MIN_DURATION,
    MIN_SCALE_FACTOR,
)
from archmotion.errors import InvalidConnectionError

# Type alias for things that can be animated
Animatable = Union[Node, Connection]


def _validate_duration(duration: float) -> None:
    """Validate animation duration is within bounds."""
    if not MIN_DURATION <= duration <= MAX_DURATION:
        msg = f"Duration must be between {MIN_DURATION} and {MAX_DURATION}, got {duration}"
        raise ValueError(msg)


def _parse_hex_color(hex_color: str) -> tuple[float, float, float]:
    """Parse a hex color string to (R, G, B) floats in [0.0, 1.0].

    Supports '#RRGGBB' and 'RRGGBB' formats.

    Raises:
        ValueError: If the color string is invalid.
    """
    color = hex_color.lstrip("#")
    if len(color) != 6:
        msg = f"Color must be 6-digit hex (e.g. '#ff5733'), got '{hex_color}'"
        raise ValueError(msg)
    try:
        r = int(color[0:2], 16) / 255.0
        g = int(color[2:4], 16) / 255.0
        b = int(color[4:6], 16) / 255.0
    except ValueError:
        msg = f"Invalid hex color: '{hex_color}'"
        raise ValueError(msg) from None
    return (r, g, b)


@dataclass(frozen=True)
class FadeIn:
    """Animation: targets appear (opacity 0 → 1).

    Args:
        *targets: One or more Nodes, Databases, or Connections to fade in.
        duration: Animation duration in seconds.
        easing: Interpolation curve type.

    Raises:
        TypeError: If no targets provided.

    Example:
        >>> scene.play(FadeIn(client, server, conn))
    """

    targets: tuple[Animatable, ...] = field(default=())
    duration: float = DEFAULT_FADE_DURATION
    easing: EasingType = EasingType.EASE_IN_OUT

    def __init__(
        self,
        *targets: Animatable,
        duration: float = DEFAULT_FADE_DURATION,
        easing: EasingType = EasingType.EASE_IN_OUT,
    ) -> None:
        if not targets:
            msg = "FadeIn requires at least 1 target."
            raise TypeError(msg)
        _validate_duration(duration)
        object.__setattr__(self, "targets", targets)
        object.__setattr__(self, "duration", duration)
        object.__setattr__(self, "easing", easing)


@dataclass(frozen=True)
class FadeOut:
    """Animation: targets disappear (opacity 1 → 0).

    Args:
        *targets: One or more Nodes, Databases, or Connections to fade out.
        duration: Animation duration in seconds.
        easing: Interpolation curve type.

    Raises:
        TypeError: If no targets provided.

    Example:
        >>> scene.play(FadeOut(old_service))
    """

    targets: tuple[Animatable, ...] = field(default=())
    duration: float = DEFAULT_FADE_DURATION
    easing: EasingType = EasingType.EASE_IN_OUT

    def __init__(
        self,
        *targets: Animatable,
        duration: float = DEFAULT_FADE_DURATION,
        easing: EasingType = EasingType.EASE_IN_OUT,
    ) -> None:
        if not targets:
            msg = "FadeOut requires at least 1 target."
            raise TypeError(msg)
        _validate_duration(duration)
        object.__setattr__(self, "targets", targets)
        object.__setattr__(self, "duration", duration)
        object.__setattr__(self, "easing", easing)


@dataclass(frozen=True)
class Transfer:
    """Animation: send a Packet along a Connection path.

    The packet slides along the routing path with easing applied.
    When `reverse=True`, the packet travels from target to source.
    When `connection` is a list, the packet traverses multiple
    connections sequentially (multi-hop).

    Args:
        connection: Single Connection or list of connected Connections.
        payload: Text label displayed on the packet (max 20 chars).
        duration: Total animation duration in seconds.
        reverse: If True, packet travels from target → source.
        packet_color: Override packet color (CSS name or hex).
        easing: Interpolation curve type.

    Raises:
        InvalidConnectionError: If connection list is not contiguous.

    Example:
        >>> scene.play(Transfer(conn_cs, payload="POST /login", duration=1.0))
        >>> scene.play(Transfer([conn_ab, conn_bc], payload="200 OK", reverse=True))
    """

    connection: Connection | list[Connection] = field(default_factory=list)
    payload: str = ""
    duration: float = DEFAULT_TRANSFER_DURATION
    reverse: bool = False
    packet_color: str | None = None
    easing: EasingType = EasingType.EASE_IN_OUT

    def __init__(
        self,
        connection: Connection | list[Connection],
        payload: str = "",
        duration: float = DEFAULT_TRANSFER_DURATION,
        reverse: bool = False,
        packet_color: str | None = None,
        easing: EasingType = EasingType.EASE_IN_OUT,
    ) -> None:
        _validate_duration(duration)
        if len(payload) > MAX_PAYLOAD_LENGTH:
            msg = f"Payload exceeds {MAX_PAYLOAD_LENGTH} characters: '{payload[:20]}...'"
            raise ValueError(msg)

        # Validate contiguous connection list
        if isinstance(connection, list):
            for i in range(len(connection) - 1):
                if connection[i].target is not connection[i + 1].source:
                    msg = (
                        f"Connections not contiguous at index {i}: "
                        f"target '{connection[i].target.label}' != "
                        f"source '{connection[i + 1].source.label}'"
                    )
                    raise InvalidConnectionError(msg)

        object.__setattr__(self, "connection", connection)
        object.__setattr__(self, "payload", payload)
        object.__setattr__(self, "duration", duration)
        object.__setattr__(self, "reverse", reverse)
        object.__setattr__(self, "packet_color", packet_color)
        object.__setattr__(self, "easing", easing)


@dataclass(frozen=True)
class Pulse:
    """Animation: glow/flash effect on a Node.

    The node's glow intensity ramps up then fades back to zero.

    Args:
        target: The Node or Database to pulse.
        color: Glow color (CSS name or hex).
        duration: Animation duration in seconds.
        intensity: Peak glow intensity (0.0-1.0).
        easing: Interpolation curve type.

    Raises:
        TypeError: If target is not a Node.

    Example:
        >>> scene.play(Pulse(gateway, color="yellow", duration=0.5))
    """

    target: Node = field(default_factory=lambda: None)  # type: ignore[assignment]
    color: str = "white"
    duration: float = DEFAULT_PULSE_DURATION
    intensity: float = DEFAULT_PULSE_INTENSITY
    easing: EasingType = EasingType.EASE_OUT

    def __init__(
        self,
        target: Node,
        color: str = "white",
        duration: float = DEFAULT_PULSE_DURATION,
        intensity: float = DEFAULT_PULSE_INTENSITY,
        easing: EasingType = EasingType.EASE_OUT,
    ) -> None:
        if not isinstance(target, Node):
            msg = f"Pulse target must be a Node, got {type(target).__name__}"
            raise TypeError(msg)
        _validate_duration(duration)
        if not 0.0 <= intensity <= 1.0:
            msg = f"Pulse intensity must be between 0.0 and 1.0, got {intensity}"
            raise ValueError(msg)
        object.__setattr__(self, "target", target)
        object.__setattr__(self, "color", color)
        object.__setattr__(self, "duration", duration)
        object.__setattr__(self, "intensity", intensity)
        object.__setattr__(self, "easing", easing)


# ──────────────────────────────────────────────
# v0.2.0 Extended Animations
# ──────────────────────────────────────────────


@dataclass(frozen=True)
class Highlight:
    """Animation: persistent border glow on a Node.

    Unlike Pulse (which ramps up then fades), Highlight ramps up
    to full intensity and STAYS there until the end of the duration.
    Useful for drawing attention to a specific node during explanation.

    Args:
        target: The Node to highlight.
        color: Highlight color (CSS name or hex).
        duration: How long the highlight stays visible.
        intensity: Glow intensity (0.0-1.0).
        easing: Ramp-up easing curve.

    Raises:
        TypeError: If target is not a Node.

    Example:
        >>> scene.play(Highlight(auth_service, color="red", duration=2.0))
    """

    target: Node = field(default_factory=lambda: None)  # type: ignore[assignment]
    color: str = "yellow"
    duration: float = DEFAULT_HIGHLIGHT_DURATION
    intensity: float = 0.8
    easing: EasingType = EasingType.EASE_IN

    def __init__(
        self,
        target: Node,
        color: str = "yellow",
        duration: float = DEFAULT_HIGHLIGHT_DURATION,
        intensity: float = 0.8,
        easing: EasingType = EasingType.EASE_IN,
    ) -> None:
        if not isinstance(target, Node):
            msg = f"Highlight target must be a Node, got {type(target).__name__}"
            raise TypeError(msg)
        _validate_duration(duration)
        if not 0.0 <= intensity <= 1.0:
            msg = f"Highlight intensity must be between 0.0 and 1.0, got {intensity}"
            raise ValueError(msg)
        object.__setattr__(self, "target", target)
        object.__setattr__(self, "color", color)
        object.__setattr__(self, "duration", duration)
        object.__setattr__(self, "intensity", intensity)
        object.__setattr__(self, "easing", easing)


@dataclass(frozen=True)
class ColorShift:
    """Animation: smoothly transition a Node's fill color.

    Animates COLOR_R, COLOR_G, COLOR_B from one hex color to another.
    Use for: service down (green→red), upgrade complete (blue→green), etc.

    Args:
        target: The Node whose color changes.
        from_color: Starting hex color (e.g. '#4caf50').
        to_color: Ending hex color (e.g. '#f44336').
        duration: Animation duration in seconds.
        easing: Interpolation curve type.

    Raises:
        TypeError: If target is not a Node.
        ValueError: If colors are invalid hex.

    Example:
        >>> scene.play(ColorShift(server, from_color="#4caf50", to_color="#f44336"))
    """

    target: Node = field(default_factory=lambda: None)  # type: ignore[assignment]
    from_color: str = "#4caf50"
    to_color: str = "#f44336"
    duration: float = DEFAULT_COLORSHIFT_DURATION
    easing: EasingType = EasingType.EASE_IN_OUT

    def __init__(
        self,
        target: Node,
        from_color: str = "#4caf50",
        to_color: str = "#f44336",
        duration: float = DEFAULT_COLORSHIFT_DURATION,
        easing: EasingType = EasingType.EASE_IN_OUT,
    ) -> None:
        if not isinstance(target, Node):
            msg = f"ColorShift target must be a Node, got {type(target).__name__}"
            raise TypeError(msg)
        _validate_duration(duration)
        _parse_hex_color(from_color)
        _parse_hex_color(to_color)
        object.__setattr__(self, "target", target)
        object.__setattr__(self, "from_color", from_color)
        object.__setattr__(self, "to_color", to_color)
        object.__setattr__(self, "duration", duration)
        object.__setattr__(self, "easing", easing)


@dataclass(frozen=True)
class ScaleUp:
    """Animation: zoom a Node up from 1.0 to a larger scale factor.

    The SCALE property is interpolated from 1.0 → factor.
    The Renderer uses this to multiply the node's bounding box dimensions.

    Args:
        target: The Node to scale.
        factor: Target scale factor (must be > 1.0).
        duration: Animation duration in seconds.
        easing: Interpolation curve type.

    Raises:
        TypeError: If target is not a Node.
        ValueError: If factor is out of range.

    Example:
        >>> scene.play(ScaleUp(server, factor=1.5, duration=0.3))
    """

    target: Node = field(default_factory=lambda: None)  # type: ignore[assignment]
    factor: float = DEFAULT_SCALE_FACTOR
    duration: float = DEFAULT_SCALE_DURATION
    easing: EasingType = EasingType.EASE_OUT

    def __init__(
        self,
        target: Node,
        factor: float = DEFAULT_SCALE_FACTOR,
        duration: float = DEFAULT_SCALE_DURATION,
        easing: EasingType = EasingType.EASE_OUT,
    ) -> None:
        if not isinstance(target, Node):
            msg = f"ScaleUp target must be a Node, got {type(target).__name__}"
            raise TypeError(msg)
        _validate_duration(duration)
        if not 1.0 < factor <= MAX_SCALE_FACTOR:
            msg = f"ScaleUp factor must be in (1.0, {MAX_SCALE_FACTOR}], got {factor}"
            raise ValueError(msg)
        object.__setattr__(self, "target", target)
        object.__setattr__(self, "factor", factor)
        object.__setattr__(self, "duration", duration)
        object.__setattr__(self, "easing", easing)


@dataclass(frozen=True)
class ScaleDown:
    """Animation: shrink a Node from 1.0 to a smaller scale factor.

    The SCALE property is interpolated from 1.0 → factor.

    Args:
        target: The Node to shrink.
        factor: Target scale factor (must be < 1.0).
        duration: Animation duration in seconds.
        easing: Interpolation curve type.

    Raises:
        TypeError: If target is not a Node.
        ValueError: If factor is out of range.

    Example:
        >>> scene.play(ScaleDown(old_server, factor=0.5, duration=0.3))
    """

    target: Node = field(default_factory=lambda: None)  # type: ignore[assignment]
    factor: float = 0.7
    duration: float = DEFAULT_SCALE_DURATION
    easing: EasingType = EasingType.EASE_IN

    def __init__(
        self,
        target: Node,
        factor: float = 0.7,
        duration: float = DEFAULT_SCALE_DURATION,
        easing: EasingType = EasingType.EASE_IN,
    ) -> None:
        if not isinstance(target, Node):
            msg = f"ScaleDown target must be a Node, got {type(target).__name__}"
            raise TypeError(msg)
        _validate_duration(duration)
        if not MIN_SCALE_FACTOR <= factor < 1.0:
            msg = f"ScaleDown factor must be in [{MIN_SCALE_FACTOR}, 1.0), got {factor}"
            raise ValueError(msg)
        object.__setattr__(self, "target", target)
        object.__setattr__(self, "factor", factor)
        object.__setattr__(self, "duration", duration)
        object.__setattr__(self, "easing", easing)
