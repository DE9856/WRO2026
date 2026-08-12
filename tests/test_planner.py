"""
tests/test_planner.py
WRO 2026 Future Engineers — pytest cases for planner/planner.py.

H.28 FIX: converted from planner.py's in-module _run_tests() into real
pytest test_* functions. No functional change.
"""

from world_model.obstacle import RED, GREEN, CARD_CATALOG
from world_model.world import WorldModel
from world_model.vehicle_state import VehicleState
from world_model.section_observer import SectionObserver
from planner.planner import Planner, ChallengeType, State, SECTIONS_PER_LAP, LAPS_TO_FINISH

REAL_VECTOR = CARD_CATALOG[13]  # two-sign card, safe pick (not excluded 9/10)


def test_wait_transitions_to_open_drive_only_after_start():
    vs = VehicleState()
    wm = WorldModel(excluded_color=RED)
    p = Planner(ChallengeType.OPEN, vs, wm)
    assert p.is_waiting()

    p.section_boundary_crossed()  # no-op before start
    assert vs.current_section == 1, "boundary crossings before start must be ignored"

    p.start_button_pressed()
    assert p.state is State.OPEN_DRIVE


def test_wait_transitions_to_obs_drive_for_obstacle_challenge():
    vs2 = VehicleState()
    wm2 = WorldModel(excluded_color=GREEN)
    p2 = Planner(ChallengeType.OBSTACLE, vs2, wm2)
    p2.start_button_pressed()
    assert p2.state is State.OBS_DRIVE


def test_section_boundary_crossings_cycle_and_advance_lap():
    vs = VehicleState()
    wm = WorldModel(excluded_color=RED)
    p = Planner(ChallengeType.OPEN, vs, wm)
    p.start_button_pressed()
    for expected_section in (2, 3, 4, 1):
        p.section_boundary_crossed()
        assert vs.current_section == expected_section, vs.current_section
    assert vs.current_lap == 2, "returning to the starting section must advance the lap"
    assert wm.lap == 2, "world_model.advance_lap() must be called in lockstep"


def test_open_challenge_finishes_after_three_laps():
    vs = VehicleState()
    wm = WorldModel(excluded_color=RED)
    p = Planner(ChallengeType.OPEN, vs, wm)
    p.start_button_pressed()
    for _ in range(SECTIONS_PER_LAP * LAPS_TO_FINISH):
        p.section_boundary_crossed()
    assert vs.current_lap == LAPS_TO_FINISH + 1
    assert p.state is State.DONE, "Open Challenge should finish outright after 3 laps"


def test_obstacle_challenge_seeks_parking_after_three_laps():
    vs = VehicleState()
    wm = WorldModel(excluded_color=RED)
    obs = SectionObserver()
    p = Planner(ChallengeType.OBSTACLE, vs, wm, section_observer=obs)
    p.start_button_pressed()
    for _ in range(SECTIONS_PER_LAP * LAPS_TO_FINISH):
        p.section_boundary_crossed()
    assert p.state is State.PARK_SEEK, "Obstacle Challenge should seek parking after 3 laps"


def test_seat_vector_forwarded_to_world_model_during_obs_drive():
    vs = VehicleState()
    wm = WorldModel(excluded_color=RED)
    obs = SectionObserver()
    p = Planner(ChallengeType.OBSTACLE, vs, wm, section_observer=obs)
    p.start_button_pressed()
    p.section_boundary_crossed(seat_vector=REAL_VECTOR, confidence=0.9)
    assert wm.world_state["section_1"] == "card_13", wm.world_state


def test_seat_vector_ignored_during_open_drive():
    vs = VehicleState()
    wm = WorldModel(excluded_color=RED)
    p = Planner(ChallengeType.OPEN, vs, wm)
    p.start_button_pressed()
    p.section_boundary_crossed(seat_vector=REAL_VECTOR, confidence=0.9)
    assert wm.world_state["section_1"] is None, "Open Challenge must never touch world_model"


def test_section_observer_reset_fires_on_every_boundary_crossing():
    vs = VehicleState()
    wm = WorldModel(excluded_color=RED)
    obs = SectionObserver()
    p = Planner(ChallengeType.OBSTACLE, vs, wm, section_observer=obs)
    p.start_button_pressed()
    obs.update(red_detections=[{"cx": 10, "distance": 80.0}], green_detections=[], roi_width=300)
    assert obs.frames_seen() == 1
    p.section_boundary_crossed()
    assert obs.frames_seen() == 0, "section_observer must be reset() on every boundary crossing"


def test_parking_flow_seek_exec_done():
    """PARK_SEEK waits for a real lot, PARK_EXEC finishes via
    parking_complete(), and a marker touch force-stops."""
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


def test_parking_marker_touched_force_stops():
    vs = VehicleState()
    wm = WorldModel(excluded_color=RED)
    p = Planner(ChallengeType.OBSTACLE, vs, wm)
    p.start_button_pressed()
    for _ in range(SECTIONS_PER_LAP * LAPS_TO_FINISH):
        p.section_boundary_crossed()
    p.parking_lot_visible({"left": {}, "right": {}, "center_x": 150, "width_px": 40})
    assert p.state is State.PARK_EXEC

    p.parking_marker_touched()
    assert p.state is State.DONE, "touching a parking marker must force-stop into DONE (Section9.24.7)"


def test_lap_phase_labels():
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


def test_query_helpers_match_state():
    vs = VehicleState()
    wm = WorldModel(excluded_color=RED)
    p = Planner(ChallengeType.OBSTACLE, vs, wm)
    assert p.is_waiting() and not p.is_driving() and not p.should_track_pillars()
    p.start_button_pressed()
    assert p.is_driving() and p.should_track_pillars() and not p.is_waiting()
