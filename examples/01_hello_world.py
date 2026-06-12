"""Example 01 — Hello World: Minimal 2-node architecture animation.

This is the simplest possible ArchMotion script.
It creates two nodes, connects them, and animates a data transfer.

Output: hello_world.mp4
"""

from archmotion import Node, Scene
from archmotion.connections import Connection
from archmotion.motions import FadeIn, Transfer


def main() -> None:
    """Build and render a minimal architecture animation."""
    scene = Scene(resolution="1080p", fps=60, theme="dark_terminal")

    # Topology: 2 nodes + 1 connection
    client = Node("Client")
    server = Node("Server").right_of(client, distance=4)
    conn = Connection(client, server)

    # Choreography
    with scene.concurrent():
        scene.play(FadeIn(client, server, conn))

    scene.play(Transfer(conn, payload="Hello!", duration=1.0))

    # Render
    scene.render("hello_world.mp4")


if __name__ == "__main__":
    main()
