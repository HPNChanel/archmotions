# Examples

Runnable example scripts demonstrating ArchMotion's capabilities. Each example produces a playable MP4 video.

---

## 01 — Hello World

**File:** `examples/01_hello_world.py`
**Complexity:** ⭐
**Nodes:** 2

Minimal example: two nodes, one connection, one animation.

```python
from archmotion import Scene, Node, Connection
from archmotion.motions import FadeIn, Transfer

gateway = Node("API Gateway")
db = Node("Database")
db.right_of(gateway, distance=4)

conn = Connection(gateway, db, label="Request")

scene = Scene()
scene.play(FadeIn(gateway, db, conn))
scene.play(Transfer(connection=conn, payload="GET /users"))
scene.render("hello_world.mp4")
```

---

## 02 — Login Flow

**File:** `examples/02_login_flow.py`
**Complexity:** ⭐⭐
**Nodes:** 4

Full login authentication flow: Client → Gateway → Auth Service → Database.

---

## 03 — Microservices Architecture

**File:** `examples/03_microservices.py`
**Complexity:** ⭐⭐⭐
**Nodes:** 5

Real-world microservices topology with API Gateway, service mesh, message queue, and background worker.

Demonstrates:

- Multiple node types (`Node`, `Queue`)
- Concurrent animations
- Chained Transfer packets
- Pulse effects on processing events

---

## 04 — OAuth2 Authorization Code Flow

**File:** `examples/04_oauth2_flow.py`
**Complexity:** ⭐⭐⭐
**Nodes:** 4

Visualizes the OAuth2 Authorization Code Grant:

1. User redirects to Auth Server
2. Auth Server issues authorization code
3. Client exchanges code for access token
4. Client accesses protected API resource

Demonstrates:

- `User` primitive (stick figure)
- Sequential Transfer with descriptive payloads
- Wait pauses for visual clarity

---

## 05 — Database Replication

**File:** `examples/05_db_replication.py`
**Complexity:** ⭐⭐⭐
**Nodes:** 4

Primary → Replica replication pattern:

- Client writes to Primary
- Primary synchronously replicates to 2 Replicas
- Concurrent Transfer animations for parallel replication

Demonstrates:

- Multiple `Database` primitives
- Concurrent animation blocks
- Highlight for active replication state

---

## 06 — YAML AI Render

**File:** `examples/06_ai_yaml_render.py`
**Complexity:** ⭐⭐
**Nodes:** 3

End-to-end demo of the YAML AI Interface: parse a YAML string and render directly.

```python
from archmotion.ai import parse_yaml_string

yaml_input = """
version: "1.0"
theme: neon_cyber
nodes:
  - id: web
    label: Web Server
  - id: api
    label: API Server
    position: { anchor: web, direction: right_of, distance: 4 }
  - id: db
    label: Database
    type: database
    position: { anchor: api, direction: right_of, distance: 4 }
connections:
  - id: c1
    source: web
    target: api
    label: REST
  - id: c2
    source: api
    target: db
    label: SQL
choreography:
  - action: play
    animation: { type: fade_in, targets: [web, api, db, c1, c2] }
  - action: play
    animation: { type: transfer, connection: c1, payload: "GET /users" }
  - action: play
    animation: { type: transfer, connection: c2, payload: "SELECT *" }
"""

scene = parse_yaml_string(yaml_input)
scene.render("yaml_demo.mp4")
```

---

## Running Examples

```bash
# Install ArchMotion in development mode
pip install -e ".[dev]"

# Run any example
python examples/01_hello_world.py
python examples/03_microservices.py
python examples/06_ai_yaml_render.py
```

All examples output MP4 files in the current directory.
