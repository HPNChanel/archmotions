"""Phase 2 -- Layout Resolution (Bounding Box, Coordinates, Routing).

Public API:
    resolve_layout() -- Main entry point for Phase 2
    ResolvedLayout   -- Output data structure
    BoundingBox      -- Axis-aligned bounding rectangle
"""

from archmotion.layout.bbox import BoundingBox
from archmotion.layout.resolver import ResolvedLayout, resolve_layout
from archmotion.layout.router import manhattan_route

__all__ = [
    "BoundingBox",
    "ResolvedLayout",
    "manhattan_route",
    "resolve_layout",
]
