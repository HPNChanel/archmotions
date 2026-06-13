"""Example 05: Database Replication (Primary → Replicas).

Demonstrates synchronous replication from a Primary database to
two Read Replicas using concurrent Transfer animations.

Output: db_replication.mp4
"""

from archmotion import Connection, Scene
from archmotion.api.primitives import Database, Node
from archmotion.motions import FadeIn, Highlight, Pulse, Transfer


def main() -> None:
    """Build and render a database replication diagram."""
    # ── Create primitives ──
    client = Node("App Server")
    primary = Database("Primary DB")
    replica1 = Database("Replica 1")
    replica2 = Database("Replica 2")

    # ── Position layout ──
    primary.right_of(client, distance=4)
    replica1.right_of(primary, distance=4)
    replica2.below(replica1, distance=3)

    # ── Connections ──
    c_write = Connection(client, primary, label="WRITE")
    c_rep1 = Connection(primary, replica1, label="WAL Stream")
    c_rep2 = Connection(primary, replica2, label="WAL Stream")

    # ── Choreography ──
    scene = Scene(resolution="1080p", fps=60, theme="dark_terminal")

    # Step 1: Show all elements
    scene.play(FadeIn(
        client, primary, replica1, replica2,
        c_write, c_rep1, c_rep2,
    ))

    # Step 2: Client writes to Primary
    scene.play(Transfer(connection=c_write, payload="INSERT INTO..."))
    scene.play(Pulse(target=primary, color="#3b82f6"))

    # Step 3: Concurrent replication to both replicas
    scene.play(Highlight(target=primary, color="#facc15"))
    with scene.concurrent():
        scene.play(Transfer(connection=c_rep1, payload="WAL"))
        scene.play(Transfer(connection=c_rep2, payload="WAL"))

    # Step 4: Replicas acknowledge
    with scene.concurrent():
        scene.play(Pulse(target=replica1, color="#22c55e"))
        scene.play(Pulse(target=replica2, color="#22c55e"))

    scene.render("db_replication.mp4")


if __name__ == "__main__":
    main()
