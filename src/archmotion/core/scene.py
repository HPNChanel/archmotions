"""Scene — the v2.0 authoring surface (virtual clock + play/wait + exports).

A :class:`Scene` holds a scene graph of :class:`~archmotion.core.graphic.Graphic`
objects, a virtual clock, and an accumulated parametric timeline. ``play``
compiles animations into actions (advancing the clock); ``wait`` pads time.
Rendering/exporting is delegated lazily to ``archmotion.render`` /
``archmotion.exporter`` so the core stays renderer-agnostic.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from archmotion.core.camera import Camera
from archmotion.core.property import CompiledTimeline, MorphAction, PropertyAction

if TYPE_CHECKING:
    from archmotion.animation.base import Animation
    from archmotion.core.graphic import Graphic
    from archmotion.renderer.theme import ThemeConfig

DEFAULT_FPS = 30
DEFAULT_RESOLUTION = (1280, 720)


class Scene:
    """A composition of graphics animated over a virtual timeline."""

    def __init__(
        self,
        *,
        fps: int = DEFAULT_FPS,
        resolution: tuple[int, int] | None = None,
        camera: Camera | None = None,
        theme: ThemeConfig | None = None,
    ) -> None:
        """Initialize resolution, camera, fps, theme and empty scene graph + clock."""
        self.fps = fps
        self.resolution = resolution if resolution is not None else DEFAULT_RESOLUTION
        self.camera = camera if camera is not None else Camera(*self.resolution)
        self.theme = theme
        self._roots: list[Graphic] = []
        self._index: dict[str, Graphic] = {}
        self._actions: list[PropertyAction | MorphAction] = []
        self._clock: float = 0.0

    # ── scene graph ──────────────────────────────────────────────

    @property
    def graphics(self) -> list[Graphic]:
        """Root-level graphics (see :meth:`all_graphics` for the full tree)."""
        return list(self._roots)

    @property
    def clock(self) -> float:
        """Current virtual time (seconds)."""
        return self._clock

    def add(self, *graphics: Graphic) -> Scene:
        """Register graphics in the scene."""
        for g in graphics:
            self._roots.append(g)
            for descendant in _walk(g):
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

    # ── timeline authoring ───────────────────────────────────────

    def play(
        self,
        *animations: Animation,
        run_time: float | None = None,
        lag_ratio: float | None = None,
    ) -> Scene:
        """Play animations at the current clock, then advance the clock."""
        from archmotion.animation.base import AnimationGroup

        if not animations:
            msg = "play() requires at least one animation."
            raise TypeError(msg)
        normalized = [_to_animation(a) for a in animations]
        if len(normalized) == 1 and run_time is None and lag_ratio is None:
            anim = normalized[0]
        else:
            anim = AnimationGroup(
                *normalized,
                lag_ratio=lag_ratio if lag_ratio is not None else 0.0,
                run_time=run_time,
            )

        for g in anim.targets():
            if g.id not in self._index:
                self.add(g)
            for descendant in _walk(g):
                self._index.setdefault(descendant.id, descendant)

        anim.begin()
        start = self._clock
        self._actions.extend(anim.compile(start))
        self._clock += anim.run_time
        anim.finish()
        return self

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

    # ── export hooks (lazy) ──────────────────────────────────────

    def resolve(self) -> dict[str, object]:
        """Return the resolved scene (graphics + timeline) for inspection."""
        return {
            "graphics": self.all_graphics(),
            "timeline": self.compile_timeline(),
            "camera": self.camera,
        }

    def render(self, output_path: str, *, fps: int | None = None, crf: int = 20) -> str:
        """Render the scene to a video file (MP4). Lazy import of the renderer."""
        from archmotion.render.frame import render_scene

        return render_scene(self, output_path, fps=fps, crf=crf)

    def to_lottie(self, *, title: str = "ArchMotion") -> dict[str, Any]:
        """Export the scene as a Lottie dict. Lazy import."""
        from archmotion.exporter.lottie_v2 import build_lottie

        return build_lottie(self, title=title)

    def to_svg(self, *, title: str = "ArchMotion Scene") -> str:
        """Export the scene as an animated SVG string. Lazy import."""
        from archmotion.exporter.svg_v2 import build_svg

        return build_svg(self, title=title)


def _walk(graphic: Graphic) -> list[Graphic]:
    """Pre-order traversal of a graphic and its descendants."""
    out = [graphic]
    for child in graphic.children:
        out.extend(_walk(child))
    return out


def _to_animation(item: object) -> Animation:
    """Coerce an :class:`AnimateBuilder` into its built :class:`Animation`."""
    from typing import cast

    from archmotion.core.graphic import AnimateBuilder

    if isinstance(item, AnimateBuilder):
        return item.build()
    return cast("Animation", item)
