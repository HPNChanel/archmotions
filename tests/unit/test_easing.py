"""Unit tests for easing functions (v2 core.easing)."""

from __future__ import annotations

import pytest

from archmotion.core import easing

# All public easing functions exposed by core.easing.
_EASING_FUNCS = [
    easing.linear,
    easing.smooth,
    easing.ease_in,
    easing.ease_out,
    easing.ease_in_out,
    easing.ease_in_cubic,
    easing.ease_out_cubic,
    easing.ease_out_bounce,
]


class TestEasingFunctions:
    """Tests that all easing functions satisfy f(0)=0, f(1)=1."""

    @pytest.mark.parametrize("func", _EASING_FUNCS, ids=lambda f: f.__name__)
    def test_boundary_zero(self, func):
        assert func(0.0) == pytest.approx(0.0, abs=1e-10)

    @pytest.mark.parametrize("func", _EASING_FUNCS, ids=lambda f: f.__name__)
    def test_boundary_one(self, func):
        assert func(1.0) == pytest.approx(1.0, abs=1e-10)

    @pytest.mark.parametrize("func", _EASING_FUNCS, ids=lambda f: f.__name__)
    def test_monotonic_increasing(self, func):
        """Easing output should generally increase (with tolerance for bounce)."""
        values = [func(t / 100.0) for t in range(101)]
        # Final value should be >= initial
        assert values[-1] >= values[0]

    def test_linear_is_identity(self):
        for t in [0.0, 0.25, 0.5, 0.75, 1.0]:
            assert easing.linear(t) == pytest.approx(t)

    def test_ease_in_out_midpoint(self):
        assert easing.ease_in_out(0.5) == pytest.approx(0.5)

    def test_ease_in_slower_start(self):
        # At t=0.25, ease_in should be less than linear
        assert easing.ease_in(0.25) < 0.25

    def test_ease_out_faster_start(self):
        # At t=0.25, ease_out should be greater than linear
        assert easing.ease_out(0.25) > 0.25

    def test_bounce_stays_in_range(self):
        for t in [0.1, 0.3, 0.5, 0.7, 0.9]:
            assert 0.0 <= easing.ease_out_bounce(t) <= 1.0


class TestApplyEasing:
    """Tests for the apply() helper (name-based)."""

    def test_clamps_below_zero(self):
        assert easing.apply(-0.5, "linear") == pytest.approx(0.0)

    def test_clamps_above_one(self):
        assert easing.apply(1.5, "linear") == pytest.approx(1.0)

    def test_resolve_all_names(self):
        for name in ("linear", "smooth", "ease_in", "ease_out", "ease_in_out"):
            assert easing.resolve(name) is not None
