"""Phase 3 -- Timeline Compilation (Compiler, Actions, Easing).

Public API:
    compile_timeline() -- Main entry point for Phase 3
    CompiledTimeline   -- Output data structure
    TransferMeta       -- Metadata for Transfer packet rendering
    ScheduledAction    -- Atomic animation unit
"""

from archmotion.timeline.actions import ScheduledAction
from archmotion.timeline.compiler import CompiledTimeline, TransferMeta, compile_timeline

__all__ = [
    "CompiledTimeline",
    "ScheduledAction",
    "TransferMeta",
    "compile_timeline",
]
