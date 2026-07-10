"""Interactive HTML player exporter for v2 scenes.

Builds a self-contained HTML file with embedded Lottie JSON (from the v2 Lottie
exporter) + the lottie-web player + interactive controls. Mirrors the v1 HTML
player output but consumes a v2 :class:`~archmotion.core.scene.Scene` directly.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from archmotion.core.scene import Scene


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
  #lottie-player {{ width: 100%; height: 100%; }}
  .controls {{
    display: flex; align-items: center; gap: 12px; margin-top: 16px;
    padding: 12px 20px; background: var(--surface); border-radius: 10px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.2);
  }}
  .btn {{
    background: none; border: 2px solid var(--accent); color: var(--accent);
    width: 36px; height: 36px; border-radius: 50%; cursor: pointer;
    display: flex; align-items: center; justify-content: center;
    font-size: 14px; transition: all 0.2s;
  }}
  .btn:hover {{ background: var(--accent); color: var(--bg); }}
  .scrub {{
    flex: 1; -webkit-appearance: none; height: 4px; border-radius: 2px;
    background: rgba(128,128,128,0.3); outline: none;
  }}
  .scrub::-webkit-slider-thumb {{
    -webkit-appearance: none; width: 14px; height: 14px; border-radius: 50%;
    background: var(--accent); cursor: pointer;
  }}
  .info {{ margin-top: 8px; font-size: 12px; opacity: 0.5; }}
</style>
</head>
<body>
<div class="player-container"><div id="lottie-player"></div></div>
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
    renderer: 'svg', loop: true, autoplay: true, animationData: animData,
  }});
  const btnPlay = document.getElementById('btn-play');
  const scrub = document.getElementById('scrub');
  const btnSpeed = document.getElementById('btn-speed');
  const btnLoop = document.getElementById('btn-loop');
  let isPlaying = true; let looping = true;
  const speeds = [0.5, 1, 1.5, 2]; let speedIdx = 1;
  btnPlay.innerHTML = '&#9646;&#9646;';
  btnPlay.addEventListener('click', () => {{
    if (isPlaying) {{ player.pause(); btnPlay.innerHTML = '&#9654;'; }}
    else {{ player.play(); btnPlay.innerHTML = '&#9646;&#9646;'; }}
    isPlaying = !isPlaying;
  }});
  scrub.addEventListener('input', () => {{
    const frame = (scrub.value / 100) * player.totalFrames;
    player.goToAndStop(frame, true); isPlaying = false; btnPlay.innerHTML = '&#9654;';
  }});
  player.addEventListener('enterFrame', () => {{
    scrub.value = (player.currentFrame / player.totalFrames) * 100;
  }});
  btnSpeed.addEventListener('click', () => {{
    speedIdx = (speedIdx + 1) % speeds.length;
    player.setSpeed(speeds[speedIdx]); btnSpeed.textContent = speeds[speedIdx] + 'x';
  }});
  btnLoop.addEventListener('click', () => {{
    looping = !looping; player.loop = looping;
    btnLoop.style.opacity = looping ? '1' : '0.4';
  }});
}})();
</script>
</body>
</html>"""


def build_html(scene: Scene, *, title: str = "ArchMotion Animation") -> str:
    """Build a self-contained interactive HTML player string for a v2 scene.

    Embeds the scene's Lottie JSON (via the v2 Lottie exporter) plus the
    lottie-web player and interactive controls.

    Args:
        scene: A v2 :class:`Scene` (with recorded animations).
        title: HTML page title.

    Returns:
        A fully self-contained HTML string.
    """
    from archmotion.exporter.lottie_v2 import build_lottie

    timeline = scene.compile_timeline()
    lottie_data = build_lottie(scene, title=title)
    theme = scene.theme

    bg = theme.background_rgba
    bg_css = f"rgb({int(bg[0] * 255)},{int(bg[1] * 255)},{int(bg[2] * 255)})"
    surface_css = (
        f"rgb({int(min(bg[0] + 0.05, 1.0) * 255)},"
        f"{int(min(bg[1] + 0.05, 1.0) * 255)},"
        f"{int(min(bg[2] + 0.05, 1.0) * 255)})"
    )
    w, h = scene.resolution

    return _HTML_TEMPLATE.format(
        title=title,
        bg_color=bg_css,
        text_color=theme.font_color,
        accent_color=theme.node_border,
        surface_color=surface_css,
        canvas_width=w,
        canvas_height=h,
        lottie_json=json.dumps(lottie_data),
        total_frames=timeline.total_frames,
        fps=timeline.fps,
        duration=f"{timeline.total_duration:.1f}",
    )
