"""Example 02 — Login Flow: The Golden Script from the PRD.

Demonstrates the full Use Case: Client → API Gateway → Auth Service → Database → Return Token.
This is the reference script used for acceptance testing (PRD DoD-01).

Output: login_flow.mp4
"""

from archmotion import Database, Node, Scene
from archmotion.connections import Connection
from archmotion.motions import FadeIn, Pulse, Transfer


def build_login_flow() -> None:
    """Build and render a complete login flow animation."""
    # 1. SCENE
    scene = Scene(resolution="1080p", fps=60, theme="dark_terminal")

    # ==========================================
    # 2. TOPOLOGY: Bày binh bố trận
    # ==========================================
    client = Node("User Mobile", icon="smartphone")
    gateway = Node("API Gateway").right_of(client, distance=4)
    auth = Node("Auth Service").right_of(gateway, distance=3)
    db = Database("Users DB").below(auth, distance=2)

    conn_cg = Connection(client, gateway)
    conn_ga = Connection(gateway, auth)
    conn_ad = Connection(auth, db)

    # ==========================================
    # 3. CHOREOGRAPHY: Đạo diễn kịch bản
    # ==========================================

    # 3.1 Bật đèn sân khấu
    with scene.concurrent():
        scene.play(FadeIn(client, gateway, auth, db))
        scene.play(FadeIn(conn_cg, conn_ga, conn_ad))

    # 3.2 Luồng Request
    scene.play(Transfer(conn_cg, payload="POST /login", duration=1.0))
    scene.play(Pulse(gateway, color="yellow", duration=0.5))

    scene.play(Transfer(conn_ga, payload="Validate", duration=0.8))
    scene.play(Pulse(auth, color="blue", duration=0.5))

    # 3.3 Auth → Database
    scene.play(Transfer(conn_ad, payload="SELECT user", duration=0.6))
    scene.play(Pulse(db, color="green", duration=0.5))

    # DB trả kết quả
    scene.play(Transfer(conn_ad, payload="User Data", reverse=True, duration=0.6))

    # 3.4 Trả 200 OK về Client
    scene.play(Pulse(auth, color="green", duration=0.5))
    scene.play(Transfer(
        [conn_ga, conn_cg],
        payload="200 OK + JWT",
        reverse=True,
        duration=1.5,
    ))

    # ==========================================
    # 4. RENDER
    # ==========================================
    scene.render("login_flow.mp4")


if __name__ == "__main__":
    build_login_flow()
