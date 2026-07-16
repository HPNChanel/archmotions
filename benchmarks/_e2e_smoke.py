"""E2E smoke test: YAML -> Scene -> MP4 via the public API."""
import os
import tempfile

from archmotion.ai import parse_yaml_string

yaml = """\
version: "2.0"
theme: dark_terminal
nodes:
  - id: api
    label: API
  - id: db
    label: DB
    type: database
    position: { anchor: api, direction: right_of, distance: 4 }
connections:
  - id: c1
    source: api
    target: db
choreography:
  - action: play
    animation: { type: fade_in, targets: [api, db, c1] }
  - action: play
    animation: { type: transfer, connection: c1, payload: GET }
"""

def main() -> None:
    """Render the public YAML smoke scene without recursive Windows spawning."""
    scene = parse_yaml_string(yaml)
    out = os.path.join(tempfile.gettempdir(), "cli_e2e.mp4")
    scene.render(out, workers=1)
    print(f"E2E: {os.path.getsize(out)} bytes at {out}")


if __name__ == "__main__":
    main()
