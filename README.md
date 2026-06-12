# ArchMotion 🎬

> **Code-to-Video Framework for System Architecture Animations**

Write Python code that describes your system architecture → Get a professional MP4 animation. No design skills needed.

## ⚡ Quick Start

```bash
pip install archmotion
```

```python
from archmotion import Scene, Node, Database
from archmotion.connections import Connection
from archmotion.motions import FadeIn, Transfer, Pulse

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
scene.play(Pulse(db, color="green", duration=0.5))
scene.play(Transfer([conn_sd, conn_cs], payload="200 OK", reverse=True, duration=1.5))

scene.render("my_architecture.mp4")
```

## 🎯 Features

- **Declarative API** — Describe architecture like you explain it to a colleague
- **Relative Positioning** — `.right_of()`, `.below()` — never touch pixel coordinates
- **Timeline Control** — Sequential + Concurrent animations with `with scene.concurrent()`
- **Zero-Config FFmpeg** — Bundled binary, no system install needed
- **Hardware Accelerated** — NVIDIA NVENC encoding (auto-fallback to CPU)
- **Zero-Disk I/O** — Frames piped directly to FFmpeg, no temp files
- **1080p / 60fps** — Professional quality output

## 📖 Examples

See the [`examples/`](examples/) directory for runnable scripts:

| Example | Description |
|---|---|
| [`01_hello_world.py`](examples/01_hello_world.py) | Minimal example — 2 nodes + 1 connection |
| [`02_login_flow.py`](examples/02_login_flow.py) | Full login flow with Auth Service + Database |

## 🏗️ Architecture

ArchMotion uses a **4-Phase Pipeline** — data flows one-way through isolated stages:

```
User Code → [Topology Builder] → [Layout Resolver] → [Timeline Compiler] → [Renderer + FFmpeg] → MP4
```

Read the [Architecture Documentation](CORE_ENGINE&ARCHITECTURE.md) for details.

## 📦 Installation

```bash
# Standard install
pip install archmotion

# With development tools
pip install archmotion[dev]

# Using uv (recommended — 10x faster)
uv pip install archmotion
```

**Requirements:** Python 3.10+ · FFmpeg (bundled) · Optional: NVIDIA GPU for hardware encoding

## 🤝 Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## 📄 License

[MIT](LICENSE) — Free for personal and commercial use.
