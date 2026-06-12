"""Connection — Directed edge between two Nodes.

Architectural Note:
    A Connection stores source/target references and optional user-provided
    waypoints. The actual routing path (pixel coordinates) is computed
    in Phase 2 by the Layout Resolver's Manhattan router.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from archmotion._types import PrimitiveType
from archmotion.api.primitives import Node
from archmotion.constants import MAX_CONNECTION_LABEL_LENGTH, Z_CONNECTION
from archmotion.errors import InvalidConnectionError


@dataclass
class Connection:
    """A directed edge (arrow) between two Nodes.

    Connections are rendered as orthogonal (Manhattan-style) polylines
    with an arrowhead at the target end.

    Args:
        source: The origin node.
        target: The destination node (must differ from source).
        label: Optional text label displayed on the connection line.
        waypoints: Optional list of (x, y) points to override auto-routing.

    Raises:
        InvalidConnectionError: If source and target are the same node.
        TypeError: If source or target is not a Node instance.

    Example:
        >>> conn = Connection(gateway, auth_service)
        >>> conn_with_label = Connection(auth, db, label="SQL Query")
    """

    source: Node
    target: Node
    label: str | None = None
    waypoints: list[tuple[float, float]] | None = None
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    primitive_type: PrimitiveType = field(default=PrimitiveType.CONNECTION, init=False)
    z_index: int = field(default=Z_CONNECTION, init=False)

    def __post_init__(self) -> None:
        """Validate connection constraints."""
        if not isinstance(self.source, Node):
            msg = f"Connection source must be a Node, got {type(self.source).__name__}"
            raise TypeError(msg)
        if not isinstance(self.target, Node):
            msg = f"Connection target must be a Node, got {type(self.target).__name__}"
            raise TypeError(msg)
        if self.source is self.target:
            raise InvalidConnectionError(
                f"Self-loop not supported: source and target are the same Node "
                f"('{self.source.label}')"
            )
        if self.label is not None:
            self.label = self.label.strip()
            if len(self.label) > MAX_CONNECTION_LABEL_LENGTH:
                msg = (
                    f"Connection label exceeds {MAX_CONNECTION_LABEL_LENGTH} characters: "
                    f"'{self.label[:20]}...'"
                )
                raise ValueError(msg)
