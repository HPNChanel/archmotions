"""Performance benchmark for the ArchMotion v2.0 render pipeline.

Builds a representative ~10-second architecture scene (3 nodes, 2 connections,
FadeIn + Transfer) and renders it through the parallel multiprocessing pool,
measuring throughput, peak RSS, and verifying the performance budgets.

Usage::

    python benchmarks/bench_render.py
    python benchmarks/bench_render.py --resolution 720p --workers 4
    python benchmarks/bench_render.py --no-shm   # force pickle IPC fallback

Budgets (from the project performance targets):
    - Render a 10s video in < 30 seconds
    - Peak RAM < 512 MB
    - Effective throughput >= 60 frames/sec

Exit code is non-zero if any budget fails.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from archmotion.core.scene import Scene

# Performance budgets
RENDER_TIME_BUDGET_SEC = 30.0
PEAK_RAM_BUDGET_MB = 512.0
THROUGHPUT_BUDGET_FPS = 60.0


@dataclass
class BenchResult:
    """Aggregated benchmark measurements."""

    total_frames: int
    elapsed_sec: float
    effective_fps: float
    peak_rss_mb: float
    encoder_label: str
    workers: int
    ipc_mode: str


def _peak_rss_mb() -> float:
    """Return an estimate of the process peak memory in MB (best-effort).

    Tries, in order:
        1. POSIX ``resource.getrusage`` (true peak RSS — Linux/Darwin).
        2. Windows ``GetProcessMemoryInfo`` via ctypes (peak working set).
        3. ``tracemalloc`` peak (Python heap only — must be started beforehand).
    """
    if sys.platform != "win32":
        try:
            import resource

            kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            # ru_maxrss is KB on Linux, bytes on macOS.
            return kb / (1024.0 * 1024.0) if sys.platform == "darwin" else kb / 1024.0
        except (ImportError, AttributeError):
            pass

    if sys.platform == "win32":
        try:
            import ctypes

            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):  # noqa: N801
                _fields_ = [
                    ("cb", ctypes.c_ulong),
                    ("PageFaultCount", ctypes.c_ulong),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            counters = PROCESS_MEMORY_COUNTERS()
            counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
            psapi = ctypes.windll.kernel32  # type: ignore[attr-defined]
            psapi.GetProcessMemoryInfo(
                psapi.GetCurrentProcess(),
                ctypes.byref(counters),
                counters.cb,
            )
            return counters.PeakWorkingSetSize / (1024.0 * 1024.0)
        except (OSError, AttributeError):
            pass

    # Last-resort fallback: Python-heap peak (undercounts C extensions).
    import tracemalloc

    _current, peak = tracemalloc.get_traced_memory()
    return peak / (1024.0 * 1024.0)


def build_bench_scene(resolution: str, fps: int) -> Scene:
    """Build a representative ~10s architecture scene for benchmarking."""
    from archmotion.animation import FadeIn, Transfer
    from archmotion.core.scene import Scene
    from archmotion.domains.architecture import Connection, Node

    scene = Scene(resolution=resolution, fps=fps)

    gateway = Node("API Gateway").set_fill("#3b82f6")
    worker = Node("Worker Service")
    db = Node("PostgreSQL")
    worker.right_of(gateway, distance=4)
    db.right_of(worker, distance=4)

    c1 = Connection(gateway, worker, label="HTTP")
    c2 = Connection(worker, db, label="SQL")

    scene.play(FadeIn(gateway, worker, db, c1, c2, run_time=1.0))
    scene.play(Transfer(c1, payload="GET", run_time=2.0))
    scene.play(Transfer(c2, payload="SELECT", run_time=2.0))
    scene.play(Transfer(c1, payload="200 OK", run_time=2.0))
    scene.wait(3.0)
    return scene


def run_benchmark(resolution: str, fps: int, workers: int | None, use_shm: bool) -> BenchResult:
    """Render the bench scene and collect measurements."""
    from archmotion.render.pool import render_pool

    scene = build_bench_scene(resolution, fps)

    tmp = os.path.join(tempfile.gettempdir(), "bench_render.mp4")
    if os.path.exists(tmp):
        os.remove(tmp)

    # Start tracemalloc early so the fallback peak measurement is meaningful.
    import tracemalloc

    tracemalloc.start()
    t0 = time.perf_counter()
    result = render_pool(scene, tmp, workers=workers, use_shared_memory=use_shm)
    elapsed = time.perf_counter() - t0
    peak = _peak_rss_mb()
    tracemalloc.stop()

    return BenchResult(
        total_frames=result.total_frames,
        elapsed_sec=elapsed,
        effective_fps=result.total_frames / elapsed if elapsed > 0 else 0.0,
        peak_rss_mb=peak,
        encoder_label=result.encoder_label,
        workers=result.workers,
        ipc_mode=result.ipc_mode,
    )


def print_report(r: BenchResult) -> bool:
    """Print the benchmark report and return True if all budgets pass."""
    print("=" * 60)
    print("ArchMotion v2.0 — Render Benchmark")
    print("=" * 60)
    print(f"  Frames rendered : {r.total_frames}")
    print(f"  Wall-clock time : {r.elapsed_sec:.2f}s")
    print(f"  Effective FPS   : {r.effective_fps:.1f}")
    print(f"  Peak RSS        : {r.peak_rss_mb:.1f} MB")
    print(f"  Encoder         : {r.encoder_label}")
    print(f"  Workers         : {r.workers}")
    print(f"  IPC mode        : {r.ipc_mode}")
    print("-" * 60)

    checks = [
        ("Render time", r.elapsed_sec, RENDER_TIME_BUDGET_SEC, "s"),
        ("Peak RAM", r.peak_rss_mb, PEAK_RAM_BUDGET_MB, "MB"),
        ("Throughput", r.effective_fps, THROUGHPUT_BUDGET_FPS, "fps"),
    ]

    all_pass = True
    for label, value, budget, unit in checks:
        # Throughput is "greater is better"; the others are "less is better".
        passed = value >= budget if unit == "fps" else value <= budget
        marker = "PASS" if passed else "FAIL"
        sign = ">=" if unit == "fps" else "<="
        print(f"  [{marker}] {label}: {value:.1f} {unit} ({sign} {budget} {unit})")
        if not passed:
            all_pass = False

    print("=" * 60)
    print("RESULT:", "ALL BUDGETS PASSED" if all_pass else "SOME BUDGETS FAILED")
    return all_pass


def main() -> int:
    """Parse args, run the benchmark, and return an exit code."""
    parser = argparse.ArgumentParser(description="ArchMotion v2.0 render benchmark")
    parser.add_argument("--resolution", default="1080p", help="Resolution preset (default 1080p)")
    parser.add_argument("--fps", type=int, default=30, help="Frame rate (default 30)")
    parser.add_argument("--workers", type=int, default=None, help="Worker count (default auto)")
    parser.add_argument(
        "--no-shm", action="store_true", help="Disable SharedMemory IPC (pickle fallback)"
    )
    args = parser.parse_args()

    try:
        result = run_benchmark(
            resolution=args.resolution,
            fps=args.fps,
            workers=args.workers,
            use_shm=not args.no_shm,
        )
    except Exception as exc:
        print(f"Benchmark failed: {exc}", file=sys.stderr)
        return 2

    return 0 if print_report(result) else 1


if __name__ == "__main__":
    sys.exit(main())
