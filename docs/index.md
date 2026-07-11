# ArchMotion

**Multi-domain code-to-video animation framework**

Transform system architecture, geometry, charts, math, and code into professional
animated walkthroughs — from Python or YAML. Cross-domain `Transform` morphs any
two vector shapes into each other.

---

## Quick Start

### 1. Install

```bash
pip install archmotion
```

### 2. Write your architecture

```python
from archmotion import Scene, Node, Database, Connection
from archmotion import FadeIn, Transfer

# Create primitives
gateway = Node("API Gateway")
db = Database("PostgreSQL")
db.right_of(gateway, distance=4)

# Connect them
conn = Connection(gateway, db, label="SQL Query")

# Animate
scene = Scene(resolution="1080p", fps=30)
scene.play(FadeIn(gateway, db, conn))
scene.play(Transfer(connection=conn, payload="SELECT *"))

# Render to MP4 (parallel pool + GPU encoding when available)
scene.render("architecture.mp4")
```

### 3. Run

```bash
python my_diagram.py
# -> architecture.mp4 (playable in any video player)
```

---

## Features

| Feature | Status |
|---|---|
| **Architecture primitives**: Node, Database, Cloud, Queue, Cache, User | ✅ |
| **Connections**: A\* obstacle-aware Manhattan routing, rounded corners, arrowheads | ✅ |
| **Animations**: FadeIn, FadeOut, Transfer, Pulse, Highlight, ColorShift, Scale | ✅ |
| **Multi-Domain Fusion**: geometry, charts, text, math (LaTeX), code in one scene | ✅ |
| **Cross-Domain Transform**: morph any two vector shapes (Node → Circle → PieChart) | ✅ |
| **Themes**: dark_terminal, neon_cyber, blueprint, light_paper | ✅ |
| **YAML AI Interface**: generate videos from LLM-produced YAML | ✅ |
| **Export**: MP4 (parallel pool + SharedMemory zero-copy IPC), Lottie, SVG, HTML | ✅ |
| **Rich DX**: progress bars, formatted errors, structured logging | ✅ |

---

## From YAML (AI Workflow)

```yaml
version: "2.0"
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

## Export Formats

| Format | Extension | Use Case |
|---|---|---|
| MP4 video | `.mp4` | Presentations, social media (Skia raster + FFmpeg) |
| Lottie JSON | `.json` | Web playback via lottie-web |
| Animated SVG | `.svg` | Docs, slides, print |
| HTML player | `.html` | Self-contained interactive player |

```python
scene.render("out.mp4")            # MP4
scene.export("out.json")           # Lottie
scene.export("out.svg")            # SVG
scene.export("out.html")           # HTML player
```

---

## Requirements

- Python 3.10+
- FFmpeg (auto-resolved via `imageio-ffmpeg`, or set `FFMPEG_BINARY`)
- GPU optional: NVENC (`h264_nvenc`) auto-detected for hardware-accelerated encoding
- LaTeX optional: `latex` + `dvisvgm` for the math domain (MP4/CLI only, not in-browser)

---

## Next Steps

- [Architecture Deep-Dive](architecture.md) — the v2.0 pipeline & module layout
- [Examples](examples.md) — runnable scripts incl. cross-domain fusion demos
- [API Reference](api.md) — full class and function documentation
