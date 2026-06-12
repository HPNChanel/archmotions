"""Scene — The central orchestrator of the ArchMotion pipeline.

Architectural Note:
    Scene is the user's primary entry point. It orchestrates all 4 Phases:
    1. Collects topology (Nodes, Connections) in Phase 1
    2. Delegates layout resolution to Phase 2
    3. Compiles timeline from play() calls in Phase 3
    4. Dispatches rendering to Phase 4

    The Scene object uses a Virtual Clock to manage sequential/concurrent
    animation timing without any async primitives — pure arithmetic on
    timestamps.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Iterator, Literal

from archmotion.constants import DEFAULT_FPS, DEFAULT_RESOLUTION, RESOLUTION_MAP
from archmotion.errors import EmptyTimelineError, TimelineError
from archmotion.exporter.pool import export_video
from archmotion.layout.resolver import resolve_layout
from archmotion.renderer.theme import get_theme
from archmotion.timeline.compiler import compile_timeline

if TYPE_CHECKING:
    from archmotion.api.connections import Connection
    from archmotion.api.primitives import Node


class Scene:
    """The central orchestrator — collects topology, records animations, dispatches render.

    Args:
        resolution: Video resolution preset ('720p', '1080p', '1440p', '4k').
        fps: Frame rate (24, 30, or 60).
        theme: Color theme name (MVP: only 'dark_terminal').
        background_color: Override theme background (hex or CSS color).

    Example:
        >>> scene = Scene(resolution="1080p", fps=60, theme="dark_terminal")
        >>> # ... add nodes, connections, animations ...
        >>> scene.render("output.mp4")
    """

    def __init__(
        self,
        resolution: Literal["720p", "1080p", "1440p", "4k"] = DEFAULT_RESOLUTION,
        fps: Literal[24, 30, 60] = DEFAULT_FPS,
        theme: str = "dark_terminal",
        background_color: str | None = None,
    ) -> None:
        if resolution not in RESOLUTION_MAP:
            msg = f"Invalid resolution '{resolution}'. Choose from: {list(RESOLUTION_MAP.keys())}"
            raise ValueError(msg)

        self._resolution = resolution
        self._canvas_width, self._canvas_height = RESOLUTION_MAP[resolution]
        self._fps = fps
        self._theme = theme
        self._background_color = background_color

        # Phase 1: Collected scene objects
        self._nodes: list[Node] = []
        self._connections: list[Connection] = []

        # Phase 3: Timeline state
        self._play_calls: list[dict[str, object]] = []
        self._current_time: float = 0.0
        self._concurrent_stack: list[float] = []
        self._is_rendered: bool = False

    # ──────────────────────────────────────────
    # Phase 1: Topology Registration
    # ──────────────────────────────────────────

    def add_node(self, node: Node) -> None:
        """Register a node in the scene graph.

        Args:
            node: The Node or Database to add.

        Note:
            In the current MVP, nodes are auto-registered when used
            in Connection or Animation constructors. This method is
            available for explicit registration.
        """
        self._nodes.append(node)

    def add_connection(self, connection: Connection) -> None:
        """Register a connection in the scene graph.

        Args:
            connection: The Connection to add.
        """
        self._connections.append(connection)

    # ──────────────────────────────────────────
    # Phase 3: Choreography (Timeline)
    # ──────────────────────────────────────────

    def play(self, animation: object, duration: float | None = None) -> None:
        """Record an animation onto the timeline.

        In sequential mode (default), this animation starts after the
        previous one ends. Inside a `concurrent()` block, it starts
        at the block's entry time.

        Args:
            animation: An Animation object (FadeIn, Transfer, Pulse, etc.).
            duration: Override the animation's default duration.

        Raises:
            TimelineError: If called after render().
        """
        if self._is_rendered:
            raise TimelineError("Cannot add animations after render() has been called.")

        effective_duration = duration if duration is not None else getattr(animation, "duration", 1.0)

        start_time = (
            self._concurrent_stack[-1]
            if self._concurrent_stack
            else self._current_time
        )

        self._play_calls.append({
            "animation": animation,
            "start_time": start_time,
            "duration": effective_duration,
        })

        if self._concurrent_stack:
            # In concurrent mode: don't advance clock per play(),
            # but track the max duration for block exit
            pass
        else:
            # Sequential mode: advance clock
            self._current_time += effective_duration

    @contextmanager
    def concurrent(self) -> Iterator[None]:
        """Context manager for concurrent animation execution.

        All play() calls inside this block start at the same timestamp.
        On exit, the clock advances by the longest animation duration.

        Example:
            >>> with scene.concurrent():
            ...     scene.play(FadeIn(node_a))
            ...     scene.play(FadeIn(node_b))
            # Both FadeIn start simultaneously

        Yields:
            None
        """
        saved_time = self._current_time
        self._concurrent_stack.append(saved_time)

        # Snapshot play_calls count to find what was added inside the block
        snapshot_count = len(self._play_calls)

        try:
            yield
        finally:
            self._concurrent_stack.pop()

            # Calculate max duration of actions added in this block
            block_calls = self._play_calls[snapshot_count:]
            if block_calls:
                max_duration = max(
                    float(call["duration"]) for call in block_calls
                )
                self._current_time = saved_time + max_duration
            else:
                # Empty concurrent block — no time advance
                self._current_time = saved_time

    def wait(self, duration: float = 1.0) -> None:
        """Pause the timeline without any animation.

        Args:
            duration: Seconds to hold the current state.

        Raises:
            ValueError: If duration <= 0.
        """
        if duration <= 0:
            msg = f"Wait duration must be positive, got {duration}"
            raise ValueError(msg)
        self._current_time += duration

    # ──────────────────────────────────────────
    # Phase 4: Render Dispatch
    # ──────────────────────────────────────────

    def render(
        self,
        output_file: str = "output.mp4",
        on_progress: object | None = None,
        show_progress: bool = True,
    ) -> Path:
        """Execute the full 4-Phase Pipeline and produce a video file.

        This method:
        1. Validates the SceneGraph (Phase 1 → Gate 1→2)
        2. Resolves layout coordinates (Phase 2 → Gate 2→3)
        3. Compiles the timeline (Phase 3 → Gate 3→4)
        4. Renders frames and pipes to FFmpeg (Phase 4)

        Args:
            output_file: Path for the output MP4 file.
            on_progress: Optional callback (frames_done, total_frames) -> None.
            show_progress: If True and no callback, show Rich progress bar.

        Returns:
            Path to the created video file.

        Raises:
            EmptyTimelineError: If no animations were recorded.
            TopologyError: If the scene graph is invalid.
            LayoutError: If coordinates cannot be resolved.
            RenderError: If rendering or encoding fails.
        """
        if not self._play_calls:
            raise EmptyTimelineError()

        # Ensure .mp4 extension
        if not output_file.endswith(".mp4"):
            output_file += ".mp4"

        output_path = Path(output_file)
        self._is_rendered = True

        # ── Phase 1: Collect Topology ──
        # Auto-discover nodes from animations + connections
        all_nodes, all_connections = self._collect_topology()

        # ── Phase 2: Layout Resolution ──
        layout = resolve_layout(
            nodes=all_nodes,
            connections=all_connections,
            canvas_width=self._canvas_width,
            canvas_height=self._canvas_height,
        )

        # ── Phase 3: Timeline Compilation ──
        timeline = compile_timeline(
            play_calls=self._play_calls,
            total_duration=self._current_time,
            fps=self._fps,
        )

        # ── Phase 4: Render + Export ──
        # Build metadata dicts for the renderer
        node_labels = {n.id: n.label for n in all_nodes}
        node_types = {n.id: n.primitive_type for n in all_nodes}
        conn_labels = {c.id: c.label for c in all_connections}

        # Auto-wire Rich progress bar when no callback provided
        if on_progress is None and show_progress:
            from archmotion.dx._progress import RenderProgress

            with RenderProgress() as progress_cb:
                result = export_video(
                    timeline=timeline,
                    layout=layout,
                    theme=get_theme(self._theme),
                    node_labels=node_labels,
                    node_types=node_types,
                    connection_labels=conn_labels,
                    output_path=output_path,
                    on_progress=progress_cb,
                )
        else:
            result = export_video(
                timeline=timeline,
                layout=layout,
                theme=get_theme(self._theme),
                node_labels=node_labels,
                node_types=node_types,
                connection_labels=conn_labels,
                output_path=output_path,
                on_progress=on_progress,  # type: ignore[arg-type]
            )

        return result.output_path

    # ──────────────────────────────────────────
    # Internal: Topology Discovery
    # ──────────────────────────────────────────

    def _collect_topology(self) -> tuple[list[Node], list[Connection]]:
        """Collect all unique Nodes and Connections from the scene.

        Sources:
            1. Explicitly added via add_node() / add_connection()
            2. Referenced in animations (FadeIn/FadeOut targets, Transfer connections)

        Returns:
            (unique_nodes, unique_connections)
        """
        from archmotion.api.connections import Connection as ConnType
        from archmotion.api.primitives import Node as NodeType
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

        seen_node_ids: set[str] = set()
        seen_conn_ids: set[str] = set()
        nodes: list[Node] = []
        connections: list[Connection] = []

        def _register_node(node: NodeType) -> None:
            if node.id not in seen_node_ids:
                seen_node_ids.add(node.id)
                nodes.append(node)

        def _register_connection(conn: ConnType) -> None:
            if conn.id not in seen_conn_ids:
                seen_conn_ids.add(conn.id)
                connections.append(conn)
                # Also register source/target nodes
                _register_node(conn.source)
                _register_node(conn.target)

        # From explicit registrations
        for node in self._nodes:
            _register_node(node)
        for conn in self._connections:
            _register_connection(conn)

        # From animations
        for call in self._play_calls:
            anim = call["animation"]
            if isinstance(anim, (FadeIn, FadeOut)):
                for target in anim.targets:
                    if isinstance(target, NodeType):
                        _register_node(target)
            elif isinstance(anim, Transfer):
                # Transfer.connection is Connection | list[Connection]
                conn_obj = anim.connection
                conn_list = conn_obj if isinstance(conn_obj, list) else [conn_obj]
                for conn in conn_list:
                    _register_connection(conn)
            elif isinstance(anim, (Pulse, Highlight, ColorShift, ScaleUp, ScaleDown)):
                # All single-target animations
                _register_node(anim.target)

        return nodes, connections

    # ──────────────────────────────────────────
    # Properties
    # ──────────────────────────────────────────

    @property
    def resolution(self) -> str:
        """Current resolution preset name."""
        return self._resolution

    @property
    def fps(self) -> int:
        """Frame rate."""
        return self._fps

    @property
    def canvas_size(self) -> tuple[int, int]:
        """Canvas dimensions as (width, height) in pixels."""
        return (self._canvas_width, self._canvas_height)

    @property
    def total_duration(self) -> float:
        """Total timeline duration in seconds."""
        return self._current_time
