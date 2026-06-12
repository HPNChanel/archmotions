"""Unit tests for Phase 3 -- Timeline Compiler.

Tests cover:
    - FadeIn decomposition (single + multi-target)
    - FadeOut decomposition (single + multi-target)
    - Transfer decomposition (single connection, multi-hop, reverse)
    - Pulse decomposition (ramp up + ramp down)
    - CompiledTimeline.actions_at() frame query
    - CompiledTimeline.snapshot_at() full state
    - Sequential vs concurrent timing
    - Total frames calculation
    - Unknown animation type error
    - Edge cases (empty timeline, boundary frames)
"""

from __future__ import annotations

import pytest

from archmotion._types import AnimatableProperty, EasingType
from archmotion.api.connections import Connection
from archmotion.api.primitives import Database, Node
from archmotion.motions._animations import FadeIn, FadeOut, Pulse, Transfer
from archmotion.timeline.actions import ScheduledAction
from archmotion.timeline.compiler import (
    CompiledTimeline,
    TransferMeta,
    compile_timeline,
)


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

FPS = 60


def _make_play_call(
    animation: object,
    start_time: float = 0.0,
    duration: float | None = None,
) -> dict[str, object]:
    """Build a play_call dict matching Scene._play_calls format."""
    effective_duration = duration if duration is not None else getattr(animation, "duration", 1.0)
    return {
        "animation": animation,
        "start_time": start_time,
        "duration": effective_duration,
    }


# ──────────────────────────────────────────────
# FadeIn Tests
# ──────────────────────────────────────────────


class TestFadeInDecomposition:
    """FadeIn produces OPACITY 0 -> 1 per target."""

    def test_single_target(self):
        node = Node("Server")
        anim = FadeIn(node)
        calls = [_make_play_call(anim, start_time=0.0)]

        result = compile_timeline(calls, total_duration=0.5, fps=FPS)

        assert len(result.actions) == 1
        action = result.actions[0]
        assert action.target_id == node.id
        assert action.prop == AnimatableProperty.OPACITY
        assert action.start_value == 0.0
        assert action.end_value == 1.0
        assert action.start_time == 0.0
        assert action.end_time == 0.5

    def test_multiple_targets(self):
        a = Node("A")
        b = Node("B")
        c = Node("C")
        anim = FadeIn(a, b, c, duration=0.3)
        calls = [_make_play_call(anim, start_time=1.0)]

        result = compile_timeline(calls, total_duration=1.3, fps=FPS)

        assert len(result.actions) == 3
        target_ids = {act.target_id for act in result.actions}
        assert target_ids == {a.id, b.id, c.id}

        # All share same timing
        for act in result.actions:
            assert act.start_time == 1.0
            assert act.end_time == 1.3
            assert act.prop == AnimatableProperty.OPACITY

    def test_easing_preserved(self):
        node = Node("X")
        anim = FadeIn(node, easing=EasingType.EASE_IN_CUBIC)
        calls = [_make_play_call(anim)]

        result = compile_timeline(calls, total_duration=0.5, fps=FPS)
        assert result.actions[0].easing == EasingType.EASE_IN_CUBIC


# ──────────────────────────────────────────────
# FadeOut Tests
# ──────────────────────────────────────────────


class TestFadeOutDecomposition:
    """FadeOut produces OPACITY 1 -> 0 per target."""

    def test_single_target(self):
        node = Node("Server")
        anim = FadeOut(node, duration=0.4)
        calls = [_make_play_call(anim, start_time=2.0)]

        result = compile_timeline(calls, total_duration=2.4, fps=FPS)

        assert len(result.actions) == 1
        action = result.actions[0]
        assert action.start_value == 1.0
        assert action.end_value == 0.0
        assert action.start_time == 2.0
        assert action.end_time == 2.4

    def test_multiple_targets(self):
        a = Node("A")
        b = Node("B")
        anim = FadeOut(a, b)
        calls = [_make_play_call(anim)]

        result = compile_timeline(calls, total_duration=0.5, fps=FPS)
        assert len(result.actions) == 2
        for act in result.actions:
            assert act.start_value == 1.0
            assert act.end_value == 0.0


# ──────────────────────────────────────────────
# Transfer Tests
# ──────────────────────────────────────────────


class TestTransferDecomposition:
    """Transfer produces PATH_PROGRESS on a virtual packet."""

    def test_single_connection(self):
        a = Node("A")
        b = Node("B")
        conn = Connection(a, b)
        anim = Transfer(conn, payload="GET /api", duration=1.0)
        calls = [_make_play_call(anim, start_time=0.0)]

        result = compile_timeline(calls, total_duration=1.0, fps=FPS)

        # One PATH_PROGRESS action
        assert len(result.actions) == 1
        action = result.actions[0]
        assert action.prop == AnimatableProperty.PATH_PROGRESS
        assert action.start_value == 0.0
        assert action.end_value == 1.0

        # TransferMeta created
        assert len(result.transfer_metas) == 1
        meta = result.transfer_metas[0]
        assert meta.packet_id == action.target_id
        assert meta.connection_ids == (conn.id,)
        assert meta.payload == "GET /api"
        assert meta.reverse is False

    def test_reverse_transfer(self):
        a = Node("A")
        b = Node("B")
        conn = Connection(a, b)
        anim = Transfer(conn, payload="200 OK", reverse=True)
        calls = [_make_play_call(anim)]

        result = compile_timeline(calls, total_duration=1.0, fps=FPS)

        action = result.actions[0]
        assert action.start_value == 1.0
        assert action.end_value == 0.0

        meta = result.transfer_metas[0]
        assert meta.reverse is True

    def test_multi_hop_transfer(self):
        a = Node("A")
        b = Node("B")
        c = Node("C")
        conn1 = Connection(a, b)
        conn2 = Connection(b, c)
        anim = Transfer([conn1, conn2], payload="Data", duration=2.0)
        calls = [_make_play_call(anim)]

        result = compile_timeline(calls, total_duration=2.0, fps=FPS)

        meta = result.transfer_metas[0]
        assert meta.connection_ids == (conn1.id, conn2.id)

    def test_packet_color(self):
        a = Node("A")
        b = Node("B")
        conn = Connection(a, b)
        anim = Transfer(conn, packet_color="#ff5733")
        calls = [_make_play_call(anim)]

        result = compile_timeline(calls, total_duration=1.0, fps=FPS)
        assert result.transfer_metas[0].packet_color == "#ff5733"


# ──────────────────────────────────────────────
# Pulse Tests
# ──────────────────────────────────────────────


class TestPulseDecomposition:
    """Pulse produces 2 GLOW_INTENSITY actions (ramp up + down)."""

    def test_pulse_creates_two_actions(self):
        node = Node("Gateway")
        anim = Pulse(node, intensity=0.8, duration=0.6)
        calls = [_make_play_call(anim, start_time=1.0)]

        result = compile_timeline(calls, total_duration=1.6, fps=FPS)

        assert len(result.actions) == 2
        ramp_up = result.actions[0]
        ramp_down = result.actions[1]

        # Ramp up: 0 -> 0.8 (first half)
        assert ramp_up.prop == AnimatableProperty.GLOW_INTENSITY
        assert ramp_up.start_value == 0.0
        assert ramp_up.end_value == 0.8
        assert ramp_up.start_time == 1.0
        assert ramp_up.end_time == pytest.approx(1.3)
        assert ramp_up.easing == EasingType.EASE_IN

        # Ramp down: 0.8 -> 0 (second half)
        assert ramp_down.start_value == 0.8
        assert ramp_down.end_value == 0.0
        assert ramp_down.start_time == pytest.approx(1.3)
        assert ramp_down.end_time == pytest.approx(1.6)
        assert ramp_down.easing == EasingType.EASE_OUT

    def test_pulse_default_intensity(self):
        node = Node("Node")
        anim = Pulse(node)
        calls = [_make_play_call(anim)]

        result = compile_timeline(calls, total_duration=0.5, fps=FPS)
        ramp_up = result.actions[0]
        assert ramp_up.end_value == 0.8  # DEFAULT_PULSE_INTENSITY


# ──────────────────────────────────────────────
# CompiledTimeline Query Tests
# ──────────────────────────────────────────────


class TestActionsAt:
    """CompiledTimeline.actions_at() returns active actions at a frame."""

    def test_active_within_range(self):
        node = Node("S")
        anim = FadeIn(node, duration=0.5)
        calls = [_make_play_call(anim, start_time=0.0)]

        result = compile_timeline(calls, total_duration=0.5, fps=FPS)

        # Frame 0 (t=0.0) should have the action
        active = result.actions_at(0)
        assert len(active) == 1
        assert active[0].target_id == node.id

    def test_inactive_after_range(self):
        node = Node("S")
        anim = FadeIn(node, duration=0.5)
        calls = [_make_play_call(anim, start_time=0.0)]

        result = compile_timeline(calls, total_duration=1.0, fps=FPS)

        # Frame 59 (t=0.98s) is after the 0.5s action
        active = result.actions_at(59)
        assert len(active) == 0

    def test_boundary_frame(self):
        node = Node("S")
        anim = FadeIn(node, duration=0.5)
        calls = [_make_play_call(anim, start_time=0.0)]

        result = compile_timeline(calls, total_duration=0.5, fps=FPS)

        # Frame 29 (t=0.483s) is just before the end
        active = result.actions_at(29)
        assert len(active) == 1

    def test_negative_frame_returns_empty(self):
        result = compile_timeline([], total_duration=1.0, fps=FPS)
        assert result.actions_at(-1) == []

    def test_overflow_frame_returns_empty(self):
        result = compile_timeline([], total_duration=1.0, fps=FPS)
        assert result.actions_at(9999) == []


class TestSnapshotAt:
    """CompiledTimeline.snapshot_at() returns full property state."""

    def test_snapshot_during_fadein(self):
        node = Node("S")
        anim = FadeIn(node, duration=1.0)
        calls = [_make_play_call(anim)]

        result = compile_timeline(calls, total_duration=1.0, fps=FPS)

        # Mid-animation (frame 30, t=0.5s)
        snap = result.snapshot_at(30)
        assert node.id in snap
        opacity = snap[node.id][AnimatableProperty.OPACITY]
        # Should be between 0 and 1 (eased)
        assert 0.0 < opacity < 1.0

    def test_snapshot_empty_on_invalid_frame(self):
        result = compile_timeline([], total_duration=1.0, fps=FPS)
        assert result.snapshot_at(-1) == {}


# ──────────────────────────────────────────────
# Total Frames Calculation
# ──────────────────────────────────────────────


class TestTotalFrames:
    """Total frame count should be ceil(duration * fps)."""

    def test_exact_duration(self):
        result = compile_timeline([], total_duration=2.0, fps=60)
        assert result.total_frames == 120

    def test_fractional_duration(self):
        result = compile_timeline([], total_duration=1.5, fps=60)
        assert result.total_frames == 90

    def test_non_exact_ceil(self):
        result = compile_timeline([], total_duration=0.3, fps=60)
        assert result.total_frames == 18  # 0.3 * 60 = 18.0

    def test_minimum_one_frame(self):
        result = compile_timeline([], total_duration=0.001, fps=60)
        assert result.total_frames >= 1


# ──────────────────────────────────────────────
# Sequential + Concurrent Timing
# ──────────────────────────────────────────────


class TestSequentialTiming:
    """Sequential play_calls should have non-overlapping time ranges."""

    def test_two_sequential_fades(self):
        a = Node("A")
        b = Node("B")

        calls = [
            _make_play_call(FadeIn(a, duration=0.5), start_time=0.0),
            _make_play_call(FadeIn(b, duration=0.5), start_time=0.5),
        ]

        result = compile_timeline(calls, total_duration=1.0, fps=FPS)

        assert len(result.actions) == 2
        act_a = next(a for a in result.actions if a.target_id == a.target_id)

        # Verify correct timeline separation
        actions_sorted = sorted(result.actions, key=lambda x: x.start_time)
        assert actions_sorted[0].end_time <= actions_sorted[1].start_time


class TestConcurrentTiming:
    """Concurrent play_calls share the same start_time."""

    def test_concurrent_same_start(self):
        a = Node("A")
        b = Node("B")

        # Both start at t=0.0 (concurrent block)
        calls = [
            _make_play_call(FadeIn(a, duration=0.5), start_time=0.0),
            _make_play_call(FadeIn(b, duration=0.5), start_time=0.0),
        ]

        result = compile_timeline(calls, total_duration=0.5, fps=FPS)

        assert len(result.actions) == 2
        assert result.actions[0].start_time == result.actions[1].start_time == 0.0


# ──────────────────────────────────────────────
# Error Cases
# ──────────────────────────────────────────────


class TestUnknownAnimation:
    """Unknown animation types should raise TypeError."""

    def test_raises_on_unknown(self):
        calls = [_make_play_call("not_an_animation", start_time=0.0, duration=1.0)]
        with pytest.raises(TypeError, match="Unknown animation type"):
            compile_timeline(calls, total_duration=1.0, fps=FPS)


# ──────────────────────────────────────────────
# Integration: Full Scene Scenario
# ──────────────────────────────────────────────


class TestFullScenario:
    """Golden Script: Login Flow timeline compilation."""

    def test_login_flow_timeline(self):
        client = Node("User Mobile")
        gateway = Node("API Gateway")
        auth = Node("Auth Service")
        db = Database("Users DB")

        conn_cg = Connection(client, gateway)
        conn_ga = Connection(gateway, auth)
        conn_ad = Connection(auth, db)

        # Simulate Scene.play() calls
        calls = [
            # t=0.0: FadeIn all nodes
            _make_play_call(FadeIn(client, gateway, auth, db, duration=0.5), start_time=0.0),
            # t=0.5: Transfer client -> gateway
            _make_play_call(Transfer(conn_cg, payload="POST /login", duration=1.0), start_time=0.5),
            # t=1.5: Transfer gateway -> auth
            _make_play_call(Transfer(conn_ga, payload="Validate", duration=1.0), start_time=1.5),
            # t=2.5: Pulse auth
            _make_play_call(Pulse(auth, duration=0.5), start_time=2.5),
            # t=3.0: Transfer auth -> db
            _make_play_call(Transfer(conn_ad, payload="SELECT *", duration=1.0), start_time=3.0),
            # t=4.0: Transfer reverse: separate connections for reverse path
            _make_play_call(
                Transfer(conn_ad, payload="200 OK", reverse=True, duration=2.0),
                start_time=4.0,
            ),
        ]

        total_duration = 6.0
        result = compile_timeline(calls, total_duration=total_duration, fps=FPS)

        # 4 FadeIn + 4 Transfer + 2 Pulse = 10 actions
        assert len(result.actions) == 10

        # 4 TransferMeta (4 Transfer calls)
        assert len(result.transfer_metas) == 4

        # Total frames
        assert result.total_frames == 360  # 6.0 * 60

        # Actions are sorted by start_time
        for i in range(len(result.actions) - 1):
            assert result.actions[i].start_time <= result.actions[i + 1].start_time

        # Snapshot at frame 0 should have FadeIn actions
        snap = result.snapshot_at(0)
        assert len(snap) == 4  # All 4 nodes fading in

        # Snapshot at frame 300 (t=5.0s) should have the reverse transfer
        snap = result.snapshot_at(300)
        assert len(snap) >= 1  # At least the reverse transfer packet
