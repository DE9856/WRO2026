"""
proximity.py
WRO 2026 Future Engineers — parking-marker proximity/collision awareness.

C.14 FIX: planner.py has had a real parking_marker_touched() event ever
since the parking state machine landed, and control/parking_maneuver.py's
own docstring explains exactly why it matters ("WRO §9.24.7 penalizes
touching the parking lot limitations") — but nothing ever CALLED
parking_marker_touched(). The only "sensing logic" anywhere in the
pipeline was that comment. Two real signals were sitting unused:

  - vehicle_controller.ino already pings an HC-SR04 every ~100ms and
    sends "DIST=<cm>\\n" uplink, but main.py's uplink loop only ever
    special-cased BTN / MODE= / LINE and silently dropped DIST= (see
    the firmware's own "NOTE ON HC-SR04" comment).
  - camera/parking.py's locate_parking_lot() already reports each
    marker's pixel width every frame, but nothing downstream of
    control/parking_maneuver.py (which only uses center_x for centering)
    ever looked at how LARGE a marker had gotten.

This module turns those two existing-but-unused signals into a single
touched()/not decision, meant to be polled once per frame while
planner.should_execute_parking() is True and fed straight into
planner.parking_marker_touched().

TWO INDEPENDENT CUES — either one alone is enough to trip:

  1. FORWARD RANGE (HC-SR04, parsed from the Arduino's "DIST=<cm>"
     uplink). This is the only sensor on the vehicle that measures
     actual physical distance rather than apparent size, so it's the
     primary cue for "something is right in front of the bumper" —
     during PARK_EXEC that's whichever marker (or the lot's back
     boundary) the vehicle is driving toward.

  2. MARKER APPARENT WIDTH (camera/parking.py's locate_parking_lot()).
     The HC-SR04 is forward-facing only, so it can't see a marker the
     vehicle drifts into sideways while still centering. A magenta
     marker's bounding-box width growing to fill a large fraction of
     the ROI is the camera-side proxy for "we are now right up against
     it" — complementary to, not a replacement for, the forward ping.

Both cues are debounced over CONSECUTIVE_FRAMES_TO_TRIP frames before
tripping (same precedent as parking_maneuver.py's own PARK_STABLE_FRAMES)
so a single noisy HC-SR04 echo — a known failure mode: stray reflections,
or a timed-out ping read as 0 — can't force-stop a manoeuvre that was
otherwise fine. Once tripped, touched() latches True until reset(): WRO
§9.24.7 penalizes the contact itself, not an ongoing condition, so
there's no "un-touching" a marker mid-manoeuvre.
"""

from __future__ import annotations
from typing import Optional

TOUCH_DISTANCE_CM = 4.0          # forward range at/below this = contact or near-contact
MARKER_FILL_RATIO = 0.35         # marker bbox width / ROI width above this = "right up against it"
CONSECUTIVE_FRAMES_TO_TRIP = 2   # debounce -- see module docstring


class ParkingCollisionGuard:
    """
    One instance per round (or re-used across PARK_EXEC attempts via
    reset()). Call update(...) once per frame while
    planner.should_execute_parking() is True; call reset() whenever
    execution is NOT active, mirroring ParkingManeuver.reset()'s
    call sites in main.py.
    """

    def __init__(self,
                 touch_distance_cm: float = TOUCH_DISTANCE_CM,
                 marker_fill_ratio: float = MARKER_FILL_RATIO,
                 frames_to_trip: int = CONSECUTIVE_FRAMES_TO_TRIP):
        self.touch_distance_cm = touch_distance_cm
        self.marker_fill_ratio = marker_fill_ratio
        self.frames_to_trip = frames_to_trip
        self._consecutive = 0
        self._touched = False

    def reset(self) -> None:
        self._consecutive = 0
        self._touched = False

    def touched(self) -> bool:
        return self._touched

    def update(self,
               forward_distance_cm: Optional[float],
               parking_lot: Optional[dict],
               roi_width: int) -> bool:
        """
        forward_distance_cm: latest HC-SR04 "DIST=<cm>" reading (None if
            no ping has arrived yet, e.g. dry-run/mock serial, or the
            most recent ping timed out on the firmware side).
        parking_lot: this frame's camera.parking.locate_parking_lot()
            result (None if fewer than two magenta markers are visible).
        roi_width: pixel width of the ROI the marker boxes were measured
            in (same frame the "left"/"right" marker "w" values came from).

        Returns True the frame (and every frame after) the guard
        latches touched. A single triggering frame is not enough on its
        own -- see CONSECUTIVE_FRAMES_TO_TRIP.
        """
        if self._touched:
            return True

        cue = False

        # Cue 1: forward ultrasonic range. vehicle_controller.ino's
        # serviceUltrasonic() deliberately sends nothing on a timed-out
        # ping rather than a bogus 0/-1 (so forward_distance_cm just
        # holds its last known value, or stays None until the first
        # real reading) -- but guard against 0/negative here anyway in
        # case of a future firmware change or a parse edge case, rather
        # than trusting the sender's exact convention.
        if forward_distance_cm is not None and forward_distance_cm > 0:
            if forward_distance_cm <= self.touch_distance_cm:
                cue = True

        # Cue 2: either marker's bounding box filling too much of the ROI.
        if not cue and parking_lot is not None and roi_width > 0:
            for marker in (parking_lot["left"], parking_lot["right"]):
                if marker["w"] / roi_width >= self.marker_fill_ratio:
                    cue = True
                    break

        self._consecutive = self._consecutive + 1 if cue else 0

        if self._consecutive >= self.frames_to_trip:
            self._touched = True

        return self._touched

