"""Scene Builder — converts a validated SceneSpec into a v2 Scene object.

Architectural Note:
    This module is the bridge between LLM-generated YAML and ArchMotion's v2
    Python API. It creates real architecture VMobjects (Node/Connection) and v2
    animations from the validated Pydantic spec, performing ID resolution along
    the way.

    The builder follows a 4-phase process:
        1. Create nodes (spec id → Node mapping)
        2. Set relative/absolute positions (resolve anchor references)
        3. Create connections (resolve source/target node references)
        4. Execute choreography (play/wait/concurrent)

Security:
    All inputs are pre-validated by Pydantic. This module does NOT perform its
    own validation — it trusts the SceneSpec contract.
"""

from __future__ import annotations

from typing import Any

from archmotion.ai.schema import (
    AbsolutePositionSpec,
    AnimationSpec,
    NodeSpec,
    SceneSpec,
)
from archmotion.animation import (
    Animation,
    AnimationGroup,
    ColorShift,
    FadeIn,
    FadeOut,
    Highlight,
    Pulse,
    Scale,
    Transfer,
)
from archmotion.constants import DEFAULT_SCALE_FACTOR
from archmotion.core.scene import Scene
from archmotion.domains.architecture.connections import Connection
from archmotion.domains.architecture.primitives import (
    Cache,
    Cloud,
    Database,
    Node,
    Queue,
    User,
)

# ──────────────────────────────────────────────
# Node Factory
# ──────────────────────────────────────────────

_NODE_FACTORIES: dict[str, type[Node]] = {
    "node": Node,
    "database": Database,
    "cloud": Cloud,
    "queue": Queue,
    "cache": Cache,
    "user": User,
}


def _create_node(spec: NodeSpec) -> Node:
    """Create a v2 architecture node instance from a NodeSpec."""
    factory = _NODE_FACTORIES.get(spec.type, Node)
    node = factory(label=spec.label)
    if spec.type == "cloud" and spec.provider:
        # Preserve the provider hint (v2 Cloud has no constructor param for it).
        node.provider = spec.provider  # type: ignore[attr-defined]
    return node


# ──────────────────────────────────────────────
# Direction Mapping
# ──────────────────────────────────────────────

_DIRECTION_METHODS = {
    "right_of": "right_of",
    "left_of": "left_of",
    "above": "above",
    "below": "below",
}


# ──────────────────────────────────────────────
# Animation Factory
# ──────────────────────────────────────────────


def _duration_kwargs(anim_spec: AnimationSpec) -> dict[str, Any]:
    """Return ``{duration: ...}`` if the spec sets a duration, else empty."""
    if anim_spec.duration is not None:
        return {"duration": anim_spec.duration}
    return {}


def _build_animation(
    anim_spec: AnimationSpec,
    nodes: dict[str, Node],
    connections: dict[str, Connection],
) -> Animation:
    """Build a v2 Animation object from an AnimationSpec.

    Args:
        anim_spec: Validated animation specification.
        nodes: Mapping of node_id → Node object.
        connections: Mapping of conn_id → Connection object.

    Returns:
        A v2 animation instance (FadeIn, Transfer, etc.).

    Raises:
        ValueError: If referenced IDs cannot be resolved.
    """
    atype = anim_spec.type
    kw = _duration_kwargs(anim_spec)

    # ── FadeIn / FadeOut ──
    if atype in ("fade_in", "fade_out"):
        targets_list: list[object] = []
        if anim_spec.targets:
            for tid in anim_spec.targets:
                if tid in nodes:
                    targets_list.append(nodes[tid])
                elif tid in connections:
                    targets_list.append(connections[tid])
                else:
                    msg = f"Unknown target '{tid}' in {atype}"
                    raise ValueError(msg)

        cls = FadeIn if atype == "fade_in" else FadeOut
        return cls(*targets_list, **kw)  # type: ignore[arg-type]

    # ── Transfer ──
    if atype == "transfer":
        conn_refs = anim_spec.connection
        if conn_refs is None:
            msg = "Transfer animation requires 'connection' field"
            raise ValueError(msg)

        if isinstance(conn_refs, list):
            conn_objs = [connections[c] for c in conn_refs]
        else:
            conn_objs = [connections[conn_refs]]

        transfer_kw = dict(kw)
        if anim_spec.payload:
            transfer_kw["payload"] = anim_spec.payload
        if anim_spec.reverse:
            transfer_kw["reverse"] = True
        if anim_spec.packet_color:
            transfer_kw["color"] = anim_spec.packet_color

        if len(conn_objs) == 1:
            return Transfer(conn_objs[0], **transfer_kw)
        return AnimationGroup(*(Transfer(c, **transfer_kw) for c in conn_objs), lag_ratio=0.0)

    # ── Pulse ──
    if atype == "pulse":
        if anim_spec.target is None:
            msg = "pulse animation requires 'target' field"
            raise ValueError(msg)
        target_node = nodes[anim_spec.target]
        pulse_kw = dict(kw)
        if anim_spec.color:
            pulse_kw["color"] = anim_spec.color
        if anim_spec.intensity is not None:
            pulse_kw["intensity"] = anim_spec.intensity
        return Pulse(target_node, **pulse_kw)

    # ── Highlight ──
    if atype == "highlight":
        if anim_spec.target is None:
            msg = "highlight animation requires 'target' field"
            raise ValueError(msg)
        target_node = nodes[anim_spec.target]
        hl_kw = dict(kw)
        if anim_spec.intensity is not None:
            hl_kw["intensity"] = anim_spec.intensity
        return Highlight(target_node, **hl_kw)

    # ── ColorShift ──
    if atype == "color_shift":
        if anim_spec.target is None:
            msg = "color_shift animation requires 'target' field"
            raise ValueError(msg)
        target_node = nodes[anim_spec.target]
        cs_kw = dict(kw)
        if anim_spec.from_color:
            cs_kw["from_color"] = anim_spec.from_color
        if anim_spec.to_color:
            cs_kw["to_color"] = anim_spec.to_color
        return ColorShift(target_node, **cs_kw)

    # ── ScaleUp / ScaleDown ──
    if atype in ("scale_up", "scale_down"):
        if anim_spec.target is None:
            msg = "scale animation requires 'target' field"
            raise ValueError(msg)
        target_node = nodes[anim_spec.target]
        default = DEFAULT_SCALE_FACTOR if atype == "scale_up" else 1.0 / DEFAULT_SCALE_FACTOR
        factor = anim_spec.factor if anim_spec.factor is not None else default
        return Scale(target_node, factor, **kw)

    msg = f"Unknown animation type: {atype}"
    raise ValueError(msg)


# ──────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────


def build_scene(spec: SceneSpec) -> Scene:
    """Convert a validated SceneSpec into a fully-wired v2 Scene.

    Args:
        spec: A validated SceneSpec (from Pydantic parsing).

    Returns:
        A fully-configured v2 Scene ready for .render() / .export().

    Raises:
        ValueError: If any ID references cannot be resolved.
    """
    scene = Scene(resolution=spec.resolution, fps=spec.fps, theme=spec.theme)

    # ── Phase 1: Create nodes (spec id → Node mapping) ──
    nodes: dict[str, Node] = {}
    for node_spec in spec.nodes:
        nodes[node_spec.id] = _create_node(node_spec)

    # ── Phase 2: Set positions (relative or absolute) ──
    for node_spec in spec.nodes:
        if node_spec.position is None:
            continue

        node = nodes[node_spec.id]

        if isinstance(node_spec.position, AbsolutePositionSpec):
            node.at(node_spec.position.x, node_spec.position.y)
            continue

        anchor = nodes[node_spec.position.anchor]
        method = getattr(node, _DIRECTION_METHODS[node_spec.position.direction])
        method(anchor, distance=node_spec.position.distance)

    # ── Phase 3: Create connections ──
    connections: dict[str, Connection] = {}
    for conn_spec in spec.connections:
        src = nodes[conn_spec.source]
        tgt = nodes[conn_spec.target]
        connections[conn_spec.id] = Connection(
            source=src,
            target=tgt,
            label=conn_spec.label or "",
            corner_radius=conn_spec.corner_radius or 0.0,
        )

    # Explicitly register every node + connection on the Scene so the full
    # topology is available even before/without animations (e.g. so the visual
    # editor can call Scene.to_layout_dict() to read all node bounding boxes).
    for node in nodes.values():
        scene.add_node(node)
    for conn in connections.values():
        scene.add_connection(conn)

    # ── Phase 4: Execute choreography ──
    for step in spec.choreography:
        if step.action == "wait":
            if step.duration is not None:
                scene.wait(step.duration)

        elif step.action == "play":
            if step.animation is None:  # validated by schema; defensive
                continue
            anim = _build_animation(step.animation, nodes, connections)
            if step.duration is not None:
                scene.play(anim, duration=step.duration)
            else:
                scene.play(anim)

        elif step.action == "concurrent":
            anims = step.animations or []
            with scene.concurrent():
                for anim_spec in anims:
                    scene.play(_build_animation(anim_spec, nodes, connections))

    return scene
