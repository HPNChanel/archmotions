"""Pydantic v2 schema models for YAML AI Interface.

Architectural Note:
    These models define the contract between LLM-generated YAML and
    ArchMotion's Scene API. Every field has strict validation with
    human-readable error messages, designed to be fed back to LLMs
    for self-correction.

Security:
    - All string fields have max_length constraints.
    - Node/connection counts are bounded by constants.
    - No eval(), exec(), or dynamic code execution.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

from archmotion.constants import (
    MAX_CONNECTION_LABEL_LENGTH,
    MAX_CONNECTIONS,
    MAX_LABEL_LENGTH,
    MAX_NODES,
    MAX_PAYLOAD_LENGTH,
    RESOLUTION_MAP,
)
from archmotion.core.color import normalize_color
from archmotion.layout.bbox import estimate_text_bbox


class StrictModel(BaseModel):
    """Schema base that rejects misspelled or unsupported YAML fields."""

    model_config = ConfigDict(extra="forbid")


# ──────────────────────────────────────────────
# Position Spec
# ──────────────────────────────────────────────


class RelativePositionSpec(StrictModel):
    """Relative positioning for a node.

    Attributes:
        anchor: ID of the reference node.
        direction: Spatial relationship to anchor.
        distance: Spacing in grid units (1 unit = 80px).
    """

    anchor: str = Field(..., min_length=1, max_length=50)
    direction: Literal["right_of", "left_of", "above", "below"]
    distance: float = Field(default=3.0, ge=1.0, le=20.0)


class AbsolutePositionSpec(StrictModel):
    """Absolute (freeform) pixel positioning for a node.

    Used by the ArchMotion Studio visual editor. The coordinate origin is the
    top-left of the canvas (y grows downward), matching the SVG/Canvas space.
    The upper bound is validated against the scene resolution in ``SceneSpec``.

    Attributes:
        x: Left edge X coordinate in pixels (>= 0).
        y: Top edge Y coordinate in pixels (>= 0).
    """

    x: float = Field(..., ge=0.0)
    y: float = Field(..., ge=0.0)


# Union of supported position specs. Kept under the historical ``PositionSpec``
# name for backward compatibility (existing imports + YAML docs).
PositionSpec = RelativePositionSpec | AbsolutePositionSpec


# ──────────────────────────────────────────────
# Node Spec
# ──────────────────────────────────────────────

NODE_TYPES = Literal["node", "database", "cloud", "queue", "cache", "user"]


class NodeSpec(StrictModel):
    """A scene graph node (server, database, cloud service, etc.).

    Attributes:
        id: Unique identifier (referenced by connections and animations).
        label: Display text inside the node.
        type: Rendering shape type.
        provider: Cloud provider (only for type='cloud').
        position: Optional positioning — relative (anchor/direction/distance)
            or absolute (x/y pixels).
    """

    id: str = Field(..., min_length=1, max_length=50)
    label: str = Field(..., min_length=1, max_length=MAX_LABEL_LENGTH)
    type: NODE_TYPES = "node"
    provider: str | None = Field(default=None, max_length=20)
    position: PositionSpec | None = None

    @field_validator("provider")
    @classmethod
    def provider_only_for_cloud(cls, v: str | None, info: ValidationInfo) -> str | None:
        """Provider field is only meaningful for cloud nodes."""
        if v is not None and info.data.get("type") != "cloud":
            msg = "provider field is only valid when type='cloud'"
            raise ValueError(msg)
        return v


# ──────────────────────────────────────────────
# Connection Spec
# ──────────────────────────────────────────────


class ConnectionSpec(StrictModel):
    """A directional edge between two nodes.

    Attributes:
        id: Unique identifier (referenced by Transfer animations).
        source: ID of the source node.
        target: ID of the target node.
        label: Optional label displayed on the connection line.
        corner_radius: Override theme default for rounded corners (pixels).
    """

    id: str = Field(..., min_length=1, max_length=50)
    source: str = Field(..., min_length=1, max_length=50)
    target: str = Field(..., min_length=1, max_length=50)
    label: str | None = Field(default=None, max_length=MAX_CONNECTION_LABEL_LENGTH)
    corner_radius: float | None = Field(default=None, ge=0.0, le=50.0)

    @model_validator(mode="after")
    def no_self_loop(self) -> ConnectionSpec:
        """Connections cannot point to themselves."""
        if self.source == self.target:
            msg = f"Self-loop not allowed: source and target are both '{self.source}'"
            raise ValueError(msg)
        return self


# ──────────────────────────────────────────────
# Animation Spec
# ──────────────────────────────────────────────

ANIMATION_TYPES = Literal[
    "fade_in",
    "fade_out",
    "transfer",
    "pulse",
    "highlight",
    "color_shift",
    "scale_up",
    "scale_down",
]


class AnimationSpec(StrictModel):
    """A single animation action.

    Fields are flexible — different animation types use different subsets.
    Validation is performed during Scene building, not here.

    Attributes:
        type: Animation type discriminator.
        targets: Node/Connection IDs (for fade_in, fade_out).
        target: Single Node ID (for pulse, highlight, color_shift, scale).
        connection: Connection ID(s) (for transfer).
        duration: Override default duration (seconds).
        payload: Packet label text (transfer only).
        color: Effect color (pulse, highlight).
        from_color: Start color hex (color_shift).
        to_color: End color hex (color_shift).
        factor: Scale factor (scale_up, scale_down).
        intensity: Glow intensity (pulse, highlight).
        reverse: Reverse direction (transfer).
        packet_color: Packet color override (transfer).
    """

    type: ANIMATION_TYPES
    targets: list[str] | None = None
    target: str | None = None
    connection: str | list[str] | None = None
    duration: float | None = Field(default=None, ge=0.1, le=60.0)
    payload: str | None = Field(default=None, max_length=MAX_PAYLOAD_LENGTH)
    color: str | None = Field(default=None, max_length=20)
    from_color: str | None = Field(default=None, max_length=10)
    to_color: str | None = Field(default=None, max_length=10)
    factor: float | None = Field(default=None, ge=0.1, le=3.0)
    intensity: float | None = Field(default=None, ge=0.0, le=1.0)
    reverse: bool = False
    packet_color: str | None = Field(default=None, max_length=20)

    @field_validator("color", "from_color", "to_color", "packet_color")
    @classmethod
    def validate_hex_color(cls, value: str | None) -> str | None:
        """Reject colors the renderer would otherwise silently turn white."""
        if value is None:
            return None
        return normalize_color(value)


# ──────────────────────────────────────────────
# Choreography Step
# ──────────────────────────────────────────────


class StepSpec(StrictModel):
    """A single choreography step.

    Actions:
        - 'play': Execute a single animation.
        - 'wait': Pause the timeline.
        - 'concurrent': Execute multiple animations simultaneously.

    Attributes:
        action: Step type discriminator.
        animation: Single animation (for 'play').
        animations: Multiple animations (for 'concurrent').
        duration: Wait duration (for 'wait') or override duration.
    """

    action: Literal["play", "wait", "concurrent"]
    animation: AnimationSpec | None = None
    animations: list[AnimationSpec] | None = None
    duration: float | None = Field(default=None, ge=0.1, le=60.0)

    @model_validator(mode="after")
    def validate_action_fields(self) -> StepSpec:
        """Ensure correct fields are set for each action type."""
        if self.action == "play" and self.animation is None:
            msg = "action='play' requires 'animation' field"
            raise ValueError(msg)
        if self.action == "concurrent" and not self.animations:
            msg = "action='concurrent' requires non-empty 'animations' list"
            raise ValueError(msg)
        if self.action == "wait" and self.duration is None:
            msg = "action='wait' requires 'duration' field"
            raise ValueError(msg)
        return self


# ──────────────────────────────────────────────
# Root Scene Spec
# ──────────────────────────────────────────────


class SceneSpec(StrictModel):
    """Root YAML schema for an ArchMotion scene.

    This is the top-level model that LLMs should generate.

    Attributes:
        version: Schema version. 2.0 is canonical; 1.0 remains readable.
        resolution: Video resolution preset.
        fps: Frame rate.
        nodes: List of scene graph nodes.
        connections: List of connections between nodes.
        choreography: Ordered list of animation steps.
    """

    version: Literal["1.0", "2.0"] = "2.0"
    theme: str = Field(default="dark_terminal", max_length=30)
    resolution: Literal["720p", "1080p", "1440p", "4k"] = "1080p"
    fps: int = Field(default=60, ge=15, le=120)
    nodes: list[NodeSpec] = Field(..., min_length=1)
    connections: list[ConnectionSpec] = Field(default_factory=list)
    choreography: list[StepSpec] = Field(..., min_length=1)

    @model_validator(mode="after")
    def validate_limits(self) -> SceneSpec:
        """Enforce security limits on node/connection counts."""
        if len(self.nodes) > MAX_NODES:
            msg = f"Too many nodes: {len(self.nodes)} (max {MAX_NODES})"
            raise ValueError(msg)
        if len(self.connections) > MAX_CONNECTIONS:
            msg = f"Too many connections: {len(self.connections)} (max {MAX_CONNECTIONS})"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def validate_unique_ids(self) -> SceneSpec:
        """Ensure all node and connection IDs are unique."""
        node_ids = [n.id for n in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            dupes = [x for x in node_ids if node_ids.count(x) > 1]
            msg = f"Duplicate node IDs: {set(dupes)}"
            raise ValueError(msg)

        conn_ids = [c.id for c in self.connections]
        if len(conn_ids) != len(set(conn_ids)):
            dupes = [x for x in conn_ids if conn_ids.count(x) > 1]
            msg = f"Duplicate connection IDs: {set(dupes)}"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def validate_references(self) -> SceneSpec:
        """Ensure all referenced IDs exist."""
        node_ids = {n.id for n in self.nodes}
        conn_ids = {c.id for c in self.connections}

        # Connection source/target must reference existing nodes
        for conn in self.connections:
            if conn.source not in node_ids:
                msg = f"Connection '{conn.id}' references unknown source node '{conn.source}'"
                raise ValueError(msg)
            if conn.target not in node_ids:
                msg = f"Connection '{conn.id}' references unknown target node '{conn.target}'"
                raise ValueError(msg)

        # Position anchors must reference existing nodes (relative positions only).
        # Absolute positions carry no anchor reference.
        for node in self.nodes:
            if isinstance(node.position, RelativePositionSpec) and (
                node.position.anchor not in node_ids
            ):
                msg = (
                    f"Node '{node.id}' position references unknown anchor '{node.position.anchor}'"
                )
                raise ValueError(msg)

        # Animation targets must reference existing nodes/connections
        all_ids = node_ids | conn_ids
        for step in self.choreography:
            anims = []
            if step.animation:
                anims.append(step.animation)
            if step.animations:
                anims.extend(step.animations)

            for anim in anims:
                if anim.targets:
                    for t in anim.targets:
                        if t not in all_ids:
                            msg = f"Animation references unknown target '{t}'"
                            raise ValueError(msg)
                if anim.target and anim.target not in node_ids:
                    msg = f"Animation references unknown target node '{anim.target}'"
                    raise ValueError(msg)
                if anim.connection:
                    refs = (
                        anim.connection if isinstance(anim.connection, list) else [anim.connection]
                    )
                    for ref in refs:
                        if ref not in conn_ids:
                            msg = f"Animation references unknown connection '{ref}'"
                            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def validate_absolute_positions(self) -> SceneSpec:
        """Ensure absolute positions fit within the scene's canvas bounds.

        Absolute coordinates denote a node's top-left corner; they must leave
        room for the (estimated) node size, so the upper bound uses the full
        canvas dimension as a hard limit.
        """
        canvas_w, canvas_h = RESOLUTION_MAP[self.resolution]
        for node in self.nodes:
            if not isinstance(node.position, AbsolutePositionSpec):
                continue
            node_w, node_h = estimate_text_bbox(node.label)
            if node.position.x + node_w > canvas_w or node.position.y + node_h > canvas_h:
                msg = (
                    f"Node '{node.id}' absolute position "
                    f"({node.position.x}, {node.position.y}) exceeds canvas "
                    f"bounds ({canvas_w}x{canvas_h})"
                )
                raise ValueError(msg)
        return self
