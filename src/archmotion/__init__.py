"""ArchMotion — Code-to-Video Framework for System Architecture Animations.

Public API re-exports for convenient user access.
Users should import from this top-level package:

    from archmotion import Scene, Node, Database

Architectural Note:
    This module only re-exports. No logic lives here.
    Implementation resides in subpackages (api/, layout/, timeline/, renderer/, exporter/).
"""

from __future__ import annotations

from archmotion.api.primitives import Database, Node
from archmotion.api.scene import Scene

__all__ = [
    "Scene",
    "Node",
    "Database",
]

__version__ = "0.1.0"
