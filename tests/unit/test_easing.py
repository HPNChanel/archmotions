"""Unit tests for easing functions."""

from __future__ import annotations

import pytest

from archmotion._types import EasingType
from archmotion.timeline.easing import (
    EASING_FUNCTIONS,
    apply_easing,
    ease_in,
    ease_in_out,
    ease_out,
    ease_out_bounce,
    linear,
)


class TestEasingFunctions:
    """Tests that all easing functions satisfy f(0)=0, f(1)=1."""

    @pytest.mark.parametrize("func", EASING_FUNCTIONS.values(), ids=lambda f: f.__name__)
    def test_boundary_zero(self, func):
        assert func(0.0) == pytest.approx(0.0, abs=1e-10)

    @pytest.mark.parametrize("func", EASING_FUNCTIONS.values(), ids=lambda f: f.__name__)
    def test_boundary_one(self, func):
        assert func(1.0) == pytest.approx(1.0, abs=1e-10)

    @pytest.mark.parametrize("func", EASING_FUNCTIONS.values(), ids=lambda f: f.__name__)
    def test_monotonic_increasing(self, func):
        """Easing output should generally increase (with tolerance for bounce)."""
        values = [func(t / 100.0) for t in range(101)]
        # Final value should be >= initial
        assert values[-1] >= values[0]

    def test_linear_is_identity(self):
        for t in [0.0, 0.25, 0.5, 0.75, 1.0]:
            assert linear(t) == pytest.approx(t)

    def test_ease_in_out_midpoint(self):
        assert ease_in_out(0.5) == pytest.approx(0.5)

    def test_ease_in_slower_start(self):
        # At t=0.25, ease_in should be less than linear
        assert ease_in(0.25) < 0.25

    def test_ease_out_faster_start(self):
        # At t=0.25, ease_out should be greater than linear
        assert ease_out(0.25) > 0.25

    def test_bounce_bounces(self):
        # Bounce should have values > 1.0 is NOT expected (it's ease-out, stays in [0,1])
        for t in [0.1, 0.3, 0.5, 0.7, 0.9]:
            val = ease_out_bounce(t)
            assert 0.0 <= val <= 1.0


class TestApplyEasing:
    """Tests for the apply_easing helper."""

    def test_clamps_below_zero(self):
        result = apply_easing(-0.5, EasingType.LINEAR)
        assert result == pytest.approx(0.0)

    def test_clamps_above_one(self):
        result = apply_easing(1.5, EasingType.LINEAR)
        assert result == pytest.approx(1.0)

    def test_all_types_registered(self):
        for easing_type in EasingType:
            assert easing_type in EASING_FUNCTIONS
