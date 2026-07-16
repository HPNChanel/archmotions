"""Packet — the data-flow token that travels along a :class:`Connection`.

A :class:`Packet` is a small circle :class:`~archmotion.core.vmobject.VMobject`
bound to a connection via its ``connection`` attribute. The renderer positions it
along the connection's route using the ``PATH_PROGRESS`` animated property (see
:func:`archmotion.render.path_render.resolve_effective`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from archmotion.constants import (
    DEFAULT_FONT_FAMILY,
    PACKET_LABEL_FONT_SIZE,
    PACKET_SIZE,
    Z_EFFECT,
    Z_LABEL,
)
from archmotion.core.vmobject import VMobject

if TYPE_CHECKING:
    from archmotion._types import Point
    from archmotion.domains.architecture.connections import Connection


class Packet(VMobject):
    """A data packet animated along a connection's route."""

    def __init__(
        self,
        label: str = "",
        *,
        connection: Connection | None = None,
        color: str | None = None,
        size: float = PACKET_SIZE,
        center: Point = (0.0, 0.0),
    ) -> None:
        """Store label/connection/size, then generate the circle outline."""
        self.label = label
        # The connection this packet travels on (set by Transfer / layout).
        self.connection: Connection | None = connection
        self.size = size
        self.center = center
        super().__init__(z_index=Z_EFFECT)
        if color is not None:
            self.set_fill(color)
        self._label_graphic = self._make_label()
        if self._label_graphic is not None:
            self.add(self._label_graphic)

    def _make_label(self) -> VMobject | None:
        """Create a payload label just above the moving packet."""
        if not self.label:
            return None
        try:
            from archmotion.domains.text.text import Text

            label = Text(
                self.label,
                family=DEFAULT_FONT_FAMILY,
                size=PACKET_LABEL_FONT_SIZE,
            )
            label.move_to(self.center[0], self.center[1] - self.size)
            label.set_z(Z_LABEL + 1)
            return label
        except (ImportError, RuntimeError):
            return None

    def generate_points(self) -> None:
        """Trace a circle of diameter ``size`` centered on ``center``."""
        r = self.size / 2.0
        cx, cy = self.center
        self.start_new_path((cx + r, cy))
        self.add_arc((cx, cy), r, 0.0, 360.0)
        self.close_path()
