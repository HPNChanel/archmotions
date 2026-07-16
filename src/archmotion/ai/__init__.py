"""YAML AI Interface — load YAML files and build Scenes.

This module provides the bridge between LLM-generated YAML and
ArchMotion's rendering pipeline. LLMs can generate YAML files
following the SceneSpec schema, and this module parses + validates
+ builds a Scene object ready for rendering.

Usage:
    >>> from archmotion.ai import load_yaml
    >>> scene = load_yaml("architecture.yaml")
    >>> scene.render(output="output.mp4")

Security:
    - Uses yaml.safe_load() exclusively (no arbitrary code execution).
    - Pydantic v2 validates all fields with strict constraints.
    - File size limited to MAX_YAML_FILE_SIZE (1MB).
    - Node/connection counts bounded by constants.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import yaml
from pydantic import ValidationError

from archmotion.ai.builder import build_scene
from archmotion.ai.schema import SceneSpec
from archmotion.errors import ArchMotionError

if TYPE_CHECKING:
    from archmotion.core.scene import Scene

# Security: maximum YAML file size (1MB)
MAX_YAML_FILE_SIZE: int = 1_048_576


class YAMLParseError(ArchMotionError):
    """Raised when YAML parsing or validation fails.

    The error message is designed to be human-readable AND
    machine-readable (for LLM feedback loops).

    Attributes:
        errors: List of validation error dicts from Pydantic.
        yaml_content: The raw YAML content that failed.
    """

    def __init__(
        self,
        message: str,
        errors: list[dict[str, object]] | None = None,
        yaml_content: str | None = None,
    ) -> None:
        """Store the message, optional Pydantic errors, and offending YAML content."""
        super().__init__(message)
        self.errors = errors or []
        self.yaml_content = yaml_content


def load_yaml(source: str | Path) -> Scene:
    """Load a YAML file and build a Scene object.

    This is the main entry point for the YAML AI Interface.
    It performs: file read → yaml.safe_load() → Pydantic validation
    → Scene building.

    Args:
        source: Path to the YAML file.

    Returns:
        A fully-configured Scene ready for .render().

    Raises:
        FileNotFoundError: If the YAML file does not exist.
        YAMLParseError: If YAML parsing or schema validation fails.
        ValueError: If scene building encounters invalid references.

    Example:
        >>> scene = load_yaml("examples/microservices.yaml")
        >>> scene.render(output="microservices.mp4")
    """
    path = Path(source)

    # Security: file existence check
    if not path.exists():
        msg = f"YAML file not found: {path}"
        raise FileNotFoundError(msg)

    # Security: file size check
    file_size = path.stat().st_size
    if file_size > MAX_YAML_FILE_SIZE:
        msg = f"YAML file too large: {file_size:,} bytes (max {MAX_YAML_FILE_SIZE:,} bytes)"
        raise YAMLParseError(msg)

    # Read and parse YAML
    raw_content = path.read_text(encoding="utf-8")

    try:
        data = yaml.safe_load(raw_content)
    except yaml.YAMLError as exc:
        msg = f"Invalid YAML syntax: {exc}"
        raise YAMLParseError(msg, yaml_content=raw_content) from exc

    if not isinstance(data, dict):
        msg = f"YAML root must be a mapping/dict, got {type(data).__name__}"
        raise YAMLParseError(msg, yaml_content=raw_content)

    # Validate with Pydantic
    try:
        spec = SceneSpec(**data)
    except ValidationError as exc:
        error_list = [dict(error) for error in exc.errors()]
        # Build human-readable error report
        lines = ["YAML validation failed:"]
        for err in error_list:
            raw_location = err.get("loc", ())
            location = raw_location if isinstance(raw_location, (list, tuple)) else (raw_location,)
            loc = " → ".join(str(part) for part in location)
            lines.append(f"  • {loc}: {err['msg']}")
        msg = "\n".join(lines)
        raise YAMLParseError(msg, errors=error_list, yaml_content=raw_content) from exc

    # Build Scene from validated spec
    return build_scene(spec)


def parse_yaml_string(yaml_string: str) -> Scene:
    """Parse a YAML string directly and build a Scene.

    Useful for LLM integrations where the YAML comes from
    a generated response rather than a file.

    Args:
        yaml_string: Raw YAML content string.

    Returns:
        A fully-configured Scene ready for .render().

    Raises:
        YAMLParseError: If parsing or validation fails.
    """
    # Security: size check
    if len(yaml_string) > MAX_YAML_FILE_SIZE:
        msg = f"YAML content too large: {len(yaml_string):,} chars (max {MAX_YAML_FILE_SIZE:,})"
        raise YAMLParseError(msg)

    try:
        data = yaml.safe_load(yaml_string)
    except yaml.YAMLError as exc:
        msg = f"Invalid YAML syntax: {exc}"
        raise YAMLParseError(msg, yaml_content=yaml_string) from exc

    if not isinstance(data, dict):
        msg = f"YAML root must be a mapping/dict, got {type(data).__name__}"
        raise YAMLParseError(msg, yaml_content=yaml_string)

    try:
        spec = SceneSpec(**data)
    except ValidationError as exc:
        error_list = [dict(error) for error in exc.errors()]
        lines = ["YAML validation failed:"]
        for err in error_list:
            raw_location = err.get("loc", ())
            location = raw_location if isinstance(raw_location, (list, tuple)) else (raw_location,)
            loc = " → ".join(str(part) for part in location)
            lines.append(f"  • {loc}: {err['msg']}")
        msg = "\n".join(lines)
        raise YAMLParseError(msg, errors=error_list, yaml_content=yaml_string) from exc

    return build_scene(spec)


__all__ = [
    "MAX_YAML_FILE_SIZE",
    "SceneSpec",
    "YAMLParseError",
    "load_yaml",
    "parse_yaml_string",
]
