"""Theme configuration — color palette, font settings, visual constants.

Architectural Note:
    MVP ships with a single theme: dark_terminal.
    Theme system extensibility is deferred to v0.2.0.
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


# ──────────────────────────────────────────────
# Theme Registry
# ──────────────────────────────────────────────

THEMES: dict[str, ThemeConfig] = {
    "dark_terminal": ThemeConfig(),
}
"""Available themes. MVP: only dark_terminal."""


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
