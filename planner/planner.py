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


# ---------------------------------------------------------------------------
# Self-test — synthetic events, no camera/hardware required.
# ---------------------------------------------------------------------------
def _run_tests():
    from world_model.obstacle import RED, GREEN, CARD_CATALOG
    from world_model.world import WorldModel
    from world_model.vehicle_state import VehicleState
    from world_model.section_observer import SectionObserver

    print("Running planner.py tests...")

    # --- Test 1: stays in WAIT until start_button_pressed(); picks the
    #     right first drive state per challenge type.
    vs = VehicleState()
    wm = WorldModel(excluded_color=RED)
    p = Planner(ChallengeType.OPEN, vs, wm)
    assert p.is_waiting()
    p.section_boundary_crossed()  # no-op before start
    assert vs.current_section == 1, "boundary crossings before start must be ignored"
    p.start_button_pressed()
    assert p.state is State.OPEN_DRIVE
    print("  [PASS] WAIT -> OPEN_DRIVE only after start_button_pressed(), ignores events before that")

    vs2 = VehicleState()
    wm2 = WorldModel(excluded_color=GREEN)
    p2 = Planner(ChallengeType.OBSTACLE, vs2, wm2)
    p2.start_button_pressed()
    assert p2.state is State.OBS_DRIVE
    print("  [PASS] WAIT -> OBS_DRIVE for the Obstacle Challenge")

    # --- Test 2: section boundary crossings cycle 1->2->3->4->1 and a full
    #     lap (back to the starting section) bumps current_lap + world_model.lap.
    vs = VehicleState()
    wm = WorldModel(excluded_color=RED)
    p = Planner(ChallengeType.OPEN, vs, wm)
    p.start_button_pressed()
    for expected_section in (2, 3, 4, 1):
        p.section_boundary_crossed()
        assert vs.current_section == expected_section, vs.current_section
    assert vs.current_lap == 2, "returning to the starting section must advance the lap"
    assert wm.lap == 2, "world_model.advance_lap() must be called in lockstep"
    print("  [PASS] section_boundary_crossed() cycles 1..4 and advances the lap on return to start")

    # --- Test 3: after 3 full laps, OPEN_DRIVE -> DONE; OBS_DRIVE -> PARK_SEEK.
    vs = VehicleState()
    wm = WorldModel(excluded_color=RED)
    p = Planner(ChallengeType.OPEN, vs, wm)
    p.start_button_pressed()
    for _ in range(SECTIONS_PER_LAP * LAPS_TO_FINISH):
        p.section_boundary_crossed()
    assert vs.current_lap == LAPS_TO_FINISH + 1
    assert p.state is State.DONE, "Open Challenge should finish outright after 3 laps"
    print("  [PASS] Open Challenge: 3 completed laps -> DONE")

    vs = VehicleState()
    wm = WorldModel(excluded_color=RED)
    obs = SectionObserver()
    p = Planner(ChallengeType.OBSTACLE, vs, wm, section_observer=obs)
    p.start_button_pressed()
    for _ in range(SECTIONS_PER_LAP * LAPS_TO_FINISH):
        p.section_boundary_crossed()
    assert p.state is State.PARK_SEEK, "Obstacle Challenge should seek parking after 3 laps"
    print("  [PASS] Obstacle Challenge: 3 completed laps -> PARK_SEEK")

    # --- Test 4: seat_vector/confidence forwarded to WorldModel.observe()
    #     only while OBS_DRIVE, using a real card vector so it actually matches.
    vs = VehicleState()
    wm = WorldModel(excluded_color=RED)
    obs = SectionObserver()
    p = Planner(ChallengeType.OBSTACLE, vs, wm, section_observer=obs)
    p.start_button_pressed()
    real_vector = CARD_CATALOG[13]  # two-sign card, safe pick (not excluded 9/10)
    p.section_boundary_crossed(seat_vector=real_vector, confidence=0.9)
    assert wm.world_state["section_1"] == "card_13", wm.world_state
    print("  [PASS] seat_vector/confidence are forwarded into WorldModel.observe() during OBS_DRIVE")

    # Confirm it's a no-op for OPEN_DRIVE (nothing to observe there).
    vs = VehicleState()
    wm = WorldModel(excluded_color=RED)
    p = Planner(ChallengeType.OPEN, vs, wm)
    p.start_button_pressed()
    p.section_boundary_crossed(seat_vector=real_vector, confidence=0.9)
    assert wm.world_state["section_1"] is None, "Open Challenge must never touch world_model"
    print("  [PASS] seat_vector is ignored during OPEN_DRIVE (no pillars in that challenge)")

    # --- Test 5: section_observer.reset() is called on every boundary crossing.
    vs = VehicleState()
    wm = WorldModel(excluded_color=RED)
    obs = SectionObserver()
    p = Planner(ChallengeType.OBSTACLE, vs, wm, section_observer=obs)
    p.start_button_pressed()
    obs.update(red_detections=[{"cx": 10, "distance": 80.0}], green_detections=[], roi_width=300)
    assert obs.frames_seen() == 1
    p.section_boundary_crossed()
    assert obs.frames_seen() == 0, "section_observer must be reset() on every boundary crossing"
    print("  [PASS] section_observer.reset() fires on every section_boundary_crossed()")

    # --- Test 6: parking flow — PARK_SEEK waits for a real lot, PARK_EXEC
    #     finishes via parking_complete(), and a marker touch force-stops.
    vs = VehicleState()
    wm = WorldModel(excluded_color=RED)
    p = Planner(ChallengeType.OBSTACLE, vs, wm)
    p.start_button_pressed()
    for _ in range(SECTIONS_PER_LAP * LAPS_TO_FINISH):
        p.section_boundary_crossed()
    assert p.state is State.PARK_SEEK
    p.parking_lot_visible(None)
    assert p.state is State.PARK_SEEK, "no lot visible yet -> stay in PARK_SEEK"
    p.parking_lot_visible({"left": {}, "right": {}, "center_x": 150, "width_px": 40})
    assert p.state is State.PARK_EXEC
    p.parking_complete()
    assert p.state is State.DONE
    print("  [PASS] PARK_SEEK -> PARK_EXEC on a real lot, -> DONE via parking_complete()")

    vs = VehicleState()
    wm = WorldModel(excluded_color=RED)
    p = Planner(ChallengeType.OBSTACLE, vs, wm)
    p.start_button_pressed()
    for _ in range(SECTIONS_PER_LAP * LAPS_TO_FINISH):
        p.section_boundary_crossed()
    p.parking_lot_visible({"left": {}, "right": {}, "center_x": 150, "width_px": 40})
    assert p.state is State.PARK_EXEC
    p.parking_marker_touched()
    assert p.state is State.DONE, "touching a parking marker must force-stop into DONE (§9.24.7)"
    print("  [PASS] parking_marker_touched() force-stops PARK_EXEC -> DONE")

    # --- Test 7: lap_phase() labels line up with current_lap.
    vs = VehicleState()
    wm = WorldModel(excluded_color=RED)
    p = Planner(ChallengeType.OBSTACLE, vs, wm)
    assert p.lap_phase() == "MAP_BUILD"
    vs.current_lap = 2
    assert p.lap_phase() == "VALIDATE"
    vs.current_lap = 3
    assert p.lap_phase() == "SPEED_RUN"
    vs.current_lap = 4
    assert p.lap_phase() == "SPEED_RUN"
    print("  [PASS] lap_phase() reports MAP_BUILD / VALIDATE / SPEED_RUN correctly")

    # --- Test 8: query helpers reflect state accurately at each phase.
    vs = VehicleState()
    wm = WorldModel(excluded_color=RED)
    p = Planner(ChallengeType.OBSTACLE, vs, wm)
    assert p.is_waiting() and not p.is_driving() and not p.should_track_pillars()
    p.start_button_pressed()
    assert p.is_driving() and p.should_track_pillars() and not p.is_waiting()
    print("  [PASS] query helpers (is_waiting/is_driving/should_track_pillars/...) match state")

    print("All planner.py tests passed.")


if __name__ == "__main__":
    _run_tests()
