# ArchMotion

**Code-to-Video Framework for System Architecture Animations**

Transform your system architecture into professional animated walkthroughs — from Python code or YAML.

---

## Quick Start

### 1. Install

```bash
pip install archmotion
```

### 2. Write your architecture

```python
from archmotion import Scene, Node, Database, Connection
from archmotion.motions import FadeIn, Transfer

# Create primitives
gateway = Node("API Gateway")
db = Database("PostgreSQL")
db.right_of(gateway, distance=4)

# Connect them
conn = Connection(gateway, db, label="SQL Query")

# Animate
scene = Scene(resolution="1080p", fps=60)
scene.play(FadeIn(gateway, db, conn))
scene.play(Transfer(connection=conn, payload="SELECT *"))

# Render
scene.render("architecture.mp4")
```

### 3. Run

```bash
python my_diagram.py
# → architecture.mp4 (playable in any video player)
```

---

## Features

| Feature | Status |
|---|---|
| **Primitives**: Node, Database, Cloud, Queue, Cache, User | ✅ |
| **Connections**: Manhattan routing with rounded corners | ✅ |
| **Animations**: FadeIn, FadeOut, Transfer, Pulse, Highlight, ColorShift, Scale | ✅ |
| **Themes**: dark_terminal, neon_cyber, blueprint, light_paper | ✅ |
| **YAML AI Interface**: Generate videos from LLM-produced YAML | ✅ |
| **Rich DX**: Progress bars, formatted errors, structured logging | ✅ |
| **Performance**: Multiprocessing + FFmpeg pipe, zero-disk I/O | ✅ |

---

## From YAML (AI Workflow)

```yaml
version: "1.0"
theme: neon_cyber
nodes:
  - id: api
    label: API Gateway
  - id: db
    label: PostgreSQL
    type: database
    position: { anchor: api, direction: right_of, distance: 4 }

connections:
  - id: c1
    source: api
    target: db
    label: SQL Query

choreography:
  - action: play
    animation: { type: fade_in, targets: [api, db, c1] }
  - action: play
    animation: { type: transfer, connection: c1, payload: "SELECT *" }
```

```python
from archmotion.ai import load_yaml
scene = load_yaml("architecture.yaml")
scene.render("output.mp4")
```

---

## Requirements

- Python 3.10+
- FFmpeg (auto-detected via `imageio-ffmpeg`)
- GPU optional: NVENC for hardware-accelerated encoding

---

## Next Steps

- [Architecture Deep-Dive](architecture.md) — Understand the 4-Phase Pipeline
- [Examples](examples.md) — Real-world runnable scripts
- [API Reference](api.md) — Full class and function documentation
