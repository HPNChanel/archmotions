# Examples

Runnable example scripts demonstrating ArchMotion v2.0's capabilities — from basic
architecture animations to cross-domain fusion demos.

---

## 01 — Hello World

**File:** `examples/01_hello_world.py`
**Complexity:** ⭐
**Nodes:** 2

Minimal example: two nodes, one connection, one animation.

```python
from archmotion import Scene, Node, Connection
from archmotion import FadeIn, Transfer

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

Real-world microservices topology with API Gateway, service mesh, message queue,
and background worker.

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

Visualizes the OAuth2 Authorization Code Grant with the `User` primitive and
sequential Transfer packets with descriptive payloads.

---

## 05 — Database Replication

**File:** `examples/05_db_replication.py`
**Complexity:** ⭐⭐⭐
**Nodes:** 4

Primary → Replica replication pattern with multiple `Database` primitives and
concurrent Transfer animations for parallel replication.

---

## 06 — YAML AI Render

**File:** `examples/06_ai_yaml_render.py`
**Complexity:** ⭐⭐
**Nodes:** 3

End-to-end demo of the YAML AI Interface: parse a YAML string and render directly.

```python
from archmotion.ai import parse_yaml_string

yaml_input = """
version: "2.0"
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
"""

scene = parse_yaml_string(yaml_input)
scene.render("yaml_demo.mp4")
```

---

## Fusion Demos (v2.0)

The v2.0 differentiator: multiple domains coexist in one scene, with cross-domain
`Transform` morphing.

| Example | Domains | Demonstrates |
|---|---|---|
| `examples/v2_fusion_demo.py` | architecture + charts + geometry | Combined best-of showcase |
| `examples/07_fusion_arch_metrics.py` | architecture + charts | Live `BarChart` beside a diagram |
| `examples/08_fusion_morph.py` | architecture + geometry + charts | `Node` → `Circle` → `PieChart` |
| `examples/09_fusion_math_over_arch.py` | architecture + math | LaTeX equation over a diagram |
| `examples/10_fusion_code_walkthrough.py` | architecture + code | `CodeBlock` with data-flow `Transfer` |

```python
from archmotion.animation import Transform
from archmotion.domains.geometry import Circle
from archmotion.domains.charts import PieChart

# Morph a database node into a circle, then a pie chart:
scene.play(Transform(db, Circle(radius=55).move_to(520, 270)))
scene.play(Transform(db, PieChart([3, 7, 5, 9], radius=60, center=(760, 340))))
```

> **LaTeX note:** the math fusion example (`09`) requires `latex` + `dvisvgm`
> installed. If absent, it prints a message and skips gracefully.

---

## Running Examples

```bash
# Install ArchMotion in development mode
pip install -e ".[dev]"

# Run any example
python examples/01_hello_world.py
python examples/03_microservices.py
python examples/v2_fusion_demo.py
```

Architecture examples output MP4 files in the current directory. Fusion demos
export SVG + Lottie by default (Skia/FFmpeg optional for MP4).
