"""Tests for loading user-authored Python Scene files."""

from __future__ import annotations

import pytest

from archmotion.loader import load_python_scene


def test_loads_unique_scene_with_configuration(tmp_path):
    source = tmp_path / "demo.py"
    source.write_text(
        """from archmotion import Circle, Scene

class Demo(Scene):
    def construct(self):
        self.add(Circle(radius=12, center=(30, 30)))
        self.wait(0.25)
""",
        encoding="utf-8",
    )

    scene = load_python_scene(source, resolution=(120, 80), fps=20)
    scene.resolve()
    assert scene.resolution == (120, 80)
    assert scene.fps == 20
    assert len(scene.graphics) == 1
    assert scene.total_duration == pytest.approx(0.25)


def test_loader_supports_sibling_imports_and_dataclass(tmp_path):
    helper = tmp_path / "helper.py"
    helper.write_text("RADIUS = 17\n", encoding="utf-8")
    source = tmp_path / "demo.py"
    source.write_text(
        """from dataclasses import dataclass
from archmotion import Circle, Scene
from helper import RADIUS

@dataclass
class Config:
    radius: float = RADIUS

class Demo(Scene):
    def construct(self):
        self.add(Circle(radius=Config().radius))
""",
        encoding="utf-8",
    )

    scene = load_python_scene(source)
    scene.resolve()
    assert scene.graphics[0].radius == 17


def test_loader_requires_name_when_multiple_scenes_exist(tmp_path):
    source = tmp_path / "demo.py"
    source.write_text(
        """from archmotion import Scene
class First(Scene): pass
class Second(Scene): pass
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Multiple scenes"):
        load_python_scene(source)
    assert type(load_python_scene(source, "Second")).__name__ == "Second"


def test_loader_does_not_mask_typeerror_from_scene_constructor(tmp_path):
    source = tmp_path / "demo.py"
    source.write_text(
        """from archmotion import Scene
class Demo(Scene):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        raise TypeError('constructor body failed')
""",
        encoding="utf-8",
    )

    with pytest.raises(TypeError, match="constructor body failed"):
        load_python_scene(source)
