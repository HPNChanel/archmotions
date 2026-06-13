# ArchMotion 🎬

> **Code-to-Video Framework for System Architecture Animations**

Write Python code or YAML that describes your system architecture → Get professional MP4, Lottie, SVG, or HTML animations. No design skills needed.

## ⚡ Quick Start

```bash
pip install archmotion
```

### Python API

```python
from archmotion import Scene, Node, Database, Connection, FadeIn, Transfer, Pulse

scene = Scene(resolution="1080p", fps=60, theme="dark_terminal")

# Define your architecture
client  = Node("Client")
server  = Node("API Server").right_of(client, distance=4)
db      = Database("PostgreSQL").right_of(server, distance=3)

conn_cs = Connection(client, server)
conn_sd = Connection(server, db)

# Choreograph the data flow
with scene.concurrent():
    scene.play(FadeIn(client, server, db, conn_cs, conn_sd))

scene.play(Transfer(conn_cs, payload="GET /users", duration=1.0))
scene.play(Pulse(server, color="yellow", duration=0.5))
scene.play(Transfer(conn_sd, payload="SELECT *", duration=0.8))
scene.play(Transfer([conn_sd, conn_cs], payload="200 OK", reverse=True, duration=1.5))

# Export to any format
scene.render("my_architecture.mp4")       # MP4 video
scene.export("my_architecture.json")      # Lottie JSON
scene.export("my_architecture.svg")       # Animated SVG
scene.export("my_architecture.html")      # Interactive HTML player
```

### YAML (AI-Friendly)

```yaml
scene:
  resolution: "1080p"
  fps: 60
  theme: neon_cyber

nodes:
  - id: client
    label: "Client"
    type: node
  - id: api
    label: "API Server"
    type: node
    position: { anchor: client, direction: right, distance: 4 }
  - id: db
    label: "PostgreSQL"
    type: database
    position: { anchor: api, direction: right, distance: 3 }

connections:
  - id: c1
    source: client
    target: api
  - id: c2
    source: api
    target: db

choreography:
  - play: { target: [client, api, db, c1, c2], animation: fade_in }
  - play: { target: c1, animation: transfer, payload: "GET /users" }
  - play: { target: c2, animation: transfer, payload: "SELECT *" }
```

### CLI

```bash
archmotion render scene.yaml -o output.mp4       # MP4 video
archmotion render scene.yaml -o output.json      # Lottie JSON
archmotion render scene.yaml -o output.html      # HTML player
archmotion render scene.yaml --theme neon_cyber   # Custom theme
archmotion themes                                 # List themes
```

## 🎯 Features

| Feature | Description |
|---|---|
| **Multi-Format Export** | MP4, Lottie JSON, Animated SVG, Interactive HTML |
| **Declarative API** | Describe architecture like you explain it to a colleague |
| **YAML AI Interface** | LLMs can generate scenes via validated YAML schema |
| **CLI** | `archmotion render` with auto format detection |
| **Relative Positioning** | `.right_of()`, `.below()` — no pixel coordinates |
| **4 Themes** | dark_terminal, neon_cyber, blueprint, light_paper |
| **8 Animations** | FadeIn, FadeOut, Transfer, Pulse, Highlight, ColorShift, ScaleUp, ScaleDown |
| **6 Primitives** | Node, Database, Cloud, Queue, Cache, User |
| **A* Pathfinding** | Obstacle-aware connection routing |
| **Zero-Copy IPC** | SharedMemory ring buffer for render workers |
| **Hardware Accel** | NVIDIA NVENC encoding (auto-fallback to CPU) |
| **1080p/60fps** | Professional quality output |

## 🎨 Themes

| Theme | Style |
|---|---|
| `dark_terminal` | Dark background, muted colors (default) |
| `neon_cyber` | Vibrant neon on black — cyberpunk aesthetic |
| `blueprint` | Technical blue gridlines — engineering style |
| `light_paper` | Light background — clean documentation style |

## 📖 Examples

See the [`examples/`](examples/) directory for runnable scripts:

| Example | Description |
|---|---|
| [`01_hello_world.py`](examples/01_hello_world.py) | Minimal — 2 nodes + 1 connection |
| [`02_login_flow.py`](examples/02_login_flow.py) | Full login flow with Auth + DB |
| [`03_concurrent_requests.py`](examples/03_concurrent_requests.py) | Parallel animations |
| [`04_microservices.py`](examples/04_microservices.py) | Microservice architecture |
| [`05_cloud_infrastructure.py`](examples/05_cloud_infrastructure.py) | Cloud + Queue + Cache |
| [`06_yaml_workflow.py`](examples/06_yaml_workflow.py) | YAML → Scene → Video |

## 🏗️ Architecture

ArchMotion uses a **4-Phase Pipeline** — data flows one-way through isolated stages:

```
User Code / YAML → [Topology] → [Layout] → [Timeline] → [Renderer] → MP4 / Lottie / SVG / HTML
```

Read the [Architecture Documentation](CORE_ENGINE&ARCHITECTURE.md) for details.

## 📦 Installation

```bash
# Standard install
pip install archmotion

# With development tools
pip install archmotion[dev]

# With documentation tools
pip install archmotion[docs]

# Using uv (recommended — 10x faster)
uv pip install archmotion
```

**Requirements:** Python 3.10+ · FFmpeg (bundled) · Optional: NVIDIA GPU for hardware encoding

## 🤝 Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## 📄 License

[MIT](LICENSE) — Free for personal and commercial use.
