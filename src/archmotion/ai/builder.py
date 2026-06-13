"""Scene Builder — converts validated SceneSpec into a Scene object.

Architectural Note:
    This module is the bridge between LLM-generated YAML and ArchMotion's
    Python API. It creates real Node/Connection/Animation objects from
    the validated Pydantic spec, performing ID resolution along the way.

    The builder follows a 4-phase process:
        1. Create nodes (id → Node mapping)
        2. Set relative positions (resolve anchor references)
        3. Create connections (resolve source/target node references)
        4. Execute choreography (play/wait/concurrent)

Security:
    All inputs are pre-validated by Pydantic. This module does NOT
    perform its own validation — it trusts the SceneSpec contract.
"""

from __future__ import annotations

from archmotion.ai.schema import (
    AnimationSpec,
    ConnectionSpec,
    NodeSpec,
    SceneSpec,
    StepSpec,
)
from archmotion.api.connections import Connection
from archmotion.api.primitives import Cache, Cloud, Database, Node, Queue, User
from archmotion.api.scene import Scene
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
    """Create a Node instance from a NodeSpec.

    Uses the type field to dispatch to the correct subclass.
    Cloud nodes get the optional provider field.
    """
    factory = _NODE_FACTORIES.get(spec.type, Node)

    if spec.type == "cloud" and spec.provider:
        return factory(label=spec.label, provider=spec.provider)

    return factory(label=spec.label)


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


def _build_animation(
    anim_spec: AnimationSpec,
    nodes: dict[str, Node],
    connections: dict[str, Connection],
) -> object:
    """Build an Animation object from an AnimationSpec.

    Args:
        anim_spec: Validated animation specification.
        nodes: Mapping of node_id → Node object.
        connections: Mapping of conn_id → Connection object.

    Returns:
        An animation instance (FadeIn, Transfer, etc.).

    Raises:
        ValueError: If referenced IDs cannot be resolved.
    """
    atype = anim_spec.type
    kwargs: dict = {}

    if anim_spec.duration is not None:
        kwargs["duration"] = anim_spec.duration

    # ── FadeIn / FadeOut ──
    if atype in ("fade_in", "fade_out"):
        targets_list: list = []
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
        return cls(*targets_list, **kwargs)

    # ── Transfer ──
    if atype == "transfer":
        conn_refs = anim_spec.connection
        if conn_refs is None:
            msg = "Transfer animation requires 'connection' field"
            raise ValueError(msg)

        if isinstance(conn_refs, list):
            conn_objs = [connections[c] for c in conn_refs]
        else:
            conn_objs = connections[conn_refs]

        if anim_spec.payload:
            kwargs["payload"] = anim_spec.payload
        if anim_spec.reverse:
            kwargs["reverse"] = True
        if anim_spec.packet_color:
            kwargs["packet_color"] = anim_spec.packet_color

        return Transfer(connection=conn_objs, **kwargs)

    # ── Pulse ──
    if atype == "pulse":
        target_node = nodes[anim_spec.target]
        if anim_spec.color:
            kwargs["color"] = anim_spec.color
        if anim_spec.intensity is not None:
            kwargs["intensity"] = anim_spec.intensity
        return Pulse(target=target_node, **kwargs)

    # ── Highlight ──
    if atype == "highlight":
        target_node = nodes[anim_spec.target]
        if anim_spec.color:
            kwargs["color"] = anim_spec.color
        if anim_spec.intensity is not None:
            kwargs["intensity"] = anim_spec.intensity
        return Highlight(target=target_node, **kwargs)

    # ── ColorShift ──
    if atype == "color_shift":
        target_node = nodes[anim_spec.target]
        if anim_spec.from_color:
            kwargs["from_color"] = anim_spec.from_color
        if anim_spec.to_color:
            kwargs["to_color"] = anim_spec.to_color
        return ColorShift(target=target_node, **kwargs)

    # ── ScaleUp ──
    if atype == "scale_up":
        target_node = nodes[anim_spec.target]
        if anim_spec.factor is not None:
            kwargs["factor"] = anim_spec.factor
        return ScaleUp(target=target_node, **kwargs)

    # ── ScaleDown ──
    if atype == "scale_down":
        target_node = nodes[anim_spec.target]
        if anim_spec.factor is not None:
            kwargs["factor"] = anim_spec.factor
        return ScaleDown(target=target_node, **kwargs)

    msg = f"Unknown animation type: {atype}"
    raise ValueError(msg)


# ──────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────


def build_scene(spec: SceneSpec) -> Scene:
    """Convert a validated SceneSpec into a fully-wired Scene.

    This is the core transformation function of the YAML AI Interface.
    It translates declarative YAML data into imperative Scene API calls.

    Args:
        spec: A validated SceneSpec (from Pydantic parsing).

    Returns:
        A fully-configured Scene ready for .render().

    Raises:
        ValueError: If any ID references cannot be resolved.
    """
    scene = Scene(resolution=spec.resolution, fps=spec.fps, theme=spec.theme)

    # ── Phase 1: Create nodes (id → Node mapping) ──
    nodes: dict[str, Node] = {}
    for node_spec in spec.nodes:
        node = _create_node(node_spec)
        nodes[node_spec.id] = node

    # ── Phase 2: Set relative positions ──
    for node_spec in spec.nodes:
        if node_spec.position is None:
            continue

        node = nodes[node_spec.id]
        anchor = nodes[node_spec.position.anchor]
        method_name = _DIRECTION_METHODS[node_spec.position.direction]
        method = getattr(node, method_name)
        method(anchor, distance=node_spec.position.distance)

    # ── Phase 3: Create connections ──
    connections: dict[str, Connection] = {}
    for conn_spec in spec.connections:
        src = nodes[conn_spec.source]
        tgt = nodes[conn_spec.target]
        conn = Connection(
            source=src,
            target=tgt,
            label=conn_spec.label,
            corner_radius=conn_spec.corner_radius,
        )
        connections[conn_spec.id] = conn

    # ── Phase 4: Execute choreography ──
    for step in spec.choreography:
        if step.action == "wait":
            scene.wait(duration=step.duration)

        elif step.action == "play":
            anim = _build_animation(step.animation, nodes, connections)
            play_kwargs: dict = {}
            if step.duration is not None:
                play_kwargs["duration"] = step.duration
            scene.play(anim, **play_kwargs)

        elif step.action == "concurrent":
            with scene.concurrent():
                for anim_spec in step.animations:
                    anim = _build_animation(anim_spec, nodes, connections)
                    scene.play(anim)

    return scene
