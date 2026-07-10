"""Phase 1 — User-facing API for Topology and Choreography.

Note:
    ``Scene`` is imported lazily (via ``__getattr__``) to avoid a circular
    import: ``timeline.compiler`` imports ``api.connections``, which runs this
    package's ``__init__``; eagerly importing ``api.scene`` here would re-enter
    ``timeline.compiler`` before it finishes defining ``CompiledTimeline``.
"""

from __future__ import annotations

from archmotion.api.connections import Connection
from archmotion.api.primitives import Cache, Cloud, Database, Node, Queue, User

__all__ = [
    "Cache",
    "Cloud",
    "Connection",
    "Database",
    "Node",
    "Queue",
    "Scene",
    "User",
]


def __getattr__(name: str) -> type:
    """Lazily import ``Scene`` (and any future heavy submodules) on first access."""
    if name == "Scene":
        from archmotion.api.scene import Scene

        return Scene
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
