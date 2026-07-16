"""Math domain: LaTeX math as a first-class morphable VMobject."""

from __future__ import annotations

from archmotion.core.vmobject import VMobject


class MathText(VMobject):
    """LaTeX math rendered to a Bezier point array (morphable).

    Compiles ``latex_expr`` via ``latex`` + ``dvisvgm`` at construction. Requires
    the native binaries (not available in Pyodide — math scenes render CLI/MP4).
    """

    def __init__(self, latex_expr: str, *, font_size: float = 1.0) -> None:
        """Store the expression + scale, then compile it to points."""
        self.latex_expr = latex_expr
        self.font_size = font_size
        super().__init__()

    def generate_points(self) -> None:
        """Compile the LaTeX expression and adopt its parsed contours."""
        from archmotion.render.tex import tex_to_vmobject

        compiled = tex_to_vmobject(self.latex_expr, font_size=self.font_size)
        self._pts = list(compiled._pts)
        self._contour_starts = list(compiled._contour_starts)
        self._last = compiled._last


Tex = MathText
"""Alias matching Manim's ``Tex`` naming."""

MathTex = MathText
"""Alias matching Manim's ``MathTex`` naming."""
