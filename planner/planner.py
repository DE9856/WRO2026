"""
planner.py
WRO 2026 Future Engineers — top-level state machine + section/lap bookkeeping.

Owns:
  - The competition state machine (Build Guide §07):
        WAIT -> OPEN_DRIVE | OBS_DRIVE -> PARK_SEEK -> PARK_EXEC -> DONE
  - Turning a "we just left a section" event (today: camera/lines.py's
    ORANGE "EXITING" corner-line rising edge, wired in main.py) into
    current_section / current_lap advancement, lap-completion detection,
    and telling world_model / section_observer when to act.

This is exactly the module main.py's "TODO(planner)" comment and
world_model/section_observer.py's "WHAT THIS DELIBERATELY DOES NOT DO"
docstring have been pointing at: WHEN a section/lap starts or ends, and
WHICH high-level state the robot is in. It does not decide HOW to steer
(control/pid.py, camera/angle.py) or WHAT a seat vector maps to
(world_model/obstacle.py, seat_estimator.py) — only WHEN/WHAT-STATE.

WORLD-MODEL SECTION CONVENTION (kept consistent with world_model/world.py):
  A "section" here is one of the 4 straightforward sections that carry
  traffic-sign seats (WRO Game Rules 2026 §5 — corner sections hold no
  seats, so world_model doesn't track them separately). One lap = 4
  section-boundary crossings back to the same starting section. This is
  coarser than the rulebook's own "8 sections per lap" count (§1.2, which
  includes corners for scoring purposes) — nothing in this codebase needs
  that finer count yet; only the 4-straightforward-section cycle that
  drives seat memory and lap completion. If corner-section-level scoring
  bookkeeping is ever added, SECTIONS_PER_LAP would need to become 8 in
  lockstep with a world_model/track.py rewrite.

>>> ASSUMPTION FLAG <<<
Like EXCLUDED_COLOR in main.py, the challenge type (Open vs Obstacle) and
starting driving direction are fixed by the judges/coin-toss before a
round (WRO Game Rules 2026 §5, §8, §9.3) and are NOT camera-detectable.
Pass them in at construction time, the same way main.py hand-sets
EXCLUDED_COLOR today.
"""

from __future__ import annotations

from enum import Enum, auto
from typing import Optional


class ChallengeType(Enum):
    OPEN = "OPEN"
    OBSTACLE = "OBSTACLE"


class State(Enum):
    WAIT = auto()          # placed in start zone, waiting for start button (§9.11)
    OPEN_DRIVE = auto()    # Open Challenge lane-following, no pillars
    OBS_DRIVE = auto()     # Obstacle Challenge: pillar obedience + world-model mapping
    PARK_SEEK = auto()     # after 3 laps (Obstacle only): searching for magenta markers
    PARK_EXEC = auto()     # executing the parking manoeuvre
    DONE = auto()          # motors stopped


SECTIONS_PER_LAP = 4       # see WORLD-MODEL SECTION CONVENTION above
LAPS_TO_FINISH = 3         # WRO Game Rules 2026 §5 / §9.22


class Planner:
    """
    Drives vehicle_state.current_section / current_lap forward, tells
    world_model when a lap completes, and tracks the robot's own
    WAIT/DRIVE/PARK/DONE state. One Planner per round.
    """

    def __init__(
        self,
        challenge: ChallengeType,
        vehicle_state,
        world_model,
        section_observer=None,
        direction: Optional[str] = None,
    ):
        self.challenge = challenge
        self.vehicle_state = vehicle_state
        self.world_model = world_model
        self.section_observer = section_observer

        if direction is not None:
            self.vehicle_state.direction = direction

        self.state = State.WAIT
        # The section the vehicle starts in doubles as the finish section
        # (WRO §9.22: "as soon as the vehicle partially leaves the starting
        # section this section also becomes the finish section").
        self.starting_section = vehicle_state.current_section
        self.sections_completed = 0

    # -----------------------------------------------------------------
    # External events — call these from main.py as the corresponding
    # real-world trigger fires.
    # -----------------------------------------------------------------

    def start_button_pressed(self) -> None:
        """WRO §9.11/§9.13 — round timer + motion starts here."""
        if self.state is not State.WAIT:
            return
        self.state = (
            State.OPEN_DRIVE if self.challenge is ChallengeType.OPEN else State.OBS_DRIVE
        )

    def section_boundary_crossed(
        self,
        seat_vector: Optional[list[int]] = None,
        confidence: float = 0.0,
    ) -> None:
        """
        Call once per corner-exit rising edge — today that's
        camera/lines.py's `detect_corner_line(...)["phase"] == "EXITING"`
        rising edge, exactly the spot main.py's TODO(planner) comment
        flags. This method is what should replace that placeholder block.

        seat_vector / confidence: only meaningful in OBS_DRIVE. Pass the
        SectionObserver.finalize()/confidence() results for the section
        being LEFT (i.e. vehicle_state.current_section BEFORE this call
        advances it) — this method forwards them into WorldModel.observe()
        so main.py no longer has to know section_key bookkeeping itself.
        """
        if self.state not in (State.OPEN_DRIVE, State.OBS_DRIVE):
            return  # boundary crossings only matter while actively driving

        if self.state is State.OBS_DRIVE and seat_vector is not None:
            section_key = f"section_{self.vehicle_state.current_section}"
            self.world_model.observe(
                section_key, seat_vector, confidence=confidence, min_confidence=0.3
            )

        self.sections_completed += 1
        self.vehicle_state.current_section = (
            self.vehicle_state.current_section % SECTIONS_PER_LAP
        ) + 1

        if self.section_observer is not None:
            self.section_observer.reset()

        if self.vehicle_state.current_section == self.starting_section:
            self.vehicle_state.current_lap += 1
            self.world_model.advance_lap()

            if self.vehicle_state.current_lap > LAPS_TO_FINISH:
                if self.challenge is ChallengeType.OPEN:
                    self.state = State.DONE
                else:
                    self.state = State.PARK_SEEK

    def parking_lot_visible(self, parking_lot: Optional[dict]) -> None:
        """Feed camera/parking.py::locate_parking_lot() output every frame."""
        if self.state is not State.PARK_SEEK or parking_lot is None:
            return
        self.state = State.PARK_EXEC

    def parking_marker_touched(self) -> None:
        """WRO §9.24.7 — touching a marker forfeits parking points; stop now."""
        if self.state is State.PARK_EXEC:
            self.state = State.DONE

    def parking_complete(self) -> None:
        """Call once the parking manoeuvre finishes (parallel, inside the lot)."""
        if self.state is State.PARK_EXEC:
            self.state = State.DONE

    # -----------------------------------------------------------------
    # Queries — the rest of the pipeline reads these every frame instead
    # of re-deriving "what should I be doing right now" from raw state.
    # -----------------------------------------------------------------

    def is_waiting(self) -> bool:
        return self.state is State.WAIT

    def is_driving(self) -> bool:
        return self.state in (State.OPEN_DRIVE, State.OBS_DRIVE)

    def should_track_pillars(self) -> bool:
        return self.state is State.OBS_DRIVE

    def should_seek_parking(self) -> bool:
        return self.state is State.PARK_SEEK

    def should_execute_parking(self) -> bool:
        return self.state is State.PARK_EXEC

    def is_done(self) -> bool:
        return self.state is State.DONE

    def lap_phase(self) -> str:
        """
        Lap-based strategy label (Build Guide §06A "Lap-Based Intelligence"
        / §07): lap 1 -> cautious mapping, lap 2 -> validation, lap 3+ ->
        aggressive/predictive. A future speed-scheduler keys off this
        string instead of re-deriving it from current_lap itself.
        """
        lap = self.vehicle_state.current_lap
        if lap <= 1:
            return "MAP_BUILD"
        if lap == 2:
            return "VALIDATE"
        return "SPEED_RUN"

    def __str__(self) -> str:
        return (
            f"{self.state.name} | challenge={self.challenge.value} "
            f"lap={self.vehicle_state.current_lap} "
            f"section={self.vehicle_state.current_section}"
        )

