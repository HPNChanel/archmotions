# ArchMotion

ArchMotion v2.0 is a Python/YAML 2D vector animation engine for technical and
educational videos. It offers a Manim-like scene lifecycle, but it is not a
drop-in Manim compatibility layer.

The production-MVP output contract is H.264 MP4 and PNG. Lottie, animated SVG,
HTML, hardware encoding, and the browser Studio are experimental.

## Quick start

```bash
python -m pip install archmotion
```

```python
from archmotion import Axes, Create, Scene, Text, Write


class Demo(Scene):
    def construct(self) -> None:
        axes = Axes(center=(640, 400), x_length=700, y_length=380)
        graph = axes.plot(lambda x: 0.45 * x * x).set_stroke("#38bdf8", width=3)
        title = Text("ArchMotion 2D").move_to(640, 80)
        self.add(axes, graph, title)
        self.play(Create(axes), Create(graph), Write(title))
```

```bash
archmotion render demo.py Demo -qm -o demo.mp4
archmotion still demo.py Demo -qm -o demo.png
```

## Supported MVP

| Area | Status |
|---|---|
| Python `Scene.construct()` and strict YAML | Production MVP |
| Hierarchical 2D vector scene graph and timelines | Production MVP |
| Architecture, geometry, charts, text, math, code | Production MVP |
| Animation groups, morphing, trackers, updaters | Production MVP |
| CPU H.264 MP4 and RGBA PNG | Production MVP |
| Lottie, animated SVG, HTML | Experimental |
| Browser Studio and browser MP4 | Experimental |
| Shared memory and hardware encoding | Experimental opt-in |
| 3D/OpenGL, audio/compositing, Manim compatibility | Unsupported |

Read the canonical
[MVP status](https://github.com/archmotion/archmotion/blob/main/MVP_STATUS.md)
before selecting ArchMotion for a project.

## YAML workflow

```yaml
version: "2.0"
theme: neon_cyber
nodes:
  - {id: client, label: Client, type: user}
  - id: api
    label: API Server
    position: {anchor: client, direction: right_of, distance: 4}
connections:
  - {id: request, source: client, target: api, label: HTTPS}
choreography:
  - action: play
    animation: {type: fade_in, targets: [client, api, request]}
  - action: play
    animation: {type: transfer, connection: request, payload: "GET /"}
```

```bash
archmotion render architecture.yaml -qm -o architecture.mp4
```

## Requirements

- Python 3.10+
- FFmpeg resolved from `FFMPEG_BINARY`, the system path, or `imageio-ffmpeg`
- Optional native `latex` + `dvisvgm` for math text
- Optional `ARCHMOTION_HARDWARE_ENCODER=auto` to probe NVENC; CPU remains the
  supported default

## Next steps

- [Architecture deep-dive](architecture.md)
- [Examples](examples.md)
- [API reference](api.md)
