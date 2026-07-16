"""Production-MVP smoke scene: Python CLI, axes, text, updater, MP4, and PNG."""

from __future__ import annotations

from archmotion import (
    AnimationGroup,
    Axes,
    Create,
    Dot,
    Scene,
    Text,
    ValueTracker,
    Write,
    always_redraw,
)


class MvpScene(Scene):
    """Exercise the minimum viable 2D authoring and render contract."""

    def construct(self) -> None:
        """Build and animate a graph with a tracker-driven point."""
        width, height = self.resolution
        axes = Axes(
            x_range=(-3.0, 3.0),
            y_range=(-1.0, 5.0),
            x_length=width * 0.65,
            y_length=height * 0.55,
            center=(width * 0.5, height * 0.58),
        ).set_stroke("#94a3b8", width=1.5)
        graph = axes.plot(lambda x: 0.45 * x * x, samples=96).set_stroke(
            "#38bdf8",
            width=3.0,
        )
        title = Text("ArchMotion 2D MVP", size=max(18.0, height * 0.08))
        title.set_fill("#f8fafc").move_to(width * 0.5, height * 0.12)

        x_value = ValueTracker(-3.0)

        def moving_point() -> Dot:
            x = x_value.get_value()
            dot = Dot(
                axes.c2p(x, 0.45 * x * x),
                radius=max(3.0, height * 0.018),
            )
            dot.set_fill("yellow")
            return dot

        point = always_redraw(moving_point)
        self.add(axes, graph, title, x_value, point)
        self.play(
            AnimationGroup(
                Create(axes),
                Create(graph),
                Write(title),
                lag_ratio=0.1,
                run_time=0.8,
            )
        )
        self.play(x_value.animate.set_value(3.0).set_run_time(1.2))
        self.wait(0.2)


if __name__ == "__main__":
    MvpScene().render("archmotion_mvp.mp4")
