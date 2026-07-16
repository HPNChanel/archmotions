"""Load user-authored Python ``Scene`` subclasses for the CLI."""

from __future__ import annotations

import importlib.util
import inspect
import sys
import uuid
from pathlib import Path

from archmotion.core.scene import Scene


def load_python_scene(
    source: str | Path,
    scene_name: str | None = None,
    *,
    resolution: tuple[int, int] | str | None = None,
    fps: int | None = None,
) -> Scene:
    """Import ``source`` and instantiate one Scene subclass defined there.

    A scene name is optional only when the file defines exactly one concrete
    Scene subclass. Imported Scene classes are ignored, which prevents the base
    class itself from being selected accidentally.
    """
    path = Path(source).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Python scene file not found: {path}")
    module_name = f"_archmotion_user_{path.stem}_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot import Python scene file: {path}")
    module = importlib.util.module_from_spec(spec)
    parent = str(path.parent)
    inserted_path = parent not in sys.path
    if inserted_path:
        sys.path.insert(0, parent)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(module_name, None)
        if inserted_path:
            sys.path.remove(parent)

    candidates: dict[str, type[Scene]] = {}
    for name, value in vars(module).items():
        if (
            inspect.isclass(value)
            and issubclass(value, Scene)
            and value is not Scene
            and value.__module__ == module.__name__
        ):
            candidates[name] = value

    if scene_name is not None:
        scene_type = candidates.get(scene_name)
        if scene_type is None:
            available = ", ".join(sorted(candidates)) or "(none)"
            raise ValueError(
                f"Scene '{scene_name}' not found in {path.name}. Available: {available}"
            )
    elif len(candidates) == 1:
        scene_type = next(iter(candidates.values()))
    elif not candidates:
        raise ValueError(f"No Scene subclass is defined in {path.name}.")
    else:
        available = ", ".join(sorted(candidates))
        raise ValueError(f"Multiple scenes found in {path.name}; choose one: {available}")

    kwargs: dict[str, object] = {
        key: value for key, value in (("resolution", resolution), ("fps", fps)) if value is not None
    }
    try:
        inspect.signature(scene_type).bind(**kwargs)
    except TypeError as exc:
        raise TypeError(
            f"{scene_type.__name__} must accept Scene configuration keyword arguments "
            "or leave __init__ unmodified."
        ) from exc
    if resolution is not None and fps is not None:
        return scene_type(resolution=resolution, fps=fps)
    if resolution is not None:
        return scene_type(resolution=resolution)
    if fps is not None:
        return scene_type(fps=fps)
    return scene_type()


__all__ = ["load_python_scene"]
