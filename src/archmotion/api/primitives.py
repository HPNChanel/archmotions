"""Scene Graph Primitives — Node, Database, Cloud, Queue, Cache, User.

Architectural Note:
    Primitives are Phase 1 data objects. They store topology (relative
    positioning) but perform NO rendering. Phase 2 (Layout Resolver)
    converts these into pixel coordinates.

    The fluent API (.right_of(), .below()) returns Self for chaining.
    Each Node may only have ONE positioning call — calling a second
    raises TopologyError.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Self

from archmotion._types import Direction, PrimitiveType
from archmotion.constants import (
    DEFAULT_DISTANCE,
    MAX_DISTANCE,
    MAX_LABEL_LENGTH,
    MIN_DISTANCE,
    Z_NODE,
)
from archmotion.errors import TopologyError


@dataclass
class RelativePosition:
    """Records a spatial relationship between two nodes.

    Attributes:
        anchor_id: ID of the reference node.
        direction: Which side of the anchor this node sits on.
        distance: Distance in grid units (converted to pixels in Phase 2).
    """

    anchor_id: str
    direction: Direction
    distance: float


@dataclass
class Node:
    """A rectangular box representing a server, service, or component.

    This is the primary building block of an ArchMotion scene.
    Nodes are positioned relative to each other using the fluent API.

    Args:
        label: Display text inside the node (1-50 characters).
        icon: Optional icon identifier (MVP: text-only, reserved for v0.2.0).

    Example:
        >>> gateway = Node("API Gateway")
        >>> auth = Node("Auth Service").right_of(gateway, distance=3)
    """

    label: str
    icon: str | None = None
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    primitive_type: PrimitiveType = field(default=PrimitiveType.NODE, init=False)
    position: RelativePosition | None = field(default=None, init=False, repr=False)
    z_index: int = field(default=Z_NODE, init=False)

    def __post_init__(self) -> None:
        """Validate label on construction."""
        if not self.label or not self.label.strip():
            msg = "Node label must not be empty."
            raise ValueError(msg)
        self.label = self.label.strip()
        if len(self.label) > MAX_LABEL_LENGTH:
            msg = f"Node label exceeds {MAX_LABEL_LENGTH} characters: '{self.label[:20]}...'"
            raise ValueError(msg)

    def _set_position(self, anchor: Node, direction: Direction, distance: float) -> Self:
        """Internal: set relative position. Raises if already positioned."""
        if self.position is not None:
            msg = (
                f"Node '{self.label}' already has a position "
                f"(relative to '{self.position.anchor_id}'). "
                "Each Node can only be positioned once."
            )
            raise TopologyError(msg)
        if not MIN_DISTANCE <= distance <= MAX_DISTANCE:
            msg = f"Distance must be between {MIN_DISTANCE} and {MAX_DISTANCE}, got {distance}"
            raise ValueError(msg)
        self.position = RelativePosition(
            anchor_id=anchor.id,
            direction=direction,
            distance=distance,
        )
        return self

    def right_of(self, anchor: Node, distance: float = DEFAULT_DISTANCE) -> Self:
        """Position this node to the right of the anchor node.

        Args:
            anchor: The reference node.
            distance: Spacing in grid units (1 unit = GRID_UNIT pixels).

        Returns:
            Self for method chaining.

        Raises:
            TopologyError: If this node already has a position.
            ValueError: If distance is out of valid range.
        """
        return self._set_position(anchor, Direction.RIGHT_OF, distance)

    def left_of(self, anchor: Node, distance: float = DEFAULT_DISTANCE) -> Self:
        """Position this node to the left of the anchor node.

        Args:
            anchor: The reference node.
            distance: Spacing in grid units.

        Returns:
            Self for method chaining.
        """
        return self._set_position(anchor, Direction.LEFT_OF, distance)

    def below(self, anchor: Node, distance: float = 2.0) -> Self:
        """Position this node below the anchor node.

        Args:
            anchor: The reference node.
            distance: Spacing in grid units.

        Returns:
            Self for method chaining.
        """
        return self._set_position(anchor, Direction.BELOW, distance)

    def above(self, anchor: Node, distance: float = 2.0) -> Self:
        """Position this node above the anchor node.

        Args:
            anchor: The reference node.
            distance: Spacing in grid units.

        Returns:
            Self for method chaining.
        """
        return self._set_position(anchor, Direction.ABOVE, distance)


@dataclass
class Database(Node):
    """A cylinder-shaped node representing a database or storage.

    Inherits all positioning methods from Node.
    The only difference is the rendering shape (cylinder vs rectangle).

    Args:
        label: Display text inside the database.

    Example:
        >>> db = Database("PostgreSQL").below(auth_service, distance=2)
    """

    def __post_init__(self) -> None:
        """Set primitive type to DATABASE after parent validation."""
        super().__post_init__()
        self.primitive_type = PrimitiveType.DATABASE


@dataclass
class Cloud(Node):
    """A cloud-shaped node representing an external/cloud service.

    Used for AWS, GCP, Azure services, CDNs, or any external dependency.
    Rendered as a cloud contour (3-arc humps on top, flat bottom).

    Args:
        label: Display text inside the cloud.
        provider: Optional cloud provider identifier ('aws', 'gcp', 'azure').

    Example:
        >>> s3 = Cloud("S3 Bucket", provider="aws").right_of(api, distance=3)
    """

    provider: str | None = None

    def __post_init__(self) -> None:
        """Set primitive type to CLOUD after parent validation."""
        super().__post_init__()
        self.primitive_type = PrimitiveType.CLOUD


@dataclass
class Queue(Node):
    """A parallelogram-shaped node representing a message queue.

    Used for Kafka, RabbitMQ, SQS, or any async messaging system.
    Rendered as a skewed rectangle with directional arrows.

    Args:
        label: Display text inside the queue.

    Example:
        >>> mq = Queue("Kafka").below(api_gateway, distance=2)
    """

    def __post_init__(self) -> None:
        """Set primitive type to QUEUE after parent validation."""
        super().__post_init__()
        self.primitive_type = PrimitiveType.QUEUE


@dataclass
class Cache(Node):
    """A diamond-shaped node representing a cache layer.

    Used for Redis, Memcached, or any in-memory cache/store.
    Rendered as a rotated square (diamond shape).

    Args:
        label: Display text inside the cache.

    Example:
        >>> redis = Cache("Redis").right_of(auth, distance=2)
    """

    def __post_init__(self) -> None:
        """Set primitive type to CACHE after parent validation."""
        super().__post_init__()
        self.primitive_type = PrimitiveType.CACHE


@dataclass
class User(Node):
    """A person-icon node representing a human actor or client.

    Used for end-users, admins, or any human interaction point.
    Rendered as a circle (head) + triangle (body).

    Args:
        label: Display text below the user icon.

    Example:
        >>> client = User("Client")
        >>> admin = User("Admin").right_of(client, distance=3)
    """

    def __post_init__(self) -> None:
        """Set primitive type to USER after parent validation."""
        super().__post_init__()
        self.primitive_type = PrimitiveType.USER

