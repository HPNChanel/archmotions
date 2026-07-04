"""Camera — the viewport mapping scene coordinates to output pixels.

ArchMotion v2.0 uses a **single, consistent coordinate space**: pixels, top-left
origin, y grows downward (identical to SVG/Canvas/skia/React Flow and to the
v1.0 architecture pipeline). This avoids the y-up/y-down confusion that arises
when fusing Manim-style math scenes with architecture diagrams.

By default the camera is an identity viewport (scene units == pixels). A
:centered" camera (:meth:`Camera.centered`) translates the origin to the frame
center for math/geometry scenes that prefer a centered layout.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from archmotion.core.transform import Transform

if TYPE_CHECKING:
    from archmotion._types import Point


@dataclass
class Camera:
    """Output viewport.

    Attributes:
        width: Output width in pixels.
        height: Output height in pixels.
        view: An optional transform applied to every graphic before paint
            (pan/zoom). Identity by default (scene == pixel).
    """

    width: int
    height: int
    view: Transform = field(default_factory=Transform.identity)

    @classmethod
    def centered(cls, width: int, height: int) -> Camera:
        """A camera whose origin (0, 0) sits at the frame center."""
        return cls(width, height, view=Transform.translation(width / 2.0, height / 2.0))

    def to_pixels(self, scene_point: Point) -> Point:
        """Map a scene point to pixel coordinates."""
        return self.view.apply_to_point(scene_point)

    @property
    def center(self) -> Point:
        """The pixel center of the viewport."""
        return (self.width / 2.0, self.height / 2.0)
