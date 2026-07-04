"""ArchMotion — Code-to-Video Framework for System Architecture Animations.

Public API re-exports for convenient user access.

Usage (Python API)::

    from archmotion import Scene, Node, Database, Cloud, Queue, Cache, User
    from archmotion import Connection, FadeIn, FadeOut, Transfer, Pulse
    from archmotion import load_yaml, parse_yaml_string

Usage (CLI)::

    archmotion render scene.yaml -o output.mp4
    archmotion render scene.yaml -o output.json
    archmotion version
    archmotion themes

Architectural Note:
    This module only re-exports. No logic lives here.
    Implementation resides in subpackages (api/, layout/, timeline/, renderer/, exporter/).
"""

from __future__ import annotations

# ── Core API ──
from archmotion.api.primitives import (
    Cache,
    Cloud,
    Database,
    Node,
    Queue,
    User,
)
from archmotion.api.connections import Connection
from archmotion.api.scene import Scene

# ── Animations ──
from archmotion.motions._animations import (
    ColorShift,
    FadeIn,
    FadeOut,
    Highlight,
    Pulse,
    ScaleDown,
    ScaleUp,
    Transfer,
)

# ── YAML AI Interface ──
from archmotion.ai import load_yaml, parse_yaml_string

__all__ = [
    # Core
    "Scene",
    "Node",
    "Database",
    "Cloud",
    "Queue",
    "Cache",
    "User",
    "Connection",
    # Animations
    "FadeIn",
    "FadeOut",
    "Transfer",
    "Pulse",
    "Highlight",
    "ColorShift",
    "ScaleUp",
    "ScaleDown",
    # YAML
    "load_yaml",
    "parse_yaml_string",
]

__version__ = "2.0.0"

# ── v2.0 multi-domain engine ──────────────────────────────────────
# The v2.0 API lives in `archmotion.core` (Scene, Graphic, VMobject, Camera,
# Style, Transform, property model), `archmotion.animation` (FadeIn, Transform,
# AnimationGroup, recipes), and `archmotion.domains` (geometry, charts, math,
# architecture). Import directly, e.g.:
#   from archmotion.core import Scene
#   from archmotion.domains.geometry import Circle, Axes
#   from archmotion.domains.architecture import Node
#   from archmotion.animation import FadeIn, Transform
