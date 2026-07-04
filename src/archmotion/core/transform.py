"""Affine 2D transforms (3x3 homogeneous matrices).

A :class:`Transform` maps local graphic coordinates into parent/canvas space.
Transforms compose with :meth:`compose` (``self @ other`` applies ``other`` first)
and apply to point arrays via :meth:`apply_to_points`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

if TYPE_CHECKING:
    from archmotion._types import Point

FloatArray = NDArray[np.float64]


@dataclass
class Transform:
    """A 3x3 homogeneous affine transform.

    Attributes:
        matrix: 3x3 row-major matrix (``matrix @ [x, y, 1]`` transforms a point).
    """

    matrix: FloatArray

    def __init__(self, matrix: object) -> None:
        """Coerce ``matrix`` to a float64 3x3 array."""
        self.matrix = np.asarray(matrix, dtype=np.float64)

    @classmethod
    def identity(cls) -> Transform:
        """The identity transform (no change)."""
        return cls(np.identity(3, dtype=np.float64))

    @classmethod
    def translation(cls, x: float, y: float) -> Transform:
        """A pure translation by ``(x, y)``."""
        matrix = np.identity(3, dtype=np.float64)
        matrix[0, 2] = x
        matrix[1, 2] = y
        return cls(matrix)

    @classmethod
    def scaling(cls, sx: float, sy: float | None = None) -> Transform:
        """A scale transform. ``sy`` defaults to ``sx`` (uniform)."""
        sy_eff = sx if sy is None else sy
        matrix = np.identity(3, dtype=np.float64)
        matrix[0, 0] = sx
        matrix[1, 1] = sy_eff
        return cls(matrix)

    @classmethod
    def rotation(cls, angle_deg: float) -> Transform:
        """A counter-clockwise rotation by ``angle_deg`` degrees."""
        rad = np.radians(angle_deg)
        cos_a = np.cos(rad)
        sin_a = np.sin(rad)
        matrix = np.identity(3, dtype=np.float64)
        matrix[0, 0] = cos_a
        matrix[0, 1] = -sin_a
        matrix[1, 0] = sin_a
        matrix[1, 1] = cos_a
        return cls(matrix)

    def compose(self, other: Transform) -> Transform:
        """Return ``self @ other`` — i.e. apply ``other`` first, then ``self``."""
        return Transform(self.matrix @ other.matrix)

    def invert(self) -> Transform:
        """The inverse transform."""
        return Transform(np.linalg.inv(self.matrix))

    def apply_to_point(self, point: Point) -> Point:
        """Transform a single point."""
        vec = np.array([point[0], point[1], 1.0], dtype=np.float64)
        result = self.matrix @ vec
        return (float(result[0]), float(result[1]))

    def apply_to_points(self, points: object) -> FloatArray:
        """Transform an ``(N, 2)`` point array (accepts any array-like)."""
        pts = np.asarray(points, dtype=np.float64).reshape(-1, 2)
        if pts.size == 0:
            return pts
        n = pts.shape[0]
        homogeneous = np.ones((n, 3), dtype=np.float64)
        homogeneous[:, :2] = pts
        result = (self.matrix @ homogeneous.T).T[:, :2]
        return np.asarray(result, dtype=np.float64)
