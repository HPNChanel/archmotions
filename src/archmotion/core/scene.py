"""Scene — the v2.0 authoring surface (virtual clock + play/wait + exports).

A :class:`Scene` holds a scene graph of :class:`~archmotion.core.graphic.Graphic`
objects, a virtual clock, and an accumulated parametric timeline. ``play``
compiles animations into actions (advancing the clock); ``wait`` pads time.
Rendering/exporting is delegated lazily to ``archmotion.render`` /
``archmotion.exporter`` so the core stays renderer-agnostic.

The public authoring API supports Manim-inspired calls
(``play(*anims, run_time=, lag_ratio=)``, ``add(*graphics)``) **and** the
ergonomic v1-style calls (``add_node``/``add_connection``, ``concurrent()``,
``play(anim, duration=)``, ``Scene(resolution="1080p", theme="dark_terminal")``,
``render(output_file=, show_progress=)``, ``export()``). It is not a Manim API
compatibility layer.
"""

from __future__ import annotations

import json
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any

from archmotion.constants import RESOLUTION_MAP
from archmotion.core.camera import Camera
from archmotion.core.color import color_to_rgba01
from archmotion.core.property import CompiledTimeline, MorphAction, PropertyAction
from archmotion.errors import EmptyTimelineError
from archmotion.render.theme import ThemeConfig, get_theme

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from archmotion.animation.base import Animation
    from archmotion.core.graphic import Graphic

DEFAULT_FPS = 30
DEFAULT_RESOLUTION = (1280, 720)


class Scene:
    """A composition of graphics animated over a virtual timeline."""

    def __init__(
        self,
        *,
        fps: int = DEFAULT_FPS,
        resolution: str | tuple[int, int] | None = None,
        camera: Camera | None = None,
        theme: str | ThemeConfig | None = None,
        background_color: str | None = None,
    ) -> None:
        """Initialize resolution, camera, fps, theme and empty scene graph + clock.

        Args:
            fps: Frame rate.
            resolution: Either a preset name ('720p'/'1080p'/'1440p'/'4k') or a
                ``(width, height)`` pixel tuple. Defaults to 720p.
            camera: Optional explicit camera (else derived from resolution).
            theme: Either a theme name string or a :class:`ThemeConfig`.
            background_color: Optional override of the theme background (hex/CSS).
        """
        if resolution is None:
            res = DEFAULT_RESOLUTION
        elif isinstance(resolution, str):
            if resolution not in RESOLUTION_MAP:
                msg = (
                    f"Invalid resolution '{resolution}'. Choose from: {list(RESOLUTION_MAP.keys())}"
                )
                raise ValueError(msg)
            res = RESOLUTION_MAP[resolution]
        else:
            res = (int(resolution[0]), int(resolution[1]))

        if res[0] <= 0 or res[1] <= 0:
            raise ValueError(f"resolution dimensions must be positive, got {res}")
        if fps <= 0:
            raise ValueError(f"fps must be positive, got {fps}")

        self.resolution = res
        self.fps = fps
        self.camera = camera if camera is not None else Camera(*res)

        if theme is None:
            self.theme = ThemeConfig()
        elif isinstance(theme, str):
            self.theme = get_theme(theme)
        else:
            self.theme = theme
        if background_color is not None:
            self.theme = _theme_with_bg(self.theme, background_color)

        self._roots: list[Graphic] = []
        self._index: dict[str, Graphic] = {}
        self._actions: list[PropertyAction | MorphAction] = []
        self._clock: float = 0.0
        self._concurrent_buffer: list[Animation] | None = None
        self._constructed = False

    # ── lifecycle ────────────────────────────────────────────────

    def setup(self) -> None:
        """Hook executed immediately before :meth:`construct`."""

    def construct(self) -> None:
        """Override in a Scene subclass to author graphics and animations."""

    def tear_down(self) -> None:
        """Hook executed immediately after :meth:`construct`."""

    def _ensure_constructed(self) -> None:
        """Execute subclass authoring exactly once."""
        if self._constructed:
            return
        self._constructed = True
        try:
            self.setup()
            self.construct()
            self.tear_down()
        except Exception:
            self._constructed = False
            raise

    # ── scene graph ──────────────────────────────────────────────

    @property
    def graphics(self) -> list[Graphic]:
        """Root-level graphics (see :meth:`all_graphics` for the full tree)."""
        return list(self._roots)

    @property
    def clock(self) -> float:
        """Current virtual time (seconds)."""
        return self._clock

    @property
    def total_duration(self) -> float:
        """Total timeline duration in seconds (alias for :attr:`clock`)."""
        return self._clock

    @property
    def canvas_size(self) -> tuple[int, int]:
        """Canvas dimensions as ``(width, height)`` in pixels."""
        return self.resolution

    def add(self, *graphics: Graphic) -> Scene:
        """Register unique graphics in the scene without duplicate families."""
        for g in graphics:
            if g in self._roots:
                continue
            family = _walk(g)
            for descendant in family:
                existing = self._index.get(descendant.id)
                if existing is not None and existing is not descendant:
                    msg = f"Duplicate graphic id '{descendant.id}'."
                    raise ValueError(msg)
            # A child already registered as a root becomes owned by the new
            # family instead of being painted twice.
            self._roots = [root for root in self._roots if root not in family[1:]]
            if g.parent is None or g.parent not in self._index.values():
                self._roots.append(g)
            for descendant in family:
                self._index[descendant.id] = descendant
        return self

    def remove(self, *graphics: Graphic) -> Scene:
        """Remove graphics from the scene."""
        for g in graphics:
            if g in self._roots:
                self._roots.remove(g)
            for descendant in _walk(g):
                self._index.pop(descendant.id, None)
        return self

    def all_graphics(self) -> list[Graphic]:
        """All graphics in paint (z_index) order: roots + descendants."""
        flat: list[Graphic] = []
        for root in self._roots:
            flat.extend(_walk(root))
        flat.sort(key=lambda g: g.z_index)
        return flat

    def add_node(self, node: Graphic) -> Scene:
        """Register an architecture node (convenience alias for :meth:`add`)."""
        return self.add(node)

    def add_connection(self, connection: Graphic) -> Scene:
        """Register an architecture connection (convenience alias for :meth:`add`)."""
        return self.add(connection)

    # ── timeline authoring ───────────────────────────────────────

    def play(
        self,
        *animations: Animation,
        run_time: float | None = None,
        lag_ratio: float | None = None,
        duration: float | None = None,
    ) -> Scene:
        """Play animations at the current clock, then advance the clock.

        Supports both styles:

        - v2: ``play(*anims, run_time=, lag_ratio=)``.
        - v1: ``play(anim, duration=)`` — ``duration`` overrides each animation's
          ``run_time``.

        Inside a :meth:`concurrent` block, animations are buffered and flushed
        together as a parallel group on block exit.
        """
        from archmotion.animation.base import AnimationGroup

        if not animations:
            msg = "play() requires at least one animation."
            raise TypeError(msg)

        normalized = [_to_animation(a) for a in animations]
        if duration is not None:
            for a in normalized:
                a.run_time = duration

        if self._concurrent_buffer is not None:
            self._concurrent_buffer.extend(normalized)
            for anim in normalized:
                _register_targets(self, anim)
            return self

        if len(normalized) == 1 and run_time is None and lag_ratio is None:
            anim = normalized[0]
        else:
            anim = AnimationGroup(
                *normalized,
                lag_ratio=lag_ratio if lag_ratio is not None else 0.0,
                run_time=run_time,
            )

        _register_targets(self, anim)
        anim.begin()
        start = self._clock
        self._actions.extend(anim.compile(start))
        self._clock += anim.run_time
        anim.finish()
        return self

    @contextmanager
    def concurrent(self) -> Iterator[None]:
        """Run all ``play()`` calls inside the block simultaneously.

        On exit, the buffered animations are compiled as one parallel group
        (``lag_ratio=0``) starting at the block's entry time, and the clock
        advances by the group's duration.
        """
        from archmotion.animation.base import AnimationGroup

        if self._concurrent_buffer is not None:
            # Nested concurrent block — flatten into the outer one.
            yield
            return

        buffer: list[Animation] = []
        self._concurrent_buffer = buffer
        try:
            yield
        finally:
            self._concurrent_buffer = None

        if buffer:
            group = AnimationGroup(*buffer, lag_ratio=0.0)
            _register_targets(self, group)
            group.begin()
            self._actions.extend(group.compile(self._clock))
            self._clock += group.run_time
            group.finish()

    def wait(self, duration: float) -> Scene:
        """Advance the clock by ``duration`` seconds (a pause)."""
        if duration < 0:
            msg = f"wait duration must be non-negative, got {duration}"
            raise ValueError(msg)
        self._clock += duration
        return self

    def compile_timeline(self) -> CompiledTimeline:
        """Build the parametric timeline from all ``play``/``wait`` calls."""
        property_actions = sorted(
            (a for a in self._actions if isinstance(a, PropertyAction)),
            key=lambda a: (a.start_time, a.target_id),
        )
        morph_actions = tuple(a for a in self._actions if isinstance(a, MorphAction))
        return CompiledTimeline(
            property_actions=tuple(property_actions),
            morph_actions=morph_actions,
            total_duration=self._clock,
            fps=self.fps,
        )

    # ── export preparation ───────────────────────────────────────

    def _prepare(self) -> None:
        """Auto-resolve architecture layout when nodes opt into relative layout.

        Only runs if at least one architecture node has a position constraint
        (``.right_of()`` / ``.at()``). Manually-placed scenes (``center=`` only)
        are left untouched.
        """
        from archmotion.domains.architecture.primitives import Node as ArchNode

        arch_nodes = [g for g in self.all_graphics() if isinstance(g, ArchNode)]
        if arch_nodes and any(getattr(n, "position", None) is not None for n in arch_nodes):
            from archmotion.domains.architecture.layout import resolve_architecture

            resolve_architecture(self, corner_radius=self.theme.conn_corner_radius)

    # ── render / export ──────────────────────────────────────────

    def render(
        self,
        output_path: str = "output.mp4",
        *,
        output_file: str | None = None,
        fps: int | None = None,
        crf: int = 20,
        show_progress: bool = False,
        on_progress: Callable[[int, int], None] | None = None,
        workers: int | None = None,
    ) -> Path:
        """Render the scene to an MP4 video file. Returns the file path.

        Rendering uses a multiprocessing worker pool by default (with a
        SharedMemory ring for zero-copy frame IPC). Pass ``workers=1`` to use the
        single-process path.

        ``on_progress``/``show_progress`` report frame progress; ``show_progress``
        prints to stderr when no explicit ``on_progress`` is given.
        """
        self._ensure_constructed()
        if not self._actions:
            raise EmptyTimelineError()

        out = output_file if output_file is not None else output_path
        if not out.endswith(".mp4"):
            out += ".mp4"

        self._prepare()
        progress = _make_progress(show_progress, on_progress)

        if workers == 1:
            from archmotion.render.frame import render_scene

            path = render_scene(
                self,
                out,
                fps=fps,
                crf=crf,
                on_progress=progress,
            )
            return Path(path)

        from archmotion.render.pool import render_pool

        result = render_pool(
            self,
            out,
            fps=fps,
            crf=crf,
            workers=workers,
            on_progress=progress,
        )
        return result.output_path

    def save_frame(
        self,
        output_file: str,
        *,
        time: float | None = None,
    ) -> Path:
        """Render one timeline timestamp to a PNG image."""
        self._ensure_constructed()
        self._prepare()
        timestamp = self.total_duration if time is None else float(time)
        if timestamp < 0 or timestamp > self.total_duration:
            raise ValueError(f"frame time must be within 0..{self.total_duration}, got {timestamp}")

        from PIL import Image

        from archmotion.core.vmobject import VMobject
        from archmotion.render.frame import FrameSpec, render_frame

        timeline = self.compile_timeline()
        frame_index = round(timestamp * timeline.fps)
        width, height = self.resolution
        spec = FrameSpec(
            frame_index=frame_index,
            width=width,
            height=height,
            fps=timeline.fps,
            graphics=[g for g in self.all_graphics() if isinstance(g, VMobject)],
            timeline=timeline,
            camera=self.camera,
            background_rgba=self.theme.background_rgba,
            theme=self.theme,
            update_roots=self.graphics,
        )
        raw = render_frame(spec)
        out = Path(output_file)
        if out.suffix.lower() != ".png":
            out = out.with_suffix(".png")
        out.parent.mkdir(parents=True, exist_ok=True)
        Image.frombytes("RGBA", (width, height), raw).save(out)
        return out

    def export(
        self,
        output_file: str,
        *,
        minify: bool = False,
        title: str = "ArchMotion Animation",
    ) -> Path:
        """Export the scene to Lottie JSON (.json), SVG (.svg), or HTML (.html).

        The format is auto-detected from the file extension. For MP4 video, use
        :meth:`render`.
        """
        self._ensure_constructed()
        if not self._actions:
            raise EmptyTimelineError()

        out = Path(output_file)
        ext = out.suffix.lower()
        supported = {".json", ".svg", ".html", ".htm"}
        if ext not in supported:
            msg = (
                f"Unsupported export format '{ext}'. "
                f"Use .json (Lottie), .svg, or .html. For MP4, use scene.render()."
            )
            raise ValueError(msg)

        self._prepare()
        out.parent.mkdir(parents=True, exist_ok=True)
        if ext == ".json":
            data = self.to_lottie(title=title)
            separators = (",", ":") if minify else None
            out.write_text(json.dumps(data, separators=separators), encoding="utf-8")
        elif ext == ".svg":
            out.write_text(self.to_svg(title=title), encoding="utf-8")
        else:
            out.write_text(self.to_html(title=title), encoding="utf-8")
        return out

    def resolve(self) -> CompiledTimeline:
        """Run layout preparation and return the compiled timeline (in-memory).

        Note:
            Unlike the v1 ``resolve()``, this returns the compiled timeline, not
            the resolved layout. For resolved node boxes, use :meth:`to_layout_dict`.
        """
        self._ensure_constructed()
        self._prepare()
        return self.compile_timeline()

    def to_lottie(self, *, title: str = "ArchMotion") -> dict[str, Any]:
        """Export the scene as a Lottie dict. Lazy import."""
        self._ensure_constructed()
        self._prepare()
        from archmotion.exporter.lottie_v2 import build_lottie

        return build_lottie(self, title=title)

    def to_svg(self, *, title: str = "ArchMotion Scene") -> str:
        """Export the scene as an animated SVG string. Lazy import."""
        self._ensure_constructed()
        self._prepare()
        from archmotion.exporter.svg_v2 import build_svg

        return build_svg(self, title=title)

    def to_html(self, *, title: str = "ArchMotion Animation") -> str:
        """Export the scene as a self-contained interactive HTML player string."""
        self._ensure_constructed()
        self._prepare()
        from archmotion.exporter.html_v2 import build_html

        return build_html(self, title=title)

    def to_layout_dict(self) -> dict[str, Any]:
        """Return resolved layout + node/connection metadata as plain dicts.

        Works without recorded animations (topology only). Returns fully
        JSON-serializable data for the ArchMotion Studio canvas.
        """
        self._ensure_constructed()

        from archmotion._types import PrimitiveType
        from archmotion.domains.architecture.connections import Connection as ArchConn
        from archmotion.domains.architecture.primitives import Node as ArchNode
        from archmotion.layout.resolver import resolve_layout

        nodes = [g for g in self.all_graphics() if isinstance(g, ArchNode)]
        conns = [g for g in self.all_graphics() if isinstance(g, ArchConn)]
        w, h = self.resolution
        layout = resolve_layout(nodes, conns, w, h)

        nodes_out: dict[str, Any] = {}
        for node in nodes:
            box = layout.node_boxes.get(node.id)
            if box is None:
                continue
            ptype = getattr(node, "primitive_type", None)
            type_name = ptype.name.lower() if isinstance(ptype, PrimitiveType) else "node"
            nodes_out[node.id] = {
                "label": node.label,
                "type": type_name,
                "x": box.x,
                "y": box.y,
                "w": box.width,
                "h": box.height,
            }

        conns_out: dict[str, Any] = {}
        for conn in conns:
            route = layout.connection_routes.get(conn.id, [])
            conns_out[conn.id] = {
                "source": conn.source.id,
                "target": conn.target.id,
                "label": conn.label,
                "route": [[float(p[0]), float(p[1])] for p in route],
            }

        return {
            "canvas": [layout.canvas_width, layout.canvas_height],
            "nodes": nodes_out,
            "connections": conns_out,
        }


def _register_targets(scene: Scene, anim: Animation) -> None:
    """Ensure an animation's target graphics are indexed in the scene."""
    for g in anim.targets():
        if g.id not in scene._index:
            scene.add(g)
        for descendant in _walk(g):
            scene._index.setdefault(descendant.id, descendant)


def _theme_with_bg(theme: ThemeConfig, background_color: str) -> ThemeConfig:
    """Return a copy of ``theme`` with an overridden background color."""
    rgba = color_to_rgba01(background_color)
    return ThemeConfig(**{**theme.__dict__, "background_rgba": rgba})


def _walk(graphic: Graphic) -> list[Graphic]:
    """Pre-order traversal of a graphic and its descendants."""
    out = [graphic]
    for child in graphic.children:
        out.extend(_walk(child))
    return out


def _to_animation(item: object) -> Animation:
    """Coerce an animation builder and reject unsupported play arguments."""
    from archmotion.animation.base import Animation

    if isinstance(item, Animation):
        return item
    build = getattr(item, "build", None)
    if callable(build):
        animation = build()
        if isinstance(animation, Animation):
            return animation
    raise TypeError("Scene.play() arguments must be Animation instances or animation builders")


def _make_progress(
    show_progress: bool,
    on_progress: Callable[[int, int], None] | None,
) -> Callable[[int, int], None] | None:
    """Build a progress callback, honouring an explicit one over ``show_progress``."""
    if on_progress is not None:
        return on_progress
    if not show_progress:
        return None

    def _cb(completed: int, total: int) -> None:
        pct = int(completed * 100 / total) if total else 0
        print(f"\rRendering: {completed}/{total} frames ({pct}%)", end="", file=sys.stderr)

    return _cb
