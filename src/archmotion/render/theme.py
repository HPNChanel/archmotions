"""Theme configuration — color palette, font settings, visual constants.

Canonical home for :class:`ThemeConfig` (v2.0).

v0.2.0 ships with 4 themes: dark_terminal (default), neon_cyber,
blueprint, and light_paper. Theme selection is exposed through
both the Python API (Scene constructor) and the YAML AI Interface.

``conn_corner_radius`` controls the smoothness of Manhattan
routing corners. A value of 12.0px provides aesthetically
pleasing rounded turns; set to 0.0 for sharp 90° bends.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ThemeConfig:
    """Visual theme configuration for rendering.

    All color values are CSS hex strings or named colors.
    The renderer reads this config to determine every visual attribute.

    Attributes:
        name: Theme identifier.
        background_rgba: Canvas background as (R, G, B, A) floats [0-1].
        node_fill: Node interior color.
        node_border: Node border color.
        node_border_width: Border stroke width (pixels).
        node_corner_radius: Rounded corner radius (pixels).
        node_shadow_color: Drop shadow color (with alpha).
        node_shadow_offset: Shadow offset (dx, dy) in pixels.
        node_shadow_blur: Shadow blur radius (pixels).
        db_fill: Database cylinder fill color.
        db_border: Database border color.
        conn_stroke: Connection line color.
        conn_stroke_width: Connection stroke width (pixels).
        conn_arrow_size: Arrowhead size (pixels).
        font_family: Font family for labels.
        font_size: Default label font size (points).
        font_color: Label text color.
        packet_size: Packet circle diameter (pixels).
        packet_color: Default packet color.
        packet_label_size: Packet label font size (points).
        glow_blur_radius: Pulse/glow effect blur radius (pixels).
    """

    name: str = "dark_terminal"

    # Background
    background_rgba: tuple[float, float, float, float] = (0.07, 0.07, 0.11, 1.0)

    # Node
    node_fill: str = "#1e1e2e"
    node_border: str = "#45475a"
    node_border_width: float = 2.0
    node_corner_radius: float = 8.0
    node_shadow_color: str = "#00000066"
    node_shadow_offset: tuple[float, float] = (4.0, 4.0)
    node_shadow_blur: float = 8.0

    # Database
    db_fill: str = "#1e3a2e"
    db_border: str = "#4caf50"

    # Connection
    conn_stroke: str = "#585b70"
    conn_stroke_width: float = 2.0
    conn_arrow_size: float = 10.0

    # Typography
    font_family: str = "Fira Code"
    font_size: float = 14.0
    font_color: str = "#cdd6f4"

    # Packet
    packet_size: float = 12.0
    packet_color: str = "#89b4fa"
    packet_label_size: float = 10.0

    # Effects
    glow_blur_radius: float = 20.0

    # Connection Routing
    conn_corner_radius: float = 12.0


# ──────────────────────────────────────────────
# Theme Registry
# ──────────────────────────────────────────────

THEMES: dict[str, ThemeConfig] = {
    "dark_terminal": ThemeConfig(),
    "neon_cyber": ThemeConfig(
        name="neon_cyber",
        background_rgba=(0.03, 0.02, 0.06, 1.0),
        node_fill="#0d0b18",
        node_border="#ff007f",
        node_border_width=2.5,
        node_corner_radius=10.0,
        node_shadow_color="#ff007f33",
        node_shadow_offset=(0.0, 0.0),
        node_shadow_blur=16.0,
        db_fill="#0d0b18",
        db_border="#00ffff",
        conn_stroke="#00ffff",
        conn_stroke_width=2.0,
        conn_arrow_size=10.0,
        font_family="Fira Code",
        font_size=14.0,
        font_color="#39ff14",
        packet_size=12.0,
        packet_color="#ff00ff",
        packet_label_size=10.0,
        glow_blur_radius=30.0,
        conn_corner_radius=14.0,
    ),
    "blueprint": ThemeConfig(
        name="blueprint",
        background_rgba=(0.05, 0.14, 0.30, 1.0),
        node_fill="#0a2240",
        node_border="#ffffffbb",
        node_border_width=1.5,
        node_corner_radius=4.0,
        node_shadow_color="#00000044",
        node_shadow_offset=(2.0, 2.0),
        node_shadow_blur=4.0,
        db_fill="#0a2240",
        db_border="#ffffff88",
        conn_stroke="#ffffff88",
        conn_stroke_width=1.5,
        conn_arrow_size=9.0,
        font_family="Fira Code",
        font_size=13.0,
        font_color="#e2e8f0",
        packet_size=10.0,
        packet_color="#63b3ed",
        packet_label_size=9.0,
        glow_blur_radius=16.0,
        conn_corner_radius=8.0,
    ),
    "light_paper": ThemeConfig(
        name="light_paper",
        background_rgba=(0.98, 0.98, 0.96, 1.0),
        node_fill="#ffffff",
        node_border="#2d3748",
        node_border_width=1.5,
        node_corner_radius=6.0,
        node_shadow_color="#00000018",
        node_shadow_offset=(3.0, 3.0),
        node_shadow_blur=6.0,
        db_fill="#f7fafc",
        db_border="#2d3748",
        conn_stroke="#4a5568",
        conn_stroke_width=1.5,
        conn_arrow_size=9.0,
        font_family="Fira Code",
        font_size=14.0,
        font_color="#1a202c",
        packet_size=12.0,
        packet_color="#3182ce",
        packet_label_size=10.0,
        glow_blur_radius=12.0,
        conn_corner_radius=10.0,
    ),
}
"""Available themes. v0.2.0: dark_terminal, neon_cyber, blueprint, light_paper."""


def get_theme(name: str) -> ThemeConfig:
    """Retrieve a theme by name.

    Args:
        name: Theme identifier.

    Returns:
        ThemeConfig instance.

    Raises:
        ValueError: If theme name is not found.
    """
    if name not in THEMES:
        available = ", ".join(THEMES.keys())
        msg = f"Unknown theme '{name}'. Available: {available}"
        raise ValueError(msg)
    return THEMES[name]
