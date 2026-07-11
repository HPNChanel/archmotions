"""Example 04: OAuth2 Authorization Code Flow.

Visualizes the full OAuth2 Authorization Code Grant sequence:
  1. User opens Client App → redirect to Auth Server
  2. Auth Server authenticates → returns authorization code
  3. Client exchanges code for access token
  4. Client calls API with Bearer token

Output: oauth2_flow.mp4
"""

from archmotion import Connection, FadeIn, Node, Pulse, Scene, Transfer, User


def main() -> None:
    """Build and render an OAuth2 flow diagram."""
    # ── Create primitives ──
    user = User("Resource Owner")
    client = Node("Client App")
    auth = Node("Auth Server")
    api = Node("API Resource")

    # ── Position layout ──
    client.right_of(user, distance=4)
    auth.right_of(client, distance=4)
    api.below(auth, distance=3)

    # ── Connections ──
    c_user_client = Connection(user, client, label="Login")
    c_client_auth = Connection(client, auth, label="/authorize")
    c_auth_client = Connection(auth, client, label="code=XYZ")
    c_client_token = Connection(client, auth, label="/token")
    c_auth_token = Connection(auth, client, label="access_token")
    c_client_api = Connection(client, api, label="Bearer token")

    # ── Choreography ──
    scene = Scene(resolution="1080p", fps=60, theme="dark_terminal")

    # Step 1: Show all elements
    scene.play(FadeIn(
        user, client, auth, api,
        c_user_client, c_client_auth, c_auth_client,
        c_client_token, c_auth_token, c_client_api,
    ))

    # Step 2: User initiates login
    scene.play(Transfer(connection=c_user_client, payload="Login"))
    scene.wait(duration=0.3)

    # Step 3: Redirect to Auth Server
    scene.play(Transfer(connection=c_client_auth, payload="/authorize"))
    scene.play(Pulse(target=auth, color="#f59e0b"))

    # Step 4: Auth Server returns code
    scene.play(Transfer(connection=c_auth_client, payload="code=XYZ"))
    scene.wait(duration=0.3)

    # Step 5: Client exchanges code for token
    scene.play(Transfer(connection=c_client_token, payload="/token"))
    scene.play(Transfer(connection=c_auth_token, payload="access_token"))
    scene.wait(duration=0.3)

    # Step 6: Client accesses API
    scene.play(Transfer(connection=c_client_api, payload="Bearer ey..."))
    scene.play(Pulse(target=api, color="#22c55e"))

    scene.render("oauth2_flow.mp4")


if __name__ == "__main__":
    main()
