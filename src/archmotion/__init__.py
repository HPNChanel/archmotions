"""ArchMotion — Multi-domain code-to-video animation framework.

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
    v2.0 public surface. The engine lives in ``archmotion.core`` (Scene, Graphic,
    VMobject, Camera), ``archmotion.domains`` (architecture/geometry/charts/...),
    ``archmotion.animation``, ``archmotion.render``, and ``archmotion.exporter``.
    This module only re-exports; no logic lives here.
"""

from __future__ import annotations

# ── YAML AI Interface ──
from archmotion.ai import load_yaml, parse_yaml_string

# ── Animations ──
from archmotion.animation import (
    ColorShift,
    FadeIn,
    FadeOut,
    Highlight,
    Pulse,
    ScaleDown,
    ScaleUp,
    Transfer,
)

# ── Core API ──
from archmotion.core.scene import Scene
from archmotion.domains.architecture import (
    Cache,
    Cloud,
    Connection,
    Database,
    Node,
    Queue,
    User,
)

__all__ = [
    "Cache",
    "Cloud",
    "ColorShift",
    "Connection",
    "Database",
    "FadeIn",
    "FadeOut",
    "Highlight",
    "Node",
    "Pulse",
    "Queue",
    "ScaleDown",
    "ScaleUp",
    "Scene",
    "Transfer",
    "User",
    "load_yaml",
    "parse_yaml_string",
]

__version__ = "2.0.0"
