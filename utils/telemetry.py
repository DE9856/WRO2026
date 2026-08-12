"""
telemetry.py
WRO 2026 Future Engineers — per-frame CSV logger.

GAP #8 FIX: there was no logging anywhere in the pipeline. This writes
one CSV row per processed frame with the state vector, planner state,
and control outputs — exactly the kind of "testing and tuning process"
evidence Appendix C's Engineering Journal rubric rewards under
Criterion 3 (Software Architecture — "testing and tuning process...
metrics used for performance evaluation") and Criterion 4 (Systems
Thinking — "iteration cycles... risk and mitigation").

Usage (see main.py):
    telemetry = TelemetryLogger()
    ...in the main loop, once per frame...
    telemetry.log(planner_state=str(planner.state), lap=..., section=...,
                   steering_deg=..., speed_pwm=..., ...)
    ...at shutdown...
    telemetry.close()

Writes to logs/run_<timestamp>.csv by default — one file per run, so old
runs are never overwritten and can be diffed/plotted afterward for the
Engineering Journal. logs/ is already in .gitignore.
"""

from __future__ import annotations
import csv
import os
import time
from typing import Optional

FIELDNAMES = [
    "frame", "t_sec", "fps",
    "planner_state", "challenge", "lap", "section", "lap_phase",
    "steering_source", "steering_deg", "speed_pwm",
    "corridor_center_x", "corridor_width_px", "corridor_confidence",
    "pillar_color", "pillar_cx", "pillar_distance_cm",
    "world_state_summary",
    "dist_front_cm", "dist_left_cm", "dist_right_cm", "imu_heading_deg",
]


class TelemetryLogger:
    def __init__(self, log_dir: str = "logs", filename: Optional[str] = None, enabled: bool = True):
        self.enabled = enabled
        self._frame = 0
        self._start_t = time.time()
        self._file = None
        self._writer = None

        if not self.enabled:
            return

        os.makedirs(log_dir, exist_ok=True)
        if filename is None:
            filename = f"run_{time.strftime('%Y%m%d_%H%M%S')}.csv"
        self.path = os.path.join(log_dir, filename)

        self._file = open(self.path, "w", newline="")
        self._writer = csv.DictWriter(self._file, fieldnames=FIELDNAMES)
        self._writer.writeheader()
        print(f"[telemetry] logging to {self.path}")

    def log(self, **kwargs) -> None:
        """Any FIELDNAMES key can be passed as a kwarg; unknown kwargs are
        ignored rather than raising, so callers can pass through partial
        state (e.g. no pillar this frame) without conditional code."""
        if not self.enabled:
            return
        self._frame += 1
        row = {k: "" for k in FIELDNAMES}
        row["frame"] = self._frame
        row["t_sec"] = round(time.time() - self._start_t, 3)
        for k, v in kwargs.items():
            if k in row:
                row[k] = v
        self._writer.writerow(row)

        # Flush periodically rather than every row — disk I/O every frame
        # at 30fps is wasteful; every 15 frames (~0.5s @30fps) balances
        # "data survives a crash" against "don't slow the control loop".
        if self._frame % 15 == 0:
            self._file.flush()

    def close(self) -> None:
        if not self.enabled or self._file is None:
            return
        self._file.flush()
        self._file.close()
        print(f"[telemetry] closed {self.path} ({self._frame} rows)")

