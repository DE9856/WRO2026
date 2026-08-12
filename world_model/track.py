"""
track.py
WRO 2026 Future Engineers — corridor-width memory across frames/sections.

GAP #7 FIX: this replaces a 10-line dead stub (`set_width` was the only
method and nothing in the codebase ever called it). This is the actual
consumer of camera/corridor.py's per-frame corridor_width_px output: a
smoothed rolling estimate plus per-section history, wired into main.py
and surfaced through utils/telemetry.py for Engineering Journal
evidence of testing/iteration (Appendix C, Criteria 3-4).

world_model/memory.py — a near-duplicate, unused generic "obstacle
list" stub — has been deleted outright rather than fixed. WorldModel
(world_model/world.py) already owns obstacle/section memory properly;
this file owns corridor-width memory specifically, a different concern
WorldModel never touched, so there was nothing worth merging.
"""

from __future__ import annotations
from collections import deque
from typing import Optional


class Track:
    """
    Rolling memory of corridor width, in pixels (see camera/corridor.py)
    and, once camera/warp.py::PX_PER_MM is calibrated, real centimetres.
    Also keeps a per-section history so section-to-section corridor
    narrowing (WRO Game Rules 2026 §8 Fig 7b — "the section where
    distance between the track borders will be reduced") can be logged
    and later reasoned about.
    """

    def __init__(self, smoothing_window: int = 5):
        self.smoothing_window = smoothing_window
        self._recent_widths_px: deque = deque(maxlen=smoothing_window)
        self.corridor_width_px: Optional[float] = None
        self.corridor_width_cm: Optional[float] = None
        self.sections: dict = {}   # section_number -> last known smoothed width_px

    def set_width(self, width_px: Optional[float], width_cm: Optional[float] = None,
                  section: Optional[int] = None) -> None:
        """Feed one frame's corridor_width_px (camera/corridor.py output).
        Silently ignores width_px=None (a frame with no corridor reading)
        rather than corrupting the rolling average with a missing value."""
        if width_px is None:
            return
        self._recent_widths_px.append(width_px)
        self.corridor_width_px = sum(self._recent_widths_px) / len(self._recent_widths_px)
        if width_cm is not None:
            self.corridor_width_cm = width_cm
        if section is not None:
            self.sections[section] = self.corridor_width_px

    def is_narrow_section(self, threshold_px: float) -> bool:
        """True if the current smoothed corridor is narrower than
        threshold_px — WRO §8 alternates 1000mm/600mm corridors; a
        narrow reading is a useful independent cross-check against the
        coin-toss-based layout the planner is told about out-of-band."""
        return self.corridor_width_px is not None and self.corridor_width_px < threshold_px

    def reset(self) -> None:
        self._recent_widths_px.clear()
        self.corridor_width_px = None
        self.corridor_width_cm = None

    def __str__(self) -> str:
        if self.corridor_width_px is None:
            return "Track(width=unknown)"
        cm = f", {self.corridor_width_cm:.1f}cm" if self.corridor_width_cm else ""
        return f"Track(width={self.corridor_width_px:.1f}px{cm})"

