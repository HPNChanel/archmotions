"""Bezier + arc geometry helpers (pure functions, numpy-backed).

Point arrays in ArchMotion are stored as a flat sequence: an initial anchor
(the ``moveTo``) followed by cubic-Bezier triplets ``[h1, h2, end]`` where the
start of each cubic is the previous point. These helpers build and measure such
geometry without touching any renderer.
"""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import NDArray

from archmotion._types import Point

FloatArray = NDArray[np.float64]
Triplet = tuple[Point, Point, Point]


def cubic_at(p0: Point, p1: Point, p2: Point, p3: Point, t: float) -> Point:
    """Evaluate a cubic Bezier at parameter ``t`` in [0, 1]."""
    mt = 1.0 - t
    a = mt * mt * mt
    b = 3.0 * mt * mt * t
    c = 3.0 * mt * t * t
    d = t * t * t
    x = a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0]
    y = a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]
    return (x, y)


def quad_to_cubic(p0: Point, control: Point, p1: Point) -> tuple[Point, Point, Point]:
    """Convert a quadratic Bezier into the cubic triplet ``[h1, h2, end]``."""
    h1 = (p0[0] + 2.0 / 3.0 * (control[0] - p0[0]), p0[1] + 2.0 / 3.0 * (control[1] - p0[1]))
    h2 = (p1[0] + 2.0 / 3.0 * (control[0] - p1[0]), p1[1] + 2.0 / 3.0 * (control[1] - p1[1]))
    return (h1, h2, p1)


def line_triplet(p0: Point, end: Point) -> Triplet:
    """Represent a straight line as a degenerate cubic triplet."""
    h1 = (p0[0] + (end[0] - p0[0]) / 3.0, p0[1] + (end[1] - p0[1]) / 3.0)
    h2 = (p0[0] + 2.0 * (end[0] - p0[0]) / 3.0, p0[1] + 2.0 * (end[1] - p0[1]) / 3.0)
    return (h1, h2, end)


def arc_triplets(
    center: Point,
    radius: float,
    start_angle: float,
    sweep_angle: float,
    n_segments: int | None = None,
) -> tuple[Point, list[Triplet]]:
    """Approximate a circular arc as cubic-Bezier triplets.

    Args:
        center: Arc center.
        radius: Arc radius.
        start_angle: Start angle in degrees.
        sweep_angle: Sweep in degrees (positive = clockwise in y-down space).
        n_segments: Number of cubic segments; auto-chosen if ``None``.

    Returns:
        ``(start_point, triplets)`` where ``start_point`` is the arc's first
        point (the ``moveTo``) and ``triplets`` is the list of cubics.
    """
    if abs(sweep_angle) < 1e-6:
        pt = _polar(center, radius, start_angle)
        return pt, []
    if n_segments is None:
        # ~one cubic per 90 degrees, minimum 1.
        n_segments = max(1, math.ceil(abs(sweep_angle) / 90.0))

    seg = sweep_angle / n_segments
    k = (4.0 / 3.0) * math.tan(math.radians(seg) / 4.0) * radius

    start_pt = _polar(center, radius, start_angle)
    triplets: list[Triplet] = []

    cur_angle = start_angle
    cur_pt = start_pt
    for _ in range(n_segments):
        nxt_angle = cur_angle + seg
        nxt_pt = _polar(center, radius, nxt_angle)
        # Tangent direction at cur_pt and nxt_pt (perpendicular to radius).
        t_in = _tangent(cur_angle, sweep_angle >= 0)
        t_out = _tangent(nxt_angle, sweep_angle >= 0)
        h1 = (cur_pt[0] + t_in[0] * k, cur_pt[1] + t_in[1] * k)
        h2 = (nxt_pt[0] - t_out[0] * k, nxt_pt[1] - t_out[1] * k)
        triplets.append((h1, h2, nxt_pt))
        cur_angle = nxt_angle
        cur_pt = nxt_pt

    return start_pt, triplets


def _polar(center: Point, radius: float, angle_deg: float) -> Point:
    rad = math.radians(angle_deg)
    return (center[0] + radius * math.cos(rad), center[1] + radius * math.sin(rad))


def _tangent(angle_deg: float, clockwise: bool) -> Point:
    rad = math.radians(angle_deg)
    sign = 1.0 if clockwise else -1.0
    return (-sign * math.sin(rad), sign * math.cos(rad))


def bezier_length(
    p0: Point,
    p1: Point,
    p2: Point,
    p3: Point,
    samples: int = 16,
) -> float:
    """Approximate the arc length of a cubic Bezier by line segments."""
    if samples < 2:
        return math.dist(p0, p3)
    prev = p0
    total = 0.0
    for i in range(1, samples + 1):
        t = i / samples
        pt = cubic_at(p0, p1, p2, p3, t)
        total += math.dist(prev, pt)
        prev = pt
    return total


def resample_array(points: FloatArray, target_count: int) -> FloatArray:
    """Pad/truncate a point array to ``target_count`` (row count).

    Padding repeats the last 3-point cubic triplet so the morphed shape keeps
    its contour structure (each appended triplet is a zero-length segment at
    the current endpoint). Truncation removes whole triplets from the end.
    """
    current = points.shape[0]
    if current == target_count or current == 0:
        return points
    if current > target_count:
        return points[:target_count]

    out = np.zeros((target_count, 2), dtype=np.float64)
    out[:current] = points
    # Repeat the last complete triplet (3 points) as zero-length segments.
    triplet_start = current - (current % 3 if current % 3 != 0 else 3)
    triplet_start = max(1, triplet_start)
    last_triplet = points[triplet_start:current]
    if last_triplet.shape[0] == 0:
        last_point = points[-1]
        for i in range(current, target_count):
            out[i] = last_point
        return out
    fill_len = last_triplet.shape[0]
    i = current
    while i < target_count:
        chunk = min(fill_len, target_count - i)
        out[i : i + chunk] = last_triplet[:chunk]
        i += chunk
    return out
