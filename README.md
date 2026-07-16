# ArchMotion

ArchMotion is a Python-first 2D vector animation engine for technical and
educational videos. It provides a Manim-like scene workflow without claiming
Manim API compatibility.

The v2.0 beta production contract is deliberately narrow: author scenes in
Python or validated YAML, then render H.264 MP4 video or a PNG still. Lottie,
animated SVG, HTML export, and the browser Studio are available as experimental
surfaces.

See [MVP status](MVP_STATUS.md) for the exact support boundary and known gaps.

## Install

```bash
python -m pip install archmotion
```

Requirements: Python 3.10+; the Python package supplies its FFmpeg runtime via
`imageio-ffmpeg`. A native `latex` + `dvisvgm` installation is only required for
`Tex`, `MathTex`, and `MathText`.

## Python scene

```python
from archmotion import Axes, Create, Dot, Scene, Text, ValueTracker, Write, always_redraw


class Parabola(Scene):
    def construct(self) -> None:
        axes = Axes(
            x_range=(-3, 3),
            y_range=(-1, 5),
            x_length=700,
            y_length=380,
            center=(640, 400),
        )
        graph = axes.plot(lambda x: 0.45 * x * x).set_stroke("#38bdf8", width=3)
        title = Text("ArchMotion 2D").move_to(640, 80)
        x = ValueTracker(-3)

        def marker() -> Dot:
            value = x.get_value()
            dot = Dot(axes.c2p(value, 0.45 * value * value), radius=10)
            dot.set_fill("yellow")
            return dot

        self.add(axes, graph, title, x, always_redraw(marker))
        self.play(Create(axes), Create(graph), Write(title))
        self.play(x.animate.set_value(3).set_run_time(1.5))


if __name__ == "__main__":
    Parabola(resolution="720p", fps=30).render("parabola.mp4")
```

Render through the CLI instead of adding a `__main__` block:

```bash
archmotion render scene.py Parabola -qm -o parabola.mp4
archmotion still scene.py Parabola -qm -o parabola.png
```

Quality presets are `-ql` (854×480/15 fps), `-qm` (1280×720/30 fps), and
`-qh` (1920×1080/60 fps). Explicit `--resolution WIDTHxHEIGHT`, `--fps`,
`--workers`, and `--crf` overrides are also supported.

## YAML scene

```yaml
version: "2.0"
theme: neon_cyber
resolution: 1080p
fps: 60
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
archmotion render scene.yaml -qm -o architecture.mp4
archmotion still scene.yaml -qm -o architecture.png
```

The YAML models reject unknown fields and invalid references instead of silently
accepting a partially understood scene.

## Production MVP capabilities

- Hierarchical 2D scene graph, affine transforms, groups, styles, themes, and
  deterministic timelines.
- Geometry, axes/function plots, architecture diagrams, charts, text, native
  LaTeX outlines, and syntax-highlighted code blocks.
- `FadeIn`/`FadeOut`, creation/writing, transforms, grouped sequencing,
  architecture recipes, chart reveals, `ValueTracker`, and `always_redraw`.
- CPU-baseline H.264 MP4 and RGBA PNG output through both Python and CLI.
- Windows-safe single-process default; parallel rendering remains available on
  supported scenes and platforms.
- Strict typing, cross-platform CI, package build/install checks, and a real
  MP4/PNG smoke scene in [`examples/12_mvp_scene.py`](examples/12_mvp_scene.py).

## Experimental capabilities

- Lottie JSON, animated SVG, and HTML player exports. The CLI emits an explicit
  warning because these formats do not yet have full MP4 feature parity.
- ArchMotion Studio (React + Pyodide) for YAML editing and browser previews.
- Shared-memory rendering and opt-in hardware encoding via
  `ARCHMOTION_HARDWARE_ENCODER=auto`.

## Not a drop-in Manim replacement

ArchMotion can now cover an MVP subset of 2D technical animation, but existing
Manim scenes cannot be imported unchanged. It does not yet provide 3D/OpenGL,
audio/video compositing, a moving-camera API, TeX template management, plugins,
or Manim's breadth of objects and community ecosystem.

## Documentation

- [MVP support matrix and gaps](MVP_STATUS.md)
- [Architecture](docs/architecture.md)
- [API reference](docs/api.md)
- [Examples](examples/README.md)
- [Roadmap](ROADMAP.md)
- [Changelog](CHANGELOG.md)

## Development

```bash
python -m pip install -e ".[dev]"
ruff check src
ruff format --check src
mypy src/archmotion --strict --ignore-missing-imports
pytest tests/unit -q --cov=archmotion
```

Studio is an experimental, separately checked surface:

```bash
cd studio
npm ci
npm run lint
npm run build
```

## License

[MIT](LICENSE)
