"""Example 06: YAML AI Interface Demo.

Demonstrates parsing a YAML architecture specification and rendering
it directly using the AI module's parse_yaml_string() function.

Output: yaml_ai_demo.mp4
"""

from archmotion.ai import parse_yaml_string

YAML_INPUT = """
version: "1.0"
theme: neon_cyber
resolution: 1080p
fps: 60

nodes:
  - id: web
    label: Web Server
  - id: api
    label: API Server
    position:
      anchor: web
      direction: right_of
      distance: 4
  - id: db
    label: PostgreSQL
    type: database
    position:
      anchor: api
      direction: right_of
      distance: 4

connections:
  - id: c1
    source: web
    target: api
    label: REST API
  - id: c2
    source: api
    target: db
    label: SQL Query

choreography:
  - action: play
    animation:
      type: fade_in
      targets: [web, api, db, c1, c2]
  - action: wait
    duration: 0.5
  - action: play
    animation:
      type: transfer
      connection: c1
      payload: "GET /users"
  - action: play
    animation:
      type: transfer
      connection: c2
      payload: "SELECT * FROM users"
  - action: play
    animation:
      type: pulse
      target: db
      color: "#22c55e"
"""


def main() -> None:
    """Parse YAML and render directly."""
    scene = parse_yaml_string(YAML_INPUT)
    scene.render("yaml_ai_demo.mp4")


if __name__ == "__main__":
    main()
