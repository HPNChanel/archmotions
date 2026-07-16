"""ArchMotion — Multi-domain code-to-video animation framework.

Public API re-exports for convenient user access.

Usage (Python API)::

    from archmotion import Scene, Node, Database, Cloud, Queue, Cache, User
    from archmotion import Connection, FadeIn, FadeOut, Transfer, Pulse
    from archmotion import load_yaml, parse_yaml_string

Usage (CLI)::

    archmotion render scene.yaml -o output.mp4
    archmotion render scene.py MyScene -qm -o output.mp4
    archmotion still scene.py MyScene -qm -o output.png
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
    Animation,
    AnimationGroup,
    ColorShift,
    Create,
    DrawBorderThenFill,
    DrawLine,
    FadeIn,
    FadeOut,
    FadeToColor,
    Flash,
    GrowBar,
    GrowFromCenter,
    GrowFromEdge,
    Highlight,
    Indicate,
    LaggedStart,
    Pulse,
    ReplacementTransform,
    Scale,
    ScaleDown,
    ScaleUp,
    StateTween,
    Succession,
    SweepPie,
    Transfer,
    Transform,
    Typewriter,
    Uncreate,
    Write,
)

# ── Core API ──
from archmotion.core import Camera, Graphic, Style, ValueTracker, VGroup, VMobject, always_redraw
from archmotion.core.scene import Scene
from archmotion.domains.architecture import (
    Cache,
    Cloud,
    Connection,
    Database,
    Node,
    Packet,
    Queue,
    User,
)
from archmotion.domains.charts import BarChart, LineChart, PieChart, ScatterPlot
from archmotion.domains.code import CodeBlock
from archmotion.domains.geometry import (
    Annulus,
    Arc,
    ArcBetweenPoints,
    Arrow,
    Axes,
    Bezier,
    Brace,
    Circle,
    DashedLine,
    Dot,
    DoubleArrow,
    Ellipse,
    FunctionGraph,
    Line,
    NumberLine,
    NumberPlane,
    ParametricFunction,
    Polygon,
    Polyline,
    Rectangle,
    RegularPolygon,
    RoundedRectangle,
    Square,
)
from archmotion.domains.math import MathTex, MathText, Tex
from archmotion.domains.text import Paragraph, Text
from archmotion.loader import load_python_scene

__all__ = [
    "Animation",
    "AnimationGroup",
    "Annulus",
    "Arc",
    "ArcBetweenPoints",
    "Arrow",
    "Axes",
    "BarChart",
    "Bezier",
    "Brace",
    "Cache",
    "Camera",
    "Circle",
    "Cloud",
    "CodeBlock",
    "ColorShift",
    "Connection",
    "Create",
    "DashedLine",
    "Database",
    "Dot",
    "DoubleArrow",
    "DrawBorderThenFill",
    "DrawLine",
    "Ellipse",
    "FadeIn",
    "FadeOut",
    "FadeToColor",
    "Flash",
    "FunctionGraph",
    "Graphic",
    "GrowBar",
    "GrowFromCenter",
    "GrowFromEdge",
    "Highlight",
    "Indicate",
    "LaggedStart",
    "Line",
    "LineChart",
    "MathTex",
    "MathText",
    "Node",
    "NumberLine",
    "NumberPlane",
    "Packet",
    "Paragraph",
    "ParametricFunction",
    "PieChart",
    "Polygon",
    "Polyline",
    "Pulse",
    "Queue",
    "Rectangle",
    "RegularPolygon",
    "ReplacementTransform",
    "RoundedRectangle",
    "Scale",
    "ScaleDown",
    "ScaleUp",
    "ScatterPlot",
    "Scene",
    "Square",
    "StateTween",
    "Style",
    "Succession",
    "SweepPie",
    "Tex",
    "Text",
    "Transfer",
    "Transform",
    "Typewriter",
    "Uncreate",
    "User",
    "VGroup",
    "VMobject",
    "ValueTracker",
    "Write",
    "always_redraw",
    "load_python_scene",
    "load_yaml",
    "parse_yaml_string",
]

__version__ = "2.0.0"
