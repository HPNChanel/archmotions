"""VGroup — a Graphic that groups children (a transformable container)."""

from __future__ import annotations

from archmotion.core.graphic import Graphic


class VGroup(Graphic):
    """A container graphic holding child graphics (no own points).

    Children are rendered individually (the scene graph flattens to all
    descendants); the group exists so a cluster of graphics can be moved, scaled
    or animated together, and styled as a unit.
    """

    def __init__(self, *graphics: Graphic, z_index: int = 0) -> None:
        """Initialize an empty group, then attach the given children."""
        super().__init__(z_index=z_index)
        for child in graphics:
            self.add(child)
