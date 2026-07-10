"""Architecture domain: fusable system-architecture primitives + connections."""

from archmotion.domains.architecture.connections import Connection
from archmotion.domains.architecture.layout import resolve_architecture
from archmotion.domains.architecture.packet import Packet
from archmotion.domains.architecture.primitives import (
    Cache,
    Cloud,
    Database,
    Node,
    Queue,
    User,
)

__all__ = [
    "Cache",
    "Cloud",
    "Connection",
    "Database",
    "Node",
    "Packet",
    "Queue",
    "User",
    "resolve_architecture",
]
