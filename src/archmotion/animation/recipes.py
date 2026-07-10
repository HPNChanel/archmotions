"""Architecture-domain recipe animations on the v2.0 base.

- :class:`Transfer` moves a packet :class:`~archmotion.domains.architecture.primitives`
  shape along a :class:`~archmotion.domains.architecture.connections.Connection`
  path (data-flow).
- :class:`Pulse` ramps a glow up then down.
- :class:`Highlight` ramps a glow up and holds.
- :class:`ColorShift` tweens the fill color.
- :class:`Scale` tweens the scale factor.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from archmotion.animation.base import Animation
from archmotion.core import easing
from archmotion.core.property import MorphAction, Property, PropertyAction

if TYPE_CHECKING:
    from archmotion.core.graphic import Graphic
    from archmotion.domains.architecture.connections import Connection
    from archmotion.domains.architecture.packet import Packet


def _hex_to_rgb01(color: str | None) -> tuple[float, float, float]:
    """Parse a hex/CSS color to (R, G, B) floats; white fallback."""
    if color is None:
        return (1.0, 1.0, 1.0)
    c = color.lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    if len(c) != 6:
        return (1.0, 1.0, 1.0)
    try:
        return (int(c[0:2], 16) / 255.0, int(c[2:4], 16) / 255.0, int(c[4:6], 16) / 255.0)
    except ValueError:
        return (1.0, 1.0, 1.0)


class Transfer(Animation):
    """Move a packet along a connection's route (data-flow).

    A :class:`~archmotion.domains.architecture.packet.Packet` is created by
    default and bound to ``connection``; pass ``packet=`` to supply a custom one.
    """

    def __init__(
        self,
        connection: Connection,
        *,
        packet: Packet | None = None,
        payload: str | None = None,
        color: str | None = None,
        run_time: float = 1.0,
        rate_func: str = easing.DEFAULT_EASING,
        reverse: bool = False,
        duration: float | None = None,
    ) -> None:
        """Store connection + packet + direction; auto-create a packet if none."""
        super().__init__(run_time=run_time, rate_func=rate_func, duration=duration)
        self._connection = connection
        self._reverse = reverse
        if packet is None:
            from archmotion.domains.architecture.packet import Packet

            packet = Packet(label=payload or "", connection=connection, color=color)
        else:
            packet.connection = connection
        self._packet = packet

    def targets(self) -> list[Graphic]:
        """The packet is the animated target."""
        return [self._packet]

    def begin(self) -> None:
        """Reveal the packet at the route start."""
        self._packet.opacity = 1.0

    def compile(self, start_time: float) -> list[PropertyAction | MorphAction]:
        """Emit a PATH_PROGRESS action for the packet along the connection."""
        end_time = start_time + self.run_time
        start_val = 1.0 if self._reverse else 0.0
        end_val = 0.0 if self._reverse else 1.0
        return [
            PropertyAction(
                target_id=self._packet.id,
                prop=Property.PATH_PROGRESS,
                start_time=start_time,
                end_time=end_time,
                start_value=start_val,
                end_value=end_val,
                easing=self.rate_func,
            )
        ]

    def finish(self) -> None:
        """Hide the packet after the transfer completes."""
        self._packet.opacity = 0.0


class Pulse(Animation):
    """Ramp a glow up to peak intensity, then back down."""

    def __init__(
        self,
        target: Graphic,
        *,
        color: str = "#ffffff",
        intensity: float = 0.8,
        run_time: float = 0.5,
        rate_func: str = "ease_out",
        duration: float | None = None,
    ) -> None:
        """Store target + glow parameters."""
        super().__init__(run_time=run_time, rate_func=rate_func, duration=duration)
        self._target = target
        self._color = color
        self._intensity = intensity

    def targets(self) -> list[Graphic]:
        """The target being pulsed."""
        return [self._target]

    def compile(self, start_time: float) -> list[PropertyAction | MorphAction]:
        """Emit ramp-up + ramp-down GLOW_INTENSITY actions."""
        mid = start_time + self.run_time / 2.0
        end = start_time + self.run_time
        return [
            PropertyAction(
                target_id=self._target.id,
                prop=Property.GLOW_INTENSITY,
                start_time=start_time,
                end_time=mid,
                start_value=0.0,
                end_value=self._intensity,
                easing="ease_in",
            ),
            PropertyAction(
                target_id=self._target.id,
                prop=Property.GLOW_INTENSITY,
                start_time=mid,
                end_time=end,
                start_value=self._intensity,
                end_value=0.0,
                easing="ease_out",
            ),
        ]


class Highlight(Animation):
    """Ramp a glow up quickly, then hold at peak for the duration."""

    def __init__(
        self,
        target: Graphic,
        *,
        intensity: float = 0.8,
        run_time: float = 2.0,
        rate_func: str = "ease_in",
        duration: float | None = None,
    ) -> None:
        """Store target + glow parameters."""
        super().__init__(run_time=run_time, rate_func=rate_func, duration=duration)
        self._target = target
        self._intensity = intensity

    def targets(self) -> list[Graphic]:
        """The target being highlighted."""
        return [self._target]

    def compile(self, start_time: float) -> list[PropertyAction | MorphAction]:
        """Emit a quick ramp-up then a hold at peak."""
        ramp_end = start_time + self.run_time * 0.15
        end = start_time + self.run_time
        return [
            PropertyAction(
                target_id=self._target.id,
                prop=Property.GLOW_INTENSITY,
                start_time=start_time,
                end_time=ramp_end,
                start_value=0.0,
                end_value=self._intensity,
                easing=self.rate_func,
            ),
            PropertyAction(
                target_id=self._target.id,
                prop=Property.GLOW_INTENSITY,
                start_time=ramp_end,
                end_time=end,
                start_value=self._intensity,
                end_value=self._intensity,
                easing="linear",
            ),
        ]


class ColorShift(Animation):
    """Tween a target's fill color from ``from_color`` to ``to_color``."""

    def __init__(
        self,
        target: Graphic,
        from_color: str = "#4caf50",
        to_color: str = "#f44336",
        *,
        run_time: float = 1.0,
        rate_func: str = easing.DEFAULT_EASING,
        duration: float | None = None,
    ) -> None:
        """Store target + color endpoints."""
        super().__init__(run_time=run_time, rate_func=rate_func, duration=duration)
        self._target = target
        self._from = _hex_to_rgb01(from_color)
        self._to = _hex_to_rgb01(to_color)

    def targets(self) -> list[Graphic]:
        """The target whose color changes."""
        return [self._target]

    def compile(self, start_time: float) -> list[PropertyAction | MorphAction]:
        """Emit FILL_R/G/B scalar tweens."""
        end_time = start_time + self.run_time
        actions: list[PropertyAction | MorphAction] = []
        for prop, sv, tv in (
            (Property.FILL_R, self._from[0], self._to[0]),
            (Property.FILL_G, self._from[1], self._to[1]),
            (Property.FILL_B, self._from[2], self._to[2]),
        ):
            actions.append(
                PropertyAction(
                    target_id=self._target.id,
                    prop=prop,
                    start_time=start_time,
                    end_time=end_time,
                    start_value=sv,
                    end_value=tv,
                    easing=self.rate_func,
                )
            )
        return actions

    def finish(self) -> None:
        """Commit the end fill color on the target's style."""
        r, g, b = self._to
        hex_color = f"#{round(r * 255):02x}{round(g * 255):02x}{round(b * 255):02x}"
        self._target.set_fill(hex_color)


class Scale(Animation):
    """Tween a target's scale from 1.0 to ``factor``."""

    def __init__(
        self,
        target: Graphic,
        factor: float,
        *,
        run_time: float = 0.3,
        rate_func: str = "ease_out",
        duration: float | None = None,
    ) -> None:
        """Store target + factor."""
        super().__init__(run_time=run_time, rate_func=rate_func, duration=duration)
        self._target = target
        self._factor = factor

    def targets(self) -> list[Graphic]:
        """The target being scaled."""
        return [self._target]

    def compile(self, start_time: float) -> list[PropertyAction | MorphAction]:
        """Emit a SCALE 1.0 -> factor action."""
        end_time = start_time + self.run_time
        return [
            PropertyAction(
                target_id=self._target.id,
                prop=Property.SCALE,
                start_time=start_time,
                end_time=end_time,
                start_value=1.0,
                end_value=self._factor,
                easing=self.rate_func,
            )
        ]


class ScaleUp(Scale):
    """Scale a target up (factor >= 1). Convenience subclass of :class:`Scale`."""

    def __init__(
        self,
        target: Graphic,
        factor: float = 1.3,
        *,
        run_time: float = 0.3,
        rate_func: str = "ease_out",
        duration: float | None = None,
    ) -> None:
        """Store target + factor (default 1.3)."""
        super().__init__(target, factor, run_time=run_time, rate_func=rate_func, duration=duration)


class ScaleDown(Scale):
    """Scale a target down (factor <= 1). Convenience subclass of :class:`Scale`."""

    def __init__(
        self,
        target: Graphic,
        factor: float = 0.77,
        *,
        run_time: float = 0.3,
        rate_func: str = "ease_out",
        duration: float | None = None,
    ) -> None:
        """Store target + factor (default 0.77)."""
        super().__init__(target, factor, run_time=run_time, rate_func=rate_func, duration=duration)
