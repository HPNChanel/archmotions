# API Reference

Auto-generated documentation from source code docstrings.

---

## Core

### Scene

::: archmotion.core.scene.Scene
    options:
      members:
        - __init__
        - play
        - wait
        - add
        - setup
        - construct
        - tear_down
        - render
        - save_frame
        - export
        - resolve
        - to_lottie
        - to_svg
        - to_html

---

### ValueTracker / always_redraw

::: archmotion.core.updaters.ValueTracker
    options:
      show_source: false

::: archmotion.core.updaters.always_redraw
    options:
      show_source: false

---

## Architecture Primitives

### Node

::: archmotion.domains.architecture.primitives.Node
    options:
      show_source: false

---

### Database

::: archmotion.domains.architecture.primitives.Database
    options:
      show_source: false

---

### Cloud

::: archmotion.domains.architecture.primitives.Cloud
    options:
      show_source: false

---

### Queue

::: archmotion.domains.architecture.primitives.Queue
    options:
      show_source: false

---

### Cache

::: archmotion.domains.architecture.primitives.Cache
    options:
      show_source: false

---

### User

::: archmotion.domains.architecture.primitives.User
    options:
      show_source: false

---

### Connection

::: archmotion.domains.architecture.connections.Connection
    options:
      show_source: false

---

## Animations

### FadeIn / FadeOut

::: archmotion.animation.base.FadeIn
    options:
      show_source: false

::: archmotion.animation.base.FadeOut
    options:
      show_source: false

---

### Transfer

::: archmotion.animation.recipes.Transfer
    options:
      show_source: false

---

### Pulse

::: archmotion.animation.recipes.Pulse
    options:
      show_source: false

---

### Highlight

::: archmotion.animation.recipes.Highlight
    options:
      show_source: false

---

### ColorShift

::: archmotion.animation.recipes.ColorShift
    options:
      show_source: false

---

### ScaleUp / ScaleDown

::: archmotion.animation.recipes.ScaleUp
    options:
      show_source: false

::: archmotion.animation.recipes.ScaleDown
    options:
      show_source: false

---

### Transform

::: archmotion.animation.base.Transform
    options:
      show_source: false

::: archmotion.animation.base.ReplacementTransform
    options:
      show_source: false

---

### Write / Uncreate / Typewriter

::: archmotion.animation.base.Write
    options:
      show_source: false

::: archmotion.animation.base.Uncreate
    options:
      show_source: false

::: archmotion.animation.base.Typewriter
    options:
      show_source: false

---

### DrawBorderThenFill

::: archmotion.animation.base.DrawBorderThenFill
    options:
      show_source: false

---

### Growth animations

::: archmotion.animation.base.GrowFromCenter
    options:
      show_source: false

::: archmotion.animation.base.GrowFromEdge
    options:
      show_source: false

::: archmotion.animation.base.GrowBar
    options:
      show_source: false

---

### Chart animations

::: archmotion.animation.recipes.DrawLine
    options:
      show_source: false

::: archmotion.animation.recipes.SweepPie
    options:
      show_source: false

---

### Indicator / effect animations

::: archmotion.animation.recipes.Flash
    options:
      show_source: false

::: archmotion.animation.recipes.Indicate
    options:
      show_source: false

::: archmotion.animation.recipes.FadeToColor
    options:
      show_source: false

---

## Geometry Domain

::: archmotion.domains.geometry.shapes.Circle
    options:
      show_source: false

::: archmotion.domains.geometry.shapes.Rectangle
    options:
      show_source: false

::: archmotion.domains.geometry.shapes.ArcBetweenPoints
    options:
      show_source: false

::: archmotion.domains.geometry.shapes.Bezier
    options:
      show_source: false

::: archmotion.domains.geometry.shapes.Brace
    options:
      show_source: false

::: archmotion.domains.geometry.coordinate_systems.NumberPlane
    options:
      show_source: false

---

## Charts Domain

::: archmotion.domains.charts.charts.BarChart
    options:
      show_source: false

::: archmotion.domains.charts.charts.LineChart
    options:
      show_source: false

::: archmotion.domains.charts.charts.PieChart
    options:
      show_source: false

::: archmotion.domains.charts.charts.ScatterPlot
    options:
      show_source: false

---

## Text Domain

::: archmotion.domains.text.text.Text
    options:
      show_source: false

::: archmotion.domains.text.text.Paragraph
    options:
      show_source: false

---

## Theme

::: archmotion.render.theme.ThemeConfig
    options:
      show_source: false

::: archmotion.render.theme.get_theme
    options:
      show_source: false

---

## YAML AI Interface

::: archmotion.ai
    options:
      members:
        - load_yaml
        - parse_yaml_string
      show_source: false

---

## Error Hierarchy

::: archmotion.errors
    options:
      show_source: false
      members: true
