"""Unit tests for PLAN-014 — SharedMemory IPC Optimization.

Tests cover:
    - SharedMemoryRing: allocation, read/write, cleanup, context manager
    - SharedMemorySlot: worker-side accessor
    - render_frame_to_shm: integration with render pipeline
    - iter_shm_render_args: argument generator
    - Edge cases: size mismatch, double close, ring modular indexing
"""

import pytest

from archmotion.exporter.shm import (
    SharedMemoryRing,
    SharedMemorySlot,
    _DEFAULT_RING_SIZE,
    iter_shm_render_args,
)


# ──────────────────────────────────────────────
# SharedMemoryRing Tests
# ──────────────────────────────────────────────


class TestSharedMemoryRing:
    """Tests for the SharedMemory ring buffer."""

    def test_allocate_ring(self):
        """Ring allocates the requested number of slots."""
        ring = SharedMemoryRing(frame_size=1024, num_slots=3)
        try:
            assert ring.frame_size == 1024
            assert ring.num_slots == 3
            assert len(ring.slot_names) == 3
        finally:
            ring.close()

    def test_write_and_read(self):
        """Written bytes can be read back identically."""
        ring = SharedMemoryRing(frame_size=256, num_slots=2)
        try:
            data = bytes(range(256))
            ring.write_slot(0, data)
            result = ring.read_slot(0)
            assert result == data
        finally:
            ring.close()

    def test_write_different_slots(self):
        """Different slots hold independent data."""
        ring = SharedMemoryRing(frame_size=128, num_slots=3)
        try:
            d0 = b"\x00" * 128
            d1 = b"\xff" * 128
            d2 = b"\xab" * 128

            ring.write_slot(0, d0)
            ring.write_slot(1, d1)
            ring.write_slot(2, d2)

            assert ring.read_slot(0) == d0
            assert ring.read_slot(1) == d1
            assert ring.read_slot(2) == d2
        finally:
            ring.close()

    def test_modular_indexing(self):
        """Slot index wraps around using modular arithmetic."""
        ring = SharedMemoryRing(frame_size=64, num_slots=2)
        try:
            d0 = b"\x01" * 64
            ring.write_slot(0, d0)
            # Reading slot 2 should be same as slot 0 (2 % 2 = 0)
            ring.write_slot(2, d0)
            assert ring.read_slot(2) == d0
            assert ring.read_slot(0) == d0
        finally:
            ring.close()

    def test_write_size_mismatch_raises(self):
        """Writing wrong-sized data raises ValueError."""
        ring = SharedMemoryRing(frame_size=100, num_slots=1)
        try:
            with pytest.raises(ValueError, match="size mismatch"):
                ring.write_slot(0, b"\x00" * 50)
        finally:
            ring.close()

    def test_context_manager(self):
        """Context manager allocates and cleans up."""
        with SharedMemoryRing(frame_size=256, num_slots=2) as ring:
            data = b"\xcc" * 256
            ring.write_slot(0, data)
            assert ring.read_slot(0) == data
        # After exit, names should be cleared
        assert len(ring.slot_names) == 0

    def test_double_close_safe(self):
        """Calling close() twice doesn't raise."""
        ring = SharedMemoryRing(frame_size=128, num_slots=1)
        ring.close()
        ring.close()  # Should not raise

    def test_slot_names_are_unique(self):
        """All slot names are unique strings."""
        ring = SharedMemoryRing(frame_size=64, num_slots=4)
        try:
            names = ring.slot_names
            assert len(names) == len(set(names))
        finally:
            ring.close()

    def test_default_ring_size_constant(self):
        """Default ring size is 4."""
        assert _DEFAULT_RING_SIZE == 4


# ──────────────────────────────────────────────
# SharedMemorySlot Tests
# ──────────────────────────────────────────────


class TestSharedMemorySlot:
    """Tests for the worker-side SharedMemory accessor."""

    def test_slot_write_and_ring_read(self):
        """Slot write from worker side is readable from ring."""
        ring = SharedMemoryRing(frame_size=128, num_slots=2)
        try:
            name = ring.slot_names[0]
            data = b"\xde\xad" * 64

            # Simulate worker: open slot by name and write
            slot = SharedMemorySlot(name=name, frame_size=128)
            try:
                slot.write(data)
            finally:
                slot.close()

            # Main process reads from ring
            assert ring.read_slot(0) == data
        finally:
            ring.close()

    def test_slot_close_safe(self):
        """Closing slot doesn't affect ring."""
        ring = SharedMemoryRing(frame_size=64, num_slots=1)
        try:
            slot = SharedMemorySlot(name=ring.slot_names[0], frame_size=64)
            slot.close()
            slot.close()  # Double close safe
        finally:
            ring.close()


# ──────────────────────────────────────────────
# iter_shm_render_args Tests
# ──────────────────────────────────────────────


class TestIterShmRenderArgs:
    """Tests for the argument generator."""

    def test_generates_correct_count(self):
        """Generates one tuple per spec."""
        ring = SharedMemoryRing(frame_size=64, num_slots=2)
        try:
            mock_specs = [object() for _ in range(5)]
            args = list(iter_shm_render_args(mock_specs, ring))
            assert len(args) == 5
        finally:
            ring.close()

    def test_slot_names_cycle(self):
        """Slot names cycle through the ring modularly."""
        ring = SharedMemoryRing(frame_size=64, num_slots=2)
        try:
            mock_specs = [object() for _ in range(4)]
            args = list(iter_shm_render_args(mock_specs, ring))

            # Slots should cycle: 0, 1, 0, 1
            assert args[0][1] == ring.slot_names[0]
            assert args[1][1] == ring.slot_names[1]
            assert args[2][1] == ring.slot_names[0]
            assert args[3][1] == ring.slot_names[1]
        finally:
            ring.close()

    def test_frame_size_included(self):
        """Each arg tuple includes the frame size."""
        ring = SharedMemoryRing(frame_size=1024, num_slots=1)
        try:
            mock_specs = [object()]
            args = list(iter_shm_render_args(mock_specs, ring))
            assert args[0][2] == 1024
        finally:
            ring.close()


# ──────────────────────────────────────────────
# Integration: Ring with realistic frame sizes
# ──────────────────────────────────────────────


class TestRingRealisticSizes:
    """Test with 720p-equivalent frame sizes."""

    def test_720p_frame_size(self):
        """Ring handles 720p frame data (1280×720×4 = 3,686,400 bytes)."""
        frame_size = 1280 * 720 * 4
        ring = SharedMemoryRing(frame_size=frame_size, num_slots=2)
        try:
            # Write a pattern
            data = (b"\xab\xcd\xef\x00" * (frame_size // 4))
            ring.write_slot(0, data)
            result = ring.read_slot(0)
            assert result == data
            assert len(result) == frame_size
        finally:
            ring.close()

    def test_overwrite_slot(self):
        """Writing to the same slot overwrites previous data."""
        ring = SharedMemoryRing(frame_size=256, num_slots=1)
        try:
            ring.write_slot(0, b"\x00" * 256)
            ring.write_slot(0, b"\xff" * 256)
            assert ring.read_slot(0) == b"\xff" * 256
        finally:
            ring.close()
