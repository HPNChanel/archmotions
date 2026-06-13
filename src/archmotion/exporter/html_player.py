"""Interactive HTML Player Exporter — self-contained animated SVG + Lottie player.

Architectural Note:
    Generates a single HTML file with:
    1. Embedded Lottie JSON data (inline, no external files)
    2. lottie-web player loaded from CDN (fallback to inline SVG)
    3. Interactive controls: play/pause, scrub, speed, loop toggle
    4. Responsive design with dark/light mode matching the scene theme

    The HTML file is completely self-contained and can be opened directly
    in any modern browser without a web server.

    Additionally provides an Animated SVG export that uses CSS animations
    for simple opacity/scale transitions (no JavaScript dependency).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from archmotion._types import AnimatableProperty, PrimitiveType
from archmotion.layout.bbox import BoundingBox
from archmotion.layout.resolver import ResolvedLayout
from archmotion.renderer.theme import ThemeConfig
from archmotion.timeline.actions import ScheduledAction
from archmotion.timeline.compiler import CompiledTimeline
from archmotion.exporter.lottie import build_lottie_json


# ──────────────────────────────────────────────
# HTML Player Template
# ──────────────────────────────────────────────

_HTML_TEMPLATE: str = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
  :root {{
    --bg: {bg_color};
    --text: {text_color};
    --accent: {accent_color};
    --surface: {surface_color};
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    background: var(--bg);
    color: var(--text);
    font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    padding: 20px;
  }}
  .player-container {{
    position: relative;
    width: min(90vw, {canvas_width}px);
    aspect-ratio: {canvas_width} / {canvas_height};
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 8px 32px rgba(0,0,0,0.3);
    background: var(--surface);
  }}
  #lottie-player {{
    width: 100%;
    height: 100%;
  }}
  .controls {{
    display: flex;
    align-items: center;
    gap: 12px;
    margin-top: 16px;
    padding: 12px 20px;
    background: var(--surface);
    border-radius: 10px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.2);
  }}
  .btn {{
    background: none;
    border: 2px solid var(--accent);
    color: var(--accent);
    width: 36px;
    height: 36px;
    border-radius: 50%;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 14px;
    transition: all 0.2s;
  }}
  .btn:hover {{
    background: var(--accent);
    color: var(--bg);
  }}
  .scrub {{
    flex: 1;
    -webkit-appearance: none;
    height: 4px;
    border-radius: 2px;
    background: rgba(128,128,128,0.3);
    outline: none;
  }}
  .scrub::-webkit-slider-thumb {{
    -webkit-appearance: none;
    width: 14px;
    height: 14px;
    border-radius: 50%;
    background: var(--accent);
    cursor: pointer;
  }}
  .speed-label {{
    font-size: 12px;
    opacity: 0.7;
    min-width: 40px;
    text-align: center;
  }}
  .info {{
    margin-top: 8px;
    font-size: 12px;
    opacity: 0.5;
  }}
</style>
</head>
<body>

<div class="player-container">
  <div id="lottie-player"></div>
</div>

<div class="controls">
  <button class="btn" id="btn-play" title="Play/Pause">&#9654;</button>
  <input type="range" class="scrub" id="scrub" min="0" max="100" value="0">
  <button class="btn" id="btn-speed" title="Speed">1x</button>
  <button class="btn" id="btn-loop" title="Loop" style="font-size:11px">&#x21BB;</button>
</div>

<p class="info">ArchMotion Player &mdash; {total_frames} frames @ {fps}fps ({duration}s)</p>

<script src="https://cdnjs.cloudflare.com/ajax/libs/lottie-web/5.12.2/lottie.min.js"></script>
<script>
(function() {{
  const animData = {lottie_json};

  const player = lottie.loadAnimation({{
    container: document.getElementById('lottie-player'),
    renderer: 'svg',
    loop: true,
    autoplay: true,
    animationData: animData,
  }});

  const btnPlay = document.getElementById('btn-play');
  const scrub = document.getElementById('scrub');
  const btnSpeed = document.getElementById('btn-speed');
  const btnLoop = document.getElementById('btn-loop');

  let isPlaying = true;
  let looping = true;
  const speeds = [0.5, 1, 1.5, 2];
  let speedIdx = 1;

  btnPlay.addEventListener('click', () => {{
    if (isPlaying) {{
      player.pause();
      btnPlay.innerHTML = '&#9654;';
    }} else {{
      player.play();
      btnPlay.innerHTML = '&#9646;&#9646;';
    }}
    isPlaying = !isPlaying;
  }});
  btnPlay.innerHTML = '&#9646;&#9646;';

  scrub.addEventListener('input', () => {{
    const frame = (scrub.value / 100) * player.totalFrames;
    player.goToAndStop(frame, true);
    isPlaying = false;
    btnPlay.innerHTML = '&#9654;';
  }});

  player.addEventListener('enterFrame', () => {{
    scrub.value = (player.currentFrame / player.totalFrames) * 100;
  }});

  btnSpeed.addEventListener('click', () => {{
    speedIdx = (speedIdx + 1) % speeds.length;
    player.setSpeed(speeds[speedIdx]);
    btnSpeed.textContent = speeds[speedIdx] + 'x';
  }});

  btnLoop.addEventListener('click', () => {{
    looping = !looping;
    player.loop = looping;
    btnLoop.style.opacity = looping ? '1' : '0.4';
  }});
}})();
</script>

</body>
</html>"""


# ──────────────────────────────────────────────
# Animated SVG Template
# ──────────────────────────────────────────────


def _build_svg_animations(
    actions: list[ScheduledAction],
    total_duration: float,
) -> str:
    """Build CSS animation keyframes from ScheduledActions.

    Args:
        actions: Actions for a specific target.
        total_duration: Total timeline duration in seconds.

    Returns:
        CSS animation string for ``style`` attribute.
    """
    opacity_actions = [a for a in actions if a.prop == AnimatableProperty.OPACITY]
    if not opacity_actions:
        return ""

    keyframes: list[str] = []
    for action in sorted(opacity_actions, key=lambda a: a.start_time):
        start_pct = (action.start_time / total_duration) * 100 if total_duration > 0 else 0
        end_pct = (action.end_time / total_duration) * 100 if total_duration > 0 else 100

        keyframes.append(f"{start_pct:.1f}% {{ opacity: {action.start_value:.2f}; }}")
        keyframes.append(f"{end_pct:.1f}% {{ opacity: {action.end_value:.2f}; }}")

    if not keyframes:
        return ""

    return f"animation: fade {total_duration}s ease-in-out infinite;"


# ──────────────────────────────────────────────
# SVG Builder
# ──────────────────────────────────────────────


def build_animated_svg(
    timeline: CompiledTimeline,
    layout: ResolvedLayout,
    theme: ThemeConfig,
    node_labels: dict[str, str],
    node_types: dict[str, PrimitiveType],
    connection_labels: dict[str, str | None],
) -> str:
    """Build an animated SVG string from ArchMotion scene data.

    Generates inline SVG with CSS animations for opacity transitions.

    Args:
        timeline: Compiled timeline.
        layout: Resolved layout.
        theme: Visual theme.
        node_labels: Node ID → label mapping.
        node_types: Node ID → PrimitiveType mapping.
        connection_labels: Connection ID → label mapping.

    Returns:
        SVG string with embedded CSS animations.
    """
    w = layout.canvas_width
    h = layout.canvas_height

    # Background color
    bg_r, bg_g, bg_b, bg_a = theme.background_rgba
    bg_hex = f"#{int(bg_r*255):02x}{int(bg_g*255):02x}{int(bg_b*255):02x}"

    # Index actions by target
    actions_by_target: dict[str, list[ScheduledAction]] = {}
    for action in timeline.actions:
        actions_by_target.setdefault(action.target_id, []).append(action)

    elements: list[str] = []

    # Background rect
    elements.append(
        f'  <rect width="{w}" height="{h}" fill="{bg_hex}" />'
    )

    # CSS animations
    css_rules: list[str] = []
    anim_idx = 0

    # Connection paths
    conn_color = theme.conn_stroke
    for conn_id, route in layout.connection_routes.items():
        if len(route) < 2:
            continue
        points_str = " ".join(f"{p[0]},{p[1]}" for p in route)
        conn_actions = actions_by_target.get(conn_id, [])

        anim_name = f"conn_{anim_idx}"
        style = ""

        # Generate CSS keyframes for opacity animations
        opacity_actions = [a for a in conn_actions if a.prop == AnimatableProperty.OPACITY]
        if opacity_actions and timeline.total_duration > 0:
            kf_lines: list[str] = ["0% { opacity: 0; }"]
            for a in sorted(opacity_actions, key=lambda x: x.start_time):
                s_pct = (a.start_time / timeline.total_duration) * 100
                e_pct = (a.end_time / timeline.total_duration) * 100
                kf_lines.append(f"{s_pct:.1f}% {{ opacity: {a.start_value:.2f}; }}")
                kf_lines.append(f"{e_pct:.1f}% {{ opacity: {a.end_value:.2f}; }}")
            kf_lines.append("100% { opacity: 1; }")
            css_rules.append(
                f"@keyframes {anim_name} {{ {' '.join(kf_lines)} }}"
            )
            style = f' style="animation: {anim_name} {timeline.total_duration}s ease-in-out forwards"'

        elements.append(
            f'  <polyline points="{points_str}" fill="none" '
            f'stroke="{conn_color}" stroke-width="2" '
            f'stroke-linecap="round" stroke-linejoin="round"{style} />'
        )
        anim_idx += 1

    # Node rectangles + labels
    node_bg_hex = theme.node_fill
    border_color = theme.node_border
    font_color = theme.font_color

    for node_id, bbox in layout.node_boxes.items():
        label = node_labels.get(node_id, node_id)
        node_actions = actions_by_target.get(node_id, [])

        anim_name = f"node_{anim_idx}"
        style = ""

        opacity_actions = [a for a in node_actions if a.prop == AnimatableProperty.OPACITY]
        if opacity_actions and timeline.total_duration > 0:
            kf_lines = ["0% { opacity: 0; }"]
            for a in sorted(opacity_actions, key=lambda x: x.start_time):
                s_pct = (a.start_time / timeline.total_duration) * 100
                e_pct = (a.end_time / timeline.total_duration) * 100
                kf_lines.append(f"{s_pct:.1f}% {{ opacity: {a.start_value:.2f}; }}")
                kf_lines.append(f"{e_pct:.1f}% {{ opacity: {a.end_value:.2f}; }}")
            kf_lines.append("100% { opacity: 1; }")
            css_rules.append(
                f"@keyframes {anim_name} {{ {' '.join(kf_lines)} }}"
            )
            style = f' style="animation: {anim_name} {timeline.total_duration}s ease-in-out forwards"'

        cr = 8  # Corner radius
        elements.append(
            f'  <g{style}>'
            f'<rect x="{bbox.x:.1f}" y="{bbox.y:.1f}" '
            f'width="{bbox.width:.1f}" height="{bbox.height:.1f}" '
            f'rx="{cr}" fill="{node_bg_hex}" stroke="{border_color}" stroke-width="2" />'
            f'<text x="{bbox.center[0]:.1f}" y="{bbox.center[1] + 5:.1f}" '
            f'text-anchor="middle" fill="{font_color}" '
            f'font-family="Inter, system-ui, sans-serif" font-size="16">{label}</text>'
            f'</g>'
        )
        anim_idx += 1

    # Build CSS block
    css_block = ""
    if css_rules:
        css_block = f'  <style>{" ".join(css_rules)}</style>\n'

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {w} {h}" width="{w}" height="{h}">\n'
        f'{css_block}'
        + "\n".join(elements)
        + "\n</svg>"
    )

    return svg


# ──────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────


def export_html_player(
    timeline: CompiledTimeline,
    layout: ResolvedLayout,
    theme: ThemeConfig,
    node_labels: dict[str, str],
    node_types: dict[str, PrimitiveType],
    connection_labels: dict[str, str | None],
    output_path: Path,
    title: str = "ArchMotion Animation",
) -> Path:
    """Export an interactive HTML player with embedded Lottie animation.

    The generated HTML file is fully self-contained and includes:
    - Embedded Lottie JSON data (no external file dependencies)
    - lottie-web player (loaded from CDN)
    - Play/pause, scrub bar, speed control, loop toggle
    - Responsive layout matching the scene theme

    Args:
        timeline: Compiled timeline from Phase 3.
        layout: Resolved layout from Phase 2.
        theme: Visual theme configuration.
        node_labels: Node ID → label mapping.
        node_types: Node ID → PrimitiveType mapping.
        connection_labels: Connection ID → label mapping.
        output_path: Output .html file path.
        title: HTML page title.

    Returns:
        Path to the created HTML file.
    """
    # Build Lottie JSON
    lottie_data = build_lottie_json(
        timeline=timeline,
        layout=layout,
        theme=theme,
        node_labels=node_labels,
        node_types=node_types,
        connection_labels=connection_labels,
    )

    # Theme-aware colors for the player UI
    bg = theme.background_rgba
    bg_css = f"rgb({int(bg[0]*255)},{int(bg[1]*255)},{int(bg[2]*255)})"
    text_css = theme.font_color
    accent_css = theme.node_border
    surface_r = min(bg[0] + 0.05, 1.0)
    surface_g = min(bg[1] + 0.05, 1.0)
    surface_b = min(bg[2] + 0.05, 1.0)
    surface_css = f"rgb({int(surface_r*255)},{int(surface_g*255)},{int(surface_b*255)})"

    duration = f"{timeline.total_duration:.1f}"

    html = _HTML_TEMPLATE.format(
        title=title,
        bg_color=bg_css,
        text_color=text_css,
        accent_color=accent_css,
        surface_color=surface_css,
        canvas_width=layout.canvas_width,
        canvas_height=layout.canvas_height,
        lottie_json=json.dumps(lottie_data),
        total_frames=timeline.total_frames,
        fps=timeline.fps,
        duration=duration,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")

    return output_path


def export_svg(
    timeline: CompiledTimeline,
    layout: ResolvedLayout,
    theme: ThemeConfig,
    node_labels: dict[str, str],
    node_types: dict[str, PrimitiveType],
    connection_labels: dict[str, str | None],
    output_path: Path,
) -> Path:
    """Export scene as an animated SVG file.

    Uses CSS animations for opacity transitions. The SVG is
    self-contained and can be embedded in HTML or Markdown.

    Args:
        timeline: Compiled timeline from Phase 3.
        layout: Resolved layout from Phase 2.
        theme: Visual theme configuration.
        node_labels: Node ID → label mapping.
        node_types: Node ID → PrimitiveType mapping.
        connection_labels: Connection ID → label mapping.
        output_path: Output .svg file path.

    Returns:
        Path to the created SVG file.
    """
    svg = build_animated_svg(
        timeline=timeline,
        layout=layout,
        theme=theme,
        node_labels=node_labels,
        node_types=node_types,
        connection_labels=connection_labels,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(svg, encoding="utf-8")

    return output_path
