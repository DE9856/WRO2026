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


# ---------------------------------------------------------------------------
# Self-test — synthetic width readings, no camera needed.
# ---------------------------------------------------------------------------
def _run_tests():
    print("Running track.py tests...")

    t = Track(smoothing_window=3)
    assert t.corridor_width_px is None
    t.set_width(100.0)
    t.set_width(110.0)
    t.set_width(90.0)
    assert abs(t.corridor_width_px - 100.0) < 1e-6, t.corridor_width_px
    print("  [PASS] set_width() smooths over a rolling window")

    t.set_width(200.0)  # window slides — oldest (100) drops out
    assert abs(t.corridor_width_px - (110 + 90 + 200) / 3) < 1e-6
    print("  [PASS] rolling window correctly evicts the oldest sample")

    t2 = Track()
    assert not t2.is_narrow_section(500)
    t2.set_width(400.0)
    assert t2.is_narrow_section(500)
    assert not t2.is_narrow_section(300)
    print("  [PASS] is_narrow_section() thresholds correctly")

    t3 = Track()
    t3.set_width(150.0, section=2)
    assert t3.sections[2] == 150.0
    print("  [PASS] per-section history is recorded")

    t3.set_width(None)  # must be a safe no-op, not a crash
    assert t3.corridor_width_px == 150.0
    print("  [PASS] set_width(None) is a safe no-op")

    t4 = Track()
    t4.set_width(120.0)
    t4.reset()
    assert t4.corridor_width_px is None
    print("  [PASS] reset() clears the rolling window and smoothed value")

    print("All track.py tests passed.")


if __name__ == "__main__":
    _run_tests()
