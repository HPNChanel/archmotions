"""Tests for the SharedMemory ring buffer (render/shm.py).

These are pure-IPC tests — no skia or ffmpeg required. They verify ring
allocation, read/write round-trip, slot modular assignment, cleanup, and the
fallback sentinel semantics.
"""

from __future__ import annotations

import pytest

from archmotion.render.shm import (
    SharedMemoryRing,
    SharedMemorySlot,
    iter_shm_slots,
)

FRAME_SIZE = 1024  # small frames for test speed


def _sample_frame(slot: int) -> bytes:
    """Deterministic test frame: all bytes = slot index mod 256."""
    return bytes([slot % 256] * FRAME_SIZE)


class TestSharedMemoryRing:
    def test_create_and_read_roundtrip(self):
        ring = SharedMemoryRing(frame_size=FRAME_SIZE, num_slots=2)
        try:
            data = _sample_frame(1)
            ring.write_slot(0, data)
            assert ring.read_slot(0) == data
        finally:
            ring.close()

    def test_slot_count(self):
        ring = SharedMemoryRing(frame_size=FRAME_SIZE, num_slots=3)
        try:
            assert len(ring.slot_names) == 3
            assert len(set(ring.slot_names)) == 3  # unique names
        finally:
            ring.close()

    def test_modular_slot_index(self):
        ring = SharedMemoryRing(frame_size=FRAME_SIZE, num_slots=2)
        try:
            # slot_index 3 wraps to slot 1 (3 % 2).
            ring.write_slot(3, _sample_frame(1))
            assert ring.read_slot(1) == _sample_frame(1)
        finally:
            ring.close()

    def test_write_size_mismatch_raises(self):
        ring = SharedMemoryRing(frame_size=FRAME_SIZE, num_slots=1)
        try:
            with pytest.raises(ValueError, match="size mismatch"):
                ring.write_slot(0, b"too short")
        finally:
            ring.close()

    def test_close_is_idempotent(self):
        ring = SharedMemoryRing(frame_size=FRAME_SIZE, num_slots=1)
        ring.close()
        ring.close()  # must not raise

    def test_context_manager_cleans_up(self):
        with SharedMemoryRing(frame_size=FRAME_SIZE, num_slots=2) as ring:
            ring.write_slot(0, _sample_frame(0))
        # After exit, slot_names is cleared.
        assert ring.slot_names == []


class TestSharedMemorySlot:
    def test_slot_write_and_close(self):
        ring = SharedMemoryRing(frame_size=FRAME_SIZE, num_slots=1)
        try:
            name = ring.slot_names[0]
            data = _sample_frame(5)
            slot = SharedMemorySlot(name=name, frame_size=FRAME_SIZE)
            slot.write(data)
            slot.close()
            # Main process reads the same bytes the worker wrote.
            assert ring.read_slot(0) == data
        finally:
            ring.close()

    def test_slot_close_idempotent(self):
        ring = SharedMemoryRing(frame_size=FRAME_SIZE, num_slots=1)
        try:
            slot = SharedMemorySlot(name=ring.slot_names[0], frame_size=FRAME_SIZE)
            slot.close()
            slot.close()  # must not raise
        finally:
            ring.close()


class TestIterShmSlots:
    def test_ordered_pairs(self):
        ring = SharedMemoryRing(frame_size=FRAME_SIZE, num_slots=3)
        try:
            pairs = list(iter_shm_slots(5, ring))
            # Frame indices are sequential.
            assert [fi for fi, _ in pairs] == [0, 1, 2, 3, 4]
            # Slot names cycle through the ring.
            names = [name for _, name in pairs]
            assert names[0] == names[3]  # 0 % 3 == 3 % 3
            assert names[1] == names[4]
        finally:
            ring.close()

    def test_empty_range(self):
        ring = SharedMemoryRing(frame_size=FRAME_SIZE, num_slots=2)
        try:
            assert list(iter_shm_slots(0, ring)) == []
        finally:
            ring.close()


class TestRingFallback:
    def test_oserror_on_allocation_propagates(self, monkeypatch):
        """If SharedMemory allocation fails, the ring raises (pool catches it)."""
        from multiprocessing import shared_memory

        def boom(*args, **kwargs):
            raise OSError("platform limit")

        monkeypatch.setattr(shared_memory, "SharedMemory", boom)
        with pytest.raises(OSError, match="platform limit"):
            SharedMemoryRing(frame_size=FRAME_SIZE, num_slots=2)
